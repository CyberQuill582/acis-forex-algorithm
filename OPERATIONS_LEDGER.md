# OPERATIONS_LEDGER.md — runtime/operational ledger (ACIS)

**Activates at go-live (phase 12, first live fill). Empty until then — this is a placeholder wired into the process so the mechanism exists before it is needed, not scrambled together after the first surprise.**

## What this is (and why it is separate from KNOWN_GAPS.md)
`KNOWN_GAPS.md` records **build-time** gaps against the spec. This file records **operational (runtime) surprises** once the engine trades real money — the "tribal knowledge" that only exists after a live VPS, real fills, a real financing table, and a real broker generate it. Kept separate so the build ledger stays clean, but in the **identical format** so both adversarial audit lenses can consume it without translation.

This ledger is **guard 3 of three** (CLAUDE.md "Operational correctness"): it is one guard, never the whole. It captures surprises *after* they surface; it does not replace guard 1 (the two-lens audit) or guard 2 (real out-of-sample validation + human sign-off before live). A log is not a validation gate.

## What goes here (log it the day it surfaces)
Anything where live reality diverged from what the code/spec assumed:
- **Real-vs-modelled fills** (GAP-0001): actual slippage/partial-fill/latency vs the declared C8 model.
- **Financing/carry reality**: actual broker swap charges vs `carry.py`/the financing table (incl. the triple-swap day and any Friday-triple metals convention).
- **Broker quirks**: symbol-suffix surprises, rejects, quote/depth anomalies, order-type handling, server-side stop behaviour.
- **Connectivity**: reconnect/backoff behaviour, weekend-gap handling, restart reconciliation vs the broker's authoritative state.
- **Observed live risk**: the **VaR breach frequency actually observed vs the 1% level** (the GAP-0103 quantity, now measured live), realised drawdown vs modelled, cluster/delta behaviour.
- Any HALT/flatten/resume in production and its post-mortem.

## Format — identical to KNOWN_GAPS.md (one entry per surprise, newest first, never delete)
```
## OPS-NNNN: <one-line title>
- Severity: critical | high | medium | low
- Likelihood: high | medium | low          (recurrence, once observed)
- Status: open | mitigated | accepted-risk | closed
- Area: [DIR:...] / adapter / broker / config §
- Observed: what live reality did, with the log timestamp / session_id / fill id that proves it
- Modelled: what the code/spec assumed (cite the module + the modelling GAP if any, e.g. GAP-0001)
- Delta + impact: how far off, and what it distorts (PnL, a §14 metric, a guard's trigger point)
- Justification: why this status (esp. accepted-risk); Linked: commits / test names / the audit pass that found it
```
Guardrail-adjacent operational findings (anything touching a HALT/veto/equity-floor trigger *in reality*) are ALSO summarised in `SPEC_AUDIT.md`, same as build-time guardrail findings. **Never** let an operational finding become a reason to weaken a guardrail without a human commit — a live divergence that makes a guard misfire is a finding to raise, not a knob to turn.

## How the audits consume this (owner directive 2026-07-18)
- **The operational-referent pass** (CLAUDE.md audit §, "standing, from go-live") reads this ledger + the live JSONL logs and re-runs the external-referent lens against **live behaviour, not just the spec**: does modelled cost/carry/slippage/fill still match what the broker actually did? It triages exactly like a phase audit (fixed+test / mitigated / accepted-risk), and its findings land here.
- **The internal-consistency lens** uses this ledger to check that a logged surprise was actually acted on — no operational finding rots, same never-rot rule as build findings.

---

## Entries
_(Activates fully at the first live fill. Demo-probe observations are logged here because ACIS-13 Appendix B names this ledger as their record. Do not backfill build-time gaps here; those live in `KNOWN_GAPS.md`.)_

## OPS-0001: First Pepperstone cTrader demo probe — the venue's answers to ACIS-13 OQ-07/08/09/12/17
- Severity: low
- Likelihood: high (venue behaviour, recurs on every order)
- Status: open — one sample each; fold the answers into ACIS-13 Appendix B at its next owner-ratified revision
- Area: adapter (`core/data/ctrader/`, `core/execution/ctrader_*`), demo account 48971796 (traderLogin 5350811)
- Observed (2026-10-01, `scripts/ctrader_probe.py` on acis-compute-1; reports `ctrader_probe_20261001T102859Z.json` read-only and `ctrader_probe_20261001T104403Z.json` with `--trade`, copied to `gs://acis-compute-0929-data/runs/2026-10-01-probe/` for the first):
  - **OQ-07 (stop atomic with the fill?):** the stop comes from the ONE order request (`relativeStopLoss` 500), and the venue places it itself, but NOT in the fill event. The `ORDER_FILLED` event (executionType 3, 10:44:02.952 UTC) has no `stopLoss`. A separate event 6 ms later (executionType 2, a STOP_LOSS_TAKE_PROFIT order) shows `stopLoss` 1.12417. The relative stop is anchored to the FILL price (1.12917 − 0.00500), not the requested price (requested 1.12416), so slippage moves the level and keeps the distance.
  - **OQ-08:** the spot `timestamp` is ms UTC (receive − venue time: median 72 ms, min 71 ms over 200 spots). The first event after subscribing is a snapshot carrying both sides. The server sent NO heartbeat in 45.8 s while spots were flowing, so its idle cadence is still unobserved.
  - **OQ-09:** not settled: EUR_USD and USD_JPY report `slDistance` 0, `distanceSetIn` 1 (points), so there is no minimum distance whose unit could be checked.
  - **OQ-12:** enums inside `payload` are integers (e.g. `executionType`, `orderType`, `positionStatus`, `permissionScope` 1 = SCOPE_TRADE); every frame was a text frame (0 binary of 299).
  - **OQ-17:** a MARKET order with `timeInForce` 3 (IMMEDIATE_OR_CANCEL) was accepted and filled whole (1,000 units = 0.01 lot, `minVolume`). No partial fill seen; one minimum-size sample cannot show that demo servers never partial-fill.
  - **OQ-06 (case 8, 11:16 UTC):** YES on the demo: a second connection (the watchdog plugin) authorised the account while the engine-like process held its socket open (SIGSTOPped), closed its position and proved the account flat. A close is ACKNOWLEDGED (execution event) before it FILLS, so an immediate reconcile still shows it ([[GAP-P12D-133]], fixed). The single-binding question is answered by a CI test that the two files agree.
  - Costs seen: slippage 0.089 bps (1 point); commission −3 at money digits 2 ($0.03) on the 0.01-lot open; symbol `commission` 300, `commissionType` 2; swaps EUR_USD long −0.73 / short 0.15, USD_JPY long 0.28 / short −1.55. Open → close took ~0.75 s; the position closed (status 3, volume 0) with 0 open positions left.
- Modelled: ACIS-13 §7.3 step 6 confirms the stop within `stop_confirm_timeout_s` (3 s) and repairs it otherwise; §6.3 (D3) sends a relative stop widened by the live spread. Demo costs never calibrate C8 (D4, GAP-0001).
- Delta + impact: no defect seen. The 6 ms gap between the fill and the stop event sits well inside the 3 s confirm window, and the face read the venue stop back (`stop_at_venue` 1.12417), so no repair request was spent. The fill-price anchoring shifts the stop by the slippage (1 point here), which the distance-based design already allows for.
- Justification: probe facts, recorded the day they were observed; the OQs stay open in Appendix B until a ratified revision folds them in. Linked: TODO item 1, GAP-P12D-131.
