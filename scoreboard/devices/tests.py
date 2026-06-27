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
