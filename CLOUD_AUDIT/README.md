# CLOUD_AUDIT/ — what this folder is

This folder holds a **reports-only** review of this project, run by cloud Opus 5.5 sessions in September 2026. Its
brief is `FLEET_PLAN.md` (shared by six projects) plus `MISSION.md` (this project's own).

- **`reports/`** holds the cloud's output: `BRIEF.md`, one report per lane, `SYNTHESIS.md`, `SPEND.md`, and
  `evidence/`.
- **`_context/`** holds what the laptop handed to the cloud:
  - a snapshot of the family constitution;
  - a copy of the local uncommitted work at hand-off time.

  Everything in `_context/` is a **snapshot**. It is not a source of truth, and it can be deleted once the reports
  have been triaged.

## For the local session that imports these reports
- **They are a finder's evidence, never a ruling** (constitution A5/A6). Triage every item into this project's own
  ledger:
  - fixed with a regression test;
  - mitigated;
  - accepted-risk, with its justification;
  - refuted.

  **You mint the ledger IDs.** The cloud deliberately did not.
- **Each report names the commit it reviewed.** The code may have moved on since; check before acting.
- **Evidence scripts are receipts,** not code to adopt. Nothing in `reports/evidence/` is imported by the project,
  and nothing there is named like a test.

## Import (on the laptop)
Import the reports **by path, not by merge**. The cloud branch was cut from GitHub's default branch, which may not
be the branch you work on.

```bash
git fetch origin
git branch -r | grep -E 'claude/|cloud'                # find the cloud's branch; its final message names it
git checkout origin/<cloud-branch> -- CLOUD_AUDIT/     # files only; your branch and history are untouched
git add CLOUD_AUDIT && git commit -m "Import the cloud review reports (<date>)"
```

The laptop's `cloud-handoff/RECONCILE.md` has the full procedure, including the non-git creative-pipeline folder.
