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
mosquitto_pub -h 10.15.20.11 -p 51883 -u deviceusr -P devicepass \
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
