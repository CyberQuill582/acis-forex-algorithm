#!/bin/bash
# Sets the ACIS human token: you invent it; only its SHA-256 fingerprint is stored. Never echoed.
set -e
while true; do
  read -r -s -p "New human token (12+ characters, you invent it): " T1; echo
  read -r -s -p "Type it again: " T2; echo
  if [ "$T1" != "$T2" ]; then echo "  they differ - try again"; continue; fi
  if [ ${#T1} -lt 12 ]; then echo "  too short (${#T1}) - use 12 or more characters"; continue; fi
  break
done
D=$(printf '%s' "$T1" | sha256sum | cut -d' ' -f1); unset T1 T2
umask 077
grep -v '^ACIS_HUMAN_TOKEN_SHA256=' /etc/acis/engine.env > /etc/acis/engine.env.new || true
echo "ACIS_HUMAN_TOKEN_SHA256=$D" >> /etc/acis/engine.env.new
mv /etc/acis/engine.env.new /etc/acis/engine.env
echo "human token fingerprint stored in /etc/acis/engine.env (the token itself is stored nowhere)"
