#!/usr/bin/env bash
set -euo pipefail
if [ ! -f .env ]; then
  echo "Create .env from .env.example and set secure values first."
  exit 1
fi
docker compose -p secure-retail-datalake build
docker compose -p secure-retail-datalake up -d postgres
docker compose -p secure-retail-datalake run --rm retail_pipeline python run_pipeline.py
docker compose -p secure-retail-datalake run --rm retail_pipeline python health_check.py
