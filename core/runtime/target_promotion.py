"""Flatten-then-promote for the target path (ACIS-03 v2.2, D-c; GAP-P12D-108), moved out of
target_loop.py (the legibility budget).

Invariants:
  * The cached ACTIVE family-version is the one the path trades. While it differs from the
    configured one, or on a first activation over held positions (left by the legacy path), no target
    is made: the universe is flattened through the reduce-only close.
  * The configured version is promoted only once every universe instrument is flat AND idle; a
    flatten that fails (a halt, a closed market) waits for the next decision. Never forced.
"""

from __future__ import annotations


def promotion_settled(store, family: str, members, engine, pending: dict, logger) -> bool:
    """True when `family` is the active version, promoting it first if the universe is flat and idle."""
    active = store.get("active_family")
    held = [i for i in members if engine.held_of(i) is not None]
    if active == family:
        return True
    if active is None and not held:
        store.put("active_family", family)
        logger.event("FAMILY_ACTIVATED", family=family)
        return True
    pending.clear()
    if held or engine.busy() & set(members):
        logger.event("FAMILY_PROMOTION_FLATTENING", staged=family, active=active, held=held)
        for instrument in held:
            engine.flatten(instrument, "family_promotion")
        return False
    store.put("active_family", family)
    logger.event("FAMILY_PROMOTED", family=family, previous=active)
    return True
