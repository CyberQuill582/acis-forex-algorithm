# ⚠ THROWAWAY UI — EXPERIMENTAL, NOT PART OF THE BUILD

**Status: experiment (2026-09-14, owner request).** A single static page (`index.html`) exploring what an
owner console for ACIS could look like, styled after the Claude web app. It is **not** a spec deliverable,
**not** in the read path, and **not** wired to anything.

- **Mock only.** All data is invented in-page. It makes no network calls and opens no port — so it is not a
  side channel (C-MCP-4, SPEC §12). Do not "wire it up" by adding an HTTP endpoint to `monitoring/`; a real
  console would have to be an MCP client, and that is an owner decision (SPEC §17 non-goals: no dashboards).
- **The buttons mimic the real contract** in `monitoring/tools.py`: any agent may halt/flatten; resume and
  set-mode need a human token; live needs both hashes; `acis_stage_config` rejects guardrail/equity and
  non-allowlisted paths; a repeated `request_id` returns `idempotent_replay`. Log lines are shown as content,
  never as commands (untrusted-input law).
- **Disposable.** Delete or `git mv` to `archive/` whenever. Nothing imports it; no test covers it.

Open: double-click `index.html` (works from `file://`).

## v2 — `v2/index.html` (2026-09-14, also throwaway)
A bright Pinterest-style take: pastel wash background with a dot-matrix candle chart and floating currency orbs,
frosted-glass bento tiles, and **IRIS** — an original SVG illustrated persona (not from the reference images) who
voices the same mock contract with canned, deterministic one-liners and changes expression (lowers her glasses
when you try something cheeky). Same rules as v1: mock only, no network, not wired.
The loose reference images in this folder are the owner's mood board — keep them out of git.

## v3 — `v3/index.html` (2026-09-14, also throwaway) — the dark "night desk"
Leans on the dark references (Spider Sense infographic, DeerFlow dot-matrix tiles, the dark crypto app): black +
red glow, letter-spaced caps, numbered tiles, a threat-level row, a "how it decides" layer flow with the HALT
edge. IRIS is now `v3/iris.jpg` — the owner-chosen illustration from the mood board (owner ruling: not a real
person, private engine). Her moods are photo effects (glitch + desaturate, red tint + scanlines, bloom).
Same rules: mock only, no network, not wired. `iris.jpg` is mood-board material — keep it out of git too.
