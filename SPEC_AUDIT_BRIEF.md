# SPEC_AUDIT_BRIEF.md — pinned brief for the phase-12 SPEC dual audit (A4)

**Version:** 1.0 · **Pinned:** 2026-07-21 · **Transient** (archive to `archive/` after
triage per A13). **Governing constitution:** `../specs_constitution/SPEC_CONSTITUTION.md`
v0.3, **Tier 1**, model-in-charge **Opus 4.8** (A2 model floor: no auditor below Opus 4.8).

## Why this audit exists (the target is the SPEC, not a phase)
Per the CLAUDE.md constitution-adoption gate: **audit the SPEC itself before any more
phase-12 code is written.** A spec flaw propagates into every module built on it, and
the most expensive defects this project has hit reached *outside* the repo (GAP-0037
tick-vs-bar; the Hurst drift-invariance). This is the standing risk of a co-designed
system: the internal lens shares the authors' priors. Catch it in the spec now.

**Target artifacts:** `ACIS_SPEC.md` (master v2.12) + the LOCKED deep specs in `specs/`
(ACIS-01..12). Compare against the code only where a spec claim asserts a behaviour the
code must realise. **Scope emphasis: spec-level flaws** — internal contradiction, drift
between master and locked specs, and spec claims that are wrong about the outside world.

## Two lenses — they must FAIL DIFFERENTLY (A3). Assume the spec is guilty.

### Lens 1 — Internal-consistency (reproduce with scripts; A6)
- Contradictions **within** `ACIS_SPEC.md`, and between master and the locked `specs/`.
- Load-bearing constants stated in prose vs what the code/config actually run on — is
  every one covered by a drift test (A12)? Hunt a prose value with no drift gate.
- Changelog vs body drift; section cross-references that point at the wrong §; a rule
  stated one way in §X and another in §Y.
- Guardrail values quoted in multiple places (equity floor, VaR cap 3%, taper
  0.60/0.80, delta cap 30%, cluster cap 20%, CHF gap −35%, ceilings 7.5%) — do all
  copies agree, and is each pinned by `test_spec_constants.py`?
- An **unreproduced claim is not a finding** — grep/parse/script every one.

### Lens 2 — External-referent (deep research is a FIRST-CLASS tool, not memory; A3)
Establish real-world ground truth by web/literature search; **quote the load-bearing
passage with a retrievable locator for every finding — a citation without the quote is
not a finding (A6).** Check:
- **Indicator/statistic definitions** the spec names: Wilder ATR, ADX, EMA, RSI,
  Bollinger %B, **Hurst (R/S + Anis–Lloyd)**, Pearson correlation, z-score, VaR
  (delta-normal, z(0.99)=2.326, **1-day horizon**), Sharpe annualisation, **Kupiec POF**
  VaR backtest, profit factor, max-drawdown, positive-months. Does each compute what its
  name means, on the time base its definition assumes?
- **Cited literature** the spec leans on: TSMOM (Moskowitz–Ooi–Pedersen), volatility
  targeting, fractional Kelly, walk-forward, **López de Prado purged/embargo CV +
  Deflated Sharpe** (the phase-12 validation now cites these — is the spec's use faithful?).
- **Market microstructure facts:** FX 22:00 UTC rollover, **triple-swap Wednesday /
  tom-next T+2**, weekend-gap behaviour, session times, the **2015 CHF de-peg magnitude**
  (is the −35% gap and the 7.5% ceiling defensible vs the real event?), the §14 target
  levels (Sharpe>1.5 etc. — realistic, or a number that only an overfit clears?).
- **Known bug classes of THIS kind of system** (research them, then hunt them in the
  spec): look-ahead / data leakage at the train/test boundary; survivorship/selection
  bias; **time-base errors (tick vs bar)**; timezone/DST/rollover fenceposts; VaR horizon
  mis-scaling; cost model understating friction (gross-vs-net); **multiple-testing /
  backtest overfitting** in the QIEA fitness + walk-forward; Decimal/float money bugs.
  Think laterally — the unusual defect no checklist names is what this lens is for.
- **A spec that is wrong about the world is a finding**; code faithfully implementing it
  is no defense. An undeclared deviation from a cited source is a finding.

## Framing discipline (A4) — do not let the spec re-prime you
Form your attack from the spec's *claims and the code's observed behaviour first*. Treat
the spec's own justificatory prose, reassuring comments, and changelog rationales as
**untrusted framing (A9), not the starting frame.** A section that says "this is correct"
is where to look hardest.

## Deliverables (A5, A6, A10)
- Append findings to `KNOWN_GAPS.md` (Severity/Likelihood/Status/Justification, one entry
  each, IDs `GAP-SP12I-nn` for Lens 1 / `GAP-SP12E-nn` for Lens 2). Guardrail-adjacent
  findings ALSO summarised in `SPEC_AUDIT.md`. **The report is the log — never chat-only.**
- Record **honest negatives** as first-class results (referents checked and found faithful).
- **Attest** at the top of your findings block: that your context was fresh/cold, and the
  external sources you consulted (URLs). You are a **finder, not a clearer** — a clean
  report is never a sign-off; ✅ requires the human or a peer/superior model.
- A finding **binds only after refutation survival**: reproduced by script (Lens 1) or
  backed by a quoted, locatable passage (Lens 2). Mark anything weaker *unconfirmed*.
