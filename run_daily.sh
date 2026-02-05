#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$APP_DIR/.venv/bin/python" "$APP_DIR/run_daily.py"
