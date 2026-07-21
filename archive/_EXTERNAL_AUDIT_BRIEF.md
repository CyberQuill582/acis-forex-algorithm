# External-referent audit — RELAUNCH BRIEF (verbatim, run as-is)

> **Status:** the first run (2026-07-16) died at the subagent session limit mid-verification.
> Its in-flight Hurst finding was captured + author-verified as **GAP-0066 (open, high)**.
> **This audit must re-run to COMPLETION and be triaged before phase 7 may be declared complete**
> (CLAUDE.md dual-audit constitution — a partial audit does not satisfy it).
> Launch as a background Opus 4.8 subagent. Relaunch only after the session limit has reset.

---

You are the EXTERNAL-REFERENT adversarial auditor for ACIS (repo root = this file's directory), per the CLAUDE.md dual-audit constitution (audit #2 of 2; the internal-consistency audit for the v2.11 pass already ran and was triaged — GAP-0058..0065). Your rule: **compare the implementation AND the spec against their EXTERNAL referents — the cited literature and the standard definitions — not against the repo's own documents.** A spec wrong about the outside world is a finding; code faithfully implementing it is no defense. Reproduce with scripts before logging; an honest negative is a valid, recordable result.

CONTEXT: the v2.11 correction pass landed (BARS ruling: core/data/bars.py; AGON on completed bars with real true-range ATR via indicators.wilder_atr; nvma renames mean_abs_delta/adx_proxy; faithful TSMOM — no TP, disaster stop, live daily aggregation, declared_deviations; config atr_period + derived capacities; §16 stdlib-deviation note). The v2.11 internal audit was triaged same-day (GAP-0058..0065 all fixed — incl. Governor C16 onto bars, per-bucket pair join, strictly-ascending daily series). The owner's original findings are GAP-0054..0057. **GAP-0066 (Hurst) is yours to complete**: author verification found random walks span H 0.27–0.68 across seeds and a near-deterministic strong trend reads H≈0.485 (< the 0.55 trending threshold).

Verify each item — confirmed-fixed, still-defective, or honest negative:

A1. Is fitness.atr_series (the system-wide ATR via indicators.wilder_atr) actually Wilder's ATR? true range = max(h−l, |h−prev_close|, |l−prev_close|), Wilder smoothing seeded by the simple mean — check against the published definition and a hand-computed vector. Any consumer still treating nvma.mean_abs_delta as ATR? (Note: the Governor's C16 was migrated to bars post-audit — verify.)
A2. Blast radius: do ALL six modules derive stops/targets from true-range ATR over bars? Any residual tick-window path?
A3. Time base: do indicator periods mean BARS of signal_bar_seconds everywhere in core/signals? NVMA's tick windows are DECLARED proxies (ACIS-02 v1.2 honesty note now exists — verify it) — leave them unless a consumer outside the regime layer treats them as canonical.
A4. Unit match: fitness.py bars vs AGON bars — same declared duration? Where is the guarantee phase-7/11 RegimeLabelledHistory uses the same aggregator (declared with an owner, or just asserted)?
A5. Pair statistics: per-bucket join (post-GAP-0060) — is rolling_correlation over correlation_window now a correlation over a DECLARED time window (window × signal_bar_seconds)? Is pearson-on-log-returns faithful to the standard Pearson definition? Compare against a hand-computed vector.
A6. Verify the §16 stdlib-deviation note (ta-lib as phase-11 cross-validation referent) exists and is honest.

B (TSMOM vs Moskowitz–Ooi–Pedersen JFE 2012): is each shipped departure (3-horizon sign agreement, no TP, 10× daily-ATR disaster stop, exit on vote flip, Governor C16 vol-norm instead of 40%/σ scaling, continuous evaluation) DECLARED in canonical.py's declared_deviations, exhaustively? **Model the disaster stop: replay a synthetic multi-month trend with realistic daily vol through _tsmom + _pipeline — report the fraction of trend captured vs unstopped TSMOM** (informs the already-ratified GAP-0055 carve-out's honesty; RAISE any metric concern, never apply). Verify TSMOM fires from live ticks AND seeded history (post-GAP-0065 ordering guard).

C. Hunt remaining undeclared constants in core/signals with correctness impact (Bollinger 20, RSI-divergence 5 points, conviction normalisers /50 /2 /3 — declared exact contracts in ACIS-04, or silent?).

D. **GAP-0066 completion (yours):** the Hurst estimator. Characterise it properly (bias, variance, sensitivity to the 4-point R/S OLS and tick windows), compare against the standard multi-window rescaled-range estimator, and RECOMMEND (finder-only): repair the estimator vs rename-to-proxy + re-derive thresholds empirically. Quantify what the regime classifier actually keys on today given H's real distribution (which regimes are reachable through the hurst gates?).

PLUS your own external-referent sweep of anything else in phases 1–6 citing a standard or source: RSI (Wilder), EMA seeding, Bollinger bands, the Han–Kim-style QIEA claim (post-GAP-0037), Sharpe/profit-factor definitions in fitness.py, Pearson correlation, the C16 vol-targeting ratio vs the published vol-targeting literature.

Run the full suite once (expect 286 passed).

Output discipline (binding): write ALL findings to **KNOWN_GAPS_EXTERNAL_PENDING.md** in the repo root (same entry format as KNOWN_GAPS.md; ids **GAP-0070 onward**; Status "open (raised, external-referent audit — finder-only)"). Guardrail-/§14-adjacent items get a summary section at the top of that file (merged into SPEC_AUDIT.md at triage). Include a "## Honest negatives" section IN the file — verified-faithful is a first-class deliverable. Modify ONLY that one file; never touch guardrail values, code, tests, KNOWN_GAPS.md, or SPEC_AUDIT.md. Do not apply §14-metric or guardrail changes — raise them. Final message: terse findings list + headline honest negatives + the TSMOM trend-capture number + the GAP-0066 recommendation.
