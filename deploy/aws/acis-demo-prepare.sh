#!/bin/bash
# ACIS demo host (AWS): install or update the checkout, the venv and the watchdog unit.
# Run as root through SSM after deploy/aws/acis-demo-userdata.sh has finished.
# Usage: acis-demo-prepare.sh <git-bundle-url> [<params.db-url>]
# Everything under /opt/acis belongs to `acis`. The watchdog unit is installed but NOT enabled:
# it needs /etc/acis/watchdog.env, which only the owner's secret steps create (deploy/README.md).
set -euo pipefail
BUNDLE_URL="$1"
PARAMS_URL="${2:-}"
as_acis() { runuser -u acis -- "$@"; }

curl -fsSL -o /tmp/acis.bundle "$BUNDLE_URL"
chown acis:acis /tmp/acis.bundle
if [ ! -d /opt/acis/repo/.git ]; then
  as_acis git clone --branch main /tmp/acis.bundle /opt/acis/repo
else
  as_acis git -C /opt/acis/repo fetch /tmp/acis.bundle main
  as_acis git -C /opt/acis/repo merge --ff-only FETCH_HEAD
fi
rm -f /tmp/acis.bundle

# pyproject's runtime dependencies, pinned to the versions the Google demo host ran (2026-10-01)
[ -x /opt/acis/venv/bin/python ] || as_acis python3 -m venv /opt/acis/venv
as_acis /opt/acis/venv/bin/pip install --quiet --disable-pip-version-check \
  aiohappyeyeballs==2.7.1 aiohttp==3.14.3 aiosignal==1.4.0 annotated-types==0.8.0 attrs==26.1.0 \
  frozenlist==1.8.0 idna==3.20 multidict==6.9.1 propcache==0.5.4 pydantic==2.13.5 \
  pydantic-settings==2.15.0 pydantic_core==2.46.5 python-dotenv==1.2.3 PyYAML==6.0.3 \
  structlog==26.1.0 typing-inspection==0.4.4 typing_extensions==4.16.0 yarl==1.25.1

as_acis install -d -m 755 /opt/acis/repo/data/runtime /opt/acis/repo/logs
if [ -n "$PARAMS_URL" ] && [ ! -e /opt/acis/repo/data/runtime/params.db ]; then
  as_acis curl -fsSL -o /opt/acis/repo/data/runtime/params.db "$PARAMS_URL"
fi

install -m644 /opt/acis/repo/deploy/systemd/acis-watchdog.service /etc/systemd/system/
install -D -m644 /opt/acis/repo/deploy/demo/acis-watchdog.aws.conf \
  /etc/systemd/system/acis-watchdog.service.d/demo-host.conf
systemctl daemon-reload

cd /opt/acis/repo
as_acis git log -1 --oneline
as_acis /opt/acis/venv/bin/python -m core.runtime --print-hashes --account pepperstone_demo
