# TOURNAMENT report: a forward record for many strategies at once (2026-10-03/04)

**Who and why.** TOURNAMENT is one of the three edge agents the owner launched on 2026-10-03. Ten families have been tested on history, and none earned on data it was not chosen from. Under §5.6, every LLM-selected family earns credit only FORWARD, so forward evidence is the bottleneck.

**This is a finder's report.** Nothing here binds until the lead triages it. **No number in it is an edge:** the only P&L read was the reproduction of vectors already stored in the look register. The smoke runs on forward days printed shapes only.

## 1. What was built

Branch `worktree-agent-a4a20570f3ea35818`, 8 commits on `d7529b4` (unpushed; main is not merged in). Research-side only: nothing touches the engine's money path, guardrails or live state.

| File | What it is |
|---|---|
| `tests/backtest/forward_record.py` | The append-only, hash-chained forward record (the look register's chain and atomic writes). Kinds: `rule`, `entry`, `days`, `revision`, `retire`. It refuses: a day before the forward start; a day twice; a day past the settled horizon or on the writing day; an entry whose first exposure has passed or that precedes its certifying boundary; an entry over the α budget or the capacity; a rule change after the first day. Its head is anchored on its own branch `forward-anchor`, through `look_anchor` (now taking `branch`/`file`). |
| `tests/backtest/forward_store.py` | The input store. Files are write-once (a changed re-fetch is a revision line); a file missing 4 days after its day is a declared hole; series freeze per date. Provides horizons and `state_hash`. Hours come from minute files from EPOCH 2026-10-01 (declared, P-7). |
| `tests/backtest/tournament_books.py` | Three book shapes: `rsim_book` (RSIM, 17:00 New York), `close_book` (event_daily) and `window_book` (event_window). The constants come from each kill script by identity, and each book returns only SETTLED days, flat before its start. |
| `tests/backtest/tournament_factory.py` | FACTORY's three books. They import main's modules lazily and write the ECB/CPI/COT views in each module's own file format. |
| `tests/backtest/tournament_registry.py` | One `Strategy(...)` per entry. The spec hash covers the formula, origin, cost map and parameters; `drift()` stops a strategy whose rule or C8 costs changed. Seeds: D1-FX13, REBAL-v1a, GOTOBI-v1a. FACTORY's three are present once their scripts are on the branch. |
| `tests/backtest/tournament_rule.py` | The pre-registered promotion rule (section 4). |
| `scripts/forward_fetch.py` | The daily fetch: Dukascopy archive bucket syncs, Yahoo S&P, the Treasury par curve, the issuers' rates, and (on main) ECB, BIS CPI and CFTC gold. |
| `scripts/tournament_daily.py` | Register, record, re-check, anchor. |
| `scripts/tournament_report.py` | The weekly report (JSON plus Markdown). |
| `deploy/forward/acis-forward.service`, `acis-forward-run.sh` | A boot-time oneshot on the AWS data server, uploading to the transfer bucket. |
| `archive/TOURNAMENT_SPEC_PROPOSAL_2026-10-03.md` | P-1..P-8, for the owner. |

**Small additive edits to shared modules** (defaults unchanged; every graded number reproduces):
- `candle_store.load(since=)`;
- `rsim_real.build(loader=, tier="forward")`;
- `look_anchor.anchor/anchored(branch=, file=)`;
- `jp_days` LAST extended to 2027-12-31;
- `universe.py` JP225 envelope raised to 120,000.

**Tests** (`test_forward_record.py`, `test_forward_store.py`, `test_tournament_rule.py`, `test_tournament_books.py`, `test_tournament_daily.py`, `test_tournament_factory.py`; 37 tests) cover:
- **No look-ahead:** each book run on data cut at a day reproduces every day it settled, exactly, for all three shapes, including cuts inside month-end weeks.
- **Append-only and chain breakage:** an edited middle line breaks the chain; an edited last line is caught only by the anchor.
- **No pre-start day and no late registration.**
- **Deterministic recompute:** a changed recompute is one revision line, and the recorded value stands.
- **Rule and cost drift.**
- **The correction for N:** Holm steps, capacity rather than count, and a null Monte Carlo (200 tournaments of 20 null entries) keeping the family-wise false-eligibility rate under α. The same Monte Carlo shows the screen alone firing on noise in more than 90% of them, and in about a third of single entries at 126 days.
- **E1 tripwire, E2 kill, pinned variant hashes, cost maps and the 2026 Q4 gotobi days.**

**Full suite on `acis-compute-1`:**
- this branch: **1494 passed, 7 skipped**;
- the branch merged with main `44ebbe9` (FACTORY and EXECUTION, throwaway merge, deleted): **1524 passed, 6 skipped**. The merge is clean.

**Parity: each forward book reproduces its registered look's stored vector bit for bit** (max |diff| 0.0; RSIM books withhold only their last, genuinely unsettled day):
- D1 against stage C `000028`: 520/521 days;
- REBAL against `000026`: 521/521;
- GOTOBI against `000023`: 521/521;
- HALLOWEEN against `000054`: 3108/3108;
- HEDGEP against `000046`: 3078/3079;
- FXVALUE against `000050`: 3104/3105.

All six variant hashes and C8 cost maps equal the register's.

## 2. The record is already registered (adopt it or discard it)

`data/forward/record` (git-ignored, in this worktree) holds 7 lines, with chain head `5488f7bc…`. Copies are in `gs://acis-compute-0929-data/agents/tournament/record/`; Google's object timestamps are the external proof that each entry predates its first exposure.

| Line | Strategy | Forward start | First exposure (UTC) | Written (UTC) |
|---|---|---|---|---|
| 1 | rule `tournament-v1` | — | — | 2026-10-03 22:18 |
| 2 | D1-FX13 | 2026-10-05 | 10-05 21:00 | 10-03 22:18 |
| 3 | REBAL-v1a | 2026-10-05 | 10-05 20:00 | 10-03 22:18 |
| 4 | GOTOBI-v1a | 2026-10-06 | 10-05 18:00 | 10-03 22:18 |
| 5 | HALLOWEEN-v1 | 2026-10-06 | 10-06 05:00 | 10-04 06:43 |
| 6 | HEDGEP-gold | 2026-10-06 | 10-06 21:00 | 10-04 06:43 |
| 7 | FXVALUE-ppp | 2026-10-06 | 10-06 21:00 | 10-04 06:43 |

- **The record holds no day yet.** Days are computed whenever the job first runs, from the forward start on: the archive bucket keeps every past day, so a late deployment loses no forward day. Only the `days` lines are written later.
- **The rule line can still be replaced** until the first `days` line. Rule on P-1/P-4 before the first run.
- **To adopt the record:** the lead copies it to the job host and pushes its anchor.
- **To discard it:** delete the directory and re-register with later starts.

## 3. Data, lags and revisions (the declared rules)

- **Dukascopy:**
  - day T's minute and tick files appear in the archive bucket at ~03:15–03:35 UTC on T+1; a month's hourly file appears on the 2nd of the next month (verified by listing, 2026-10-03);
  - a file is fetched once and frozen, and a changed re-fetch is logged as a revision;
  - a file still missing after 4 days is a hole, read as no data from then on.
- **Series:**
  - the S&P (Yahoo), the Treasury 7-year yield, the ECB fixings and the CFTC gold report freeze through their last print, at most yesterday;
  - the overnight rates freeze through today − 2 (a late print is ignored, the table forward-fills);
  - BIS CPI freezes through month − 5.
- **Settlement:**
  - D1, HEDGEP and FXVALUE settle a day when every instrument's next 08:00 New York fill is in the data, and decide only through the rates' freeze. HEDGEP also waits for the day before its next report could be read; FXVALUE for the month whose ECB and CPI inputs are frozen.
  - REBAL waits for the minute, S&P and Treasury horizons; GOTOBI for the ticks; HALLOWEEN for every index's minutes.
  - **Typical lag:** REBAL, GOTOBI and HALLOWEEN about 1 day; D1, HEDGEP and FXVALUE about 2–3 days.
- **Re-check:** every run recomputes every recorded day. Any difference (a revised input, a code change) becomes a revision line and makes that strategy ineligible until the owner looks at it.
- **Found on real data (fixed or declared):**
  - JP225 passed the 60,000 envelope (2026-04);
  - the US CPI for 2025-10 is missing, which breaks FXVALUE's 2026-02 warm-up rank (ranks are now computed from the forward start only);
  - REBAL's month-end term and HALLOWEEN's season both need the NEXT session's date, which forward means the published calendar (the NYSE rules; the next weekday). The full-data recompute equals them except after an unscheduled closure or a season-turn feed hole.

## 4. The promotion rule (pre-registered: `tournament_rule.PARAMS`, hashed into line 1)

"Eligible for owner review" (never a promotion, never live) requires all three of these:

1. **The milestone-D screen:** at least 126 forward days, a net annual Sharpe ≥ 0.5, not killed by stage D's E2 (claim = half the development Sharpe), and no −6σ* tripwire.
2. **Corrected significance:**
   - **either** weighted Holm over the capacity (20, α 0.05) on the one-sided HAC p-values at the looks 126/252/504 only, with Bonferroni over the looks;
   - **or** E1 ≥ 400 (e-Bonferroni).
3. **An intact, reproducible record:** no broken or torn line, the anchor when checked, and no revision line.

**Honest power:** the bar is a Sharpe of 4.45 / 3.14 / 2.22 at 126 / 252 / 504 days. Even alone and uncorrected for N, a family needs 1.50 at 504 days. **Six months of forward data cannot tell a 0.5-Sharpe strategy from noise**: a zero-edge family passes the D screen 36% of the time, and one of six does 93% of the time.

So the tournament's realistic yield in 2026–27 is:
- fast kills (E2);
- a ranked scoreboard with the luck shown beside it;
- the correlation matrix (breadth by mechanism).

It will not certify an edge. FACTORY's request to count its five looks is answered by P-1: the correction covers every FORWARD hypothesis the tournament can hold (capacity 20, α never recycled). History-killed candidates make no forward test, and selecting survivors on history does not bias a forward test.

## 5. Deployment (cheapest durable home: the AWS data server)

`i-08cd48694bea9e3db`, eu-west-1, on the free plan to 2027-03-11:
- **Data access:** its role already reads the Dukascopy bucket (in-region, so no transfer charge) and writes the transfer bucket.
- **Cost:** about 15 minutes a day of a stopped-by-default instance, around $1 a month of credits; the disk is already paid for.
- **Why not elsewhere:** the Google credits end 2026-10-21. The AWS demo host is on the money path and blocks its `acis` user from the instance role, so it is not used for research.

**The lead does** (via SSM, as `acis-data`):
1. Integrate this branch with main.
2. Clone it to `/data/acis/forward/repo`.
3. Build the venv: `python3.11 -m venv /data/acis/forward/venv && pip install structlog "pydantic>=2" pydantic-settings PyYAML "numpy>=2.4,<2.5"`.
4. Assemble `/data/acis/forward/archive/` (`dukascopy_candles` from `/data/acis/r15/…`; `macro`, `treasury`, `jp_holidays`, `fx_value` and `cot` from the laptop via the transfer bucket).
5. Copy the 7-line record to `/data/acis/forward/record`.
6. Install the unit: `sudo cp deploy/forward/acis-forward.service /etc/systemd/system/ && sudo systemctl enable acis-forward`.
7. Run it once with `/etc/acis/forward.keepalive` present and check `last_run.json`.

Until the server is set up, `python scripts/tournament_daily.py` on the laptop advances the record (about 3 minutes, using the owner's AWS CLI credentials).

**The owner does:**
1. **The schedule:** in the AWS console, open EventBridge, then Scheduler, then Create schedule. Use the recurring cron `15 6 * * ? *` (UTC), the target "Amazon EC2 StartInstances", and `{"InstanceIds": ["i-08cd48694bea9e3db"]}`, and let it create its role. This needs the root or an admin user: `acis-data` cannot create schedules.
2. **Optional:** enable Versioning on `acis-transfer-565257597310` (S3, the bucket, Properties). Each daily upload then keeps a server timestamp, and an overwrite is visible.
3. **Decide the anchor** (with GAP-P12D-86):
   - the GitHub `forward-anchor` branch, pushed by the lead at each weekly report (the server holds no push credential); or
   - S3 Object Lock.
4. **Rule on the open questions below.**

## 6. Open questions for the owner (one grouped ask)

1. **The promotion rule:** P-1a as coded (FWER, capacity 20), or P-1b (FDR), P-1c (a smaller capacity) or P-1d (uncorrected). Plus P-4: does a paid challenge need D plus significance, or D plus your explicit acceptance of the luck number?
2. **Adopt the registered record**, or discard it and re-register later.
3. **FXVALUE:** keep it, or retire it. FACTORY says the lead may decline it. Its α stays spent either way.
4. **The tripwire (P-5):** as written, tail-calibrated, or freeze-only.
5. **E2's units (P-2) and σ* for event books (P-3):** ratify the readings.
6. **The stage-D look amendment (P-6),** so forward looks can be registered.
7. **The forward data-source departure (P-7)** and the JP225 envelope (P-8): ratify them.
8. **GOTOBI:** forward only v1a (as briefed), or also v1c (the 09:54 exit the live draft uses), as a new entry with its own α.
9. **The host and anchor (section 5).**
10. **Your own hypotheses (`hypotheses/`):** each becomes one registry entry with `Origin("human")`. History can also certify them (stage A), and the forward record runs in parallel. Register each before its first exposure.
