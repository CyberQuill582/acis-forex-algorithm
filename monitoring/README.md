# `[DIR:monitoring]` — MCP Monitoring & Control Plane

**Blueprint only — no implementation yet.** The only external observability/control surface — no side channels, no ad-hoc HTTP.

- **Deep spec:** `../specs/ACIS-08-MONITORING_MCP.md` · **Master:** `../ACIS_SPEC.md` §12
- **Exposes:** read-only resources (`acis://status`, `acis://risk/snapshot`, `acis://regime/current`, `acis://params/{active,pending}`, `acis://performance/daily`, `acis://config/guardrails`, `acis://logs/tail/{stream}`) + schema-validated tools.
- **Planned files:** `server.py`, `resources.py`, `tools.py`, `prompts.py`, `auth.py`
- **Safety asymmetry (binding):** any agent may `acis_halt`/`acis_flatten`; only a **human token** may `acis_resume`/`acis_set_mode`. `acis_stage_config` rejects guardrail/equity paths at the schema level.
- **Owns corrections:** C-MCP-1 (human gate), C-MCP-2 (guardrail schema reject), C-MCP-3 (idempotency by request_id), C-MCP-4 (no side channel), C-MCP-5 (safety asymmetry), C-MCP-6 (heartbeat rule).
