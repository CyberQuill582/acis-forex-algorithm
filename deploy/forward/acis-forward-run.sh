#!/bin/bash
# The forward tournament's daily run on the AWS data server (TOURNAMENT, 2026-10-04; plan in
# archive/TOURNAMENT_REPORT_2026-10-03.md). Runs as ec2-user from acis-forward.service at boot:
# - fetches the newest public inputs (the Dukascopy archive bucket is in this region: no transfer cost),
#   records every registered strategy's newly settled days and re-checks the recorded ones;
# - copies the record, the input store's manifest and series, and the run log to the transfer bucket,
#   whose object versions are the server-side timestamps of every daily head;
# - on Mondays also writes the weekly report there. It never trades and reads no secret.
set -euo pipefail
F=/data/acis/forward
B=s3://acis-transfer-565257597310/forward
cd "$F/repo"
export PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1
"$F/venv/bin/python" scripts/tournament_daily.py --store "$F/inputs" --staging "$F/staging" \
  --record "$F/record" --archive "$F/archive" > "$F/last_run.json"
"$F/venv/bin/python" scripts/tournament_report.py --record "$F/record" --out "$F/report.json" --md "$F/report.md" > /dev/null
aws s3 sync "$F/record" "$B/record" --only-show-errors
aws s3 cp "$F/inputs/manifest.jsonl" "$B/inputs/manifest.jsonl" --only-show-errors
aws s3 sync "$F/inputs/series" "$B/inputs/series" --only-show-errors
aws s3 cp "$F/last_run.json" "$B/runs/$(date -u +%Y-%m-%d).json" --only-show-errors
if [ "$(date -u +%u)" = "1" ]; then
  aws s3 cp "$F/report.md" "$B/reports/$(date -u +%Y-%m-%d).md" --only-show-errors
  aws s3 cp "$F/report.json" "$B/reports/$(date -u +%Y-%m-%d).json" --only-show-errors
fi
