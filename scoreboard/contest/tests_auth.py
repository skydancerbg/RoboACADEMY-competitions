import secrets

from django.contrib.auth.models import Group, User
from django.test import TestCase

from contest.models import Competition, CompetitionType, Contest, ItemStates, Run, RunState, Team
from contest.models import UserProfile


def _tok():
    return secrets.token_hex(8)


def _make_setup():
    contest = Contest.objects.create(name='Auth Test Contest')
    comp = Competition.objects.create(
        name='Auth Cat', contest=contest,
        competition_type=CompetitionType.TIMED,
        status=ItemStates.OPEN, num_laps=1, num_runs=3, token=_tok(),
    )
    team = Team.objects.create(name='Auth Team', contest=contest, token=_tok())
    return contest, comp, team


def _group(name):
    g, _ = Group.objects.get_or_create(name=name)
    return g


def _user_in_group(username, group_name):
    u = User.objects.create_user(username=username, password='test')
    u.groups.add(_group(group_name))
    return u


class AnonymousAccessTest(TestCase):
    """Unauthenticated users are redirected to login for all judge views."""

    def setUp(self):
        self.contest, self.comp, self.team = _make_setup()

    def test_contest_list_redirects_to_login(self):
        r = self.client.get(f'/contest/contest/{self.contest.id}')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_run_create_redirects_to_login(self):
        r = self.client.post(f'/contest/competition/{self.comp.id}/run/create',
                             {'team_id': self.team.id})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_competition_board_fragment_is_public(self):
        r = self.client.get(f'/contest/competition/{self.comp.id}/fragment/')
        self.assertEqual(r.status_code, 200)

    def test_public_index_is_accessible(self):
        r = self.client.get('/contest/')
        self.assertEqual(r.status_code, 200)


class JudgeGroupAccessTest(TestCase):
    """Judge-group user can access contest views but not organiser views."""

    def setUp(self):
        self.contest, self.comp, self.team = _make_setup()
        self.user = _user_in_group('judge1', 'Judge')
        self.client.force_login(self.user)

    def test_judge_can_access_contest_list(self):
        r = self.client.get(f'/contest/contest/{self.contest.id}')
        self.assertEqual(r.status_code, 200)

    def test_judge_can_create_run(self):
        r = self.client.post(f'/contest/competition/{self.comp.id}/run/create',
                             {'team_id': self.team.id})
        self.assertIn(r.status_code, [200, 302])
        self.assertEqual(Run.objects.filter(team=self.team, competition=self.comp).count(), 1)

    def test_judge_denied_organiser_dashboard(self):
        r = self.client.get('/contest/organise/')
        self.assertEqual(r.status_code, 403)


class OrganiserGroupAccessTest(TestCase):
    """Organiser-group user can access both judge and organiser views."""

    def setUp(self):
        self.contest, self.comp, self.team = _make_setup()
        self.user = _user_in_group('org1', 'Organiser')
        self.client.force_login(self.user)

    def test_organiser_can_access_dashboard(self):
        r = self.client.get('/contest/organise/')
        self.assertEqual(r.status_code, 200)

    def test_organiser_can_access_contest_list(self):
        r = self.client.get(f'/contest/contest/{self.contest.id}')
        self.assertEqual(r.status_code, 200)


class RegistrationTest(TestCase):
    """Registration form creates inactive user with correct profile."""

    def test_registration_creates_inactive_user(self):
        r = self.client.post('/contest/register/', {
            'username': 'newjudge',
            'first_name': 'New',
            'last_name': 'Judge',
            'email': 'new@example.com',
            'password': 'securepass123',
            'password2': 'securepass123',
            'requested_role': 'judge',
            'organisation': 'School ABC',
            'country': 'Bulgaria',
        })
        self.assertEqual(r.status_code, 302)
        user = User.objects.get(username='newjudge')
        self.assertFalse(user.is_active)
        self.assertEqual(user.profile.requested_role, 'judge')
        self.assertEqual(user.profile.organisation, 'School ABC')

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username='taken', password='test')
        r = self.client.post('/contest/register/', {
            'username': 'taken',
            'first_name': 'A', 'last_name': 'B',
            'email': 'a@b.com',
            'password': 'pass123', 'password2': 'pass123',
            'requested_role': 'judge',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already taken')

    def test_password_mismatch_rejected(self):
        r = self.client.post('/contest/register/', {
            'username': 'mismatch',
            'first_name': 'A', 'last_name': 'B',
            'email': 'a@b.com',
            'password': 'pass123', 'password2': 'different',
            'requested_role': 'judge',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Passwords do not match')

    def test_register_pending_page_renders(self):
        r = self.client.get('/contest/register/pending/')
        self.assertEqual(r.status_code, 200)


class ApproveUsersActionTest(TestCase):
    """Admin approve action activates user and assigns to requested group."""

    def setUp(self):
        self.admin = User.objects.create_superuser('superadmin', password='test')
        self.client.force_login(self.admin)

    def test_approve_activates_user_and_assigns_group(self):
        pending = User.objects.create_user('pending1', password='test', is_active=False)
        UserProfile.objects.create(user=pending, requested_role='judge')
        Group.objects.get_or_create(name='Judge')

        r = self.client.post('/admin/auth/user/', {
            'action': 'approve_users',
            '_selected_action': [pending.pk],
        })
        self.assertIn(r.status_code, [200, 302])
        pending.refresh_from_db()
        self.assertTrue(pending.is_active)
        self.assertTrue(pending.groups.filter(name='Judge').exists())
