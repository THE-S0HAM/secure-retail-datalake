#!/usr/bin/env bash
set -euo pipefail
if [ ! -f .env ]; then
  echo "Create .env from .env.example and set secure values first."
  exit 1
fi
docker compose build
docker compose up -d postgres
docker compose run --rm retail_pipeline python health_check.py || true
docker compose run --rm retail_pipeline python run_pipeline.py
docker compose run --rm retail_pipeline python health_check.py
