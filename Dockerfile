# ACIS deployment image (pre-phase-12 VPS deployment-readiness gate, SPEC v2.10).
#
# The project runs FROM SOURCE (pyproject sets pythonpath=["."]); it is not a
# pip-installable package (flat multi-package layout). So we install only the
# declared runtime deps and put the repo on PYTHONPATH — exactly how pytest and
# the loop owner run it. Deps mirror pyproject [project.dependencies].
#
# Default command is the WATCHDOG — the always-on safety process (SPEC §8.6),
# the one thing already runnable today. The engine runtime entrypoint arrives
# with the phase-12 three-loop runtime; docker-compose defines it as a separate
# supervised service. Nothing here can reach a guardrail file (human-commit-only).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Runtime deps only (no dev/test tooling in the deployment image — CI runs tests).
RUN pip install --no-cache-dir \
    structlog "pydantic>=2" pydantic-settings PyYAML

# Source tree (.dockerignore trims tests, .git, logs, scratch).
COPY . .

# Non-root, with a writable logs dir for the JSONL envelope + heartbeat/marker.
RUN useradd --create-home acis \
    && mkdir -p /app/logs \
    && chown -R acis:acis /app
USER acis

CMD ["python", "scripts/acis_watchdog.py"]
