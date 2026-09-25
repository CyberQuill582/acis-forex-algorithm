# SPEND — ACIS cloud review (estimates only; the owner's usage panel is the truth)

**Model and effort.**
- The lead session's system prompt names the model `claude-opus-5-5` (Opus 5.5).
- The session cannot observe its own reasoning effort. The launcher configured xhigh, and this record takes
  that as given, unverified.
- Every lane is launched with `model: "opus"`. There are no Sonnet, Haiku or Explore agents.

| Time (UTC) | Event | Agents | Note |
|---|---|---|---|
| 17:33 | Lead P0 bootstrap + baseline | 1 (lead) | 808 passed / 6 skipped, ledger green, governance `--session` RED (comment-shape) |
| 17:40–17:58 | Lead P1 reconnaissance + brief | 1 | ~11 WebSearch; WebFetch egress blocked for most primaries |
| 17:38 | P2 launch: C1 (3h), C2 (2h), C3 (3h), C4 (2h), C5 (2h) | 5 opus lanes | general-purpose type, model opus |
| (run 1 total, est.) | Run 1 stopped by owner (WebFetch blocked) | 1 lead + 5 lanes | ~7 min lead; 5 lanes stopped at ~3 min each. Rough estimate $3–6. |
| 17:58–18:03 | **Run 2** lead: tripwire OK (arxiv, qoppac fetched), P0 re-bootstrap, baseline | 1 | 808 passed / 6 skipped; ledger 187/0; governance --session RED (unchanged) |
| 18:04 | Run 2 P2 launch: C1 (3h), C2 (2h), C3 (3h), C4 (2h), C5 (2h) | 5 opus lanes | general-purpose type, model opus; fresh time boxes |
| 2026-09-24 19:52 | Run 2 cut off by the usage limit before synthesis; container reclaimed | — | C3's `h7_on` and `p7_off_scr*` runs were lost with `/tmp` |
| 2026-09-25 02:35 | **Finishing session** (lead only): network tripwire OK; review tree rebuilt at BASE; handoff re-unpacked (it moved to `6a58e89`) | 1 (lead) | Opus 5.5 by system prompt; effort not observable (xhigh configured) |
| 02:36–~03:00 | Synthetic engine re-runs `h7_on` + `h7_off` (seed 7, 5 folds), 2 processes | 0 agents | The one bounded horizon re-run, plus its reproduction arm |
| 02:40–~03:05 | One `opus` general-purpose helper digests the local finals for §4.2 (a work agent, not an audit) | 1 | 25-minute box |
| (finishing total, est.) | Lead reading, P3, synthesis, close | 1 lead + 1 helper | **Rough estimate $12–20**, unobservable from inside the session; the owner's usage panel is the truth |
