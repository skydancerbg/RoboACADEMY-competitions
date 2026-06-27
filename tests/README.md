# RoboACADEMY — End-to-End Testing Quick Start

This directory contains the lap timer simulator and the full test scenario reference.

## Prerequisites

- Django dev server running: `http://100.118.13.80:8000`
- `mqtt_bridge` running in a dedicated terminal (see below)
- Python venv active: `source ~/venv/bin/activate`
- MQTT broker reachable at `10.15.20.11:51883`

## Start the MQTT bridge (Terminal A — keep open throughout testing)

```bash
ssh competitions_dev
cd ~/competitions/scoreboard && source ~/venv/bin/activate
python manage.py mqtt_bridge
```

The bridge log should show: `Connected to MQTT broker 10.15.20.11:51883`

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
mosquitto_pub -h 10.15.20.11 -p 51883 -u deviceusr -P devicepass \
  -t robosteam/laptimer/AA:BB:CC:DD:EE:01/event \
  -m '{"seq": 1, "ts": "2026-06-27T12:00:00.000Z"}'
```

Expect: `LapEvent.objects.count()` unchanged; bridge log shows "Duplicate … ignored".
