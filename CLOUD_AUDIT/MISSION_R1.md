# MISSION R1 — ACIS: research and plan the new training and validation direction (owner-ratified R-1)

Read `FLEET_PLAN.md` first. Its hard rules bind here: reports only, quote your sources, grade the evidence, and use
no real market data. This mission runs **after** the six-project fleet, on the reserve credit.

## 0. The task, in the owner's words (2026-09-25)
> "I want thorough research and planning done on the 6 recommended steps. Web search should be used as a first
> class tool to discover methods that work and, if possible, add to the methods. Find innovative ways to go about
> the training so that we get a bleeding-edge trading algo and not a joke."

**The deliverables:**
1. **A research dossier.**
2. **A concrete, buildable plan.** The local ACIS lead turns it into spec amendments, written as OLD/NEW blocks under
   ACIS governance, and then into code.

"Bleeding edge" means methods that **survive honest out-of-sample evaluation**, not methods that are merely new.
Every recommendation carries its evidence grade, a falsifier, and its complexity cost.

## 1. What the owner ratified (R-1, the DIRECTION; the specifics are this mission's job)
1. **Few, economically motivated rules, with parameters pooled across instruments** and chosen coarsely for
   robustness. This replaces QIEA's per-regime × per-instrument 11-gene evolution with argmax champion staging.
2. **Breadth over length:** pooled rules tested on 20–40 instruments (more FX pairs, metals, indices, energies), not 8.
3. **An expanding training window**, in place of the 2-year rolling window. C1 measured the rolling window realising
   0.02 of a 0.65 Sharpe edge; an expanding window realised 0.52–0.72 of a 1.22 edge.
4. **Iterate freely, but register every run.** The verdict comes from a search-aware test over the whole register,
   never from the best run. C1: keep-best-of-20 passes noise 44–53% of the time.
5. **Unlimited iteration on synthetic markets, for the machinery only.** First fix the generator's whole-path
   demeaning bias (`tests/backtest/synthetic_market.py:83-84`), then add realistic properties.
6. **The only uncontaminated tests** are held-out instruments and forward time. The 2024–25 holdout is used ONCE.
   The demo account's forward record is the decisive test.

**Owner-ratified items this direction touches.** Each needs a drafted OLD/NEW amendment, and none may change
silently:
- the 2-year walk-forward window;
- the DSR ≥ 0.95 `passed` gate (GAP-P12D-16);
- TSMOM as "required canonical" (ACIS-04 §6.6);
- QIEA staging (master §5, ACIS-03);
- the 8-instrument universe.

## 2. Read first
- **The cloud ACIS review** on branch `claude/acis-cloud-review-2026-09-24`, under `CLOUD_AUDIT/reports/`:
  - `SYNTHESIS.md`;
  - `C1_CALIBRATOR.md` (the frontier, the protocols, the looks budget);
  - `C3_ENGINE_FORENSICS.md` (the generator bias; a slow daily rule against the arena);
  - `C4_PROVEN_PARTS.md` (degrees of freedom, the kill list, the referents);
  - `BRIEF.md` (the field brief);
  - `P3_LEAD_VERIFICATION.md`.
- **The local five-agent finals**, on `origin/main`, in `archive/`:
  - `RESEARCH_VALIDATION_FIREWALL_2026-09-24.md`;
  - `RESEARCH_EDGE_FACTORY_2026-09-24.md` (the hypothesis slate and the factory design);
  - `RESEARCH_PROP_ECONOMICS_2026-09-24.md` (the minimum edge for +EV, and survival-first sizing);
  - `RESEARCH_PROP_VENUES_2026-09-24.md`.
- **The local builders' work:** the look register and the oracle loop, on `origin/main` or in `_context` worktrees.
- **The code at BASE,** for mapping: `core/optimizer/`, `core/signals/`, `tests/backtest/`, `config/`.

**Build on all of it; do not redo it.** Where you disagree, say so, with evidence.

## 3. The questions (web research is a first-class tool)
For **each** of the six directions, answer:
- **(a) The state of the art, 2020–2026,** from primary sources, quoted and graded.
- **(b) What the profitable minority** and institutional practitioners actually do.
- **(c) The concrete ACIS design.**
- **(d) What is newer or better** that plausibly beats that baseline.
- **(e) How we would know:** the falsifier and the measure.

Cross-cutting questions:
- **Squeezing the most uncontaminated evidence** out of finite history plus forward time:
  - **Breadth and effective breadth:** correlation-adjusted, e.g. an instrument-diversification multiplier.
  - **Hierarchical or Bayesian pooling and shrinkage** of rule performance across instruments.
  - **Held-out instrument sets.**
  - **Anytime-valid sequential testing of the demo forward record,** using e-values or e-processes, or SPRT, so the
    owner can monitor continuously without inflating false positives. What record length and trade count proves
    what?
- **Innovative training that survives honest evaluation.** For each: out-of-sample evidence in FX, futures or CFDs;
  cost sensitivity; data needs; complexity cost; and a verdict of adopt, adapt or reject. Candidates:
  - forecast combination and handcrafting;
  - hierarchical models;
  - meta-labeling;
  - ensembles;
  - online, regret-bounded allocation among rules;
  - volatility-managed exposure;
  - regime as a weight, not a gate;
  - ML such as gradient boosting or sequence models, under purged, embargoed CV;
  - LLM-generated hypotheses under a strict contamination rule (post-cutoff or forward-only grading).
- **A hype filter.** Name popular "AI trading" methods that fail honest evaluation, with sources. Leads to check:
  arXiv 2608.27734, "What survives honest evaluation?", and the 2025–26 agentic-trading surveys.
- **The synthetic market lab.** Which generators can be trusted for testing *machinery*?
  - **Parametric:** GARCH-t, jumps, regime switching, weekend gaps, session spreads.
  - **Agent-based simulators,** e.g. ABIDES.
  - **Generative models,** e.g. Quant GANs and diffusion models, with their known failure modes.
  - **Note:** a bootstrap of real returns is itself a look at real data, and counts as one.
  - **Deliver** a generator spec and a working prototype, with stylized-facts tests. Synthetic only.
- **The data plan.**
  - Which Dukascopy instruments to add, taking 20–40 in total.
  - Their typical spreads and costs, their correlations and effective breadth, and whether prop firms allow them.
  - Bar resolutions.
  - How much laptop disk and download time the plan needs.
- **The research-factory architecture:**
  - a registry, extending ACIS-11 `ProvenanceStore` or the local look register;
  - a bar-level research simulator, reconciled to the tick harness, with the reconciliation test spec;
  - the gates: exploration → validation → holdout once → demo incubation → challenge;
  - the looks budget and kill criteria;
  - a compute estimate.

## 4. Recommended lanes (4, in parallel; the lead may re-cut them, recording why in BRIEF_R1.md)
| Lane | Focus | Web cap | Time box |
|---|---|---|---|
| **R1-A VALIDATION SCIENCE** | Extend C1 and the local VALIDATOR. Anytime-valid sequential testing for demo incubation; hierarchical shrinkage of Sharpe across instruments; FDR and register-aware verdicts. Simulate on synthetic data the power at the expected demo trade counts. | 30 | 2.5 h |
| **R1-B EDGE AND BREADTH** | Rule families that work across markets (trend at several speeds, carry, seasonality or scheduled flows, value where it exists); pooled parameterisation; forecast combination; the instrument universe and cost map; compatibility with prop rules; what the minority does. | 40 | 2.5 h |
| **R1-C SYNTHETIC MARKET LAB** | Generator redesign and a prototype, validated against stylized facts; a comparison of parametric, agent-based and generative approaches; how the lab plugs into the harness without a second cost model. | 25 | 2.5 h |
| **R1-D INNOVATION AND ARCHITECTURE** | The candidates above, put through the hype filter; the factory architecture mapped onto ACIS code, as lean deltas plus a kill list; where out-of-band LLM help fits under the contamination rule. | 40 | 2.5 h |

## 5. Deliverables, under `CLOUD_AUDIT/reports/r1/`
- **`BRIEF_R1.md`,** pinned before launch.
- **One report per lane,** following the FLEET_PLAN §6 contract.
- **`PLAN_R1.md`,** the lead's synthesis. **It is the priority deliverable. If the budget is short, cut lanes, never
  the plan.** It contains:
  1. **The recommended training and validation architecture,** on one page.
  2. **A phased build plan:** order, dependencies, effort, and lines added and removed.
  3. **The experiment plan:** a pre-registered hypothesis slate (building on ARCHITECT's), the looks budget, the kill
     criteria, and the demo incubation protocol (length, sequential test, thresholds).
  4. **Spec amendment drafts** as OLD/NEW blocks, for every ratified item it touches. These are proposals only.
  5. **Owner decisions,** each with a recommendation.
  6. **The bar that separates "bleeding edge" from "a joke",** stated as measurable acceptance criteria. For example:
     a register-corrected out-of-sample Sharpe confidence interval, and a forward e-value threshold on the demo.
- **Close with the FLEET_STATUS line** keyed `acis-r1`.

## 6. Boundaries and budget
- **No real market data.** This mission designs how real data will be used; it does not use any. Synthetic
  experiments only.
- **Credit:** R1 runs on the reserve. If the credit runs out, the owner's plan usage continues it automatically.
  Finish PLAN_R1.md whatever happens.
- **Usage limits:** if a usage limit stops the session, stop cleanly with everything pushed. The owner will type
  "continue" after the reset.
- **Reports only.** Commit with the pathspec form. Cite only ACIS ledger IDs that exist at BASE.
