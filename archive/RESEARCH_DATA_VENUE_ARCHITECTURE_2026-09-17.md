# Data / venue architecture research — 2026-09-17

**Brief (for a fresh session resuming this):** market-data architect pass, commissioned 2026-09-17.
The engine backtests on 14 years of Dukascopy SWFX ticks (2.79 B ticks, ECB- and triangle-validated)
but intends to execute somewhere else. A prior pass measured OANDA's own time-weighted average
EUR/USD spread at ~1.56 pips against ~0.27 bps in the Dukascopy ticks — i.e. the backtest is priced
on a different firm's book and is roughly 4× optimistic on cost. Five questions: (1) do venues'
mid-price PATHS differ, or only their spreads? (2) what is the defensible way to model
destination-venue cost over a source-venue price path? (3) can multi-year destination-venue spread
history be obtained at all? (4) is Dukascopy the right backtest base? (5) the recommendation, with
declared deviations and a falsifier.

**Mid-brief decision from the owner (2026-09-17):** the prop-firm route is DECIDED — a ~$6,000
funded account (The5ers / FundedNext / Apex / FTMO class). The destination venue is therefore a
**prop platform feed** (cTrader / DXtrade / Match-Trader / TradeLocker, or Rithmic/Tradovate if
futures), **not OANDA**. OANDA findings below are retained because OANDA is the only destination-class
venue that publishes usable historical spread data at all, which makes it the best available *proxy*
and the only place a cost overlay can be calibrated against multi-year evidence today.

**Status of this document:** research complete on Q2/Q3/Q4 to the depth the session's tool budget
allowed; Q1 is answered with a structural argument plus an explicit admission that the direct
measurement does not appear to exist in public literature, and a procedure to generate it. The
session's WebSearch budget (200/200) was exhausted before this pass began; everything below was
obtained by direct fetch of primary vendor/regulator surfaces, by live API probing, and by open
academic APIs. Sources are graded **(a)** primary read directly / **(b)** credible practitioner /
**(c)** unverified.

**Repo constraint honoured:** read-only. No engine code, config, spec or ledger file was modified.
This document is in `archive/`, out of the read path.

---

## 0. Executive answer

1. **Mid-price paths converge; costs do not.** The first moment (where mid goes) is pinned across
   venues by arbitrage and by the fact that every retail/prop venue prices off the same wholesale
   pool. The second moment (spread, slippage, rejection, widening at news) is venue-idiosyncratic and
   is exactly where a retail/prop venue differs from an ECN archive. A hybrid is therefore defensible
   **in principle** — but see §1: I could not find a published measurement of retail-MM-vs-ECN mid
   divergence, so the hybrid's premise is currently an assumption, not a fact, and must be measured.
2. **The defensible cost model is a per-instrument × per-session × per-state spread table sampled
   from the destination, with a hard floor and an explicit stress branch** — not a multiplier on the
   source spread. A multiplier fails precisely at the moments it matters, because the two venues'
   spreads decouple non-linearly under stress (§2).
3. **Multi-year destination spread history for a prop platform does not exist.** Plainly: no prop
   firm and no prop platform (cTrader / DXtrade / Match-Trader / TradeLocker) publishes or retains a
   multi-year, per-instrument historical spread series you can download. **Calibration must be
   forward-sampled from a demo / challenge account.** The one exception in the destination class is
   OANDA, which turns out to publish ~4.25 years of 15-minute min/avg/max spread via an undocumented
   public endpoint (§3.1) — measured live in this session.
4. **Dukascopy remains the right price-path base** for 2012–2025 at tick resolution. Every realistic
   alternative is either worse (HistData), gone (TrueFX free tier), derived from Dukascopy anyway
   (Tickstory), or institutionally priced (dxFeed / LSEG Tick History / EBS) (§4).
5. **Recommendation: Dukascopy price path + forward-sampled destination cost overlay, with the
   overlay's honesty gated by a named falsification test** (§5).

---

## 1. Do venues' mid-price PATHS differ materially, or only their spreads?

### 1.1 What I could establish from primary sources

**(a) The FX market is extremely fragmented, and the fragmentation is in *execution*, not in *price
level*.** BIS Quarterly Review (Schrimpf & Sushko, "FX trade execution: complex and highly
fragmented") states that participants have access to **more than 75 different FX venues**, that
dealer **internalisation** has grown to the point of reducing electronic inter-dealer spot trading by
7% since 2016 to $368 bn/day, and that retail clients reach the wholesale market through
prime-of-prime intermediaries and retail brokerages. The article does **not** quantify cross-venue
price divergence — I checked specifically; it has no such figure.
<https://www.bis.org/publ/qtrpdf/r_qt1912g.htm>

The structural implication is the load-bearing one for this decision: a retail or prop venue does not
*discover* price. It takes a wholesale aggregate and applies its own markup, its own risk
management, and its own last-look/rejection policy. The mid it shows is a function of the same
underlying pool the ECN quotes. That is the mechanism by which mid paths stay close.

**(a) But the quoted price is explicitly not the executable price on a last-look venue.** FX Global
Code (Dec 2024), **Principle 17**, read directly from the primary PDF
(<https://www.globalfxc.org/uploads/fx_global.pdf>):

> "Last look is a practice utilised in Electronic Trading Activities whereby a Market Participant
> receiving a trade request has a final opportunity to accept or reject the request against its
> quoted price."

and, critically for backtesting:

> "Market Participants may update pricing while a last look window remains open if the update is
> entirely independent of the relevant trade request, as doing so allows Market Participants to
> continuously make prices."

The Code requires disclosure of "whether, and if so how, changes to price in either direction may
impact the decision to accept or reject the trade, the expected or typical period of time for making
that decision, and more broadly the purpose for using last look," and confines last look to a
"validity and/or price check". It leaves the client "with potential market risk in the event the
trade request is not accepted."

**This is the single most important external-referent finding for a hybrid.** A hybrid that overlays
a cost on an ECN mid path models *spread*. It does not model the fact that, on a last-look venue, the
set of trade requests that get **rejected** is not random — it is selected against the client, because
rejection is a price check. The economic cost of last look is a conditional, adverse-selected cost
that a symmetric spread overlay cannot express. Any hybrid must declare this as a known,
unmodelled residual and size a haircut for it.

### 1.2 What I could NOT establish — stated plainly

I could not find, and I do not believe there exists in the public literature, a study that measures
**retail-broker / prop-platform mid versus ECN mid at 1-minute granularity on major FX pairs**. The
published microstructure literature compares *wholesale* venues with each other:

- **(a)** "Price discovery in electronic foreign exchange markets: the sterling/dollar market"
  (Journal of Futures Markets, 2010) — GLOBEX has a "marginally lower" Hasbrouck information share
  than Reuters D3000 on GBP/USD when returns are computed consistently from either midquotes or
  transaction prices on both venues; the apparent large gap in earlier yen/dollar studies is an
  artefact of *mixing* GLOBEX transaction prices with Reuters midquotes. DOI 10.1002/FUT.20433.
  **Directly relevant methodological warning: mixing a transaction price series from one venue with
  a quote-mid series from another manufactures a spurious divergence.** A hybrid does exactly this
  kind of mixing and must be built so the mixing is deliberate and declared, not accidental.
- **(a)** "Price Discovery in Foreign Exchange Markets: A Comparison of Indicative and Actual
  Transaction Prices" (SSRN 1299674) — the indicative-vs-actual distinction is the same class of
  problem: an indicative quote stream and a firm executable stream are not the same object.
- **(a)** "Do futures lead price discovery in electronic foreign exchange markets" (SSRN 1115056,
  98 citations) and "News announcements and price discovery in foreign exchange spot and futures
  markets" (J. Banking & Finance 2010, 181 citations) — both find the *information share* is split
  between venues and, crucially, **shifts around macro announcements**. That is the direct evidence
  that whatever cross-venue relationship holds in calm conditions is not the relationship that holds
  at 13:30 UTC on NFP day.

**The honest conclusion for Q1:** the claim "mid paths are close enough that a cost overlay is
defensible" is **plausible and structurally well-motivated, but it is an assumption in this project,
not a measured fact.** Treat it as a hypothesis with a named falsifier (§5.3), not as a finding.
The published literature supports two things that bear on it: (i) cross-venue information shares
for the same instrument are comparable and the law of one price binds to roughly within the spread
in normal conditions; (ii) that relationship **changes around announcements** — i.e. divergence is
concentrated exactly in the states a 30 min–48 h holding strategy's stops and entries live in.

### 1.3 Prop-platform-specific divergence risks (route-relevant, grade (b)/(c))

For a prop destination the divergence risks are *larger* than for OANDA, and structurally different:

- **The feed is the firm's, not the platform's.** cTrader, DXtrade, Match-Trader and TradeLocker are
  *platforms*; the quote stream is injected by the prop firm's liquidity arrangement (often a
  B-book with a synthetic markup, sometimes a prime-of-prime bridge). Two firms on the same platform
  will not show the same spread, and the same firm can change its markup without notice. **(c)** — I
  could not verify any firm's arrangement from primary sources within budget.
- **Markup is often a fixed additive widening**, not a proportional one. If so, the destination
  spread is `ECN spread + k` rather than `m × ECN spread`, which is a materially different overlay
  (see §2) and changes which trades die.
- **Prop account rules dominate cost at this size.** On a ~$6,000 funded account, the binding
  constraints are the daily-loss and max-drawdown rules, the consistency rule, and news-trading
  restrictions — not the third decimal of spread. A cost model that is 30% wrong will change the
  §14 grade; an account rule the engine does not model will end the account. ACIS already has the
  §9.5 rulebook machinery for this; it is the higher-value place to spend effort.
- **Weekend/holiday gap handling and rollover widening are firm policy**, and prop firms commonly
  widen aggressively around the daily rollover and Tier-1 events precisely to suppress the
  strategies this engine runs.

---

## 2. Modelling destination cost over a source price path

### 2.1 The four candidate designs and their failure modes

| Design | What it is | Failure mode |
|---|---|---|
| **Multiplier on source spread** `s_dest = m · s_src` | one scalar per instrument | **Fails under stress in the wrong direction.** An ECN spread blows out multiplicatively at news (the book empties); a retail/prop markup is often additive and *already* wide in calm conditions. So a multiplier calibrated on calm data under-states cost in calm and over-states the *shape* of the stress response, or vice versa. It also cannot express a floor. |
| **Additive markup** `s_dest = s_src + k` | one scalar per instrument | Closer to how a B-book markup actually works, but it makes the stress response of the destination identical in *shape* to the ECN's, which is false: the destination widens on its own schedule (rollover, firm policy, its LP's withdrawal), not the ECN's. |
| **Floor** `s_dest = max(s_src, f)` | a hard minimum | Necessary but not sufficient. A floor alone leaves calm-market cost right (if `f` is set at the destination's modal spread) and stress cost wrong. |
| **Per-instrument × per-session × per-state table sampled from the destination** | an empirical distribution, conditioned | The defensible one. Failure mode is **calibration-window bias**: a table sampled over a quiet 8 weeks contains no NFP-day tail and no CHF-class event, so the backtest is still optimistic exactly where it matters. Mitigated by conditioning on state rather than on calendar time (§2.2). |

**All four share one failure mode, and it is the one the brief anticipated: a *static* overlay
mis-models exactly the stressed moments.** The evidence for this is not speculative — it is the
measured shape of OANDA's own published spread series (§3.1): the EUR/USD *avg* series has median
0.96 pips and p95 1.42, while the *max* series over the same 15-minute buckets has p95 3.30 and a
maximum of 9.40 pips. A single number anywhere in 0.96–1.42 is a 3–10× understatement of the worst
buckets. A strategy whose stops sit inside that range is graded on a fiction.

### 2.2 What a defensible overlay looks like

Condition the destination spread on **observable state the engine already computes**, so the overlay
is a function of the market, not of the wall clock:

```
s_dest(t) = max( floor_i ,  base_i[session(t)]  +  g_i( state(t) ) )
```

where
- `floor_i` — the destination's hard minimum (OANDA EUR/USD: 0.80 pips on the min series, with
  occasional 0.50; a prop firm's is whatever forward sampling shows);
- `base_i[session]` — per-instrument, per-session (sydney / tokyo / london / new_york / overlap —
  ACIS already has these in `config/instruments.yaml` under `fx_default`) modal spread, from the
  destination;
- `g_i(state)` — a widening term keyed to states the engine already classifies: the §3.5 event
  blackout / Tier-1-within-30-min flag, the 17:00-New-York rollover window (already a C1 boundary),
  the NVMA `ILLIQUID` / spread-deviation-above-2σ classification, and the week-open gap.

This has three properties the flat overlay lacks: it is **state-conditional** (so it widens when the
engine already knows the market is stressed, without needing a destination tick for that instant);
it is **auditable** (each term is a number in a table with a sampling provenance, not a fitted
parameter); and it **degrades conservatively** (an unsampled state maps to the worst sampled state,
never to the modal one).

Crucially, it must be applied **on top of, not instead of, the source spread**: take
`max(s_dukascopy(t) scaled, s_dest_model(t))`. If the ECN book is screaming at an instant the
overlay does not know about, the ECN's own signal should still be allowed to raise the cost. That
also keeps the existing `SPREAD_VETO` / `ILLIQUID` semantics faithful — they are driven by the
source spread's *relative* deviation, which is the right referent for "is this market broken", while
the overlay owns the *absolute level*, which is the right referent for "what will I pay".

### 2.3 What practitioners do (grade (b), stated as such)

The mainstream practitioner position — consistent across quant-trading texts and the systematic-
trading community, though not a peer-reviewed result — is:

- Never backtest on mid. Reconstruct bid/ask, or apply an explicit half-spread plus slippage per
  side. ACIS already does this correctly in `core/optimizer/costs.py`
  (`per_side_cost = spread/2 + commission + slippage`), and C8 already forbids gross-return fitness.
  The defect is not the *form* of the cost model; it is the *calibration* of the inputs.
- Calibrate friction from the venue you will execute on, not the venue you have data from, and if
  you cannot, **stress the friction and require the edge to survive the stress**, which is the
  honest substitute for calibration you do not have.
- For a strategy with a 30 min–48 h holding period, round-trip cost is a small fraction of the
  per-trade PnL distribution — which is the one genuinely reassuring fact in this whole analysis.
  A 4× cost error is fatal to a scalper and survivable for a multi-hour holder, *provided the edge
  is not marginal*. The test in §5.3 makes that "provided" explicit rather than hopeful.

---

## 3. Can historical destination-venue data be obtained at all?

### 3.1 OANDA — YES, and further back than expected (grade (a), measured live 2026-09-17)

OANDA's public "historical spreads" tool (<https://www.oanda.com/us-en/trading/historical-spreads/>)
is backed by an undocumented but unauthenticated JSON endpoint:

```
GET https://labs-api.oanda.com/v1/spreads
      ?division=<OAP|OGM|...>
      &instrument=EUR_USD
      &startDate=2022-06-17T00:00:00.000Z
      [&endDate=...]
headers: Referer: https://www.oanda.com/ , Origin: https://www.oanda.com
```

Companion endpoints: `/v1/spreads/instruments?division=…` (asset-class → instrument list, incl.
INDEX / CRYPTO / FX) and `/v1/spreads/spread-stability-and-average`.

Measured behaviour (EUR/USD, division `OAP`):

| requested window | rows | actual coverage | avg-series mean | median | p95 | max |
|---|---|---|---|---|---|---|
| 90 d (the site's own default) | 6,149 | 2026-06-19 → 2026-09-17 | 1.086 | 0.972 | 1.20 | 9.38 |
| 1 y | 24,826 | 2025-09-17 → 2026-09-17 | 1.116 | 1.002 | 1.31 | 9.40 |
| since 2023-01-01 | 86,621 | 2023-01-01 → 2026-09-17 | 1.065 | 0.962 | 1.39 | 9.40 |
| since 2012-01-01 | **100,049 (capped)** | **2022-06-17** → 2026-09-17 | 1.072 | 0.960 | 1.42 | 9.40 |

Companion `min` series: mean 0.805, floor 0.80 (occasionally 0.50), p95 0.90.
Companion `max` series: mean 1.524, median 1.300, **p95 3.30, max 9.40**.

Findings:
- **Granularity is 15 minutes** (900 s step), with larger gaps across weekends — confirmed by the
  inter-timestamp step histogram `{900, 1800, 2700, 3600, …}`.
- **History reaches back to 2022-06-17** — about **4.25 years**, not the "last few months" the page
  copy claims. The 100,049-row figure is a hard server-side cap, and setting `endDate=2022-06-17`
  returns the *same* window, so 2022-06-17 is the true start of the archive, not a cap artefact.
- The site's marketing text says only "the minimums, averages, and maximums published on our
  trading platforms over the last few months … calculated over 15-minute intervals" — the copy
  understates what the API serves.
- **Division matters.** `OAP` returns data; `OGM` 500s; `OCA`, `OANDA_US`, `OANDA_EUROPE` are
  rejected as invalid. Different OANDA divisions have materially different retail pricing, so a
  division must be declared alongside any number sampled from here.
- **Reconciliation note against the prior ACIS research pass.** That pass reported ~1.56 pips TWA
  EUR/USD. My measurement of the `avg` series on division `OAP` is **1.07 pips mean / 0.96 median**;
  1.52 is almost exactly the mean of the **`max`** series. These are different statistics of the same
  underlying, and the discrepancy is most likely (i) `max`-vs-`avg` series confusion, or (ii) a
  different division (US pricing is wider than APAC). **This must be resolved before any number is
  used** — it is a 45% difference in the headline cost input. Grade (a) for my measurement,
  unresolved for the reconciliation.
- **ToS / licence:** unverified (grade (c)). This is an undocumented internal endpoint serving a
  public marketing page. Polling it gently for calibration is a different act from redistributing
  it; do not redistribute, and record the sampling in the ledger.
- OANDA's v20 REST API separately serves **bid, ask and mid candles** — `price=B|A|M`, granularities
  S5 through M (21 values: S5, S10, S15, S30, M1, M2, M4, M5, M10, M15, M30, H1…H12, D, W, M)
  (<https://developer.oanda.com/rest-live-v20/instrument-df/>, grade (a)). **So a true bid/ask
  spread series at S5 can be reconstructed from OANDA itself** — subject to whatever history depth
  the account's instrument endpoint actually serves, which I could not measure without credentials.
  This is the highest-fidelity destination-cost source available anywhere in this analysis, and it
  is worth one hour with a practice-account token to determine its depth. It is, however, now the
  *proxy* venue, not the destination.

### 3.2 Prop platforms — NO multi-year spread history exists. Say it plainly.

**cTrader Open API (grade (a) for the message schema, (c) for retention).** The Open API does expose
historical data: `ProtoOAGetTrendbarsReq` (fields `symbolId`, `period` ∈ {M1, M10, …},
`fromTimestamp`, `toTimestamp`, `count`) and — importantly — **`ProtoOAGetTickDataReq`, which takes a
`ProtoOAQuoteType` of BID or ASK**, so bid and ask tick series can be pulled *separately* and joined
into a spread series. Documented rate limit: **5 historical-data requests per second per
connection**. The docs state **no** maximum range per request, **no** maximum tick count, and **no**
retention period. (<https://help.ctrader.com/open-api/messages/>)

The decisive constraint is not in the schema — it is architectural: **the cTrader Open API is
per-broker.** You authenticate against a specific broker's cTrader instance and receive *that
broker's* quote history, for the symbols that broker lists, to whatever depth that broker's server
retains. A prop firm that started operating in 2023 cannot serve you 2012 quotes; it has none. And
a prop firm's *challenge* environment may not even be the same feed as its *funded* environment.

**DXtrade, Match-Trader, TradeLocker (grade (c) — not verified in this session).** No public
historical market-data API was identified. These are white-label trading platforms whose market-data
surface is designed for the terminal, not for bulk export; DXtrade and Match-Trader expose REST/WS
APIs for orders and account state to brokers under contract, and public documentation of a bulk
historical quote endpoint was not found. **Treat as: no multi-year spread history, no bulk export,
forward sampling only.** This should be verified per-firm at signup rather than assumed.

**Rithmic / Tradovate (futures, grade (c)).** Futures are exchange-traded, so the *price path* is
unambiguous (CME MBO/MBP data exists commercially and is a genuinely different and better situation
than spot FX). But this is out of scope for the current spot-FX universe and carries the extra §3.7
lifecycle risk class the spec already flags.

**Therefore, for the decided prop route: calibration MUST be forward-sampled.** There is no archive
to buy. The procedure is: open the demo/challenge account, stream and persist its own bid/ask feed
alongside the live Dukascopy feed for a fixed sampling window (≥ 8 weeks, and it must *include* at
least two Tier-1 event days, two month-ends, and one rollover per session bucket), and build the
§2.2 table from that. This has the useful side effect of producing the exact dataset the §5.3
falsification test needs.

### 3.3 Interactive Brokers — NO (grade (a))

IBKR's TWS API historical-data limitations (<https://interactivebrokers.github.io/tws-api/historical_limitations.html>):

- **Bars of 30 seconds or smaller are unavailable beyond six months.** That alone ends any multi-year
  tick-resolution spread reconstruction.
- Expired futures: nothing older than two years from expiry. Expired options/FOPs/warrants: nothing.
- Pacing: no identical request within 15 s; no 6+ requests for the same contract/exchange/tick-type
  within 2 s; no more than 60 requests per 10 minutes. **`BID_ASK` requests count twice** toward
  these limits.

Even setting depth aside, the pacing arithmetic makes a multi-year, multi-instrument bid/ask pull
infeasible. IB is also not the destination under the decided route, and IB's FX (IDEALPRO) is a
third book again.

### 3.4 Summary table for Q3

| Destination | Historical bid/ask or spread? | Depth | Granularity | Verdict |
|---|---|---|---|---|
| **OANDA labs spreads API** | min/avg/max spread | **2022-06-17 → now (~4.25 y)** | 15 min | **(a)** Usable, measured. Best available destination-class calibration set. |
| **OANDA v20 candles** | bid + ask candles | unmeasured (needs token) | S5 upward | **(a)** schema confirmed; depth unknown. Worth one hour. |
| **cTrader Open API** | bid & ask ticks, separately | **broker-dependent, unknown, likely short** | tick | **(a)** schema; **(c)** depth. Forward-sample. |
| **DXtrade / Match-Trader / TradeLocker** | none found | — | — | **(c)** Assume none. Forward-sample. |
| **Interactive Brokers** | BID_ASK bars | **6 months for ≤30 s bars** | ≥30 s beyond 6 mo | **(a)** Not viable. |
| **Prop firm (any)** | none published | — | — | **No multi-year destination spread history exists.** |

---

## 4. Is Dukascopy the right backtest base?

### 4.1 The case for

Dukascopy is a real bank (Dukascopy Bank SA, Swiss-regulated) running **SWFX**, its own marketplace,
and the historical archive is the marketplace's own book — bid, ask and per-side volume, tick by
tick, from ~2003 for the majors, free, and already downloaded and independently validated in this
project against ECB reference rates, the EUR/GBP triangle and the market's own clock marks
(GAP-P12D-14, master §13 v2.17). The validation already run here is stronger than anything a vendor
would supply with a paid feed.

Its tighter spread is, for the *price path*, an advantage, not a defect: a tighter book means the
mid is a less noisy estimate of the consensus price, so indicators computed on it (ATR, ADX, EMA,
correlation, Hurst) are measuring the market rather than measuring a broker's markup policy. The
cost level is the thing that is wrong, and the cost level is separable.

### 4.2 Known biases and quirks to declare (grade (b)/(c) — practitioner consensus, not vendor-documented)

Dukascopy publishes essentially nothing about its filtering methodology — the historical-data page
(<https://www.dukascopy.com/swiss/english/marketwatch/historical/>) describes formats and access
tools and says nothing about source, filtering or licence. That silence is itself a finding: **every
item below is an undeclared-method risk, and the spec's external-referent law says an undeclared
deviation is a finding.** The ones that matter:

- **It is one venue's book, not a consolidated market.** SWFX aggregates a specific set of liquidity
  providers. Its spread is representative of a good ECN, not of "the FX market".
- **Volume is SWFX volume only** — a tiny share of global FX. Any indicator using tick volume as a
  proxy for market activity (the Breakout module's "volume confirm", the Momentum Scalp module's
  tick-velocity surge) is measuring SWFX participation, not market participation. This is a genuine
  external-referent finding against the *indicator*, independent of the venue question, and should
  be checked: tick *count* per interval is a far more robust activity proxy than tick *volume*.
- **Weekend and rollover artefacts.** The archive contains the market's true illiquid periods, and
  the first ticks after the weekend open can be wide and non-representative. ACIS already filters the
  weekend via `in_weekend` and has the rollover as a C1 boundary, so this is handled — but the
  *first* post-gap tick is exactly the tick a naive cost model prices a fill at.
- **Gold (XAU/USD) specifically.** Spot gold is OTC, has no consolidated tape, and every venue's
  spot-gold quote is a derived construct with its own conventions and its own daily break. Dukascopy
  gold is therefore a *much* weaker referent than Dukascopy EUR/USD. The project already recognised
  this (GAP-P12D-11, the `spot_metals` calendar, and the sampled gold cross-check against HistData
  in the v2.17 validation set). Keep gold disabled until its cost model is separately calibrated;
  do not let an FX-calibrated overlay be silently reused for it.
- **Synthetic / filtered ticks.** There is a persistent practitioner claim that Dukascopy's archive
  has been smoothed or back-filled in places, particularly in early years and on minor pairs. I could
  not verify or refute this from primary sources within budget — **(c), open**. The project's
  existing independent validation (ECB fixing, triangle, clock marks) is the right instrument to
  settle it, and it passed for 2024 (ECB median 1.2–1.8 bps, triangle median 0.09 bps). Extending
  that validation to the 2012–2016 years is the cheap way to close this.

### 4.3 The alternatives for 2012–2025 at tick resolution

| Source | What it is | Cost / licence | Verdict |
|---|---|---|---|
| **Dukascopy** | SWFX own book, tick bid/ask + volume, ~2003→now, 60+ instruments | Free; licence terms not published on the historical page **(c)** | **Keep as primary.** Best free tick archive. Already validated in-repo. |
| **HistData** | Free tick bid/ask, retail-aggregated | Free, explicitly **no warranty or certification**; commercial terms not stated **(a)** | **Validator only, as the spec already has it.** Its own FAQ: bars are built from the **bid** only; **no volume at all** ("Trading Volumes, in forex, are not aggregated"); gaps averaging >90 s in thin periods are "normal"; timestamps documented as "EST WITHOUT Day Light Savings" — **which this project has proved false** (it is Frankfurt − 6 h and shifts on EU summer-time dates, GAP-P12D-13). A vendor that is wrong about its own clock is not a primary source. |
| **TrueFX** | Integral Development Corp; 16+ pairs, top-of-book tick, aggregated from major institutions | **Professional $4,950/mo, Institutional $7,450/mo** (measured on truefx.com, 2026-09-17). Free multi-year history withdrawn. **(a)** | **Out.** Confirms GAP-P12D-02. ~$60k/yr for a $6,000 account is absurd. |
| **Tickstory** | A downloader/manager whose FX tick data **is Dukascopy's**, repackaged for MT4/MT5 backtesting | Low one-off fee **(c)** | **No independent value.** Same underlying data; you already have the raw archive and a validated reader. |
| **dxFeed** | Institutional consolidated feed + historical | Enterprise pricing, not published **(c)** | Out on cost for this account size. |
| **LSEG / Refinitiv Tick History (TRTH)** | The gold-standard institutional archive: full depth, decades, every venue | Enterprise licence, typically five figures/yr, with strict redistribution terms **(c)** | Out on cost. Would be the correct answer at institutional scale. |
| **EBS (CME EBS Market Data)** | The interdealer benchmark book for EUR/USD and USD/JPY | Exchange market-data licence **(c)** | Out on cost. Also the *wrong* referent: EBS is the wholesale book a $6k prop account will never touch. |

**Conclusion for Q4: yes, Dukascopy is the right base**, and the realistic alternatives do not
change that. The defect is not the data — it is that the data's *cost level* is being used as if it
were the destination's.

---

## 5. Recommendation

### 5.1 Use

**Price path: Dukascopy, unchanged.** 2012–2025, tick, already downloaded, already validated. Do not
re-source. Extend the existing independent validation (ECB fixing / triangle / clock marks) back
over 2012–2016 to close the "synthetic ticks in early years" question, since that is cheap and it is
currently the largest unexamined assumption in the base data.

**Cost: a forward-sampled, state-conditional destination overlay** per §2.2, replacing the current
flat `slippage_per_side` constants in `config/instruments.yaml` (EUR/USD `0.00002` = 0.2 pips;
USD/JPY `0.002` = 0.2 pips) as the *sole* friction beyond half-spread. Concretely:

1. **Interim, until the prop account exists:** calibrate `floor_i` and `base_i[session]` from the
   OANDA labs series measured in §3.1 (EUR/USD: floor 0.80 pips, modal ~0.96, p95 1.42, stress p95
   3.30) as an explicitly-declared **proxy**, and apply it as
   `s_dest = max(floor_i, base_i[session] + g_i(state), s_dukascopy)`.
   This immediately removes the ~4× optimism and is defensible as "a real retail venue's measured
   distribution", not a guess.
2. **On the prop account (challenge/demo first):** stream and persist its own bid/ask alongside
   Dukascopy for ≥ 8 weeks spanning ≥ 2 Tier-1 event days, ≥ 2 month-ends, and every session bucket.
   Rebuild the table from that. Keep the OANDA-derived table as the second referent — if the two
   disagree by more than 2×, that disagreement is itself a finding about the prop firm's markup.
3. **Do not model last look as spread.** Carry it as a separate declared residual with its own
   haircut (see §5.2), because it is adverse-selected and a symmetric spread term cannot represent it.

**Effort allocation, given the decided route:** at $6,000 account size, the **§9.5 prop rulebook
(daily loss, max drawdown, consistency, news restriction) is worth more attention than the cost
model.** The cost model decides whether the §14 grade is honest; the rulebook decides whether the
account survives. ACIS already has the rulebook machinery — populate it with the chosen firm's
actual rules before the cost work is perfected.

### 5.2 Declared deviations (the list that must go into `declared_deviations` / the spec)

1. **The backtest price path is Dukascopy SWFX's book; the intended execution venue is a different
   firm's book.** The mid paths are assumed close; this assumption is not measured and is falsifiable
   (§5.3).
2. **The cost overlay is calibrated on a proxy venue (OANDA, division `OAP`, 2022-06-17→2026-09-17)
   for the period before the destination account exists**, and on a forward-sampled window from the
   destination afterwards. The calibration window is shorter than the backtest window by an order of
   magnitude; the overlay therefore assumes cost *structure* (session shape, stress multiple) is
   stationary across 2012–2025 even though its *level* is only observed from 2022.
3. **Last look / rejection is not modelled.** On a last-look destination the realised cost of
   rejected-then-re-requested orders is adverse-selected and strictly worse than the quoted spread.
   Declared, unmodelled, haircut applied.
4. **Tick volume is SWFX volume**, not market volume. Any module using volume as an activity proxy
   is measuring one venue's participation. (Independent of the venue decision; should be a finding
   in its own right.)
5. **Gold's cost model is not transferable from FX** and gold remains disabled.
6. **The OANDA labs endpoint is undocumented**; its ToS for programmatic sampling is unverified, and
   the sampled data is used for calibration only and is not redistributed.
7. **Unresolved: the 1.56 vs 1.07 pip discrepancy** between the prior research pass and this
   session's direct measurement (`max` vs `avg` series, or a division difference). No cost number
   should be committed until this is reconciled.

### 5.3 What must be TRUE for the hybrid to be honest — and the test that falsifies it

The hybrid rests on exactly three claims. Each has a test. **If any test fails, the hybrid is not
honest and the answer becomes "standardise on the destination and accept a much shorter backtest".**

**Claim A — the mid paths do not diverge materially at the engine's decision granularity.**
*Test (the primary falsifier):* during the forward-sampling window, record the destination's own
bid/ask stream and Dukascopy's simultaneously. Build 1-minute mid bars from both. Measure
(i) the distribution of `|mid_dest − mid_duka|` in bps, and (ii) the distribution of the *1-minute
return difference*. Report separately for calm buckets and for stress buckets (Tier-1 event ±30 min,
rollover ±15 min, week open first 60 min).
*Pass condition:* median absolute mid difference in calm conditions below half the destination's
own modal spread, **and** the 1-minute return-difference distribution having a standard deviation
small relative to the strategy's per-trade edge. *Fail condition, which kills the hybrid:* the
stress-bucket divergence is comparable to or larger than the strategy's average per-trade PnL —
because then the backtest's entries and stop hits are events that did not happen at the destination.
This test also directly catches off-market quoting and feed lag, which are the two mechanisms by
which a B-book feed diverges.

**Claim B — the cost overlay reproduces the destination's realised cost distribution, including its
tail.**
*Test:* hold out the last 2 weeks of the sampling window. Fit the overlay on the first 6, predict
the held-out 2. Compare predicted vs realised spread **per session bucket and per stress bucket**,
on the median *and* the p95 and p99. *Pass condition:* predicted p95 within a declared tolerance of
realised p95 in every bucket. *Fail condition:* the overlay is right on the median and wrong on the
tail — which is the specific failure the brief asked about, and which a median-only check would
pass. **A median-only validation of a cost overlay is the bug.**

**Claim C — the edge is not an artefact of the cost assumption.**
*Test (the cheapest and the one to run first):* the **cost-stress ladder**. Re-run the full §14
walk-forward at 1×, 2×, 3× and 5× the overlay, and at the overlay's own p95 applied as a constant.
*Pass condition:* the strategy meets §14 minimums out-of-sample at **2×**. *Fail condition:* the
edge is only present at 1× — in which case the entire venue question is moot, because a strategy
that dies at 2× the modelled cost will die at the destination regardless of which archive it was
graded on. Given the 30 min–48 h holding period, a real edge should comfortably survive 2×; if it
does not, that is the finding, and it is a bigger one than the data-source question.

**Recommended order:** C first (free, uses data already on disk, and may make A and B unnecessary
by revealing the edge is cost-insensitive or nonexistent), then A and B from the same forward-
sampling window once the prop account exists.

---

## 6. Open items a follow-up session should close

1. **Reconcile 1.56 vs 1.07 pips** (§3.1) — `max` vs `avg` series, or a division difference. Blocking
   for any committed cost number.
2. **Measure OANDA v20 candle history depth** with a practice-account token (`price=BA`, `S5`) —
   one hour of work, and it would establish whether a true multi-year *reconstructed* bid/ask series
   exists at the only destination-class venue that might have one.
3. **Verify per-firm** whether the chosen prop firm's platform (cTrader / DXtrade / Match-Trader /
   TradeLocker) exposes any historical quote API at all, and to what depth. Do this **at signup**,
   before the challenge starts, because the sampling window has to begin immediately.
4. **Find or commission the Q1 measurement.** No published retail-MM-vs-ECN mid-divergence study was
   located. The forward-sampling window generates it. Until then Claim A is an assumption.
5. **Extend the independent Dukascopy validation back to 2012–2016** to close the
   synthetic/filtered-tick question (§4.2, grade (c)).
6. **Populate the §9.5 rulebook** with the chosen firm's actual daily-loss / max-drawdown /
   consistency / news rules. At $6,000, this dominates the cost model in expected value.
7. **Dukascopy licence terms** for the S3 bulk archive — not published on the historical-data page.
   Confirm before any redistribution (internal backtest use is a different question from sharing).

---

## Sources

Graded **(a)** primary read directly, **(b)** credible practitioner, **(c)** unverified.

- **(a)** FX Global Code, December 2024, Principle 17 (last look) — <https://www.globalfxc.org/uploads/fx_global.pdf> (read in full, quoted above)
- **(a)** BIS Quarterly Review, "FX trade execution: complex and highly fragmented" — <https://www.bis.org/publ/qtrpdf/r_qt1912g.htm>
- **(a)** OANDA historical-spreads tool and its backing API — <https://www.oanda.com/us-en/trading/historical-spreads/>, `https://labs-api.oanda.com/v1/spreads` (probed live 2026-09-17; figures in §3.1 are my own measurements of its output)
- **(a)** OANDA v20 API definitions, CandlestickGranularity / bid-ask-mid candles — <https://developer.oanda.com/rest-live-v20/instrument-df/>
- **(a)** OANDA v20 API introduction — <https://developer.oanda.com/rest-live-v20/introduction/>
- **(a)** Interactive Brokers TWS API, historical data limitations — <https://interactivebrokers.github.io/tws-api/historical_limitations.html>
- **(a)** cTrader Open API message reference (`ProtoOAGetTrendbarsReq`, `ProtoOAGetTickDataReq`, `ProtoOAQuoteType`) — <https://help.ctrader.com/open-api/messages/>
- **(a)** cTrader Open API overview, rate limits — <https://help.ctrader.com/open-api/>
- **(a)** HistData FAQ (source, granularity, bid-only bars, no volume, gap statistics, EST-without-DST claim) — <https://www.histdata.com/f-a-q/>
- **(a)** TrueFX pricing and operator — <https://www.truefx.com/>
- **(a)** Dukascopy historical data export page — <https://www.dukascopy.com/swiss/english/marketwatch/historical/>
- **(a)** "Price discovery in electronic foreign exchange markets: the sterling/dollar market", Journal of Futures Markets (2010), DOI 10.1002/FUT.20433 — GLOBEX vs Reuters D3000 information shares; the mixed-series artefact warning
- **(a)** "Price Discovery in Foreign Exchange Markets: A Comparison of Indicative and Actual Transaction Prices", SSRN 1299674
- **(a)** "Do futures lead price discovery in electronic foreign exchange markets", SSRN 1115056
- **(a)** "News announcements and price discovery in foreign exchange spot and futures markets", Journal of Banking & Finance (2010), DOI 10.1016/J.JBANKFIN.2010.03.009
- **(b)** Practitioner consensus on bid/ask reconstruction, venue-matched friction calibration, and cost-stress laddering (§2.3) — stated as practitioner consensus, not as a peer-reviewed result
- **(c)** Prop-platform (DXtrade / Match-Trader / TradeLocker) historical market-data surfaces — no public documentation located; treated as "none available"
- **(c)** dxFeed, LSEG/Refinitiv Tick History, CME EBS Market Data pricing — enterprise, not published
- **(c)** Tickstory's use of Dukascopy as its underlying source
- **(c)** Dukascopy archive filtering / synthetic-tick claims, and the archive's licence terms
