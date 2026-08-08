# Secure Retail Data Lakehouse

An internship-level secure batch Data Engineering pipeline with privacy-preserving transformations and Azure VM deployment. It generates repeatable synthetic retail data, applies a Raw → Bronze → Silver → Gold workflow, and loads analytics datasets into PostgreSQL.

## Problem and objectives
Retail source data includes customer PII and payment information. This project demonstrates a simple batch workflow that preserves restricted source data in Raw, removes CVV in Bronze, masks and tokenizes PII in Silver, and publishes privacy-reduced datasets in Gold.

Objectives: generate realistic synthetic data; validate it before processing; protect PII; provide useful retail summaries; create text/HTML reports; load rerunnable current-state tables to PostgreSQL; and support local Docker/Azure VM execution.

## Architecture and data flow
```
Products + Customers + Transactions
            ↓ validation
Raw (restricted CSV source files)
            ↓ CVV hard drop + lineage
Bronze
            ↓ masking, redaction, SHA-256 salted tokens
Silver
            ↓ age, postal generalization, summaries
Gold → PostgreSQL → reports
```

Raw is intentionally unmasked to simulate a source system. It is restricted and must not be exposed to analytics users. The current CSV files are overwritten on each run for simplicity; `run_id` and `ingestion_timestamp` preserve transformed-layer lineage. PostgreSQL uses replace loads, preventing duplicate current-state rows on reruns.

## Technology stack
Python 3.10+, Pandas, PostgreSQL, SQLAlchemy, Faker, hashlib, python-dotenv, pytest, Docker, Docker Compose, and HTML/text reports.

## Project structure
```
data/{raw,bronze,silver,gold}/     Layer CSV outputs
master_data/                       Product master copy
reports/ logs/ backups/            Operational outputs
database/                          Database notes
deploy/                            Azure Ubuntu scripts
scripts/generators/                Source generators and validation
scripts/{bronze,silver,gold}_layer.py
scripts/database_loader.py         PostgreSQL loader
scripts/generate_reports.py        Data quality and HTML reports
tests/                             pytest checks
run_pipeline.py                    Complete pipeline entry point
health_check.py                    Environment/database check
backup_database.py                 pg_dump wrapper
```

## Privacy strategy
- **Bronze:** CVV is permanently dropped before the output CSV is written. Remaining fields receive `run_id` and UTC `ingestion_timestamp`.
- **Silver:** customer names become `***`; emails retain only first character/domain; phones and cards retain only four trailing digits. Full addresses are removed. SHA-256 tokens are created for email and phone using `HASH_SALT` from `.env`.
- **Gold:** date of birth, full address, raw/masked email, raw/masked phone, card number, and CVV are absent. Postal codes become `560XXX`. Gold keeps tokens, loyalty tiers, calculated ages, age groups, and analytics fields.

The data-quality report checks required columns, missing data, duplicate records, IDs, references, dates, amounts, and quantities. Privacy checks enforce CVV removal and Gold forbidden-column rules. Any critical validation or privacy failure stops downstream processing.

## Local setup and run
Prerequisites: Python 3.10+ and a reachable PostgreSQL instance for full database execution.

**PowerShell (Windows):**
```powershell
cd "C:\path\to\secure-retail-datalake"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env`: set a long random `HASH_SALT`, PostgreSQL credentials, and data counts. Keep `DB_REQUIRED=true` for a complete run. Then run:
```powershell
python run_pipeline.py
python health_check.py
python -m pytest -q
```

The complete entry point is `python run_pipeline.py`. It generates products, customers, transactions, Raw, Bronze, Silver, Gold, quality reports, and—when `DB_REQUIRED=true`—the four PostgreSQL Gold tables. `DB_REQUIRED=false` is an explicit local CSV-only development option; database loading is reported as skipped, never passed.

Outputs include `reports/data_quality_report.txt`, `reports/pipeline_metrics_report.txt`, `reports/pipeline_summary.html`, and `logs/pipeline.log`.

## PostgreSQL and backup
The loader creates/replaces `customers_gold`, `transactions_gold`, `customer_summary`, and `sales_summary` through SQLAlchemy. Verify it with `python health_check.py`; it checks connection and all expected tables. Create a dump where `pg_dump` is installed:
```powershell
python backup_database.py
```
Backups are timestamped under `backups/`.

## Docker
Create `.env` from `.env.example`, set `HASH_SALT` and strong PostgreSQL passwords, then:
```bash
docker compose build
docker compose up -d postgres
docker compose run --rm retail_pipeline python run_pipeline.py
docker compose run --rm retail_pipeline python health_check.py
```
`retail_pipeline` uses `DB_HOST=postgres`, not localhost. PostgreSQL has no host `ports` mapping, so it is only reachable by Compose services. The named `postgres_data` volume persists database data. To clean up containers without deleting the database volume: `docker compose down`.

## Azure Ubuntu VM deployment
1. Create an Ubuntu VM with SSH key authentication. In its NSG, allow inbound TCP 22 only from trusted IP ranges. Do **not** create a PostgreSQL (5432) inbound rule.
2. Connect by SSH and install Docker:
```bash
sudo apt-get update && sudo apt-get install -y git
# Clone the repository first, then execute its setup script:
git clone <your-github-repository-url> secure-retail-datalake
cd secure-retail-datalake
chmod +x deploy/*.sh
./deploy/setup_vm.sh
exit
```
3. SSH in again (the Docker group change then applies), create secrets, and deploy:
```bash
cd secure-retail-datalake
cp .env.example .env
nano .env                 # set DB_PASSWORD, POSTGRES_PASSWORD, HASH_SALT
./deploy/deploy.sh
```
4. Review `reports/`, `logs/pipeline.log`, and use `./deploy/backup_database.sh` for a database dump.

Security recommendations: use SSH keys rather than passwords; restrict SSH through the Azure NSG; never expose PostgreSQL publicly; store `.env` only on the VM; use strong unique secrets; limit VM user access; and apply regular OS/Docker updates. Database passwords and `HASH_SALT` are not in source code or the Dockerfile. This is not claimed to be production-grade security.

## Testing and troubleshooting
Run `python -m pytest -q`. Tests cover generation, source validation, CVV hard-drop, masking, address redaction, deterministic tokenization, Gold privacy, age bands, amount buckets, and postal-code generalization.

Common issues:
- **`HASH_SALT must be set`:** create `.env` and set a non-empty salt.
- **PostgreSQL connection error:** start PostgreSQL, verify `DB_HOST/PORT/NAME/USER/PASSWORD`, then run `python health_check.py`.
- **Docker pipeline cannot connect:** run it through Compose, where the database hostname is `postgres`.
- **Validation failure:** inspect `reports/data_quality_report.txt` and `logs/pipeline.log`; Bronze and later layers will not run.

## Known limitations and future scope
This is a full-refresh batch project with CSV storage and `replace` table loads. It has no scheduling, incremental processing, data catalog, encryption-at-rest configuration, user access controls, secret manager, or production monitoring. Suitable future improvements include Azure Key Vault, managed PostgreSQL, managed identity, schema migrations, automated CI, retention controls, role-based access, and incremental loads.
