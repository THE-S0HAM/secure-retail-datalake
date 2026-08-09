#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="secure-retail-datalake"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "Create .env from .env.example and set DB passwords and HASH_SALT."
  exit 1
fi

docker compose -p "$PROJECT_NAME" build --no-cache
docker compose -p "$PROJECT_NAME" up -d postgres
docker compose -p "$PROJECT_NAME" run --rm retail_pipeline
docker compose -p "$PROJECT_NAME" run --rm retail_pipeline python health_check.py

echo "Secure Retail Data Lakehouse deployment completed successfully."
