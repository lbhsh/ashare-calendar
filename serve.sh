#!/usr/bin/env bash
# Local smoke-test server for calendar subscription (same LAN only).
set -euo pipefail
cd "$(dirname "$0")"
python3 generate_ics.py
PORT="${1:-8765}"
echo "Serving $(pwd)/ashare_events.ics on http://0.0.0.0:${PORT}/ashare_events.ics"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
