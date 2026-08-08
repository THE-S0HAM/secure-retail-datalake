#!/usr/bin/env bash
set -euo pipefail
docker compose run --rm retail_pipeline python backup_database.py
