# Lever 2 desk study: a futures venue (lead, 2026-10-03, fourth session)

Owner ruling: "Lever 2 desk study (Recommended)". Paper only: no build, no look, no account. Written by the lead
(claude-opus-5-5) from web sources; every claim carries its grade (a: primary/official, b: secondary, c: unverified).
Ledger: GAP-P12D-158.

## 1. Who would host ACIS (Kenya resident, a fully automated engine on a cloud server)

| Venue | Kenya | Full automation | Cloud server (VPS) | Verdict |
|---|---|---|---|---|
| Topstep | **Ineligible** (a: help.topstep.com eligibility FAQ, "Kenya" under "can't trade or receive payouts") | API allowed (TopstepX/ProjectX, $29/mo) (b) | **Prohibited**: "personal device" only (b) | Out, twice |
| Apex Trader Funding | Restricted (b: 84-country list, 2026-04) | **Prohibited** on funded accounts: semi-automated only (b) | — | Out (memory: dropped 2026-09-24) |
| Tradeify | Accepted (b: aggregator lists) | Own bots allowed with proof of sole ownership, no HFT, >50% of trades held >10 s (b) | Verification by live video of the code on "your own PC" (b): a server is doubtful | Doubtful |
| FundedNext Futures | Accepted (b) | **Allowed**, EAs and bots, both phases (a: helpfutures.fundednext.com 14298560) | Not stated (a) | Possible; a daily close-out by 15:10 CT is reported (c), which would forbid overnight holds |
| Own account, Interactive Brokers | Accepted (b: broker comparison sites; verify at signup) | API (TWS / IB Gateway) on any host | Allowed | **The clean route**: no prop rules, but own capital |

## 2. What a round trip costs (ex ante)

| Instrument | Round trip | Source |
|---|---|---|
| US500 CFD (C8 at Dukascopy's spread) | ~2.1 bp | IMOM dry check (GAP-P12D-158) |
| MES micro E-mini (IBKR) | ~1.0–1.3 bp: 1 tick = 0.38 bp spread + ~$0.7/side fees on ~$33k | b: IBKR $0.35/contract for micros, plus exchange fees |
| ES E-mini | ~0.5–0.6 bp | b |
| XAU CFD (C8) | ~3.7 bp | GOLD-EW ex ante (GAP-P12D-158) |
| MGC micro gold | ~1.0–1.4 bp: 1 tick = 0.38 bp + fees on ~$26k | b |
| 10Y micro yield futures | ~0.25 bp **of yield** ($1 tick + fees on a $10 DV01) | a: CME specs via its own article; margin ~$200 |

**Granularity on ~$6k at a 20% vol target (~$1,200/yr of P&L vol):** one MES (~$5.3k/yr vol) or MGC (~$3.9k/yr) is 3–4× the budget. One 10Y micro yield contract (~$900/yr at ~90 bp/yr) fits, and so do micro FX futures (M6E ~$950/yr).

## 3. Which ideas revive at futures costs

- **IMOM: no.** Gross ~+0.55; the cost slope is 1.27 Sharpe per 2.1 bp. At MES that gives about −0.24 net, at ES about +0.19, but ES is far too big for the account. The replication cited in the 2026-10-01 slate also reports the edge "compressed since 2025".
- **GOLD-EW: uncertain.** At MGC, Combo costs ~7%/yr instead of ~18.8%, against a ~22% pre-decay gross (2013–18) that was ≤ 0 by 2017–18 in the thesis's own data. The 2025 desk notes claim a revival. One contract is ~3× the vol budget, and a prop daily close-out would forbid its overnight long.
- **AUCTION: yes in principle.** It is the strongest mechanism on the slate (Lou, Yan & Zhang, RFS 2013: net Sharpe 0.9 in 1980–2008). Micro yield futures fit both the account and the cost: ~0.25 bp of yield against a 2–4 bp concession. **Its kill test needs no venue**: the Treasury par yields are on disk (`data/r1_real/treasury`), and TreasuryDirect publishes the auction calendar free (P&L-blind to fetch). Caveat: the micro yield contract settles to the latest on-the-run note, so it rolls at every auction, which needs a declared treatment.

## 4. Recommendation

1. **AUCTION's kill test on history first**, on the yields already on disk, before any venue spend. Of all the options, it is the closest to a real test.
2. **No venue build until a futures-only idea survives.** A futures venue means a new adapter (IBKR or Tradovate) and an owner ruling outside R1-D9's swap-free CFD scope.
3. **If a futures route is taken, prefer an own-money IBKR account** with micro yield or FX futures over a futures prop firm, because the prop firms run into Kenya, automation and VPS barriers.

## Sources
- Topstep eligibility: https://help.topstep.com/en/articles/8284116-eligibility-faq
- Topstep automation and VPS: https://blog.pickmytrade.io/topstepx-automation-2026/ , https://www.jptradingcapital.com/blog/en/does-topstep-allow-bot-trading
- Apex automation and countries: https://blog.traderspost.io/article/automate-apex-trader-funding-with-traderspost , https://apextraderfunding.com/help-center/getting-started/restricted-countries/
- Tradeify bots: https://blog.traderspost.io/article/automate-tradeify-with-traderspost
- FundedNext Futures bots: https://helpfutures.fundednext.com/en/articles/14298560-is-the-usage-of-automated-trading-systems-eas-and-bots-allowed-in-fundednext-futures
- Kenya-accepting futures firms: https://propfirmmatch.com/futures/prop-firm-lists/countries/kenya
- IBKR Kenya and micro commissions: https://brokerchooser.com/best-brokers/best-futures-brokers-in-kenya , https://interactivebrokers.co.uk/en/pricing/commissions-futures.php?re=amer
- CME micro yield futures: https://www.cmegroup.com/articles/2024/micro-treasury-futures-vs-yield-futures.html , https://www.ironbeam.com/knowledge-base/micro-10-year-yield-futures-10y-contract-specifications/
- Futures data (Databento, $125 free credits, ~$0.50/GB CME history): https://databento.com/pricing
