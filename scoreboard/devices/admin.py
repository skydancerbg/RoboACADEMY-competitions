from django.contrib import admin
from .models import LapTimerDevice, LapEvent


@admin.register(LapTimerDevice)
class LapTimerDeviceAdmin(admin.ModelAdmin):
    list_display  = ('friendly_name', 'device_id', 'device_type', 'status',
                     'last_seen', 'country', 'organisation')
    list_filter   = ('device_type', 'status')
    search_fields = ('friendly_name', 'device_id', 'organisation')


@admin.register(LapEvent)
class LapEventAdmin(admin.ModelAdmin):
    list_display = ('device', 'competition', 'run', 'timestamp_utc', 'sequence')
    list_filter  = ('device', 'competition')
