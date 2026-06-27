# MQTT Protocol Reference — RoboSTEAM Competitions

## Broker

| Setting | Value |
|---------|-------|
| Host | `10.15.20.11` |
| Port | `51883` (plain TCP forwarded to Mosquitto 1883) |
| Protocol | MQTT v3.1.1 |
| Auth | username `deviceusr` / password in `project.env` |
| QoS | 1 (at-least-once) — server deduplicates by sequence number |
| TLS | Deferred — add once Nginx TLS passthrough is configured |

---

## Topic Structure

```
robosteam/competition/{competition_id}/cmd     # server → all devices in competition
robosteam/laptimer/{mac_address}/event         # lap timer → server (beam crossing)
robosteam/laptimer/{mac_address}/status        # lap timer → server (heartbeat)
robosteam/robot/{mac_address}/cmd              # server → specific robot
robosteam/robot/{mac_address}/status           # robot → server (heartbeat)
```

`{mac_address}` is the device MAC address in uppercase colon-separated format, e.g. `AA:BB:CC:DD:EE:FF`.  
`{competition_id}` is the Django PK of the `Competition` (Category) model.

---

## Payloads

All payloads are JSON. All timestamps are ISO 8601 UTC.

### `robosteam/laptimer/{mac}/event` — Lap timer beam crossing

Published by the lap timer device each time the IR beam is broken.

```json
{
  "seq": 42,
  "ts": "2026-06-27T10:15:30.123Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `seq` | integer | Monotonically increasing counter per device. Used for deduplication under QoS 1. |
| `ts` | string | UTC timestamp of the beam crossing from the device's hardware clock. |

### `robosteam/laptimer/{mac}/status` — Lap timer heartbeat

Published periodically by the lap timer to signal it is alive.

```json
{
  "ts": "2026-06-27T10:15:00.000Z",
  "firmware": "1.0.0"
}
```

### `robosteam/robot/{mac}/status` — Robot heartbeat

Published periodically by the robot.

```json
{
  "ts": "2026-06-27T10:15:00.000Z",
  "firmware": "1.0.0"
}
```

### `robosteam/competition/{competition_id}/cmd` — Competition command (server → devices)

Published by the server to start or stop a run in a given category.

```json
{ "cmd": "START", "run_id": 17 }
```
```json
{ "cmd": "STOP" }
```

| Field | Type | Description |
|-------|------|-------------|
| `cmd` | string | `START` or `STOP` |
| `run_id` | integer | Django PK of the `Run` being started (START only) |

### `robosteam/robot/{mac}/cmd` — Robot-specific command (server → robot)

Same payload as competition command. Used when targeting a single robot directly.

---

## Server-side processing (mqtt_bridge management command)

| Topic | Handler |
|-------|---------|
| `laptimer/+/event` | Create `LapEvent` (deduplicate by device+sequence); mark device ONLINE |
| `laptimer/+/status` | Update `LapTimerDevice.last_seen` and status=ONLINE |
| `robot/+/status` | Update `LapTimerDevice.last_seen` and status=ONLINE (device_type=ROBOT) |

**Raw LapEvents** (competition/run = null) are written as they arrive. Phase 4 scoring logic assigns them to the correct Competition and Run when a run is in ACTIVE state.

---

## Authoritative timing rule

The lap timer is the **only** timing source. The robot never self-reports start or end time. All elapsed times are calculated by the server from consecutive `LapEvent.timestamp_utc` values.
