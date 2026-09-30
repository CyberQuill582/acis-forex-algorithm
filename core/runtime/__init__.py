"""The three-loop runtime (master §10, `[DIR:core/runtime]`, v2.25): the composition root.

Mental model — the invariants every module here keeps:
  * It WIRES, it never decides what a layer owns. NVMA vetoes, AGON signals, the Governor
    sizes, the orchestrator executes, Risk halts. The runtime only carries objects between
    them, on their cadences, and turns a sized order into venue work (the position policy).
  * One position per instrument (GAP-0075). A same-side repeat is ignored, an opposite order
    reverses as close-then-open, and exits are engine-driven (target, max hold) except the
    stop, which rests at the venue (§279). This is the backtest book's policy, in production.
  * Paper mode never reaches a real venue: its orders go to the in-process paper venue.
    Practice orders go to the attached venue only when it is practice-eligible (master v2.23).
  * The upward edge is the only way back up: Risk halts through `PersistentHaltSink`, which
    forwards first and records second. Only the human resume lifts a halt or a freeze.
  * No layer imports this package (tests/unit/test_import_contract.py).
"""
