"""The TREND family's provenance (master §5.6 v2.22; GAP-P12D-116/122): every record pins its
source and declares the departures the code actually makes."""

from __future__ import annotations

from core.signals import families, rules
from core.signals.ewm import CARVER_COMMIT
from core.signals.provenance import ProvenanceStore
from tests.optimizer_fixtures import CapturingLogger


def test_carvers_members_pin_the_commit_and_the_scalars_they_use() -> None:
    for sid in ("trend_d1_v1", "trend_breakout_v1"):
        assert CARVER_COMMIT in families.RECORDS[sid].citation
    assert "3.75/2.65/1.87" in families.RECORDS["trend_d1_v1"].citation
    assert tuple(rules.EWMAC_SCALARS.values()) == (3.75, 2.65, 1.87)


def test_every_departure_the_code_makes_is_declared() -> None:
    d1 = " ".join(families.RECORDS["trend_d1_v1"].declared_deviations)
    for must in ("EXCESS-return price", "execution clock", "TOWARD ZERO", "EQUAL weight", "FDM fixed at 1.09"):
        assert must in d1, must
    assert any("ceil(lookback/2)" in d for d in families.RECORDS["trend_breakout_v1"].declared_deviations)
    mop = " ".join(families.RECORDS["trend_mop12_v1"].declared_deviations)
    for must in ("carry differential", "last weekday", "span 121", "exactly zero is flat"):
        assert must in mop, must
    assert rules.D1_FDM == 1.09 and rules.MOP_COM_DAYS == 60


def test_registration_is_idempotent(tmp_path) -> None:
    store = ProvenanceStore(tmp_path / "prov.db", 90, CapturingLogger())
    assert families.register_family(store) == list(families.RECORDS)
    assert families.register_family(store) == []
