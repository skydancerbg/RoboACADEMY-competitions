from datetime import timedelta

from django.test import TestCase
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
