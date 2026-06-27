import json

import paho.mqtt.publish as publish
from django.conf import settings


def _auth():
    return {'username': settings.MQTT_USERNAME, 'password': settings.MQTT_PASSWORD}


def publish_competition_command(competition_id: int, cmd: str, **extra) -> None:
    """Publish a START or STOP command to all devices in a competition."""
    topic = f'robosteam/competition/{competition_id}/cmd'
    payload = json.dumps({'cmd': cmd, **extra})
    publish.single(
        topic,
        payload=payload,
        hostname=settings.MQTT_BROKER_HOST,
        port=settings.MQTT_BROKER_PORT,
        auth=_auth(),
        qos=1,
    )


def publish_robot_command(mac: str, cmd: str, **extra) -> None:
    """Publish a command to a specific robot."""
    topic = f'robosteam/robot/{mac}/cmd'
    payload = json.dumps({'cmd': cmd, **extra})
    publish.single(
        topic,
        payload=payload,
        hostname=settings.MQTT_BROKER_HOST,
        port=settings.MQTT_BROKER_PORT,
        auth=_auth(),
        qos=1,
    )
