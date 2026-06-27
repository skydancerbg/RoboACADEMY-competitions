import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import DeviceType, LapTimerDevice, RegistrationStatus


@csrf_exempt
@require_POST
def register_device(request):
    """
    POST /devices/register/
    Body (JSON): {mac, friendly_name, device_type, country, school}

    Idempotent: creates device on first call, updates mutable fields on subsequent
    calls with the same MAC. registration_status is not reset for existing devices.
    """
    try:
        body = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    mac           = str(body.get('mac', '')).strip().upper()
    friendly_name = str(body.get('friendly_name', '')).strip()
    device_type   = str(body.get('device_type', DeviceType.LAPTIMER)).strip().upper()
    country       = str(body.get('country', '')).strip()
    school        = str(body.get('school', '')).strip()

    if not mac:
        return JsonResponse({'error': 'mac is required'}, status=400)
    if not friendly_name:
        return JsonResponse({'error': 'friendly_name is required'}, status=400)
    if device_type not in DeviceType.values:
        return JsonResponse(
            {'error': f'device_type must be one of {DeviceType.values}'},
            status=400,
        )

    device, created = LapTimerDevice.objects.get_or_create(
        device_id=mac,
        defaults={
            'friendly_name': friendly_name,
            'device_type': device_type,
            'country': country,
            'organisation': school,
        },
    )

    if not created:
        device.friendly_name = friendly_name
        device.device_type   = device_type
        device.country       = country
        device.organisation  = school
        device.save(update_fields=['friendly_name', 'device_type', 'country', 'organisation'])

    return JsonResponse(
        {
            'device_id':           device.device_id,
            'friendly_name':       device.friendly_name,
            'device_type':         device.device_type,
            'registration_status': device.registration_status,
            'created':             created,
        },
        status=201 if created else 200,
    )
