#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/filmcraft_agent.py" bootstrap "$@"
python3 "$ROOT/scripts/check_project.py"
