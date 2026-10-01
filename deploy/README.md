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
sudo python3 -m venv /opt/acis/venv               # Debian 12 refuses pip into the system Python (PEP 668, GAP-P12D-134)
sudo /opt/acis/venv/bin/pip install structlog "pydantic>=2" pydantic-settings PyYAML "aiohttp>=3.9,<4"   # pyproject's dependencies, as CI installs them
sudo install -d -o acis -g acis /opt/acis/logs

# broker credential for the watchdog — root-owned, 0600, NEVER in the repo
# (the cTrader plugin reads ACIS_CTRADER_CLIENT_ID, ACIS_CTRADER_CLIENT_SECRET and ACIS_CTRADER_TOKEN_STORE)
echo 'ACIS_WATCHDOG_CREDENTIALS=<token>' | sudo install -m600 /dev/stdin /etc/acis/watchdog.env

sudo cp deploy/systemd/acis-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now acis-watchdog          # the breaker is now supervised
sudo systemctl status acis-watchdog
```

The `acis-engine.service` unit runs the three-loop runtime, `python -m core.runtime
--venue --account pepperstone_demo` (master §10, `core/runtime/`). Enable it only once
`/etc/acis/engine.env` (root-owned, 0600) holds the venue credentials and
`ACIS_HUMAN_TOKEN_SHA256` (the digest of your human token, never the token). It always boots
in PAPER on the venue's prices, and a paper process leaves the demo account's positions to
their venue stops (it logs them critical). Practice, and lifting halts, need a human at a
terminal. One engine runs per deployment (a second is refused, exit 2), so stop the unit first:

```bash
sudo systemctl stop acis-engine
/opt/acis/venv/bin/python -m core.runtime --print-hashes --account pepperstone_demo     # read what you attest to
sudo systemd-run --pty --uid=acis --gid=acis -p EnvironmentFile=/etc/acis/engine.env   -p WorkingDirectory=/opt/acis -E PYTHONPATH=/opt/acis   /opt/acis/venv/bin/python -m core.runtime --venue --account pepperstone_demo --practice   --ack-guardrail <hash> --ack-rulebook <hash>     # asks for the token; add --resume to lift halts
```

**Stopping it.** Ctrl+C, `systemctl stop` or a shutdown (SIGINT/SIGTERM) is a deliberate stop:
the engine closes every position, halts, then exits 0 (GAP-P12D-135; the closes get 30 s, inside
systemd's default 90 s stop timeout). The halts persist, so the next practice start needs
`--practice --resume` (one token prompt covers both). A position still open after the closes is
logged `STOP_LEFT_POSITIONS`, and the watchdog flattens it once the heartbeat goes stale.

The engine's exit codes: 0 the feed ended or a deliberate stop, 1 a loop stalled (flattened and halted), 2 refused
(the attach, a foreign position, a second engine), 3 a human step refused, 4 the venue stayed
unreachable. The unit does not restart on 2 or 3, and stops after 10 starts in an hour.

Both units are OS-hardened (`ProtectSystem=strict`); the watchdog may write only
`/opt/acis/logs`, the engine only `logs/`, `data/` and its token store, so neither
process can write `config/guardrail_limits.yaml` or `config/watchdog.yaml` even if its
code tried — guard-integrity enforced by the kernel, not by promises.

## The demo host (acis-demo-1, Google Cloud e2-medium, Debian 12)

The Pepperstone demo runs from a git checkout at `/opt/acis/repo` with the venv at
`/opt/acis/venv`, all as the owner's login user, because the owner starts practice by hand in
`tmux` with the human token. `deploy/demo/` holds that host's pieces:

```bash
bash deploy/demo/acis_setup.sh           # owner: Open API credentials + Playground tokens at hidden prompts
bash deploy/demo/set_human_token.sh      # owner: invent the human token; only its sha256 is stored
sudo sh -c 'grep "^ACIS_CTRADER_" /etc/acis/engine.env > /etc/acis/watchdog.env && chmod 600 /etc/acis/watchdog.env'
sudo install -m644 deploy/systemd/acis-watchdog.service /etc/systemd/system/
sudo install -D -m644 deploy/demo/acis-watchdog.override.conf /etc/systemd/system/acis-watchdog.service.d/demo-host.conf
sudo systemctl daemon-reload && sudo systemctl enable --now acis-watchdog   # survives a reboot
```

The engine unit is not installed there: after a reboot the watchdog finds the engine silent and
flattens any open position, and the owner restarts practice in `tmux` with the token.

## The AWS demo host (acis-demo-aws, t3.small, Debian 12, eu-west-1)

The permanent demo host (owner ruling 2026-10-01, "Hybrid, on AWS"): the same watchdog-only
boot as acis-demo-1, but the watchdog and the practice engine both run as the `acis` user,
which has no sudo. The host takes no SSH. The session drives it through SSM (`aws ssm
send-command` as IAM user `acis-data`), and the owner's shell is Session Manager in the AWS
console (EC2 → `acis-demo-aws` → Connect → Session Manager), which logs in as `ssm-user`, with sudo.

- **Launch** (as `acis-data`): t3.small with standard CPU credits, Debian 12, 30 GB gp3
  encrypted, IMDSv2 only, no key pair, the default security group (no inbound from outside),
  instance profile `acis-data-server-role`, tags `Project=acis` + `Name=acis-demo-aws`, user data
  `deploy/aws/acis-demo-userdata.sh` (the SSM agent, the `acis` user and its secret
  directories, and a firewall rule that keeps `acis` processes off the metadata service).
- **Code:** `deploy/aws/acis-demo-prepare.sh <bundle-url> <params.db-url>` through SSM, with
  presigned URLs to `s3://acis-transfer-565257597310/demo/`. It clones or fast-forwards
  `/opt/acis/repo`, builds `/opt/acis/venv` with the demo's pinned dependencies, places
  `params.db` once, and installs the watchdog unit with `deploy/demo/acis-watchdog.aws.conf`,
  NOT enabled. Re-run it with a new bundle to update the checkout.

**One engine and one watchdog per demo account, across all hosts.** A watchdog whose own
engine is silent flattens every position on the account, so a second host's watchdog would
flatten the first host's trades. The cutover order is fixed: stop the old engine flat and
stop its host, then enable the new watchdog, then start practice.

The owner's steps, in Session Manager:

```bash
sudo -u acis -i                                  # the acis user's shell
cd /opt/acis/repo
bash deploy/demo/acis_setup.sh                   # credentials + a fresh Playground token pair, hidden prompts
bash deploy/demo/set_human_token.sh              # the human token; only its sha256 is stored
exit                                             # back to ssm-user
sudo sh -c 'grep "^ACIS_CTRADER_" /etc/acis/engine.env > /etc/acis/watchdog.env && chmod 600 /etc/acis/watchdog.env'
sudo systemctl enable --now acis-watchdog        # only after the old host is stopped
sudo -u acis tmux new -s acis                    # then, inside tmux:
cd /opt/acis/repo && set -a && . /etc/acis/engine.env && set +a
/opt/acis/venv/bin/python -m core.runtime --print-hashes --account pepperstone_demo
/opt/acis/venv/bin/python -m core.runtime --venue --account pepperstone_demo --practice --ack-guardrail <hash> --ack-rulebook <hash>
```

Detach with Ctrl+B then D; reattach with `sudo -u acis tmux attach -t acis`. After any
deliberate stop the next start needs `--practice --resume`.

## Container path

```bash
docker compose up -d watchdog        # the always-on breaker (runnable today)
docker compose --profile engine up -d  # the engine, in paper on the venue's prices
```

Docker restarts the engine container on EVERY exit, including 2 and 3, which need a human
(it has no equivalent of `RestartPreventExitStatus`). Each start re-attaches and spends the
request budget, which stays hard, so the loop is bounded but wasteful. The systemd unit is
the supported path for the demo.

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
