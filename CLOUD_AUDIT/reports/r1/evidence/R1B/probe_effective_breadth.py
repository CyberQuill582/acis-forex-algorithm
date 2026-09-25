"""R1-B receipt: effective breadth of the proposed universe from PUBLISHED correlation levels (no data).

Inputs quoted, not computed:
  - Babu, Levine, Ooi, Pedersen & Stamelos (2020), JOIM 18(1), Table 4 Panel A: average pairwise correlation
    of per-instrument 12-month TSMOM strategy returns = 0.07 within traditional assets (1985-2017), and
    Table 2: median single-asset gross SR 0.34, diversified-portfolio gross SR 1.17 (58 traditional assets).
  - Verdelhan (2018), JF 73(1): a carry and a dollar factor "account for 20% to 90%" of bilateral FX moves,
    so within-FX strategy correlation is plausibly well above the cross-asset 0.07 (value NOT published
    here: it is swept as a sensitivity).
Formula: N_eff = 1' 1 N^2 / (1' R 1) for equal weights; SR_p = s * sqrt(N_eff) for equal-SR sleeves.
Check: s = 0.34, N = 58, uniform rho = 0.07 gives SR_p = 1.16 vs the paper's 1.17 (formula reproduces it).
"""
import numpy as np

def neff(blocks, rho_w, rho_a):
    n = sum(blocks); R = np.full((n, n), rho_a); i = 0
    for b in blocks:
        R[i:i + b, i:i + b] = rho_w.get(b, rho_w["default"]) if isinstance(rho_w, dict) else rho_w; i += b
    np.fill_diagonal(R, 1.0)
    return n * n / R.sum()

s, N = 0.34, 58
print(f"check: uniform rho 0.07, N=58 -> SR_p = {s * np.sqrt(neff([N], 0.07, 0.07)):.2f} (paper 1.17)")
prim = [13, 2, 6, 2]            # FX, metals, indices, energies in the proposed 23-instrument explored set
full = [16, 2, 8, 3, 1]         # the full 30 (incl. held-out; copper as its own block)
print("\nN_eff of the 23 explored instruments (blocks FX13/metal2/index6/energy2), across-class rho 0.05:")
for rw in (0.07, 0.15, 0.25, 0.35, 0.5):
    print(f"  within-class rho {rw:.2f}: N_eff = {neff(prim, rw, 0.05):5.1f}; SR_p at s=0.34 -> "
          f"{0.34 * np.sqrt(neff(prim, rw, 0.05)):.2f}; at s=0.15 -> {0.15 * np.sqrt(neff(prim, rw, 0.05)):.2f}")
print("\nSame for the 8 declared instruments at BASE (FX7 + XAU):")
for rw in (0.07, 0.25, 0.5):
    print(f"  within-class rho {rw:.2f}: N_eff = {neff([7, 1], rw, 0.05):5.1f}")
print("\nFX-only 16 vs FX16 + 14 non-FX, within-class rho 0.35, across 0.05:")
print(f"  FX16 alone: N_eff = {neff([16], 0.35, 0.05):.1f}; 30 mixed: N_eff = {neff(full, 0.35, 0.05):.1f}")

# --- IDM / FDM under class-equal handcrafted weights (pre-registered ASSUMED correlations, no data) ---
def idm(blocks, rho_w, rho_a):
    n = sum(blocks); R = np.full((n, n), rho_a); w = []; i = 0
    for b in blocks:
        R[i:i + b, i:i + b] = rho_w; i += b; w += [1.0 / len(blocks) / b] * b
    np.fill_diagonal(R, 1.0); w = np.array(w)
    return 1.0 / np.sqrt(w @ R @ w)
print("\nIDM, class-equal weights over the 23 explored (FX13/metal2/index6/energy2), across rho 0.05:")
for rw in (0.15, 0.25, 0.35):
    print(f"  within rho {rw:.2f}: IDM = {idm(prim, rw, 0.05):.2f} (Carver caps IDM at 2.5)")
Rf = np.array([[1, .87, .58], [.87, 1, .87], [.58, .87, 1]])   # null position correlations, sim_rule_turnover_null.out
w3 = np.ones(3) / 3
print(f"FDM for EWMAC 16/64, 32/128, 64/256 equal-weighted (null correlations): {1 / np.sqrt(w3 @ Rf @ w3):.2f}")

# --- net portfolio SR ~= (s - c) * sqrt(N_eff): cost is a deterministic drag, it does not diversify ---
ne = neff(prim, 0.25, 0.05)
print(f"\nNet SR_p ~= (s - c) * sqrt(N_eff), N_eff = {ne:.1f} (within 0.25, across 0.05):")
print("  s (gross per-instrument SR) \\ c (cost SR/yr):  0.02 swap-free   0.10 low-markup   0.21 FTMO median")
for s_ in (0.15, 0.25, 0.34):
    print(f"  s = {s_:.2f}{'':>34}" + "".join(f"{(s_ - c) * np.sqrt(ne):>+17.2f}" for c in (0.02, 0.10, 0.21)))
