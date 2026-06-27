from django.db import models
from django.utils.translation import gettext_lazy as _


class DeviceType(models.TextChoices):
    LAPTIMER = 'LAPTIMER', _('Lap Timer')
    ROBOT    = 'ROBOT',    _('Robot')


class DeviceStatus(models.TextChoices):
    ONLINE  = 'ONLINE',  _('Online')
    OFFLINE = 'OFFLINE', _('Offline')
    ERROR   = 'ERROR',   _('Error')


class RegistrationStatus(models.TextChoices):
    PENDING  = 'PENDING',  _('Pending approval')
    ACTIVE   = 'ACTIVE',   _('Active')
    INACTIVE = 'INACTIVE', _('Inactive')


class LapTimerDevice(models.Model):
    device_id     = models.CharField(
        max_length=17, unique=True,
        help_text='MAC address, used as unique device identifier.')
    friendly_name = models.CharField(
        max_length=100,
        help_text='Human-readable name set by operator on device web page.')
    device_type   = models.CharField(
        max_length=10, choices=DeviceType.choices,
        default=DeviceType.LAPTIMER)
    status        = models.CharField(
        max_length=10, choices=DeviceStatus.choices,
        default=DeviceStatus.OFFLINE)
    registration_status = models.CharField(
        max_length=10, choices=RegistrationStatus.choices,
        default=RegistrationStatus.PENDING,
        help_text='Approval state: PENDING=awaiting admin approval, ACTIVE=approved, INACTIVE=deactivated.')
    last_seen     = models.DateTimeField(null=True, blank=True)
    country       = models.CharField(max_length=100, blank=True)
    organisation  = models.CharField(
        max_length=200, blank=True,
        help_text='School or organisation.')

    class Meta:
        verbose_name        = 'Device'
        verbose_name_plural = 'Devices'

    def __str__(self):
        return f'{self.friendly_name} ({self.device_id})'


class LapEvent(models.Model):
    device        = models.ForeignKey(
        LapTimerDevice, on_delete=models.CASCADE,
        related_name='lap_events')
    competition   = models.ForeignKey(
        'contest.Competition', on_delete=models.CASCADE,
        related_name='lap_events',
        null=True, blank=True,
        help_text='Category assigned by scoring logic after the run. Null for raw unprocessed events.')
    run           = models.ForeignKey(
        'contest.Run', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lap_events',
        help_text='The Run this event is assigned to (set by server).')
    timestamp_utc = models.DateTimeField(
        help_text='Hardware timestamp from device (UTC, ISO 8601).')
    sequence      = models.PositiveIntegerField(
        help_text='Monotonically increasing per-device counter for deduplication.')
    received_at   = models.DateTimeField(
        auto_now_add=True,
        help_text='Server receive time (for latency measurement).')
    lap_number    = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='0=start crossing, 1=first lap, 2=second lap, etc. Set by scoring engine.')

    class Meta:
        unique_together = (('device', 'sequence'),)
        ordering        = ['timestamp_utc']

    def __str__(self):
        return f'LapEvent seq={self.sequence} @ {self.timestamp_utc}'
