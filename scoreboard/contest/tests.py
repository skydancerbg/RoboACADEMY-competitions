import json
import secrets

from django.test import Client, TestCase

from contest.models import (
    Competition, CompetitionType, Contest, ItemStates, Result, Run, RunState, Team,
)
from devices.models import DeviceType, LapTimerDevice


def _tok():
    return secrets.token_hex(8)


def _make_setup(status=ItemStates.OPEN, ctype=CompetitionType.TIMED, num_laps=1, num_runs=3):
    contest = Contest.objects.create(name='Test Contest')
    comp = Competition.objects.create(
        name='Test Category', contest=contest,
        competition_type=ctype, status=status,
        num_laps=num_laps, num_runs=num_runs,
        token=_tok(),
    )
    team = Team.objects.create(name='Team A', contest=contest, token=_tok())
    return contest, comp, team


def _make_active_run(team, comp):
    from django.utils import timezone
    return Run.objects.create(
        team=team, competition=comp,
        start_time=timezone.now(), duration=0,
        state=RunState.ACTIVE,
    )


def _make_pending_run(team, comp):
    from django.utils import timezone
    return Run.objects.create(
        team=team, competition=comp,
        start_time=timezone.now(), duration=0,
        state=RunState.PENDING,
    )


# ── BUG-01 regression ─────────────────────────────────────────────────────────

class BUG01ContestTableTimedOpenTest(TestCase):
    """contest_competitions must show Result.score for TIMED+OPEN categories, not None."""

    def setUp(self):
        self.client = Client()
        self.contest, self.comp, self.team = _make_setup(
            status=ItemStates.OPEN, ctype=CompetitionType.TIMED
        )
        Result.objects.create(team=self.team, competition=self.comp, score=15002)

    def test_timed_open_score_rendered_not_none(self):
        resp = self.client.get(f'/contest/contest/{self.contest.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '15002')

    def test_none_not_in_table_for_timed_open(self):
        resp = self.client.get(f'/contest/contest/{self.contest.id}')
        content = resp.content.decode()
        # Should not render a bare "None" cell for a team that has a Result
        self.assertNotIn('> None<', content)
        self.assertNotIn('>None<', content)


class BUG01ContestTableJudgedOpenTest(TestCase):
    """JUDGED+OPEN column still shows correctly after BUG-01 fix."""

    def setUp(self):
        self.client = Client()
        self.contest, self.comp, self.team = _make_setup(
            status=ItemStates.OPEN, ctype=CompetitionType.JUDGED
        )
        Result.objects.create(team=self.team, competition=self.comp, score=82)

    def test_judged_open_score_rendered(self):
        resp = self.client.get(f'/contest/contest/{self.contest.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '82')


# ── BUG-02 regression ─────────────────────────────────────────────────────────

class BUG02RunCreateStatusGuardTest(TestCase):
    """run_create must return 400 when competition.status is not OPEN."""

    def setUp(self):
        self.client = Client()

    def test_run_create_open_competition_succeeds(self):
        _, comp, team = _make_setup(status=ItemStates.OPEN)
        resp = self.client.post(
            f'/contest/competition/{comp.id}/run/create',
            {'team_id': team.id},
        )
        self.assertIn(resp.status_code, [200, 302])
        self.assertEqual(Run.objects.filter(team=team, competition=comp).count(), 1)

    def test_run_create_closed_competition_rejected(self):
        _, comp, team = _make_setup(status=ItemStates.CLOSED)
        resp = self.client.post(
            f'/contest/competition/{comp.id}/run/create',
            {'team_id': team.id},
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertIn('not open', data['error'])
        self.assertEqual(Run.objects.filter(team=team, competition=comp).count(), 0)

    def test_run_create_new_status_rejected(self):
        _, comp, team = _make_setup(status=ItemStates.NEW)
        resp = self.client.post(
            f'/contest/competition/{comp.id}/run/create',
            {'team_id': team.id},
        )
        self.assertEqual(resp.status_code, 400)

    def test_run_limit_still_enforced_for_open(self):
        _, comp, team = _make_setup(status=ItemStates.OPEN, num_runs=1)
        # First run: succeeds
        self.client.post(
            f'/contest/competition/{comp.id}/run/create',
            {'team_id': team.id},
        )
        # Second run: exceeds limit
        resp = self.client.post(
            f'/contest/competition/{comp.id}/run/create',
            {'team_id': team.id},
        )
        self.assertEqual(resp.status_code, 400)

    def test_run_start_completed_rejected(self):
        _, comp, team = _make_setup(status=ItemStates.OPEN)
        run = _make_pending_run(team, comp)
        run.state = RunState.COMPLETED
        run.save()
        resp = self.client.post(f'/contest/run/{run.id}/start')
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertIn('COMPLETED', data['error'])

    def test_run_stop_completed_rejected(self):
        _, comp, team = _make_setup(status=ItemStates.OPEN)
        run = _make_pending_run(team, comp)
        run.state = RunState.COMPLETED
        run.save()
        resp = self.client.post(f'/contest/run/{run.id}/stop')
        self.assertEqual(resp.status_code, 400)


# ── Score validation guards ───────────────────────────────────────────────────

class RunScoreValidationTest(TestCase):
    """run_score must reject invalid scores and wrong competition type."""

    def setUp(self):
        self.client = Client()
        _, self.judged_comp, self.team = _make_setup(
            status=ItemStates.OPEN, ctype=CompetitionType.JUDGED
        )
        _, self.timed_comp, _ = _make_setup(
            status=ItemStates.OPEN, ctype=CompetitionType.TIMED
        )

    def _pending_run(self, comp):
        return _make_pending_run(self.team, comp)

    def test_score_zero_rejected(self):
        run = self._pending_run(self.judged_comp)
        resp = self.client.post(f'/contest/run/{run.id}/score', {'score': 0})
        self.assertEqual(resp.status_code, 400)

    def test_score_101_rejected(self):
        run = self._pending_run(self.judged_comp)
        resp = self.client.post(f'/contest/run/{run.id}/score', {'score': 101})
        self.assertEqual(resp.status_code, 400)

    def test_score_on_timed_run_rejected(self):
        run = _make_pending_run(self.team, self.timed_comp)
        resp = self.client.post(f'/contest/run/{run.id}/score', {'score': 75})
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertIn('JUDGED', data['error'])

    def test_valid_score_accepted(self):
        run = self._pending_run(self.judged_comp)
        resp = self.client.post(f'/contest/run/{run.id}/score', {'score': 75})
        self.assertIn(resp.status_code, [200, 302])
        run.refresh_from_db()
        self.assertEqual(run.score, 75)
        self.assertEqual(run.state, RunState.COMPLETED)
