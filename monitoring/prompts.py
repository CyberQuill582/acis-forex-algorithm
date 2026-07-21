"""Canonical report prompts (ACIS-08 §11, master §12).

Templates for LLM-side analysis that read ONLY from resources/logs. All research
is out-of-band per the §0 LLM boundary; a prompt's output lands as staged
code/config (via `acis_stage_config`) or human proposals — NEVER as live
signals, a control action, or a guardrail change (untrusted-input law, C-MCP-7).

These are declarative descriptors: the name, what the analysis is for, and the
read-only resources it draws on. The MCP server exposes them by name; the actual
reasoning happens in the out-of-band client.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    purpose: str
    reads: tuple[str, ...]      # read-only resources it draws on


CANONICAL_PROMPTS: tuple[PromptTemplate, ...] = (
    PromptTemplate(
        "daily-performance-brief",
        "Narrate the daily rollup: PnL, take-rate, notable halts.",
        ("acis://performance/daily", "acis://status", "acis://logs/tail/risk")),
    PromptTemplate(
        "halt-postmortem",
        "Reconstruct a HALT from the risk log; propose scenario-book additions (§8.5).",
        ("acis://logs/tail/risk", "acis://risk/snapshot", "acis://status")),
    PromptTemplate(
        "literature-distil",
        "From a cited source → a faithful strategy spec + falsifier (§5.6 research loop).",
        ("acis://strategies/provenance",)),
    PromptTemplate(
        "strategy-provenance-audit",
        "Walk attempt counts, plateaus, rung history honestly before any live-promotion proposal.",
        ("acis://strategies/provenance",)),
    PromptTemplate(
        "geopolitical-brief",
        "§3.6 slow lane: world events → staged watchlist/taxonomy/caution proposals, never live signals.",
        ("acis://events/picture",)),
    PromptTemplate(
        "starvation-diagnosis",
        "§10: per-gate skip attribution → a targeted staged-config proposal, or 'the market offered nothing'.",
        ("acis://status",)),
)

PROMPTS_BY_NAME = {p.name: p for p in CANONICAL_PROMPTS}
