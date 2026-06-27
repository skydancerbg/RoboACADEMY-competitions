# RoboACADEMY — End-to-End Test Scenarios (Phase 5.5)

These 10 scenarios validate the full competition platform before any hardware firmware
is written. Run them in order. See `README.md` for environment setup.

## Test Fixture

| Item | Value |
|------|-------|
| Contest | `RoboACADEMY Test Cup 2026` (status=OPEN, points_table={"1":10,"2":8,"3":6,"4":4,"5":2}) |
| Category 1 | `Line Following` — TIMED, num_laps=3, num_runs=3, timeout=120s |
| Category 2 | `Object Manipulation` — JUDGED, num_runs=3 |
| Teams | `Team Alpha`, `Team Bravo`, `Team Charlie` |
| Simulator MAC | `AA:BB:CC:DD:EE:01` (do not pre-create in admin — S1 tests auto-registration) |

## Expected Final Timing Table

| Team | Category | Run | --sequence | time_ms | is_best |
|------|----------|-----|-----------|---------|---------|
| Alpha | TIMED | 1 | `2,6,5,4` | **15,000** | ★ |
| Alpha | TIMED | 2 | `2,7,9,8` | 24,000 | |
| Alpha | TIMED | 3 | `2,5,10,8` | 23,000 | |
| Bravo | TIMED | 1 | `2,9,8,7` | 24,000 | |
| Bravo | TIMED | 2 | `2,8,8,8` | 24,000 | (tie with Run 1; Run 1 keeps ★) |
| Bravo | TIMED | 3 | `2,8,7,6` | **21,000** | ★ |
| Charlie | TIMED | 1 | manual | VOIDED | |
| Charlie | TIMED | 2 | manual | VOIDED | |
| Charlie | TIMED | 3 | `2,8,9,10` | **27,000** | ★ |
| Alpha | JUDGED | 1 | n/a | score=75 | |
| Alpha | JUDGED | 2 | n/a | score=82 | ★ |
| Alpha | JUDGED | 3 | n/a | score=68 | |
| Bravo | JUDGED | 1 | n/a | score=91 | ★ |
| Bravo | JUDGED | 2 | n/a | score=78 | |
| Bravo | JUDGED | 3 | n/a | score=85 | |
| Charlie | JUDGED | 1 | n/a | score=60 | |
| Charlie | JUDGED | 2 | n/a | score=70 | ★ |
| Charlie | JUDGED | 3 | n/a | score=45 | |

**Overall points:** Alpha=18, Bravo=18 (intentional tie), Charlie=12

---

## S1 — Device Auto-Registration via Heartbeat

**Goal:** Verify the MQTT bridge auto-creates a `LapTimerDevice` row on first heartbeat.
The default `friendly_name` should equal the MAC address.

**Steps:**
1. Start simulator (no `--sequence` needed here — just heartbeat):
   ```bash
   python ~/competitions/tests/lap_timer_sim.py \
     --mac AA:BB:CC:DD:EE:01 --competition 1 --laps 3
   ```
2. Wait up to 35 seconds for the first heartbeat to publish.

**Verify:**
- [ ] `/admin/devices/laptimertimer/` shows exactly one device
- [ ] `device_id = "AA:BB:CC:DD:EE:01"`
- [ ] `friendly_name = "AA:BB:CC:DD:EE:01"` (MAC used as default — not yet renamed)
- [ ] `status = ONLINE`, `last_seen` is populated and recent
- [ ] `mqtt_bridge` log shows: `Heartbeat: AA:BB:CC:DD:EE:01`

**Post-S1 admin actions (required before S2):**
1. Edit the device: set `friendly_name = "Sim Timer 1"`
2. Edit the Line Following category: set `lap_timer = Sim Timer 1 (AA:BB:CC:DD:EE:01)`
3. Navigate to `/contest/competition_board/<id>` — info bar should show `Timer: Sim Timer 1`

---

## S2 — Alpha Run 1: Scripted Timing Happy Path

**Goal:** Full end-to-end TIMED pipeline. Judge clicks Start → server publishes MQTT START
with `run_id` → simulator receives it → publishes 4 crossings → scoring signal fires →
`try_finalize_run` computes 15,000 ms → `is_best=True` → `Result` upserted.

**time_ms explained:**
`--sequence "2,6,5,4"` → crossing 0 at t+2s (clock starts), crossing 3 at t+17s.
`time_ms = (t+17s) − (t+2s) = 15,000 ms`. The 2s pre-start delay is NOT in time_ms.

**Steps:**
1. Keep the simulator running from S1 (sequence counter continues from seq=1).
2. Navigate to `/contest/competition_board/<Line Following id>`.
3. Select **Team Alpha** in "Queue run for" dropdown → click **Create Run**.
4. Click **Start** on Alpha's pending run.
5. Wait ~17 seconds for simulator to publish all 4 crossings.
6. Refresh the page.

**Verify:**
- [ ] Simulator log: 4 "Crossing published" lines ending with "RUN COMPLETE"
- [ ] 4 `LapEvent` rows in `/admin/devices/lapevent/`, all with `run=Alpha Run 1`
- [ ] `Run.state = COMPLETED`
- [ ] `Run.time_ms = 15000` (±50 ms acceptable for network jitter)
- [ ] `Run.is_best = True`
- [ ] `Result(team=Alpha, competition=LineFollowing).score = 15000`
- [ ] Runs table shows ★ on Alpha Run 1
- [ ] `format_ms` renders: `15000 → "0:15.000"`
- [ ] `mqtt_bridge` log shows MQTT START was published with the correct `run_id`

---

## S3 — Alpha Run 2: Slower Run Does Not Steal is_best

**Goal:** `_update_best_timed_result` keeps `is_best` on Run 1 when Run 2 is slower (24,000 ms).

**Same simulator session (seq counter continues from S2).**

**Steps:**
1. Create Run for Alpha → Start.
2. Simulator will fire `--sequence "2,7,9,8"` → 24,000 ms.

**Verify:**
- [ ] Run 2: `state=COMPLETED`, `time_ms=24000`, `is_best=False`
- [ ] Run 1: `is_best=True` (unchanged)
- [ ] `Result.score` still `15000`
- [ ] Board: only one ★ (on Run 1)

---

## S4 — Alpha Run 3: Faster But Still Not Best + Run Limit Enforcement

**Goal:** Run 3 (23,000 ms) does not beat Run 1 (15,000 ms). After 3 runs,
Alpha disappears from the "Queue run for" dropdown (run limit enforced).

**Simulator: `--sequence "2,5,10,8"` → 23,000 ms**

**Verify:**
- [ ] Run 3: `state=COMPLETED`, `time_ms=23000`, `is_best=False`
- [ ] Run 1: `is_best=True` (time_ms=15000, still best)
- [ ] `Result.score` still `15000`
- [ ] "Queue run for" dropdown no longer shows "Team Alpha"

---

## S5 — Bravo Multi-Run + Intra-Team Time Tie

### S5a — Bravo Run 1

**Simulator: `--sequence "2,9,8,7"` → 24,000 ms**

**Verify:**
- [ ] `is_best=True`, `Result.score=24000`
- [ ] Board: Alpha 1st (15,000), Bravo 2nd (24,000)

### S5b — Bravo Run 2 (Intentional Tie)

**Simulator: `--sequence "2,8,8,8"` → 24,000 ms (identical to Run 1)**

**Verify:**
- [ ] Run 2: `state=COMPLETED`, `time_ms=24000`, `is_best=False`
- [ ] Run 1: `is_best=True` (lower PK wins when `min()` sees equal values)
- [ ] `Result.score` still `24000` (same value either way)
- [ ] Exactly ONE Bravo run has `is_best=True`

### S5c — Bravo Run 3 (New Best)

**Simulator: `--sequence "2,8,7,6"` → 21,000 ms**

**Verify:**
- [ ] Run 3: `is_best=True`, `Result.score=21000`
- [ ] Runs 1 and 2: `is_best=False`
- [ ] Board: Alpha 1st (15,000), Bravo 2nd (21,000)

---

## S6 — Charlie DNF Scenarios (Manual Mode)

**Goal:** Voided runs excluded from Result calculation. Only Charlie's valid Run 3 produces a Result.

### S6a — Run 1: Only Starting Crossing, Then Voided

```bash
python ~/competitions/tests/lap_timer_sim.py \
  --mac AA:BB:CC:DD:EE:01 --competition 1 --laps 3 --mode manual
```

1. Create Run for Charlie → click **Start**.
2. Simulator shows "Press Enter to publish crossing 0". Press Enter **once**.
3. Immediately click **Void** in the browser.

**Verify:**
- [ ] `Run.state = VOIDED`
- [ ] 1 `LapEvent` in DB with `run = Charlie Run 1`
- [ ] No `Result` row for Charlie yet
- [ ] `mqtt_bridge` log shows STOP published

### S6b — Run 2: Two Crossings, Then Voided

1. Create Run for Charlie → Start.
2. Press Enter **twice** (crossing 0 and crossing 1 = 1 lap of 3 complete).
3. Click **Void** in browser.

**Verify:**
- [ ] `Run.state = VOIDED`
- [ ] 2 `LapEvents` assigned to Charlie Run 2
- [ ] Still no `Result` for Charlie

### S6c — Run 3: Valid Completion

Switch simulator back to auto mode:
```
--sequence "2,8,9,10"  →  time_ms = 8000+9000+10000 = 27,000 ms
```

**Verify:**
- [ ] `Run.state = COMPLETED`, `time_ms=27000`, `is_best=True`
- [ ] `Result.score=27000`
- [ ] Runs table for Charlie: VOIDED / VOIDED / COMPLETED★
- [ ] 3-team board: Alpha (15,000) / Bravo (21,000) / Charlie (27,000)

---

## S7 — JUDGED Competition: Object Manipulation

**Goal:** Full JUDGED scoring path — score form → `run_score` view → `score_judged_run()` →
`_update_best_judged_result()` → Result. No simulator needed.

**URL:** `/contest/competition_board/<Object Manipulation id>`

### Team Alpha (3 runs)

- Run 1 (from PENDING state — no need to click Start): submit score=75
  - Expected: `state=COMPLETED`, `score=75`, `is_best=True`, `Result.score=75`
- Run 2 (click Start first, then submit): score=82
  - Expected: `is_best` moves to Run 2 (82 > 75), `Result.score=82`
- Run 3: score=68
  - Expected: `is_best` stays on Run 2 (82 > 68), `Result.score=82`

### Team Bravo (3 runs)

- Run 1: score=91 → `is_best=True`, `Result.score=91`
- Run 2: score=78 → `is_best` stays on Run 1 (91 > 78)
- Run 3: score=85 → `is_best` stays on Run 1 (91 > 85)

### Team Charlie (3 runs)

- Run 1: score=60 → `is_best=True`, `Result.score=60`
- Run 2: score=70 → `is_best` moves to Run 2 (70 > 60), `Result.score=70`
- Run 3: score=45 → `is_best` stays on Run 2 (70 > 45)

**Verify (all teams):**
- [ ] Alpha: `Result.score=82`, ★ on Run 2
- [ ] Bravo: `Result.score=91`, ★ on Run 1
- [ ] Charlie: `Result.score=70`, ★ on Run 2
- [ ] JUDGED board: Bravo (91) / Alpha (82) / Charlie (70)
- [ ] Scores displayed as raw integers (no `format_ms`)
- [ ] Stopwatch widget visible on JUDGED board; absent on TIMED board
- [ ] MQTT bridge log is silent (no START/STOP published for JUDGED runs)
- [ ] Score submitted from PENDING state (without clicking Start) succeeds

---

## S8 — Competition Board and Cross-Competition View

**Goal:** Verify UI rendering accuracy. Surfaces the BUG-01 cross-table issue.

### TIMED Board (`/contest/competition_board/<Line Following id>`)

- [ ] Info bar contains: "Type: Timed", "3 laps", "120s timeout", "Timer: Sim Timer 1", "Max runs: 3"
- [ ] `format_ms` output: 15000→"0:15.000", 21000→"0:21.000", 27000→"0:27.000"
- [ ] ★ column: exactly one ★ per team
- [ ] Charlie's two voided runs show state "Voided" (not blank or error)
- [ ] No stopwatch widget on TIMED board

### Cross-Competition Table (`/contest/contest/<contest id>`)

**While categories are OPEN (BUG-01):**
- [ ] TIMED columns show blank / NULL — document this as BUG-01:
  `contest_competitions` uses `Max('score')` on `Run.score`; TIMED runs have `score=NULL`.

**After setting both categories to CLOSED in admin:**
- [ ] TIMED columns now show numeric values (from `Result.score`)
- [ ] Table cells: Alpha=[15000, 82], Bravo=[21000, 91], Charlie=[27000, 70]

---

## S9 — Overall Ranking: Eligibility and Tie Verification

**Goal:** Verify all Result preconditions for overall ranking. Confirm the intentional tie.

**Pre-step:** Close both categories (admin → set status=CLOSED).

**Verify:**
- [ ] `Result.objects.count() == 6` (3 teams × 2 categories)
- [ ] Points: Alpha=10+8=18, Bravo=8+10=18 (TIE), Charlie=6+6=12
- [ ] Tie-break: Alpha has 1 first place (TIMED), Bravo has 1 first place (JUDGED) → still tied
- [ ] Document finding: `OverallResult` model needed for automated rank computation (Phase 8)

---

## S10 — Error Handling and Guard Conditions

All checks below should return HTTP 400 and leave DB state intact.

| Check | Action | Expected |
|-------|--------|----------|
| S10a | POST `run_start` on an ACTIVE run | HTTP 400, state unchanged |
| S10b | POST `run_stop` on a COMPLETED run | HTTP 400, state unchanged |
| S10c | Submit score=0 to a JUDGED run | HTTP 400, `run.score` remains null |
| S10d | Submit score=101 to a JUDGED run | HTTP 400, `run.score` remains null |
| S10e | Submit score=75 to a TIMED run | HTTP 400, no score stored |
| S10f | Publish LapEvent with a `seq` already in DB (see command below) | LapEvent count unchanged |
| S10g | Publish LapEvent when no run is ACTIVE | Event stored with `run=None`, no crash |

**S10f — Deduplication test command:**
```bash
mosquitto_pub -h 10.15.20.11 -p 1883 -u deviceusr -P devicepass \
  -t robosteam/laptimer/AA:BB:CC:DD:EE:01/event \
  -m '{"seq": 1, "ts": "2026-06-27T12:00:00.000Z"}'
```
Expected: `mqtt_bridge` log shows "Duplicate LapEvent ignored" (or similar); DB count unchanged.

---

## Known Bugs to Fix (Phase 5.5a)

| ID | Description | Fix |
|----|-------------|-----|
| BUG-01 | Cross-table uses `Max('score')` → NULL for TIMED+OPEN categories | Use `Result.score` for OPEN too, or query `Max('time_ms')` |
| BUG-02 | `Competition.state` not enforced in run views — can run when FINISHED | Add state guard to `run_create`/`run_start`/`run_stop` |
| BUG-03 | `LapEvent.lap_number` never populated | Compute and set `lap_number` in `try_finalize_run` |

---

## Execution Order Summary

```
SETUP: Create Contest + 2 Categories + 3 Teams in admin
       Start mqtt_bridge (Terminal A)
       Start dev server

S1  → Device auto-registration (wait 35s for heartbeat)
      Post-S1 admin: rename device "Sim Timer 1"; assign to Line Following

S2 → S3 -> S4    (Alpha: all 3 TIMED runs — ONE simulator session, do not restart)
S5a -> S5b -> S5c (Bravo: all 3 TIMED runs)
S6a -> S6b -> S6c (Charlie: 2 DNF + 1 valid — use manual mode for S6a/S6b)

S7               (JUDGED: 9 runs total — no simulator needed)

S8               (Board rendering — requires S2–S7 complete)
S9               (Overall ranking — close categories first)
S10              (Error guards — can run after S2 and S7 provide data)
```

**IMPORTANT:** S2, S3, S4 must use the same simulator process. Restarting resets the
sequence counter to 1 — the bridge's `(device, sequence)` unique_together constraint
would silently discard duplicates, so the run would never receive enough crossings to
finalize. If you must restart, note the last `seq` value and do not reuse those numbers.

---

## S11–S20: Server Phase 5.6–5.12 Scenarios

These scenarios cover Overall Ranking (S11–S13), WebSocket live push (S14),
Auto-timeout (S15), Device Self-Registration (S16), MQTT Fallback / Manual
Mode (S17), and Robot Simulator integration (S18–S20).

**Automated scenarios** (S11–S13, S15–S17) run without a browser or MQTT broker.
**Manual scenarios** (S14, S18–S20) require a browser and/or live MQTT.

---

### S11 — Overall Ranking (automated)

**Goal:** Verify that `OverallResult` rows are created correctly when all 3 teams
complete both a TIMED and a JUDGED category.

| Team    | TIMED ms | TIMED rank | JUDGED score | JUDGED rank | Total pts | Overall rank |
|---------|----------|------------|--------------|-------------|-----------|--------------|
| Alpha   | 10 000   | 1st (10)   | 90           | 1st (10)    | 20        | **1**        |
| Bravo   | 20 000   | 2nd (8)    | 80           | 2nd (8)     | 16        | **2**        |
| Charlie | 30 000   | 3rd (6)    | 70           | 3rd (6)     | 12        | **3**        |

**Run:**
```bash
cd ~/competitions/scoreboard && source ~/venv/bin/activate
python ../tests/run_ranking_scenarios.py --scenario S11
```

**Verify:**
- [ ] All 3 `OverallResult` rows created
- [ ] `is_eligible=True` for all 3 teams
- [ ] `total_points` and `rank` match the table above
- [ ] Script exits 0

---

### S12 — Tie-break by 1st-place count (automated)

**Goal:** When two teams have equal `total_points`, the team with more 1st-place
category finishes ranks higher.

| Category | Alpha | Bravo   | Charlie |
|----------|-------|---------|---------|
| Cat A    | 1st   | 2nd     | 3rd     |
| Cat B    | 1st   | 2nd     | 3rd     |
| Cat C    | 3rd   | **1st** | 2nd     |
| **Total** | **26 pts** | **26 pts** | **20 pts** |
| **Rank**  | **1** | **2**  | **3**   |

Alpha wins tie (2 firsts vs Bravo's 1 first).

**Run:**
```bash
python ../tests/run_ranking_scenarios.py --scenario S12
```

**Verify:**
- [ ] `Alpha.total_points == Bravo.total_points == 26`
- [ ] `Alpha.rank == 1`, `Bravo.rank == 2` (tie-break resolved correctly)
- [ ] Script exits 0

---

### S13 — DNF exclusion from Overall Ranking (automated)

**Goal:** A team that has a Result in only some categories is ineligible for the
Overall Ranking (`is_eligible=False`, `rank=None`) but still appears in individual
category tables.

**Setup:** Charlie completes TIMED but deliberately has no JUDGED result.

**Run:**
```bash
python ../tests/run_ranking_scenarios.py --scenario S13
```

**Verify:**
- [ ] `Charlie.is_eligible == False`
- [ ] `Charlie.rank is None` (excluded from Overall Ranking)
- [ ] `Charlie.total_points == 0`
- [ ] Charlie still appears in TIMED category result table
- [ ] Alpha and Bravo have valid ranks
- [ ] Script exits 0

---

### S14 — Live WebSocket scoreboard push (manual)

**Goal:** Changes to run/result state push to connected browsers automatically
without a page refresh.

**Prerequisites:** Dev server running, at least one TIMED competition with ≥1 team.

**Steps:**
1. Open the competition board in a browser: `http://100.118.13.80:8000/contest/competition/<id>/`
2. Open browser DevTools → Console. Confirm: `[WS] Connected` is logged.
3. In a second terminal, complete a run using the lap timer simulator (S2-style).
4. Watch the scoreboard in the browser.

**Verify:**
- [ ] `#ws-status` indicator shows green "Live" within 2 s of page load
- [ ] Scoreboard table updates automatically when the run finalises (no manual refresh)
- [ ] DevTools Console shows: `[WS] Reloading board...`
- [ ] Running the lap timer sim for a second team also triggers a board update

---

### S15 — Auto-timeout (automated)

**Goal:** An ACTIVE TIMED run that exceeds `timeout_seconds` is automatically
voided by `check_and_void_timed_out_runs()`.

**Run:**
```bash
python ../tests/run_server_complete_scenarios.py --scenario S15
```
*(The script creates a run with `timeout_seconds=5` and waits 6 s before calling
`check_and_void_timed_out_runs()`.)*

**Verify:**
- [ ] `run.state == VOIDED` after the call
- [ ] `check_and_void_timed_out_runs()` return value ≥ 1
- [ ] Script exits 0

**Background daemon test (optional manual):**
```bash
# Start the daemon (auto-checks every 10 s)
python ~/competitions/scoreboard/manage.py timeout_runs --interval 10 &

# Create a run with timeout_seconds=12 in admin, start it, wait 15 s
# Verify its state changes to VOIDED in admin or shell
```

---

### S16 — Device Self-Registration (automated)

**Goal:** A device POSTs to `/devices/register/` and starts as PENDING; admin
approval transitions it to ACTIVE; re-registration preserves the ACTIVE status.

**Run:**
```bash
python ../tests/run_server_complete_scenarios.py --scenario S16
```

**Verify:**
- [ ] POST → 201 Created, `registration_status=PENDING`
- [ ] Re-register (update friendly name) → 200, status preserved as ACTIVE
- [ ] Script exits 0

---

### S17 — MQTT Fallback / Manual Mode (automated)

**Goal:** When the MQTT broker disconnects, all ACTIVE runs are voided; judges
can then post manual results via the Manual Entry form.

**Run:**
```bash
python ../tests/run_server_complete_scenarios.py --scenario S17
```

**Verify:**
- [ ] `void_active_runs_on_disconnect()` voids all ACTIVE runs
- [ ] TIMED manual entry: `Result.score=8500`, `is_manual=True`
- [ ] JUDGED manual entry: `Result.score=77`, `is_manual=True`
- [ ] Script exits 0

**Manual UI test (optional):**
1. Start a run, verify it is ACTIVE in admin.
2. Kill mqtt_bridge; the run should become VOIDED automatically.
3. Open the runs page; the VOIDED run card should show the Manual Entry form.
4. Fill in time (TIMED) or score (JUDGED) and submit.
5. Verify Result appears in the results table with an "(M)" indicator.

---

### S18 — Robot receives START/STOP commands (manual, live MQTT)

**Goal:** Start the robot simulator and verify it receives `START` and `STOP`
commands from the competition server via MQTT.

**Prerequisites:** mqtt_bridge running, competition exists in DB.

**Terminal A — mqtt_bridge:**
```bash
ssh competitions_dev
source ~/venv/bin/activate
python ~/competitions/scoreboard/manage.py mqtt_bridge
```

**Terminal B — robot simulator:**
```bash
source ~/venv/bin/activate
export MQTT_USERNAME=deviceusr
export MQTT_PASSWORD=devicepass
python ~/competitions/tests/robot_sim.py \
  --mac 11:22:33:44:55:01 --competition <cat_id>
```

**Steps:**
1. In browser: open competition, create a run for a team, click **Start**.
2. Observe Terminal B.

**Verify:**
- [ ] Robot sim logs `>>> START received (source=competition, run_id=<id>) <<<`
- [ ] Click **Void** (or let timeout fire): robot sim logs `>>> STOP received <<<`
- [ ] No error messages in mqtt_bridge terminal

---

### S19 — Robot + lap timer end-to-end (manual, live MQTT)

**Goal:** Robot receives START via MQTT; lap timer fires N beam-crossings; server
records `time_ms`; scoreboard updates via WebSocket.

**Terminal A — mqtt_bridge (running)**
**Terminal B — lap timer sim:**
```bash
python ~/competitions/tests/lap_timer_sim.py \
  --mac AA:BB:CC:DD:EE:01 --competition <cat_id> --laps 1 --sequence "2,6"
```

**Terminal C — robot sim:**
```bash
python ~/competitions/tests/robot_sim.py \
  --mac 11:22:33:44:55:01 --competition <cat_id>
```

**Steps:**
1. Open competition board in browser.
2. Create and start a run. Verify robot sim logs `START`.
3. Fire lap crossings from Terminal B.
4. Observe the board update in the browser.

**Verify:**
- [ ] Robot sim logs START
- [ ] Lap timer sim fires the correct number of crossings
- [ ] Run state transitions to COMPLETED
- [ ] `time_ms` recorded correctly
- [ ] Browser scoreboard updates without refresh

---

### S20 — Multi-robot simultaneous START (manual, live MQTT)

**Goal:** Two robot simulators both receive the `START` command simultaneously
when a run is started (competition-level broadcast).

**Terminal B — robot 1:**
```bash
python ~/competitions/tests/robot_sim.py --mac 11:22:33:44:55:01 --competition <cat_id>
```

**Terminal C — robot 2:**
```bash
python ~/competitions/tests/robot_sim.py --mac 11:22:33:44:55:02 --competition <cat_id>
```

**Steps:**
1. Start a run in browser.
2. Observe both terminals.

**Verify:**
- [ ] Both robot sims log `>>> START received <<<` within the same second
- [ ] Both receive the same `run_id` in the payload
- [ ] No duplicate messages / infinite loops in either terminal

---

## Execution Order Summary — S11–S20

```
Automated (no broker/browser needed):
  S11 → python tests/run_ranking_scenarios.py --all       (all 3 ranking scenarios)
  S15, S16, S17 → python tests/run_server_complete_scenarios.py --all

Manual (browser + MQTT):
  S14  — WebSocket live push   (browser + any run completion)
  S18  — Robot receives START/STOP (mqtt_bridge + robot_sim.py)
  S19  — Robot + lap timer E2E  (mqtt_bridge + lap_timer_sim.py + robot_sim.py)
  S20  — Multi-robot START      (mqtt_bridge + 2× robot_sim.py)
```

**All S1–S20 complete when:**
- [ ] S1–S10 passed (previous sign-off 2026-06-27)
- [ ] S11–S13 automated scripts exit 0
- [ ] S15–S17 automated scripts exit 0
- [ ] S14 verified manually in browser
- [ ] S18–S20 verified manually with live MQTT
