# Secure Retail Data Lakehouse

An internship-level batch ETL project built with Python, Pandas, PostgreSQL, and Docker. It keeps the architecture explicit and small:

```text
Generate + validate source data
          ↓
Raw → Bronze → Silver → Gold → PostgreSQL → Reports
```

## What the pipeline does

- Generates configurable synthetic products, customers, and transactions.
- Validates columns, empty data, missing values, duplicates, emails, dates, numeric values, amounts, and relationships.
- Saves Raw source data unchanged.
- Removes CVV and adds a UTC ingestion timestamp and run ID in Bronze.
- Masks names, email, phone, and cards; removes full addresses and exact DOB; creates salted SHA-256 email and phone tokens in Silver.
- Creates age, age group, amount bucket, generalized postal code, customer summary, and sales summary in Gold.
- Replaces four PostgreSQL tables on each run and creates four simple reports.

## Project structure

```text
secure-retail-datalake/
├── data/{raw,bronze,silver,gold}/   # Runtime CSV files
├── reports/                         # Runtime reports
├── backups/                         # Timestamped SQL dumps
├── deploy/deploy.sh                 # Azure Ubuntu deployment
├── tests/test_pipeline.py
├── pipeline.py                      # Generation, layers, reports, orchestration
├── validation.py                    # Data and privacy checks
├── database.py                      # PostgreSQL connection and loading
├── health_check.py
├── backup_database.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── .dockerignore
```

Generated data, reports, logs, backups, and `.env` are not included in the Docker image.

## Privacy by layer

| Layer | Treatment |
|---|---|
| Raw | Generated source data saved unchanged; restricted access |
| Bronze | CVV removed; ingestion timestamp and run ID added |
| Silver | PII masked, full address redacted, exact DOB removed, card masked, salted SHA-256 tokens added |
| Gold | Exact DOB/card/email/phone/address absent; age and age group added; postal code generalized |

The token is `SHA-256(HASH_SALT + normalized value)`. Gold contains deterministic tokens for joins but no raw email or phone.

## Configuration

Copy `.env.example` to `.env` and set all passwords plus a long random `HASH_SALT`. Never commit `.env`.

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=secure_retail_lakehouse
DB_USER=postgres
DB_PASSWORD=your-special@password
HASH_SALT=your-long-random-secret
CUSTOMER_COUNT=10000
TRANSACTION_COUNT=50000
PRODUCT_COUNT=1000
DB_REQUIRED=true
POSTGRES_DB=secure_retail_lakehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-special@password
```

`DB_PASSWORD` supports reserved characters such as `@`, `:`, `/`, and `#`; `database.py` safely URL-encodes credentials. For Docker, the application receives the `POSTGRES_*` values automatically, so `POSTGRES_PASSWORD` is the database password used by both containers.

## Run with Docker Compose

PostgreSQL is only on the private Compose network; port 5432 is not published to the VM.

```bash
docker compose -p secure-retail-datalake build
docker compose -p secure-retail-datalake up -d postgres
docker compose -p secure-retail-datalake run --rm retail_pipeline
docker compose -p secure-retail-datalake run --rm retail_pipeline python health_check.py
```

A second pipeline run safely replaces the four Gold tables:

```bash
docker compose -p secure-retail-datalake run --rm retail_pipeline
```

Tables: `customers_gold`, `transactions_gold`, `customer_summary`, and `sales_summary`.

## Reports

The `reports/` folder contains:

- `validation_report.txt`
- `data_quality_report.txt`
- `pipeline_metrics_report.txt`
- `pipeline_summary.html`

Reports include row counts, missing/duplicate counts, statuses, execution time, run ID, Gold counts, and database load counts. They never include passwords, `HASH_SALT`, CVV, card data, or raw PII.

## Tests

```bash
python -m pytest -q
```

Run the file pipeline without PostgreSQL when developing locally:

```bash
# Set DB_REQUIRED=false in .env
python pipeline.py
```

## Backup and persistence

Create a timestamped SQL backup with:

```bash
docker compose -p secure-retail-datalake run --rm retail_pipeline python backup_database.py
```

Backups are written to `backups/`. The named `postgres_data` volume keeps data when PostgreSQL restarts. Stop only this project while preserving its database:

```bash
docker compose -p secure-retail-datalake stop postgres
docker compose -p secure-retail-datalake start postgres
```

Do not use `down -v` unless this project's database should be deleted.

## Azure Ubuntu VM

Install Docker Engine and the Compose plugin using Docker's official Ubuntu instructions, then:

```bash
git clone <repository-url>
cd secure-retail-datalake
cp .env.example .env
nano .env
chmod 600 .env
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

The deployment uses the fixed Compose project name `secure-retail-datalake`. It does not publish PostgreSQL, use Nginx, change certificates, or stop/remove other containers, networks, or volumes. It can coexist with the existing Krushi Ledger/Fabric deployment.

Never run global cleanup commands such as `docker system prune`, `docker volume prune`, or `docker network prune` on the shared VM.

## Local Python option

Install dependencies with `python -m pip install -r requirements.txt`. A local PostgreSQL server must match the `DB_*` settings when `DB_REQUIRED=true`. Use `python health_check.py` after a successful database load.

This is an educational full-refresh project. It intentionally avoids services, APIs, classes, migration frameworks, and complex abstractions.
