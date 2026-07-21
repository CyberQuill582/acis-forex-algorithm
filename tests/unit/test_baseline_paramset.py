"""Baseline-freeze enforcement (owner directive 2026-07-21).

The pristine, market-UNTRAINED ACIS baseline must stay an immutable, always-
cloneable reference: markets get re-fought by cloning THIS and letting a NEW
named ParamSet diverge through the QIEA/ParamLibrary + challenger lane
(SPEC §5.6/§5.7) — never by editing the baseline in place. The truest fingerprint
of "the untrained algorithm" is its gene SEARCH SPACE (`GENE_SPECS`) — the DNA it
evolves within. This test is the teeth: any silent drift of that DNA away from
`config/baseline_manifest.json` fails here, forcing a conscious RE-BASELINE
(update the manifest + cut a new git tag + record it in BASELINE.md).

This does NOT pin a trading ParamSet — the architecture deliberately ships none
(a regime is untradeable until a CALIBRATED set is promoted); inventing one would
be the fabricated artifact the lean-build law (§17/§18) forbids.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.optimizer.param_types import GENE_SPECS

_MANIFEST = Path(__file__).resolve().parents[2] / "config" / "baseline_manifest.json"


def _manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_exists_and_declares_the_tag() -> None:
    m = _manifest()
    assert m["baseline"] == "acis-untrained-v1"
    assert m["git_tag"] == "baseline-untrained-v1"
    assert "immutability_rule" in m and m["immutability_rule"]


def test_gene_space_matches_the_frozen_baseline() -> None:
    """The pristine DNA has not silently drifted. If this fails, you changed the
    search space — that is a conscious re-baseline, not a bug to paper over:
    update config/baseline_manifest.json AND cut a new git tag."""
    frozen = _manifest()["gene_space"]
    live = {name: [lo, hi, is_int] for name, (lo, hi, is_int) in GENE_SPECS.items()}
    assert live == frozen, (
        "GENE_SPECS drifted from the frozen baseline. Re-baseline consciously: "
        "regenerate config/baseline_manifest.json + cut a new tag (see BASELINE.md)."
    )


def test_every_frozen_gene_type_is_faithful() -> None:
    """The is_int flags in the manifest match the genome exactly (a float gene
    silently becoming int, or vice-versa, is a drift the range check alone could
    miss if lo/hi happened to coincide)."""
    frozen = _manifest()["gene_space"]
    for name, (_, _, is_int) in GENE_SPECS.items():
        assert frozen[name][2] is is_int
