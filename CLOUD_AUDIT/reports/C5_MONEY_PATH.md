# C5 MONEY-PATH SAFETY — ACIS cloud review, run 2

- **Lane:** C5 MONEY-PATH SAFETY. **Model:** Opus 5.5 (the system reports `claude-opus-5-5`); the reasoning effort cannot be observed from inside the session.
- **Fresh context:** yes. I launched no subagents, and I wrote only under `CLOUD_AUDIT/reports/`.
- **Reviewed commit (BASE):** `7695ed04` in `/tmp/review-acis`. I imported it read-only with bytecode writing disabled, and `git status` there stays clean.
- **Date:** 2026-09-24, about 18:04–18:20 UTC.
- **Web use:** 2 WebSearch calls and 6 WebFetch calls, against a budget of 15. The primary sources are in §6.
- **Evidence:** everything is in `CLOUD_AUDIT/reports/evidence/C5/`:
  - `repro_money_path.py` (P1–P7) and its `_output.txt`;
  - `repro_prop_rules.py` (SCOUT's claims confirmed, plus N-1) and its `_output.txt`;
  - `repro_stage_config_relax.py`.

  Run any of them with `PYTHONDONTWRITEBYTECODE=1 python <script> /tmp/review-acis`. They use synthetic data only.
- **Status:** finder, not clearer. Every item below is a proposal for the local lead and the owner to triage.

---

## 1. Executive summary

1. **No position opened through the real dispatch path ever gets a server-side stop.** `ExecutionOrchestrator._submit_once` (`core/execution/orchestrator.py:211-215`) never passes `SizedOrder.stop_loss` to `face.submit_order`.
   - The §279 conformance tests (`tests/integration/test_adapter_conformance.py:137-165`) call the face directly, so they are green while the only production path fails to protect.
   - Combine this with the watchdog living on the same VPS: if the VPS or its network dies, the positions carry no protection at all.
   - Reproduced as P1. TODO Track A step 4 names the threading work; my evidence is that the tests cannot catch its absence. **(a: code, reproduced)**
2. **A lost acknowledgement turns a real fill into an orphan and a double fill.**
   - On `ConnectionError`, the "reconcile" (`orchestrator.py:216-224`) only logs the broker's positions, then resubmits.
   - After two failures it books a synthetic REJECT with 0 units filled.
   - Against a venue that does not deduplicate by fragment ID, P2 ends with **2,000 units open at the venue while the engine, the Risk Monitor and the heartbeat all say 0**. The watchdog would then only alert, never flatten.
   - cTrader documents `clientOrderId` but says nothing about deduplicating on it. **(a: code, reproduced; cTrader docs)**
3. **Every human-only HALT lives in process memory, so a restart is a relaxation.**
   - `CapitalGovernor._halts` has no persistence.
   - `RiskStore.record_halt`, `save_restrictive_state` and `load_restrictive_state` have **no production caller**.
   - `acis-engine.service` has `Restart=always` with `RestartSec=5`. A crash therefore clears MCP, platform-drawdown, VaR and cluster halts within 5 seconds, and SCOUT's anchor re-base hands out fresh drawdown budgets on top.
   - Reproduced as P5 and S-D. **[owner decision]** because it concerns HALT semantics. **(a: code, reproduced)**
4. **The watchdog's flatten is not fenced off from the engine.**
   - Take an engine that hangs for 40 seconds (not dies). The watchdog flattens at the broker. The engine then recovers, the watchdog re-arms, and the engine still believes it is long.
   - The engine's next "close" **opens an unprotected short** on a netting venue. Reproduced as P6. **(a: reproduced)**
5. **SCOUT's four prop-fit findings are all confirmed by script** (S-A to S-D):
   - the $9,000 floor flattens and HALTs a $6k account on its first evaluate;
   - every platform rule is built with `resets_daily=False`, and `DrawdownRule` has no reset instant or zone;
   - a 332-unit order (0.0033 lot) is dispatched to a venue that declares a 0.01-lot minimum;
   - a restart re-bases every drawdown measure to 0%. **(a)**
6. **New: the `ftmo` rulebook stand-in is *looser* than FTMO's real daily rule, which refutes the "stricter-of" claim** in `guardrails.py:51-56`.
   - When a realised gain lifts the balance while another position is open at a loss, FTMO is breached at equity 9,850 against a 9,900 floor.
   - At that moment ACIS measures its trailing rule at 1.5% (distance 0.30) and does not even taper.
   - Reproduced as N-1. **[owner decision]**, because it is guardrail-adjacent. **(a)**
7. **An agent can make the book bigger with `acis_stage_config` alone, with no human token.**
   - The allowlist admits `governor.marginal_alpha_window = 10`, below `marginal_alpha_min_trades = 20`.
   - The estimator is then pinned at NEUTRAL 1.0 forever, which switches off the 0.25 anti-greed floor that a losing book earns. That is a 4× size increase.
   - This contradicts `monitoring/tools.py:181-182`, which claims "no risk-raising value on any path". **[owner decision]** **(a: reproduced)**
8. **The execution freeze is checked once per order, not once per fragment** (`orchestrator.py:90`).
   - If a HALT lands between fragments, the remaining *open* fragments still fill: 2 of 3 in P3.
   - It is latent at today's $1k base unit, but it becomes live the moment sizing becomes NAV-relative, as SCOUT proposes. **(a)**
9. **Time.**
   - A host clock 949 seconds slow (GAP-P12D-51) makes the normaliser raise on **100 of 100** live ticks; a fast one flags every tick stale. Both fail safe, but the engine cannot trade.
   - Nothing compares host time with broker time at start-up.
   - The paper/live `mode` is consumed by no trading code. The live gate is a label that is not bound to which account the face trades. **(a)**
10. **S6 is upgraded to (a), and S2 is upgraded to (a) with a correction.**
    - **S6:** FTMO's daily loss is reset at 00:00 CE(S)T from that instant's balance, minus 5% of initial capital, and tested on equity. Fetched from the primary page, modified 2026-09-24.
    - **S2:** "74–89% of retail accounts typically lose money" is ESMA's own 27 Mar 2018 statement drawn from NCA analyses. It is **not** a broker disclosure.

## 2. Body

### 2.1 Defect list

Severities are proposals.

| # | Where | Defect | Repro | Severity |
|---|---|---|---|---|
| D1 | `core/execution/orchestrator.py:211-215` | `stop_loss` is never forwarded, so no §279 venue stop is placed on any order. The conformance tests bypass the orchestrator. | P1 | **Critical**: a pre-demo blocker |
| D2 | `orchestrator.py:202-224`, `:168-173` | Reconnect "reconcile" is log-only. The retry relies on the face deduplicating by `fragment_id` (the contract says so at `venue.py:146`, but no real venue provides it). Giving up books REJECT/0 while the venue may hold the fill. The broker positions are logged, then ignored. | P2 | **Critical** |
| D3 | `core/risk/monitor.py:313` via `write_heartbeat` | The heartbeat's `open_positions` is the engine's *internal* view. The docstring calls it "broker-reconciled truth", which D2 falsifies. The watchdog flattens only if that count is above 0 (`scripts/acis_watchdog.py:144-146`). | P2 | High |
| D4 | `core/governor/capital_governor.py:73,119-121,134-138`; `core/risk/store.py:57-78` (no callers) | HALTs and the taper and alpha state are not persisted or restored. With `Restart=always`, a crash means the halts are lifted within about 5 seconds. Only the equity-floor HALT re-asserts itself, and only while equity is still below the floor. | P5 | **High [owner decision]** |
| D5 | `core/risk/guardrails.py:90` (anchors in memory only) | Every drawdown anchor re-bases to 0% on restart. This confirms SCOUT §5.1-F. | S-D | High **[owner decision]** |
| D6 | `scripts/acis_watchdog.py:147-160`, `:119-128` | A flatten is not fenced: no HALT is written for the engine, and no "externally flattened" marker is read by it. The watchdog re-arms on the next heartbeat. A hung engine that recovers trades from a stale book: on a netting venue its close becomes a reverse open. | P6 | High |
| D7 | `orchestrator.py:90`, `:126-127`, `:156-158` | The freeze is checked only at `submit` entry. The per-fragment `_dispatch` sleeps, then submits opens, without re-checking. | P3 | Medium (latent) |
| D8 | `monitor.py:366-373` | Restart-adopted positions are marked at `avg_price=1.0`. On USD_JPY that gives ±$993 of fake daily P&L per 1,000 units, and a spurious per-instrument HALT on shorts. `BrokerPosition` has no entry-price field, although cTrader provides one. | P4 | Medium |
| D9 | `config/platform_rules.yaml:60-68` + `guardrails.py:36-79` | The `ftmo` stand-in is looser than FTMO whenever the 00:00 balance exceeds the equity high-water mark seen so far. The "stricter-of" claim is false. This extends SCOUT's §8.2 correction. | N-1 | High **[owner decision]** |
| D10 | `config/system_config.yaml:131` + `core/governor/marginal_alpha.py:52-54` | An agent can stage a window below `min_trades`, which pins sizing at 1.0 and drops the 0.25 floor. | `repro_stage_config_relax.py` | Medium **[owner decision]** |
| D11 | `orchestrator.py:136-152` | `min_lot`, `lot_step` and the venue's minimum are never checked, and remainder retries can create sub-minimum fragments. This confirms SCOUT §5.1-B. | S-C | High (for prop) |
| D12 | `core/risk/guardrails.py:220` + `config/guardrail_limits.yaml:13` | The absolute $9,000 floor halts any account under $9k. This confirms SCOUT. | S-A | Blocking **[owner decision]** |
| D13 | `guardrails.py:122` + `config/schemas.py:450-454` | A daily reset instant, zone or anchor cannot be expressed, and the engine day is fixed at 17:00 New York (`core/data/fx_clock.py:107-112`). This confirms SCOUT. | S-B | Blocking for prop **[spec]** |
| D14 | `core/data/normaliser.py:194-198`; no start-up time check | With a slow host every tick raises; with a fast host every tick is stale. Neither produces a precise alarm. GAP-P12D-51 owns the host fix and names the pre-live check. | P7 | Medium |
| D15 | `monitoring/mode.py` | `mode` is read by no code in `core/`. "paper" does not stop a face that is attached to a funded or live account. | grep in §2.3 | High before any real credential |
| D16 | `deploy/systemd/acis-engine.service` `Restart=always` + `verify_attach` raising `AttachHalt` (`core/execution/venue.py:306-310`) | Restarting with positions open will likely loop every 5 seconds (inferred: the runtime is unbuilt), and each attach calls `open_positions`. That is about 17k broker requests a day against FTMO's 2,000/day cap, and it contradicts GAP-0018's "a human decides". The watchdog may then flatten, since the heartbeat is stale. The interaction is undesigned. | code read | Medium |
| D17 | `monitor.py:133,161` | `daily_pnl` in the snapshot and the MCP buckets by UTC calendar date, while the engine's daily drawdown uses the 17:00 New York trading day. What the human reads disagrees with what the guard measures. | code read | Low |

### 2.2 Which decisions hang on the wall clock

- **Market-time decisions use the broker's tick `event_time`:** regime, signals, the Governor's weekend and session gates, and bar close. This is correct, and GAP-P12D-51's own ledger text says graded results are unaffected.
- **Wall-clock decisions:**
  - the orchestrator's `now_fn`, which covers the fill time, fragment scheduling and the `realised_by_day` bucketing;
  - the watchdog timeline, which is only relative, and correct;
  - the MCP audit timestamps;
  - `recv_time`, stamped by the adapter from the host clock (the skew and staleness guards, D14).
- **What the unbuilt runtime must decide:** the `now` it passes to `RiskMonitor.evaluate`. That value decides when the engine's daily drawdown resets at 17:00 New York, and would decide a future FTMO 00:00 CE(S)T reset. **Recommendation:** pass the broker-server time, meaning the latest `event_time` or the venue's server timestamp, never the host clock. Also refuse to start if the host differs from the broker by more than about 2 seconds.
- **Tracking a daily limit anchored somewhere else:** not possible today (D13). One engine day can straddle two FTMO days, so SCOUT's "two 2% engine budgets per firm day" stands. D9 shows the stand-in can also miss a breach within a single day.

### 2.3 The control plane

- **Is resume human-token only?**
  - At the MCP layer, yes: `monitoring/auth.py` does a constant-time SHA-256 compare, and `tools.py:123-126` gates on it.
  - But `CapitalGovernor.resume` accepts **any non-empty string** (`capital_governor.py:134-135`). Its "own teeth" are presence checks only.
  - Any future caller that is not the MCP tool (a runtime hook, a restart path) would bypass the credential check. The human token is enforced one layer up, not at the guard.
- **Can a path weaken a guard?**
  - The guardrail file is unreachable by schema.
  - But the path-level allowlist is not risk-monotone (D10), and a restart relaxes every halt (D4, D5). The guard-integrity law's own test ("if an agent can edit the guard, it is not a guard") is failed through the *process lifecycle*, not through config.
- **How fast is the kill switch?**
  - `acis_halt` blocks new entries on the Governor's next sizing call, which is effectively instant.
  - `acis_flatten` goes to `ControlTarget.flatten`. **No production `HaltSink` or `ControlTarget` exists**: `grep -rn "HaltSink)"` outside `tests/` finds none. MCP flatten and Risk's equity-floor flatten therefore close nothing today (GAP-0091b runtime).
  - The watchdog acts after 30–35 seconds of silence (30 s timeout plus a 5 s poll), then retries every 5 seconds without backoff. A broker refusing for hours burns the request cap (FTMO allows 2,000 a day).
- **Mode:** D15.

### 2.4 History: documented failures, and the lesson each teaches ACIS

- **Knight Capital, 1 Aug 2012 (SEC, (a)).**
  - What happened: *"During the first 45 minutes after the market opened on August 1, Knight Capital's router rapidly sent more than 4 million orders"*, with a loss of *"more than $460 million"*.
  - The cause was a bad deployment: it *"incorrectly deployed new code in the same router"*.
  - The SEC found Knight lacked *"adequate controls at a point immediately prior to its submission of orders"* and had financial risk controls *"not capable of preventing the entry of orders that exceeded pre-set capital thresholds"*.
  - **Lesson for ACIS:** the GAP-0075 firehose plus the missing adapter-level order and request budget (SCOUT §5.1-C) is the same class of failure, a missing pre-submission control. The fix belongs **at the adapter boundary**, as a hard daily count and a per-minute count, not in the loop's logic.
- **The SNB CHF de-peg, 15 Jan 2015 (FXCM press release, (a)).**
  - FXCM: *"clients experienced significant losses, generated negative equity balances owed to FXCM of approximately $225 million."*
  - **Lesson for ACIS:** a server-side stop bounds *intent*, not loss. ACIS already carries a CHF −35% scenario (GAP-0108, closed). For the demo, the gap-through behaviour of the firm's simulated server must be observed and logged (GAP-P12D-42 is the priceBound variant on OANDA).
- **cTrader Open API ((a), Spotware docs).**
  - `clientOrderId`: *"Optional user-specific clientOrderId (similar to FIX ClOrderID). MaxLength = 50."* No deduplication is documented.
  - `stopLoss`: *"Not supported for MARKET orders"*, so only `relativeStopLoss` can ride on a market order (SCOUT §3).
  - `ProtoOAReconcileReq`: *"Request for getting Trader's current open positions and pending orders data."*
  - **Lesson for ACIS:** D2's fix must be *query-then-decide*: reconcile and look for the `clientOrderId` or `label` before any resubmission. Blind retry must never be the fix.
  - ACIS's IDs are uuid4 (36 characters) plus `:i:pN:xN`, which comes to about 44 characters, inside the 50 limit. Any lengthening would break it silently.

### 2.5 Pre-demo checklist (all must be true before the first demo order)

1. **D1 is fixed.** The orchestrator forwards `stop_loss`. Add a conformance case that goes *through the orchestrator* and asserts `resting_stops()` after the fill. Because cTrader market orders take only `relativeStopLoss`, add an **attach-time check that every open position has a resting stop**, and HALT if one does not.
2. **D2 is fixed.**
   - On an ambiguous send, query the venue by `clientOrderId` before retrying.
   - After giving up, ingest the broker's net position into Risk, not a synthetic REJECT/0.
   - Add a conformance case, "ack lost after fill", that must end with engine == broker.
3. **The heartbeat's `open_positions` comes from a broker query**, or the watchdog queries the broker itself (D3).
4. **HALTs are persisted and restored before the first evaluate**, and the drawdown anchors with them, or a restart forces a human-resume HALT (D4, D5). **[owner decision]**
5. **The watchdog flatten writes a fence** (a HALT marker the engine must read and obey before its next order), and **the engine re-reconciles with the broker after any gap in its loop longer than the watchdog timeout** (D6).
6. **A hard adapter-level request and order counter** sits below the firm's cap: stop new opens at 50% of the cap, and at 80% of it HALT everything except closes. The GAP-0075 position gate is in place first.
7. **Min-lot and lot-step handling:** the minimum and step are read from the venue at attach, sizes are rounded down, and an order that rounds to 0 lots is recorded as a skip (D11). For the demo, the owner decides the account size and sizing basis (D12). **[owner decision]**
8. **Time:** the host is on NTP. The start-up check refuses to start if the host and the broker's server time differ by more than 2 seconds. The runtime passes broker time to `evaluate` (D14).
9. **The `mode` is bound to the face.** When `mode != live`, the adapter must refuse an account the venue reports as live or funded (D15). The owner decides whether an FTMO Free Trial counts as "paper".
10. **The flatten path exists** (a production `HaltSink` and `ControlTarget`). A scripted demo drill must pass: MCP `acis_flatten`, an equity-floor trip at a demo-scaled floor, and `kill -9` of the engine followed by a watchdog flatten. Each must end flat at the broker, verified by `open_positions()`.
11. **The rulebook entry for the demo firm is written against the primary text**, with SCOUT §8.2 applied and D9 closed or explicitly accepted. **[owner decision]**
12. **The weekend, pre-close and news entry bans follow SCOUT §5.1-G** (the FTMO gap-trading clause).

### 2.6 Pre-funded checklist (added on top of pre-demo)

- **Demo evidence exists:** at least 20 trading days with no orphan, a zero reconcile diff at every restart, and request use under 25% of the cap on the worst day.
- **Stop behaviour is recorded:** at least one observed stop-out, with gap-through and slippage behaviour logged in `OPERATIONS_LEDGER.md` (GAP-0001 class).
- **Everything below is re-verified:**
  - D4, D5 and D9 are resolved by the owner;
  - a firm-day loss tracker is anchored at the firm's zone and anchor (D13), with a pre-breach **flatten**, not only an entry halt;
  - the floor is relative to the account's initial capital.
- **The watchdog runs on a different host or network** from the engine: a second small VPS, or the firm's own server-side stops proven in drill. Its credentials are stored separately, and a live account holds only the watchdog's credentials.
- **§14 is met out of sample and the human signs off** (unchanged; never self-enabled).
- The rule on accepting D10 or D16 is written down.

### 2.7 Day-one demo runbook (outline)

- **T−1 day.**
  - Run the drill from checklist item 10 on the demo.
  - Record the broker's minimum lot, lot step, stop distance and server time zone.
  - Confirm FTMO's (or E8's) request counting by email (SCOUT email Q2).
- **Start.**
  - The engine starts HALTED.
  - The human checks that attach returns flat, that time skew is under 2 seconds, and that the rulebook hash matches, then resumes with the token.
- **Watch continuously:**
  - After every fill, compare the reconcile diff (engine against broker positions and against resting stops): **HALT on any mismatch.**
  - Watch the request count against the cap: **HALT at 50%.**
  - Watch for `EXEC_RECONCILE` and `venue_unreachable` events: **HALT on the first one**, then investigate for an orphan.
  - Watch the watchdog log: any `WATCHDOG_STALE` means a human reviews before the next resume.
  - Slippage against modelled costs goes into `OPERATIONS_LEDGER.md`.
- **Halt immediately** on any of the following:
  - a position without a resting stop;
  - a rejected close;
  - a firm-day loss above 50% of the firm's daily limit, measured by the human's own firm-anchored calculation, because ACIS cannot measure it (D13);
  - any clock alarm;
  - any engine restart.
- **End of day:**
  - Flatten before the weekend or pre-close window if the account type needs it.
  - Export the fills and compare them with the broker statement.
  - Read "it traded" as plumbing only (GAP-P12D-49).

## 3. What I could not verify

- **Whether FTMO's cTrader accounts sit on Spotware's demo or live host.** This decides how D15 is bound.
- **Whether a firm's simulated server deduplicates `clientOrderId`.** The docs are silent; it must be tested on the demo.
- **The real runtime's restart behaviour** (D16). The runtime is unbuilt, so that finding is inferred from the systemd unit and `verify_attach`.
- **Whether FTMO counts reconcile and position queries toward its 2,000 requests.** This is SCOUT's open question Q2.
- **The WebFetch quotes** are rendered by the fetch tool's extractor. The FTMO and ESMA passages match SCOUT's independent verbatim extraction and the ESMA search index, but I did not byte-compare them. I could not extract the Knight PDF locally (the PDF library is broken in this container), so its quotes come from the SEC press release page.

## 4. Residual risk

- The unbuilt three-loop runtime is where most of D1–D6 will either be fixed or be re-created. None of the reproductions can bind a design that does not exist yet.
- The mock face is netting, and FTMO's cTrader accounts are probably hedging, so D6's reverse-open becomes a *rejected close*. That is still a stale-book failure, but a different one.
- The gap-through behaviour of prop servers is unknown until it is observed.
- Clean reproductions against a mock are not proof that a real adapter behaves the same way.

## 5. Proposed ledger items (no IDs)

| Item | Sev / Lik | Proposed status | Tag | Value / complexity cost |
|---|---|---|---|---|
| The orchestrator never forwards `stop_loss`, and the §279 conformance bypasses the orchestrator (D1) | Critical / High | open, pre-demo blocker | [impl] | Closes the only VPS-death protection. About +1 argument, one conformance case through the orchestrator, and one attach-time stop audit (roughly 30 lines, 0 new concepts). |
| Ack-lost fill → orphan and double fill; the reconcile is log-only (D2, D3) | Critical / Medium | open, pre-demo blocker | [impl] | Removes the orphan class. Query-then-decide in `_submit_once`, plus broker-sourced heartbeat positions (roughly 40 lines, 1 concept: "ambiguous send"). |
| HALTs and drawdown anchors are not persisted; a restart is a relaxation (D4, D5) | High / Medium | open | [owner decision] | Makes "resumes are human-only" true across crashes. Wire the existing `RiskStore` tables (they already exist; roughly 30 lines, 0 new concepts), or force HALT-on-start. |
| The watchdog flatten is unfenced from the engine (D6) | High / Low–Medium | open | [impl] | Removes stale-book trading after a flatten. One marker file read before each order, plus a loop-gap reconcile (roughly 20 lines). |
| The `ftmo` stand-in is looser than FTMO's daily rule; the "stricter-of" claim is false (D9) | High / Medium | open | [owner decision] / [spec — owner ratification] | Needs the §5.3 schema extension from SCOUT (a zone, a reset instant and a day-start anchor): one rule type, roughly 60 lines. |
| The staged `marginal_alpha_window` can switch off the losing-book floor (D10) | Medium / Low | open | [owner decision] | Raise the allowlist minimum to ≥ `min_trades`, or make the path human-gated. A 1-line config change, 0 concepts. |
| The freeze is not re-checked per fragment (D7) | Medium / Low | open | [impl] | A 3-line check in `_dispatch`. |
| Reconcile adopts positions at price 1.0, and `BrokerPosition` lacks an entry price (D8) | Medium / Medium | open | [impl] | Add `avg_price` to the contract: 1 field. |
| No host-vs-broker time gate (D14) | Medium / High | extends GAP-P12D-51's residual | [impl] | One start-up check of roughly 15 lines. |
| `mode` is not bound to the venue account type (D15) | High / Low | open | [owner decision] | An adapter refusal rule: 1 check, plus the owner's definition of "paper" for a prop trial. |
| Restart loop against `AttachHalt` and the request cap (D16) | Medium / Medium | open | [impl] | `RestartPreventExitStatus` for the attach halt, or a start-halted design. Config only. |
| `Governor.resume` accepts any non-empty string | Low / Low | open | [impl] | Verify the token at the guard, or take a verified-capability object. About 5 lines. |
| `daily_pnl` uses UTC days while the guard uses the New York day (D17) | Low / High | open | [impl] | 1 line. |

**On net complexity:** every fix above wires machinery that already exists (`RiskStore`, `resting_stops`, `open_positions`) or adds a single check. None adds a module. The item that grows the codebase most is D9, the schema change, and SCOUT already scoped it.

## 6. Sources (accessed 2026-09-24)

| Source | URL | Grade |
|---|---|---|
| FTMO Trading Objectives (Maximum Daily Loss and Maximum Loss, 2-Step; page modified 2026-09-24). **Verifies S6.** | https://ftmo.com/en/trading-objectives/ | (a) |
| ESMA press release, 27/03/2018: *"74-89% of retail accounts typically lose money on their investments, with average losses per client ranging from €1,600 to €29,000."* **S2 upgraded, and corrected: it is a regulator statement based on NCA analyses, not broker disclosures.** | https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors | (a) |
| cTrader Open API messages (`ProtoOANewOrderReq`, `ProtoOAReconcileReq`) | https://help.ctrader.com/open-api/messages/ | (a) |
| SEC press release 2013-222, Knight Capital | https://www.sec.gov/newsroom/press-releases/2013-222 | (a) |
| FXCM, "FXCM Comments on Swiss Franc Movement", 16 Jan 2015 | https://www.globenewswire.com/news-release/2015/01/16/697841/33730/en/FXCM-Comments-on-Swiss-Franc-Movement.html | (a) (the firm's own release) |
| SCOUT final (local pass, untrusted and extended here) | `_context/local-wip/files/archive/RESEARCH_PROP_VENUES_2026-09-24.md` | evidence, not authority |
