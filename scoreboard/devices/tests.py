from django.test import TestCase
from django.utils import timezone
from .models import LapTimerDevice, LapEvent, DeviceType, DeviceStatus


class LapTimerDeviceModelTest(TestCase):
    def setUp(self):
        self.device = LapTimerDevice.objects.create(
            device_id='AA:BB:CC:DD:EE:FF',
            friendly_name='Timer-1',
            device_type=DeviceType.LAPTIMER,
            status=DeviceStatus.OFFLINE,
            country='Bulgaria',
            organisation='ROBO STEAM ACADEMY',
        )

    def test_str(self):
        self.assertEqual(str(self.device), 'Timer-1 (AA:BB:CC:DD:EE:FF)')

    def test_default_status_is_offline(self):
        self.assertEqual(self.device.status, DeviceStatus.OFFLINE)

    def test_default_device_type_is_laptimer(self):
        self.assertEqual(self.device.device_type, DeviceType.LAPTIMER)


class LapEventModelTest(TestCase):
    def setUp(self):
        from contest.models import Contest, Competition, Team, Run, CompetitionType

        self.device = LapTimerDevice.objects.create(
            device_id='11:22:33:44:55:66',
            friendly_name='Timer-2',
        )
        self.contest = Contest.objects.create(name='Test Contest')
        self.competition = Competition.objects.create(
            name='Line Following',
            contest=self.contest,
            competition_type=CompetitionType.TIMED,
        )
        self.team = Team.objects.create(name='Team Alpha', contest=self.contest)
        self.run = Run.objects.create(
            team=self.team,
            competition=self.competition,
            start_time=timezone.now(),
            duration=0,
        )
        self.event = LapEvent.objects.create(
            device=self.device,
            competition=self.competition,
            run=self.run,
            timestamp_utc=timezone.now(),
            sequence=1,
        )

    def test_str(self):
        self.assertIn('LapEvent seq=1', str(self.event))

    def test_unique_together_device_sequence(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            LapEvent.objects.create(
                device=self.device,
                competition=self.competition,
                timestamp_utc=timezone.now(),
                sequence=1,
            )

# ── Phase 5.9: Device self-registration API tests ─────────────────────────────

import json

from django.test import TestCase

from devices.models import DeviceType, LapTimerDevice, RegistrationStatus


class DeviceRegistrationAPITest(TestCase):
    """POST /devices/register/ creates and idempotently updates devices."""

    URL = '/devices/register/'

    def _post(self, payload):
        return self.client.post(
            self.URL,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_register_new_device_returns_201(self):
        r = self._post({'mac': 'AA:BB:CC:DD:EE:01', 'friendly_name': 'Lab Timer'})
        self.assertEqual(r.status_code, 201)

    def test_register_new_device_creates_record(self):
        self._post({'mac': 'AA:BB:CC:DD:EE:02', 'friendly_name': 'Lab Timer', 'device_type': 'LAPTIMER'})
        self.assertTrue(LapTimerDevice.objects.filter(device_id='AA:BB:CC:DD:EE:02').exists())

    def test_new_device_has_pending_registration_status(self):
        self._post({'mac': 'AA:BB:CC:DD:EE:03', 'friendly_name': 'Lab Timer'})
        dev = LapTimerDevice.objects.get(device_id='AA:BB:CC:DD:EE:03')
        self.assertEqual(dev.registration_status, RegistrationStatus.PENDING)

    def test_duplicate_mac_returns_200(self):
        self._post({'mac': 'AA:BB:CC:DD:EE:04', 'friendly_name': 'Timer A'})
        r = self._post({'mac': 'AA:BB:CC:DD:EE:04', 'friendly_name': 'Timer A Renamed'})
        self.assertEqual(r.status_code, 200)

    def test_duplicate_mac_updates_friendly_name(self):
        self._post({'mac': 'AA:BB:CC:DD:EE:05', 'friendly_name': 'Old Name'})
        self._post({'mac': 'AA:BB:CC:DD:EE:05', 'friendly_name': 'New Name'})
        dev = LapTimerDevice.objects.get(device_id='AA:BB:CC:DD:EE:05')
        self.assertEqual(dev.friendly_name, 'New Name')

    def test_duplicate_mac_does_not_reset_registration_status(self):
        """Re-registration of an approved device must not reset it to PENDING."""
        self._post({'mac': 'AA:BB:CC:DD:EE:06', 'friendly_name': 'Timer'})
        dev = LapTimerDevice.objects.get(device_id='AA:BB:CC:DD:EE:06')
        dev.registration_status = RegistrationStatus.ACTIVE
        dev.save()
        self._post({'mac': 'AA:BB:CC:DD:EE:06', 'friendly_name': 'Timer Updated'})
        dev.refresh_from_db()
        self.assertEqual(dev.registration_status, RegistrationStatus.ACTIVE)

    def test_register_missing_mac_returns_400(self):
        r = self._post({'friendly_name': 'No Mac'})
        self.assertEqual(r.status_code, 400)

    def test_register_missing_friendly_name_returns_400(self):
        r = self._post({'mac': 'AA:BB:CC:DD:EE:07'})
        self.assertEqual(r.status_code, 400)

    def test_register_invalid_device_type_returns_400(self):
        r = self._post({'mac': 'AA:BB:CC:DD:EE:08', 'friendly_name': 'Timer', 'device_type': 'UNKNOWN'})
        self.assertEqual(r.status_code, 400)

    def test_register_robot_device_type(self):
        r = self._post({'mac': 'AA:BB:CC:DD:EE:09', 'friendly_name': 'PicoBot', 'device_type': 'ROBOT'})
        self.assertEqual(r.status_code, 201)
        dev = LapTimerDevice.objects.get(device_id='AA:BB:CC:DD:EE:09')
        self.assertEqual(dev.device_type, DeviceType.ROBOT)

    def test_register_stores_country_and_school(self):
        self._post({
            'mac': 'AA:BB:CC:DD:EE:0A', 'friendly_name': 'Timer BG',
            'country': 'Bulgaria', 'school': 'ROBO STEAM Academy',
        })
        dev = LapTimerDevice.objects.get(device_id='AA:BB:CC:DD:EE:0A')
        self.assertEqual(dev.country, 'Bulgaria')
        self.assertEqual(dev.organisation, 'ROBO STEAM Academy')

    def test_response_body_contains_registration_status(self):
        r = self._post({'mac': 'AA:BB:CC:DD:EE:0B', 'friendly_name': 'Timer'})
        data = r.json()
        self.assertIn('registration_status', data)
        self.assertEqual(data['registration_status'], RegistrationStatus.PENDING)

    def test_get_not_allowed(self):
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 405)

    def test_invalid_json_returns_400(self):
        r = self.client.post(self.URL, data='not json', content_type='application/json')
        self.assertEqual(r.status_code, 400)


class DeviceAdminActionsTest(TestCase):
    """Approve and deactivate admin actions update registration_status."""

    def test_default_registration_status_is_pending(self):
        dev = LapTimerDevice.objects.create(device_id='CC:DD:EE:FF:00:01', friendly_name='T')
        self.assertEqual(dev.registration_status, RegistrationStatus.PENDING)

    def test_approve_action_sets_active(self):
        from devices.admin import approve_devices
        dev = LapTimerDevice.objects.create(device_id='CC:DD:EE:FF:00:02', friendly_name='T')
        approve_devices(None, None, LapTimerDevice.objects.filter(pk=dev.pk))
        dev.refresh_from_db()
        self.assertEqual(dev.registration_status, RegistrationStatus.ACTIVE)

    def test_deactivate_action_sets_inactive(self):
        from devices.admin import deactivate_devices
        dev = LapTimerDevice.objects.create(
            device_id='CC:DD:EE:FF:00:03', friendly_name='T',
            registration_status=RegistrationStatus.ACTIVE,
        )
        deactivate_devices(None, None, LapTimerDevice.objects.filter(pk=dev.pk))
        dev.refresh_from_db()
        self.assertEqual(dev.registration_status, RegistrationStatus.INACTIVE)
