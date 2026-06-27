from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from contest.models import Competition, CompetitionType, Contest, Result, Run, RunState, Team
from devices.models import DeviceType, LapEvent, LapTimerDevice
from scoring.engine import (
    _update_best_judged_result,
    _update_best_timed_result,
    assign_lap_event_to_active_run,
    crossings_needed,
    score_judged_run,
    try_finalize_run,
)


def make_device(mac='AA:BB:CC:DD:EE:FF'):
    return LapTimerDevice.objects.create(device_id=mac, friendly_name='Timer', device_type=DeviceType.LAPTIMER)


def make_contest():
    return Contest.objects.create(name='Test Contest')


def make_competition(contest, device=None, num_laps=1, ctype=CompetitionType.TIMED):
    return Competition.objects.create(
        name='Test Category',
        contest=contest,
        competition_type=ctype,
        num_laps=num_laps,
        lap_timer=device,
    )


def make_team(contest, name='Team A'):
    return Team.objects.create(name=name, contest=contest)


def make_run(team, competition, state=RunState.ACTIVE):
    return Run.objects.create(
        team=team,
        competition=competition,
        start_time=timezone.now(),
        duration=0,
        state=state,
    )


def make_lap_event(device, seq, offset_seconds=0, run=None, competition=None):
    ts = timezone.now() + timedelta(seconds=offset_seconds)
    return LapEvent.objects.create(
        device=device, sequence=seq, timestamp_utc=ts, run=run, competition=competition,
    )


# ── TIMED scoring tests ───────────────────────────────────────────────────────

class CrossingsNeededTest(TestCase):
    def test_one_lap_needs_two_crossings(self):
        contest = make_contest()
        comp = Competition.objects.create(name='C', contest=contest, competition_type=CompetitionType.TIMED, num_laps=1)
        run  = make_run(make_team(contest), comp)
        self.assertEqual(crossings_needed(run), 2)

    def test_three_laps_needs_four_crossings(self):
        contest = make_contest()
        comp = Competition.objects.create(name='C', contest=contest, competition_type=CompetitionType.TIMED, num_laps=3)
        run  = make_run(make_team(contest), comp)
        self.assertEqual(crossings_needed(run), 4)


class AssignLapEventTest(TestCase):
    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, self.device)
        self.team = make_team(self.contest)
        self.run  = make_run(self.team, self.competition, state=RunState.ACTIVE)

    def test_assigns_event_to_active_run(self):
        event = make_lap_event(self.device, seq=1)
        self.assertEqual(assign_lap_event_to_active_run(event), self.run)
        event.refresh_from_db()
        self.assertEqual(event.run, self.run)
        self.assertEqual(event.competition, self.competition)

    def test_no_active_run_returns_none(self):
        self.run.state = RunState.COMPLETED
        self.run.save()
        self.assertIsNone(assign_lap_event_to_active_run(make_lap_event(self.device, seq=1)))

    def test_unassigned_device_returns_none(self):
        other = make_device(mac='11:22:33:44:55:66')
        self.assertIsNone(assign_lap_event_to_active_run(make_lap_event(other, seq=1)))


class TryFinalizeRunTest(TestCase):
    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, self.device, num_laps=1)
        self.team = make_team(self.contest)
        self.run  = make_run(self.team, self.competition, state=RunState.ACTIVE)

    def test_not_finalized_with_one_crossing(self):
        make_lap_event(self.device, seq=1, run=self.run, competition=self.competition)
        self.assertFalse(try_finalize_run(self.run))
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, RunState.ACTIVE)

    def test_finalized_with_two_crossings_for_one_lap(self):
        make_lap_event(self.device, seq=1, offset_seconds=0, run=self.run, competition=self.competition)
        make_lap_event(self.device, seq=2, offset_seconds=5, run=self.run, competition=self.competition)
        self.assertTrue(try_finalize_run(self.run))
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, RunState.COMPLETED)
        self.assertAlmostEqual(self.run.time_ms, 5000, delta=50)

    def test_time_uses_first_and_nth_crossing_only(self):
        make_lap_event(self.device, seq=1, offset_seconds=0,  run=self.run, competition=self.competition)
        make_lap_event(self.device, seq=2, offset_seconds=5,  run=self.run, competition=self.competition)
        make_lap_event(self.device, seq=3, offset_seconds=99, run=self.run, competition=self.competition)
        try_finalize_run(self.run)
        self.run.refresh_from_db()
        self.assertAlmostEqual(self.run.time_ms, 5000, delta=50)


class UpdateBestTimedResultTest(TestCase):
    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, self.device)
        self.team = make_team(self.contest)

    def _completed_run(self, time_ms, penalty=0):
        run = make_run(self.team, self.competition, state=RunState.COMPLETED)
        run.time_ms = time_ms
        run.penalty_time_ms = penalty
        run.save()
        return run

    def test_fastest_run_marked_best(self):
        slow = self._completed_run(10000)
        fast = self._completed_run(5000)
        _update_best_timed_result(fast)
        fast.refresh_from_db(); slow.refresh_from_db()
        self.assertTrue(fast.is_best)
        self.assertFalse(slow.is_best)

    def test_penalty_included_in_best(self):
        penalised = self._completed_run(5000, penalty=3000)   # total 8000
        clean     = self._completed_run(7000, penalty=0)      # total 7000
        _update_best_timed_result(clean)
        penalised.refresh_from_db(); clean.refresh_from_db()
        self.assertTrue(clean.is_best)
        self.assertFalse(penalised.is_best)

    def test_result_upserted_with_best_total(self):
        run = self._completed_run(6000, penalty=500)
        _update_best_timed_result(run)
        result = Result.objects.get(team=self.team, competition=self.competition)
        self.assertEqual(result.score, 6500)

    def test_result_updated_when_faster_run_arrives(self):
        slow = self._completed_run(10000)
        _update_best_timed_result(slow)
        fast = self._completed_run(5000)
        _update_best_timed_result(fast)
        self.assertEqual(Result.objects.get(team=self.team, competition=self.competition).score, 5000)


# ── JUDGED scoring tests ──────────────────────────────────────────────────────

class ScoreJudgedRunTest(TestCase):
    def setUp(self):
        self.contest     = make_contest()
        self.competition = make_competition(self.contest, ctype=CompetitionType.JUDGED)
        self.team = make_team(self.contest)

    def test_run_marked_completed_with_score(self):
        run = make_run(self.team, self.competition, state=RunState.ACTIVE)
        score_judged_run(run, 85, 'Great performance')
        run.refresh_from_db()
        self.assertEqual(run.state, RunState.COMPLETED)
        self.assertEqual(run.score, 85)
        self.assertEqual(run.judge_comment, 'Great performance')

    def test_result_created(self):
        run = make_run(self.team, self.competition, state=RunState.ACTIVE)
        score_judged_run(run, 75)
        result = Result.objects.get(team=self.team, competition=self.competition)
        self.assertEqual(result.score, 75)

    def test_score_from_pending_state(self):
        run = make_run(self.team, self.competition, state=RunState.PENDING)
        score_judged_run(run, 90)
        run.refresh_from_db()
        self.assertEqual(run.state, RunState.COMPLETED)


class UpdateBestJudgedResultTest(TestCase):
    def setUp(self):
        self.contest     = make_contest()
        self.competition = make_competition(self.contest, ctype=CompetitionType.JUDGED)
        self.team = make_team(self.contest)

    def _completed_run(self, score):
        run = make_run(self.team, self.competition, state=RunState.COMPLETED)
        run.score = score
        run.save()
        return run

    def test_highest_score_marked_best(self):
        low  = self._completed_run(60)
        high = self._completed_run(90)
        _update_best_judged_result(high)
        high.refresh_from_db(); low.refresh_from_db()
        self.assertTrue(high.is_best)
        self.assertFalse(low.is_best)

    def test_result_updated_when_higher_score_arrives(self):
        first = self._completed_run(70)
        _update_best_judged_result(first)
        better = self._completed_run(85)
        _update_best_judged_result(better)
        self.assertEqual(Result.objects.get(team=self.team, competition=self.competition).score, 85)

    def test_lower_score_does_not_replace_best(self):
        high = self._completed_run(90)
        _update_best_judged_result(high)
        low = self._completed_run(50)
        _update_best_judged_result(low)
        high.refresh_from_db()
        self.assertTrue(high.is_best)
        self.assertEqual(Result.objects.get(team=self.team, competition=self.competition).score, 90)


# ── BUG-03 regression ─────────────────────────────────────────────────────────

class BUG03LapNumberPopulatedTest(TestCase):
    """try_finalize_run must set lap_number on each LapEvent (0=start, 1=lap1, …)."""

    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, device=self.device, num_laps=3)
        self.team = make_team(self.contest)

    def _make_events(self, run, count, base_seq=200):
        base_ts = timezone.now()
        for i in range(count):
            LapEvent.objects.create(
                device=self.device, run=run, competition=self.competition,
                timestamp_utc=base_ts + timedelta(seconds=i * 5),
                sequence=base_seq + i,
            )

    def test_lap_numbers_set_after_finalize(self):
        run = make_run(self.team, self.competition)
        self._make_events(run, count=4)  # 3 laps + start crossing
        try_finalize_run(run)
        events = list(LapEvent.objects.filter(run=run).order_by('timestamp_utc'))
        self.assertEqual(len(events), 4)
        for expected, ev in enumerate(events):
            self.assertEqual(
                ev.lap_number, expected,
                f'seq={ev.sequence} expected lap_number={expected}, got {ev.lap_number}'
            )

    def test_lap_number_zero_is_start_crossing(self):
        run = make_run(self.team, self.competition)
        self._make_events(run, count=4, base_seq=300)
        try_finalize_run(run)
        first = LapEvent.objects.filter(run=run).order_by('timestamp_utc').first()
        self.assertEqual(first.lap_number, 0)

    def test_final_crossing_has_correct_lap_number(self):
        run = make_run(self.team, self.competition)
        self._make_events(run, count=4, base_seq=400)
        try_finalize_run(run)
        last = LapEvent.objects.filter(run=run).order_by('timestamp_utc').last()
        self.assertEqual(last.lap_number, 3)  # 3-lap run

    def test_incomplete_run_leaves_lap_number_null(self):
        run = make_run(self.team, self.competition)
        self._make_events(run, count=2, base_seq=500)  # only 2 of 4 crossings
        try_finalize_run(run)
        run.refresh_from_db()
        self.assertEqual(run.state, RunState.ACTIVE)  # not completed
        events = LapEvent.objects.filter(run=run)
        for ev in events:
            self.assertIsNone(ev.lap_number)  # not set until finalized


# ── Phase 5.5b: Integration tests (signal chain) ──────────────────────────────

class TimedScoringSignalIntegrationTest(TestCase):
    """
    Full TIMED scoring signal chain:
    LapEvent.objects.create() -> post_save signal -> assign_lap_event_to_active_run
    -> try_finalize_run -> Run.COMPLETED + Result upserted.
    """

    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, device=self.device, num_laps=2)
        self.team = make_team(self.contest)
        self._base_ts = timezone.now()
        self.run = make_run(self.team, self.competition)  # ACTIVE

    def _save_event(self, seq, offset_secs):
        return LapEvent.objects.create(
            device=self.device,
            timestamp_utc=self._base_ts + timedelta(seconds=offset_secs),
            sequence=seq,
        )

    def test_partial_crossings_do_not_finalize(self):
        self._save_event(seq=1, offset_secs=0)
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, RunState.ACTIVE)

    def test_all_crossings_finalize_run(self):
        self._save_event(seq=10, offset_secs=0)   # start crossing
        self._save_event(seq=11, offset_secs=5)   # lap 1
        self._save_event(seq=12, offset_secs=12)  # lap 2 (finish)
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, RunState.COMPLETED)
        self.assertEqual(self.run.time_ms, 12000)

    def test_result_upserted_after_finalize(self):
        self._save_event(seq=20, offset_secs=0)
        self._save_event(seq=21, offset_secs=8)
        self._save_event(seq=22, offset_secs=15)
        result = Result.objects.get(team=self.team, competition=self.competition)
        self.assertEqual(result.score, 15000)

    def test_is_best_set_on_only_completed_run(self):
        self._save_event(seq=30, offset_secs=0)
        self._save_event(seq=31, offset_secs=6)
        self._save_event(seq=32, offset_secs=10)
        self.run.refresh_from_db()
        self.assertTrue(self.run.is_best)

    def test_lap_numbers_set_by_signal_chain(self):
        self._save_event(seq=40, offset_secs=0)
        self._save_event(seq=41, offset_secs=7)
        self._save_event(seq=42, offset_secs=13)
        events = list(
            LapEvent.objects.filter(run=self.run).order_by('timestamp_utc')
        )
        self.assertEqual([ev.lap_number for ev in events], [0, 1, 2])


class JudgedScoringSignalIntegrationTest(TestCase):
    """
    Full JUDGED scoring integration: POST to run_score view -> score_judged_run
    -> _update_best_judged_result -> Run.COMPLETED + is_best + Result.
    """

    def setUp(self):
        import secrets
        self.client = Client()
        self.contest = make_contest()
        self.competition = Competition.objects.create(
            name='Judged Cat', contest=self.contest,
            competition_type=CompetitionType.JUDGED,
            num_laps=1, num_runs=3, token=secrets.token_hex(8),
        )
        self.team = make_team(self.contest)

    def _pending_run(self):
        return make_run(self.team, self.competition, state=RunState.PENDING)

    def test_first_score_sets_is_best(self):
        run = self._pending_run()
        self.client.post(f'/contest/run/{run.id}/score', {'score': 75})
        run.refresh_from_db()
        self.assertEqual(run.state, RunState.COMPLETED)
        self.assertTrue(run.is_best)

    def test_higher_score_takes_is_best(self):
        r1 = self._pending_run()
        self.client.post(f'/contest/run/{r1.id}/score', {'score': 70})
        r2 = self._pending_run()
        self.client.post(f'/contest/run/{r2.id}/score', {'score': 85})
        r1.refresh_from_db(); r2.refresh_from_db()
        self.assertFalse(r1.is_best)
        self.assertTrue(r2.is_best)

    def test_lower_score_does_not_take_is_best(self):
        r1 = self._pending_run()
        self.client.post(f'/contest/run/{r1.id}/score', {'score': 90})
        r2 = self._pending_run()
        self.client.post(f'/contest/run/{r2.id}/score', {'score': 60})
        r1.refresh_from_db(); r2.refresh_from_db()
        self.assertTrue(r1.is_best)
        self.assertFalse(r2.is_best)

    def test_result_reflects_best_score(self):
        for score in [65, 88, 72]:
            run = self._pending_run()
            self.client.post(f'/contest/run/{run.id}/score', {'score': score})
        result = Result.objects.get(team=self.team, competition=self.competition)
        self.assertEqual(result.score, 88)


class OrphanLapEventSignalTest(TestCase):
    """
    Signal must not crash when no ACTIVE run is found for the device.
    LapEvent stored with run=None.
    """

    def setUp(self):
        self.device = make_device()

    def test_orphan_stored_with_run_none(self):
        ev = LapEvent.objects.create(
            device=self.device,
            timestamp_utc=timezone.now(),
            sequence=999,
        )
        ev.refresh_from_db()
        self.assertIsNone(ev.run)
        self.assertIsNone(ev.competition)

    def test_no_result_created_for_orphan(self):
        LapEvent.objects.create(
            device=self.device,
            timestamp_utc=timezone.now(),
            sequence=998,
        )
        self.assertEqual(Result.objects.count(), 0)


class DeduplicationSignalTest(TestCase):
    """
    Second save with same (device, sequence) must be silently discarded.
    Signal must not fire, LapEvent count must not change.
    """

    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, device=self.device, num_laps=1)
        self.team = make_team(self.contest)
        self.run = make_run(self.team, self.competition)

    def test_duplicate_seq_not_saved(self):
        LapEvent.objects.create(
            device=self.device, run=self.run, competition=self.competition,
            timestamp_utc=timezone.now(), sequence=50,
        )
        count_before = LapEvent.objects.count()
        # get_or_create with same seq — simulates mqtt_bridge deduplication
        _, created = LapEvent.objects.get_or_create(
            device=self.device, sequence=50,
            defaults={'timestamp_utc': timezone.now()},
        )
        self.assertFalse(created)
        self.assertEqual(LapEvent.objects.count(), count_before)

    def test_run_not_double_finalized(self):
        """A run that finalizes on crossing N must not change if crossing N is re-delivered."""
        # Finalize with 2 crossings (1-lap run)
        LapEvent.objects.create(
            device=self.device, run=self.run, competition=self.competition,
            timestamp_utc=timezone.now(), sequence=60,
        )
        LapEvent.objects.create(
            device=self.device, run=self.run, competition=self.competition,
            timestamp_utc=timezone.now() + timedelta(seconds=10), sequence=61,
        )
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, RunState.COMPLETED)
        time_ms_first = self.run.time_ms

        # Re-deliver crossing 61 (duplicate) — must not alter the run
        LapEvent.objects.get_or_create(
            device=self.device, sequence=61,
            defaults={'timestamp_utc': timezone.now()},
        )
        self.run.refresh_from_db()
        self.assertEqual(self.run.time_ms, time_ms_first)
