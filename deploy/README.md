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
| Process supervision | `deploy/systemd/acis-watchdog.service`, `deploy/systemd/acis-engine.service` | ✅ watchdog live; engine unit is a template pending the phase-12 runtime |
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

The `acis-engine.service` unit is a **template** — do not enable it until the
phase-12 three-loop runtime entrypoint exists (it would restart-loop). Both units
are OS-hardened (`ProtectSystem=strict` + a single `ReadWritePaths=/opt/acis/logs`)
so neither process can write `config/guardrail_limits.yaml` or `config/watchdog.yaml`
even if its code tried — guard-integrity enforced by the kernel, not by promises.

## Container path

```bash
docker compose up -d watchdog        # the always-on breaker (runnable today)
# docker compose --profile engine up -d   # once the phase-12 runtime entrypoint lands
```

## Still required before live (not part of THIS gate — see TODO phase 12)

- Real ≥2-yr Dukascopy/TrueFX out-of-sample data + honest §14 grading.
- The three-loop production runtime + in-loop wiring (GAP-0091b VaR/marks,
  GAP-0099 per-fill breaker, GAP-0075 position accounting) — this is what fills
  in the `engine` service/unit `ExecStart` and threads each `SizedOrder.stop_loss`
  to the venue's server-side stop.
- Real platform adapters (ACIS-13) — each runs `test_adapter_conformance.py`
  unchanged against its demo environment, **including the §279 server-side-stop
  assertions**, before it may be selected.
- `GAP-P10E-03`: harden the MCP bearer-secret auth at this deployment gate.
- Human live sign-off — always last, human-only.
