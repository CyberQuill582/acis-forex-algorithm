# Owner hypotheses: the one route history can certify (GAP-P12D-158, owner ruling "A + B + D")

Under §5.6 an idea an LLM proposed, selected or refined can only be KILLED by history; it earns credit only on
data after its proposal date. An idea of YOURS carries no such boundary (`look_claims.Origin("human")`), so the
whole 2012–2023 record can certify it, through stage A at α 0.03 for the first family. There are two human routes:

| Route | Origin | What history can certify it |
|---|---|---|
| Your own rule, from your own trading, reasoning or a mentor | `human` | all of it |
| A paper or book YOU chose, not one an LLM pointed you to | `literature` (no model fields) | data after its publication date |

## How to keep it human

1. **Write it here first**, one file per idea: `hypotheses/<short-name>.md`. Do not ask Claude (or any LLM) to
   brainstorm, improve or pick between ideas: that makes it LLM-origin. Asking Claude to explain a concept is fine.
2. **Commit it yourself** (`git add hypotheses/<name>.md && git commit -m "hypothesis <name>"`). The commit date
   is the provenance record, and it comes before anyone looks at data for it.
3. **Be complete.** When Claude implements it, every ambiguity goes back to you as a question. Claude never
   chooses a parameter, window or instrument for you, since that would be refining it.
4. **One version per idea, graded once.** Decide what you would accept as failure before it is graded.

## The file, five headings

```
# <name>
1. Rule: instrument(s); when it is long / short / flat; how size is set; when it exits.
2. Why it should keep working: who is forced to trade against it, or what risk it is paid for.
3. Origin: your own idea, or the book or paper you chose (title, author, year), and the date you wrote this.
4. Failure: the result that would make you drop it.
5. Clock: it must decide once a day at the 17:00 New York close (RSIM can certify that); an intraday-window
   rule can only be killed on history until an event verdict exists (master v2.34).
```

Available data: hourly candles 2012–2025 for 13 FX pairs, XAU, XAG, US500, US30, UK100, JP225, EU50, AUS200;
ticks for 7 FX pairs and gold; the Treasury par curve; the S&P 500 close. The instruments GER40 and US100 are
held out for stage C only.
