# R1 dual-audit evidence (copied from the session scratchpad, 2026-09-25)

These are the seeded reproduction scripts and their outputs behind
`archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md` and
`archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md`, triaged in `R1_AUDIT_TRIAGE_2026-09-25.md`.
They were copied here so they outlive the session's temp folder.

- **Tree paths.** The scripts expect the tree they audited (`271d8e0`) as their first argument, or as
  hard-coded scratch paths. Export that tree with `git archive 271d8e0` to re-run them.
- **Left out on purpose:**
  - the third-party paper and documentation extracts (MOP 2012, FDA 2022, Bailey et al., White 2000,
    Waudby-Smith & Ramdas, the pysystemtrade docs and code). The reports quote the passages they use.
  - the spec diffs, which `git show 271d8e0` regenerates.
