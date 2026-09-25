"""R1-B receipt: a mechanical, pre-registrable held-out instrument draw (no data involved).

Rule: within each asset class, sort the candidates by SHA-256(SALT + "|" + symbol) and hold out the first
k. Every instrument whose real data ACIS already holds on disk (the 8 declared at BASE:
EUR/USD, USD/JPY, USD/CHF, XAU/USD, GBP/USD, AUD/USD, USD/CAD, EUR/GBP) is FORCED into the explored
(primary) set before the draw: they have been read by runs, validation checks (GAP-P12D-14) or auditors
(GAP-P12D-71 measured TSMOM votes on the declared FX pairs), so none of them is uncontaminated. The SALT is pinned by the commit that first publishes this file; re-salting after any look
at real data is forbidden, and any re-salt before that must be recorded with its reason.
"""
import hashlib

SALT = "ACIS-R1-holdout-2026-09-25"
UNIVERSE = {
    "FX": ["EUR/USD", "USD/JPY", "GBP/USD", "AUD/USD", "USD/CAD", "USD/CHF", "NZD/USD", "EUR/GBP",
           "EUR/JPY", "GBP/JPY", "AUD/JPY", "EUR/CHF", "EUR/AUD", "AUD/NZD", "CAD/JPY", "CHF/JPY"],
    "METAL": ["XAU/USD", "XAG/USD", "XCU/USD"],
    "INDEX": ["US500", "US100", "US30", "GER40", "UK100", "JP225", "EU50", "AUS200"],
    "ENERGY": ["USOIL", "UKOIL", "NATGAS"],
}
K = {"FX": 3, "METAL": 1, "INDEX": 2, "ENERGY": 1}
FORCED_PRIMARY = {"EUR/USD", "USD/JPY", "USD/CHF", "XAU/USD", "GBP/USD", "AUD/USD", "USD/CAD", "EUR/GBP"}

def h(s):
    return hashlib.sha256(f"{SALT}|{s}".encode()).hexdigest()

held, prim = {}, {}
for cls, syms in UNIVERSE.items():
    eligible = sorted((s for s in syms if s not in FORCED_PRIMARY), key=h)
    held[cls] = eligible[:K[cls]]
    prim[cls] = [s for s in syms if s not in held[cls]]
for cls in UNIVERSE:
    print(f"{cls:<7} held-out: {', '.join(held[cls]):<32} explored: {', '.join(prim[cls])}")
print(f"\ntotal {sum(map(len, UNIVERSE.values()))}: explored {sum(map(len, prim.values()))}, "
      f"held-out {sum(map(len, held.values()))}")
