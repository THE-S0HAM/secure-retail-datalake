#!/usr/bin/env bash
set -euo pipefail
docker compose -p secure-retail-datalake run --rm retail_pipeline python backup_database.py
