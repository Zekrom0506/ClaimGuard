#!/usr/bin/env bash
# One-time setup: builds the data, trains the risk model and loads the policies.
#
#   Local (inside the backend's virtual environment):  bash scripts/setup.sh
#   Docker:  docker compose run --rm api bash /project/scripts/setup.sh
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
BACKEND_PATH="${BACKEND_PATH:-$PROJECT_ROOT/backend}"

echo "[1/6] Building the synthetic sample policy PDF"
python "$PROJECT_ROOT/scripts/build_sample_policy.py"

echo "[2/6] Generating synthetic demo requests"
python "$PROJECT_ROOT/scripts/generate_synthetic_cases.py" --count 30

echo "[3/6] Generating synthetic training records"
python "$PROJECT_ROOT/ml/generate_training_data.py"

echo "[4/6] Training the denial-risk model"
python "$PROJECT_ROOT/ml/train_risk_model.py"

echo "[5/6] Creating database tables"
cd "$BACKEND_PATH"
alembic upgrade head

echo "[6/6] Loading policies (downloads the embedding model the first time)"
python -m scripts.ingest_policies

echo "Done. The 40 labelled evaluation cases are already in data/evaluation/."
