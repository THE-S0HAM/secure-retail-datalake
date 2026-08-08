# Database

PostgreSQL is populated from Gold CSV datasets by `scripts/database_loader.py`.

The loader uses `replace` mode, so current analytical tables are safe to reload without duplicate rows. Database credentials are supplied through environment variables only.
