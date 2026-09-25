# BASELINE — the pristine, untrained ACIS

**Owner directive (2026-07-21): preserve the raw, market-untrained algorithm as
an immutable, always-cloneable reference, so it can be re-evolved differently in
a future training run (a better model, or Fable 5) without ever losing the clean
starting point.** This file records what that baseline *is* and the rule that
keeps it pristine.

## What the baseline is (and is not)

ACIS is **not a trained model with weights.** There is nothing to "retrain."
What "training on market data" means here is **QIEA parameter calibration** — and
the architecture already separates the two things your idea wants kept apart:

- **The architecture** = the deterministic code in the seven `core/` layers. By
  design it *never calcifies* (SPEC design-principle #11): it is the raw engine,
  fixed, and it is never "trained into."
- **The trainable part** = an `ActiveParamSet` produced by the QIEA optimizer
  (`core/optimizer/`), staged and promoted through the `ParamLibrary`. That —
  not a fork of the code — is the "diverged, market-optimised clone."

So the pristine untrained baseline **is** `{ the code at the git tag } +
{ config/*.yaml defaults } + { the gene SEARCH SPACE, GENE_SPECS }`. There is no
single "baseline ParamSet" that trades: a regime is untradeable until a
*calibrated* set is promoted (that is deliberate; fabricating a trading baseline
would be the speculative artifact §17/§18 forbid).

## The immutable reference

| Reference | Where | Immutable by |
|-----------|-------|--------------|
| Code + config snapshot | git tag **`baseline-untrained-v1`** | git (annotated tag) |
| Gene search space (the DNA) | `config/baseline_manifest.json` | `tests/unit/test_baseline_paramset.py` (drift guard) |

To start a fresh, differently-evolved lineage in the future: **clone from the
tag**, then let the QIEA + challenger lane evolve a NEW named ParamSet on the new
data. You never edit the baseline to do this.

## How a future run "evolves it differently" — already in the spec

The mechanism your idea describes is exactly SPEC §5.6/§5.7, with the honesty
gates that keep it from lying:

- **Challenger lane (§5.7):** bespoke variants run concurrently in paper on the
  same live data; one becomes champion only by beating it **out-of-sample**,
  through the full `incubation → paper → live` ladder — never by swap-in.
- **Graveyard (§5.7):** retired variants are kept with full provenance and a
  declared revival condition — *"a library, not a landfill."*
- **A future/better model (incl. Fable 5)** contributes **out-of-band only**
  (SPEC §0 / non-negotiable rule 1 — no LLM in the fast loop): it may *propose*
  strategy variants or parameter searches through the §5.6 research loop, which
  then enter incubation and must clear the same §14 out-of-sample gate + human
  sign-off. It never "trains the engine" at runtime.

## The rule (binding)

**Append-only. The baseline is never mutated in place.** Changing the gene search
space is a conscious **re-baseline**, not an edit: update
`config/baseline_manifest.json`, cut a **new** git tag (`baseline-untrained-v2`,
…), and record it below. The drift-guard test fails on any silent change — that
is the enforcement.

### Re-baseline log (append-only)
- `baseline-untrained-v1` — 2026-07-21 — initial freeze at phases 1–11 ✅
  (master spec v2.12, 11-gene search space). The pristine pre-live baseline.
- **Re-baseline APPROVED, not yet cut — 2026-09-25 (owner, R1-D4: "i ratify all your recommendations for
  R1-D1 to D14"; master v2.21 §5, ACIS-03 v2.0).** QIEA's per-regime gene search is replaced by pooled, fixed
  rule parameters.
  - **At R1.7**, when the QIEA code is retired by `git mv`, the manifest and the drift-guard test are
    re-pointed, the new tag `baseline-untrained-v2` is cut, and the new tag is recorded here.
  - **Until then:** the v1 manifest and its test stay exactly as they are, and `baseline-untrained-v1` is
    never moved.
