#!/bin/bash
# ACIS first-demo setup: secrets are typed at hidden prompts, written 0600, never echoed.
set -e
sudo install -d -m 700 -o "$USER" /etc/acis /var/lib/acis
umask 077

ask() {  # $1 label, $2 regex, $3 expected length; result in REPLY_VAL. Re-asks until valid.
  local v junk
  while true; do
    while read -r -s -t 0.2 junk; do :; done      # drop any leftover pasted lines
    read -r -s -p "$1 (paste ONCE - the screen stays blank - then Enter): " v; echo
    v="$(printf '%s' "$v" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [[ "$v" =~ $2 ]]; then
      echo "  ok: $1 accepted (${#v} characters)"
      REPLY_VAL="$v"; return
    fi
    echo "  NOT accepted (${#v} characters; expected about $3). Pasted twice? Copy just the value, paste once."
  done
}

ask "Client ID" '^[0-9]+_[A-Za-z0-9]{20,70}$' "55: digits, an underscore, letters"; A="$REPLY_VAL"
echo "  (it starts with ${A:0:8}... - check that against the website)"
ask "Client secret" '^[A-Za-z0-9]{20,70}$' "50"; B="$REPLY_VAL"
printf 'ACIS_CTRADER_CLIENT_ID=%s\nACIS_CTRADER_CLIENT_SECRET=%s\nACIS_CTRADER_TOKEN_STORE=/var/lib/acis/ctrader_tokens.json\n' "$A" "$B" > /etc/acis/engine.env
unset A B REPLY_VAL
echo "credentials written: /etc/acis/engine.env"
set -a; . /etc/acis/engine.env; set +a
cd /opt/acis/repo
if [ "$1" != "--keep-tokens" ]; then /opt/acis/venv/bin/python scripts/ctrader_setup.py tokens; fi
echo "--- accounts this token can reach ---"
/opt/acis/venv/bin/python scripts/ctrader_setup.py accounts
