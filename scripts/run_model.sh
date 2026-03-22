#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
python scripts/run_model.py "$@"
