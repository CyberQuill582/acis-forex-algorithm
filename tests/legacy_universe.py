"""The legacy test universe: the shipped config narrowed to the two pairs the legacy engine's tests and
synthetic harnesses (falsification, leakage, oracle) were written for, with the target path off.

The shipped config (R1.6) enables the 13 explored FX pairs for the target-position path. The legacy
QIEA engine is not the demo's path on them (R6-3), and its synthetic markets carry first mids for a
few pairs only, so its harnesses keep their original scope here rather than refusing the shipped one."""

from __future__ import annotations

from config.schemas import AcisConfig

LEGACY_TEST_UNIVERSE = ("EUR_USD", "USD_JPY")


def legacy_view(cfg: AcisConfig) -> AcisConfig:
    """The config with only LEGACY_TEST_UNIVERSE enabled and no target path."""
    inst = {s: sp.model_copy(update={"enabled": s in LEGACY_TEST_UNIVERSE})
            for s, sp in cfg.instruments.instruments.items()}
    venue = cfg.system.venue
    if venue is not None:
        venue = venue.model_copy(update={"symbol_names": {s: n for s, n in venue.symbol_names.items()
                                                          if s in LEGACY_TEST_UNIVERSE}})
    return cfg.model_copy(update={
        "instruments": cfg.instruments.model_copy(update={"instruments": inst}),
        "system": cfg.system.model_copy(update={"targets": None, "venue": venue})})
