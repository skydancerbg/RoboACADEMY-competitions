# RoboACADEMY — End-to-End Testing Quick Start

This directory contains the lap timer simulator and the full test scenario reference.

## Prerequisites

- Django dev server running: `http://100.118.13.80:8000`
- `mqtt_bridge` running in a dedicated terminal (see below)
- Python venv active: `source ~/venv/bin/activate`
- MQTT broker reachable at `10.15.20.11:1883`

## Start the MQTT bridge (Terminal A — keep open throughout testing)

```bash
ssh competitions_dev
cd ~/competitions/scoreboard && source ~/venv/bin/activate
python manage.py mqtt_bridge
```

The bridge log should show: `Connected to MQTT broker 10.15.20.11:1883`

## Start the simulator (Terminal B)

```bash
ssh competitions_dev
source ~/venv/bin/activate
export MQTT_USERNAME=deviceusr
export MQTT_PASSWORD=devicepass
```

### Auto mode — scripted crossing intervals

```bash
python ~/competitions/tests/lap_timer_sim.py \
  --mac AA:BB:CC:DD:EE:01 \
  --competition 1 \
  --laps 3 \
  --sequence "2,6,5,4"
```

The simulator starts, sends a heartbeat, and waits for a `START` command from the server.
When the judge clicks **Start** in the browser, it fires 4 crossings at the specified intervals.

**`--sequence` format:** `"<delay0>,<delay1>,...,<delayN>"` where N = num_laps.
- `delay0` = seconds to wait before crossing 0 (pre-start settle — NOT counted in `time_ms`)
- `delay1..N` = seconds between subsequent crossings (these ARE counted in `time_ms`)
- Example: `"2,6,5,4"` → crossing 0 at +2s; lap 1 in 6s; lap 2 in 5s; lap 3 in 4s → `time_ms = 15,000 ms`

### Manual mode — press Enter per crossing (for DNF/void tests)

```bash
python ~/competitions/tests/lap_timer_sim.py \
  --mac AA:BB:CC:DD:EE:01 \
  --competition 1 \
  --laps 3 \
  --mode manual
```

Press Enter each time you want a crossing published. Click **Void** in the browser
at any point to end the run early (tests the VOIDED state path).

### Uniform interval mode (smoke test)

```bash
python ~/competitions/tests/lap_timer_sim.py \
  --mac AA:BB:CC:DD:EE:01 \
  --competition 1 \
  --laps 1 \
  --interval 5
```

Publishes 2 crossings 5 s apart → `time_ms ≈ 5,000 ms`.

## Admin setup (do once before running S1)

1. Log in: `http://100.118.13.80:8000/admin/` (user: `admin`)
2. Create **Contest**: `RoboACADEMY Test Cup 2026`, status=OPEN,
   `points_table = {"1": 10, "2": 8, "3": 6, "4": 4, "5": 2}`
3. Create **Category 1** (verbose: Competition): `Line Following`, contest=Test Cup,
   `competition_type=TIMED`, `num_laps=3`, `num_runs=3`, `timeout_seconds=120`
4. Create **Category 2**: `Object Manipulation`, contest=Test Cup,
   `competition_type=JUDGED`, `num_runs=3`
5. Create **Teams**: `Team Alpha`, `Team Bravo`, `Team Charlie` (all under Test Cup 2026)
6. **Do NOT** pre-create any LapTimerDevice — Scenario S1 tests auto-registration.
7. After S1 registers the device: rename `friendly_name = "Sim Timer 1"`,
   then assign it to the Line Following category (`lap_timer` field).

## Run the test scenarios

See **TEST_SCENARIOS.md** for the complete S1–S10 reference with expected outcomes
and verification checklists.

Recommended order: S1 → S2 → S3 → S4 → S5a → S5b → S5c → S6a → S6b → S6c → S7 → S8 → S9 → S10

**Critical:** Keep the same simulator process for S2–S4 (Team Alpha) and S5a–S5c (Team Bravo).
The sequence counter increments across runs within a session. Restarting resets it to 1,
which the bridge deduplicates silently — the run would never finalize.

## Run the Django test suite

After completing all scenarios, run from the server:

```bash
cd ~/competitions/scoreboard && source ~/venv/bin/activate
python manage.py test scoring devices mqtt_bridge contest
```

All 35+ tests must pass. If any regression is found, fix it before moving to Phase 6.

## Deduplication test (S10f)

```bash
mosquitto_pub -h 10.15.20.11 -p 1883 -u deviceusr -P devicepass \
  -t robosteam/laptimer/AA:BB:CC:DD:EE:01/event \
  -m '{"seq": 1, "ts": "2026-06-27T12:00:00.000Z"}'
```

Expect: `LapEvent.objects.count()` unchanged; bridge log shows "Duplicate … ignored".


---

## Robot Simulator (`tests/robot_sim.py`)

Simulates a PicoBot robot over MQTT. Use this alongside `lap_timer_sim.py`
for S18–S20 scenarios that require a robot to receive START/STOP commands.

### Start the robot simulator (Terminal C)

```bash
ssh competitions_dev
source ~/venv/bin/activate
export MQTT_USERNAME=deviceusr
export MQTT_PASSWORD=devicepass
```

#### Basic — listen for commands and log them

```bash
python ~/competitions/tests/robot_sim.py \
  --mac 11:22:33:44:55:01 \
  --competition 4
```

The sim connects, publishes a heartbeat, and waits silently.
When the judge clicks **Start** in the browser, you will see:

```
[12:34:56] >>> START received (source=competition, run_id=42) <<<
             full payload: {"cmd": "START", "run_id": 42, "competition_id": 4}
```

When **Void** or a timeout fires:

```
[12:35:28] >>> STOP received  (source=competition, run_id=42) <<<
             full payload: {"cmd": "STOP", "run_id": 42}
```

#### With ACK response (`--respond`)

Publishes a status message back to `robosteam/robot/{mac}/status` on every
START/STOP, confirming the robot received the command:

```bash
python ~/competitions/tests/robot_sim.py \
  --mac 11:22:33:44:55:01 \
  --competition 4 \
  --respond
```

Example output after a START:

```
[12:34:56] >>> START received (source=competition, run_id=42) <<<
             full payload: {"cmd": "START", "run_id": 42, "competition_id": 4}
[12:34:56] ACK sent: {"device_id": "11:22:33:44:55:01", "ts": "2026-06-27T12:34:56.123Z", "firmware_version": "robot-sim-1.0", "ack": "START", "run_id": 42}
```

#### Two robots simultaneously (S20 — multi-robot START)

Open two terminals, each with a different `--mac`:

```bash
# Terminal C
python ~/competitions/tests/robot_sim.py --mac 11:22:33:44:55:01 --competition 4

# Terminal D
python ~/competitions/tests/robot_sim.py --mac 11:22:33:44:55:02 --competition 4
```

Both sims subscribe to `robosteam/competition/4/cmd`. When the judge starts
a run, both consoles should print the START command within the same second.

#### Robot sim + lap timer sim together (S19)

```bash
# Terminal B — lap timer
python ~/competitions/tests/lap_timer_sim.py \
  --mac AA:BB:CC:DD:EE:01 --competition 4 --laps 3 --sequence "2,6,5,4"

# Terminal C — robot
python ~/competitions/tests/robot_sim.py \
  --mac 11:22:33:44:55:01 --competition 4
```

Judge starts run → robot sim logs START → lap timer fires 4 crossings →
server records `time_ms` → scoreboard updates via WebSocket.

### CLI argument reference — robot_sim.py

| Argument | Default | Description |
|----------|---------|-------------|
| `--mac` | `11:22:33:44:55:01` | Robot MAC (used as device_id and MQTT client_id) |
| `--competition` | `1` | Category DB id (for competition-level cmd topic) |
| `--broker` | `10.15.20.11` | MQTT broker host |
| `--port` | `51883` | MQTT broker port |
| `--user` | `$MQTT_USERNAME` | MQTT username (overrides env var) |
| `--password` | `$MQTT_PASSWORD` | MQTT password (overrides env var) |
| `--respond` | off | Send ACK status message on each START/STOP |
