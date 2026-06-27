from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from contest.models import Competition, CompetitionType, Contest, Result, Run, RunState, Team
from devices.models import DeviceType, LapEvent, LapTimerDevice
from scoring.engine import (
    _update_best_result,
    assign_lap_event_to_active_run,
    crossings_needed,
    try_finalize_run,
)


def make_device(mac='AA:BB:CC:DD:EE:FF'):
    return LapTimerDevice.objects.create(device_id=mac, friendly_name='Timer', device_type=DeviceType.LAPTIMER)


def make_contest():
    return Contest.objects.create(name='Test Contest')


def make_competition(contest, device=None, num_laps=1):
    return Competition.objects.create(
        name='Line Following',
        contest=contest,
        competition_type=CompetitionType.TIMED,
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
        device=device,
        sequence=seq,
        timestamp_utc=ts,
        run=run,
        competition=competition,
    )


class CrossingsNeededTest(TestCase):
    def test_one_lap_needs_two_crossings(self):
        contest = make_contest()
        competition = Competition.objects.create(
            name='C', contest=contest, competition_type=CompetitionType.TIMED, num_laps=1
        )
        run = make_run(make_team(contest), competition, state=RunState.ACTIVE)
        self.assertEqual(crossings_needed(run), 2)

    def test_three_laps_needs_four_crossings(self):
        contest = make_contest()
        competition = Competition.objects.create(
            name='C', contest=contest, competition_type=CompetitionType.TIMED, num_laps=3
        )
        run = make_run(make_team(contest), competition, state=RunState.ACTIVE)
        self.assertEqual(crossings_needed(run), 4)


class AssignLapEventTest(TestCase):
    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, self.device)
        self.team = make_team(self.contest)
        self.run = make_run(self.team, self.competition, state=RunState.ACTIVE)

    def test_assigns_event_to_active_run(self):
        event = make_lap_event(self.device, seq=1)
        result = assign_lap_event_to_active_run(event)
        self.assertEqual(result, self.run)
        event.refresh_from_db()
        self.assertEqual(event.run, self.run)
        self.assertEqual(event.competition, self.competition)

    def test_no_active_run_returns_none(self):
        self.run.state = RunState.COMPLETED
        self.run.save()
        event = make_lap_event(self.device, seq=1)
        self.assertIsNone(assign_lap_event_to_active_run(event))

    def test_device_not_assigned_to_competition_returns_none(self):
        other_device = make_device(mac='11:22:33:44:55:66')
        event = make_lap_event(other_device, seq=1)
        self.assertIsNone(assign_lap_event_to_active_run(event))


class TryFinalizeRunTest(TestCase):
    def setUp(self):
        self.device = make_device()
        self.contest = make_contest()
        self.competition = make_competition(self.contest, self.device, num_laps=1)
        self.team = make_team(self.contest)
        self.run = make_run(self.team, self.competition, state=RunState.ACTIVE)

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

    def test_time_ms_uses_first_and_nth_crossing_only(self):
        # 3 crossings for num_laps=1 — only first and second count
        make_lap_event(self.device, seq=1, offset_seconds=0, run=self.run, competition=self.competition)
        make_lap_event(self.device, seq=2, offset_seconds=5, run=self.run, competition=self.competition)
        make_lap_event(self.device, seq=3, offset_seconds=99, run=self.run, competition=self.competition)
        try_finalize_run(self.run)
        self.run.refresh_from_db()
        self.assertAlmostEqual(self.run.time_ms, 5000, delta=50)


class UpdateBestResultTest(TestCase):
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

    def test_best_run_marked(self):
        slow = self._completed_run(10000)
        fast = self._completed_run(5000)
        _update_best_result(fast)
        fast.refresh_from_db()
        slow.refresh_from_db()
        self.assertTrue(fast.is_best)
        self.assertFalse(slow.is_best)

    def test_penalty_included_in_best(self):
        run_fast_raw = self._completed_run(5000, penalty=3000)   # total 8000
        run_slow_raw = self._completed_run(7000, penalty=0)      # total 7000
        _update_best_result(run_slow_raw)
        run_fast_raw.refresh_from_db()
        run_slow_raw.refresh_from_db()
        self.assertTrue(run_slow_raw.is_best)
        self.assertFalse(run_fast_raw.is_best)

    def test_result_created_with_best_total(self):
        run = self._completed_run(6000, penalty=500)
        _update_best_result(run)
        result = Result.objects.get(team=self.team, competition=self.competition)
        self.assertEqual(result.score, 6500)

    def test_result_updated_when_better_run_comes_in(self):
        slow = self._completed_run(10000)
        _update_best_result(slow)
        fast = self._completed_run(5000)
        _update_best_result(fast)
        result = Result.objects.get(team=self.team, competition=self.competition)
        self.assertEqual(result.score, 5000)
