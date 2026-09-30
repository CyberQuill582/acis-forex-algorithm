# ACIS deployment (pre-phase-12 VPS deployment-readiness gate)

This is the **deployment-readiness** scaffold from SPEC v2.10, item (b), and the
phase-12 checklist item **"Pre-phase-12 VPS deployment-readiness gate."** It does
**not** enable live trading — ACIS stays paper-only until the §14 out-of-sample
gate is met on real data **and** a human signs off (CLAUDE.md; `TODO.md` phase 12).

## What the gate delivers

| Part | Artifact | Status |
|------|----------|--------|
| CI merge gate | `.github/workflows/ci.yml` — full suite on every push/PR to `main`, run twice for determinism | ✅ runnable |
| Docker scaffold | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | ✅ image builds; watchdog service runs |
| Process supervision | `deploy/systemd/acis-watchdog.service`, `deploy/systemd/acis-engine.service` | ✅ watchdog live; engine unit runs `python -m core.runtime` (2026-09-30), not yet enabled |
| Server-side stop verification | `tests/integration/test_adapter_conformance.py::test_server_side_stop_*` | ✅ asserted per adapter (§279) |

## Topology

Two **independent** processes by design (SPEC §8.6): the watchdog must not die
with the engine.

```
          logs/heartbeat.json  (shared volume / shared dir)
   engine ───writes──▶  ◀──reads─── watchdog ──flatten_all()──▶ broker
   (fast loop)                      (own interpreter, 0 core/ imports)
```

The watchdog reads the engine's heartbeat; on silence beyond `watchdog_timeout_s`
**with open positions**, it flattens via the broker plugin from outside the blast
radius. It can only ever flatten/halt — never size, resume, or write config.

## Bare VPS (systemd)

```bash
sudo useradd --system --home /opt/acis acis
sudo rsync -a --exclude .git ./ /opt/acis/         # deploy the source tree
sudo install -d -o acis -g acis /opt/acis/logs

# broker credential for the watchdog — root-owned, 0600, NEVER in the repo
echo 'ACIS_WATCHDOG_CREDENTIALS=<token>' | sudo install -m600 /dev/stdin /etc/acis/watchdog.env

sudo cp deploy/systemd/acis-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now acis-watchdog          # the breaker is now supervised
sudo systemctl status acis-watchdog
```

The `acis-engine.service` unit runs the three-loop runtime, `python -m core.runtime
--venue --account pepperstone_demo` (master §10, `core/runtime/`). Enable it only once the
venue credentials exist in `/etc/acis/engine.env` (root-owned, 0600). It always boots in
PAPER on the venue's prices; practice needs a human at a terminal:

```bash
python -m core.runtime --print-hashes --account pepperstone_demo    # read what you attest to
python -m core.runtime --venue --account pepperstone_demo --practice     --ack-guardrail <hash> --ack-rulebook <hash>                     # asks for the human token
```

Both units are OS-hardened (`ProtectSystem=strict`); the watchdog may write only
`/opt/acis/logs`, the engine only `logs/`, `data/` and its token store, so neither
process can write `config/guardrail_limits.yaml` or `config/watchdog.yaml` even if its
code tried — guard-integrity enforced by the kernel, not by promises.

## Container path

```bash
docker compose up -d watchdog        # the always-on breaker (runnable today)
# docker compose --profile engine up -d   # the runtime entrypoint exists; the compose engine service is not yet wired
```

## Still required before live (not part of THIS gate — see TODO phase 12)

- Real ≥2-yr Dukascopy/TrueFX out-of-sample data + honest §14 grading.
- ~~The three-loop production runtime + in-loop wiring~~ BUILT 2026-09-30 (`core/runtime/`,
  GAP-0075/0099/0091b); its open remainder for an unattended demo is GAP-P12D-131 and
  feed reconnect GAP-0020.
- Real platform adapters (ACIS-13) — each runs `test_adapter_conformance.py`
  unchanged against its demo environment, **including the §279 server-side-stop
  assertions**, before it may be selected.
- `GAP-P10E-03`: harden the MCP bearer-secret auth at this deployment gate.
- Human live sign-off — always last, human-only.
