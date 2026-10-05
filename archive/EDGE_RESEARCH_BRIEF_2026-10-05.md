# Edge research brief — two Fable agents, 2026-10-05 (pinned before launch, A4)

**Launched by the owner's explicit request (2026-10-05 22:40 EAT):** "launch 2 fable auditors at medium effort to do investigations on how we could get an edge ... tackle from different angles. we want an edge that works and works good and a way to keep evolving and coming up with new working edges as the market is dynamic ... use the google cloud server however you wish."

These are **research agents, not A3 phase audits** (no phase is being audited). Owner of the ledger entry: [[GAP-P12D-161]].

## Shared context (both agents read this)

ACIS is a deterministic, LLM-free-at-runtime systematic trading engine for one small operator in Kenya, run from the cloud. Venue today: a Pepperstone cTrader **demo** (CFDs: FX, metals, index CFDs; energy refused by the data layer). Planned money venue: a swap-free prop-firm account (E8 One shortlisted; ~$6k scale; prop rules: daily-loss and max-drawdown limits). Target the owner set: forward net Sharpe ≥ 0.5 over 6 months on the demo before any paid challenge; the weekly target in `archive/RESEARCH_PROP_RETURNS_2026-10-02.md` needs ~0.65–0.85 net.

**What has been tried (read the table in `TODO.md` "Where we stand on an edge", and [[GAP-P12D-158]] in `KNOWN_GAPS.md`):** D1 trend (13 FX), D3 turn of month, REBAL (60/40 rebalancing, US500), IMOM (intraday momentum), GOTOBI (USD/JPY Tokyo fix), FXHEDGE (month-end 4 pm fix), GOLD-EW, OPEX, AUCTION, IREV, DCARRY, HALLOWEEN, HEDGEP, FXVALUE, plus the legacy engine (TSMOM/TREND/BREAKOUT/MEAN_REVERSION) that loses on its own planted market. Several survived 2012–2023 and **none earned on the sealed 2024–25 holdout**. Every family so far was an LLM-selected published anomaly; published anomalies lose about half their return after publication. The CFD spread killed several gross edges (IMOM ≈ +0.55 gross).

**Governance you must respect (binding):**
- SPEC §5.6: an idea an LLM selects is **LLM-origin**. History can only KILL it; credit comes only from the forward record (`scripts/tournament_daily.py`, `data/forward/`, master v2.36 milestone D = a spending gate, never evidence). Your proposals are LLM-origin. Say so; do not dress them up as anything else.
- **The look register** (`data/validation/looks`) records every real-data look. **Do NOT run backtests on the real 2012–2025 data** (laptop or server): an unregistered look is data snooping and corrupts the register; the 2024–25 holdout is spent for several families. Instead, write each test you want as a **pre-registration spec** (rule, instruments, window, cost model, kill threshold, version split) for the owner to approve.
- You MAY use the Google compute server for synthetic simulations, power/sample-size calculations, cost arithmetic, and replicating published numbers from public data you download yourself (state the source URL). Rules: VM `acis-compute-1` only (project `acis-compute-0929`, zone europe-west1-b; gcloud at `%LOCALAPPDATA%\Google\google-cloud-sdk\bin\gcloud.cmd`). Start it if stopped (`gcloud compute instances start acis-compute-1 --zone=europe-west1-b`; if capacity fails, retry a few minutes). Work ONLY in your own directory `/opt/acis/edge-<A|B>/`. **Never touch `acis-demo-1`, the AWS hosts, `/opt/acis/repo`, or `data/validation/looks`. Do NOT stop the VM** (the other agent may be using it; the lead stops it). Laptop: no heavy runs (owner directive).
- **Do not edit the repository** except to write your one report file. No commits. Launch no subagents.
- **WebSearch cap: 70 calls each** (shared session budget ~200). When spent, switch to WebFetch on primary URLs and say so in your method note.
- Never guardrails: you may not propose weakening `config/guardrail_limits.yaml`, the equity floor, or HALT/veto semantics.

**Read first (skim, don't re-derive):** `CLAUDE.md`, `TODO.md` START HERE block, `KNOWN_GAPS.md` [[GAP-P12D-158]] and [[GAP-P12D-148]], and the earlier research so you do not repeat it: `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md`, `archive/RESEARCH_EDGE_SHARPEN_2026-10-01.md`, `archive/RESEARCH_FACTORY_2026-10-03.md`, `archive/LEVER3_MEMO_2026-10-03.md`, `archive/RESEARCH_LEVER2_FUTURES_2026-10-03.md`, `archive/TOURNAMENT_REPORT_2026-10-03.md`.

**Quality bar (both):** reason from economics first (who loses the money you earn, and why they keep losing it). Every number you cite carries a retrievable source (URL + locator) or is marked UNCONFIRMED; every arithmetic claim is shown or scripted. Adversarially attack your own best idea before you recommend it. Honest negatives are first-class: if the honest answer is "a durable 0.5+ net Sharpe is unlikely at this scale and venue", say so and say what would change it. Attest the model you ran as.

## Agent A — "the supply of edges" (WHAT to trade)

Question: **where does a durable, cost-surviving edge for a small automated operator on CFDs/prop (or on a venue change you justify) actually come from, given everything ACIS has already killed?**
1. Post-mortem: why did the tested families fail on 2024–25 (publication decay, crowding, regime, costs, too-narrow single-instrument bets)? What does the pattern say about where NOT to look?
2. A taxonomy of edge sources ranked for THIS operator: risk premia (carry, trend across many markets, volatility selling and its tail), forced/constrained flows (index rebalances, hedging, fixings, roll, CTA/vol-target deleveraging), behavioural, structural/microstructure, information (alternative data, news/NLP), and execution edges. For each: who pays, capacity vs our size (small is an ADVANTAGE in some), sensitivity to the retail CFD spread and swap-free rules, post-publication survival evidence.
3. **Diversification as the edge:** the arithmetic of combining many weak uncorrelated streams (e.g. 5 streams at 0.3 with ρ≈0 → ~0.67). Which combinations are realistically available, and what correlations in stress?
4. Venue/instrument changes that would unlock edges (futures micros, a lower-spread CFD venue, crypto perps, options) — with their costs, prop-firm/automation constraints, and the Kenyan-operator reality.
5. **Deliver** a ranked shortlist (≤ 8) of concrete candidates, each with: mechanism and who pays; expected net Sharpe after costs AND a publication haircut (show the math); data needed and whether ACIS has it; a draft pre-registration spec (rule, versions, window, kill threshold); and the single strongest reason it might fail.

Report: `archive/EDGE_RESEARCH_A_SUPPLY_2026-10-05.md`.

## Agent B — "the edge factory" (HOW to keep finding, validating, and rotating edges)

Question: **what system lets ACIS keep generating new working edges, detect when one dies, and reallocate — honestly, cheaply, and within ACIS's rules — as markets change?**
1. How professional systematic shops run the research-to-retirement lifecycle: idea generation, incubation/paper trading, sizing-in, decay monitoring, retirement. What do small/solo quants do that actually works?
2. Statistics of honest discovery under many trials: deflated Sharpe, PBO/CSCV, FDR, the ACIS look register; **forward power math**: how many months of forward data to tell Sharpe 0.5 or 1.0 from 0 at this trade frequency, and how a portfolio of many forward candidates changes that (multiplicity in stage D). Script it.
3. Adaptive allocation across live/forward strategies: Bayesian/shrinkage allocators, bandits (Thompson sampling) over strategies, regime-conditional weighting, online learning — what works out of sample vs what overfits; how a decayed edge is detected fast without killing healthy ones on noise (CUSUM/SPRT-style tripwires vs ACIS's per-family tripwires).
4. Automated hypothesis generation: genetic programming, ML feature mining, LLM idea generation — evidence on what survives, and how to make the generator itself honest (pre-registration, holdout budgeting, synthetic-null calibration). How should ACIS use LLM agents under §5.6 so the pipeline produces forward-certifiable candidates rather than mined history?
5. **Deliver** a concrete architecture that extends what ACIS already has (forward tournament, look register, milestone D, RSIM/event simulator): what to build, in what order, its cost in compute and owner minutes per month (the owner wants a low-cost autopilot), what to stop doing, and the power-math table. Mark every proposal that would need a spec change as such.

Report: `archive/EDGE_RESEARCH_B_FACTORY_2026-10-05.md`.
