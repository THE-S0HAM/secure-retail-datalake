# Secure Retail Data Lakehouse

A Python-based Data Engineering project that implements a secure layered ETL pipeline: **Raw → Bronze → Silver → Gold**. It combines synthetic retail data generation, validation, privacy-preserving transformations, SHA-256 tokenization, PostgreSQL loading, and automated reports.

## Project overview
Secure Retail Data Lakehouse is the final project for the **Celebal Excellence Internship 2026**. It simulates how a retail organization can process customer and transaction data securely before exposing analytics-ready datasets.

The pipeline generates realistic synthetic retail data, validates it, organizes it in a Medallion Architecture, protects personal information, loads final Gold datasets into PostgreSQL, and creates execution and data-quality reports. The code is intentionally modular, readable, and suitable for an internship-level Data Engineering project.

## Problem statement
Retail systems contain customer names, email addresses, phone numbers, payment details, and transaction history. Making this source data directly available to analysts creates privacy risks. This project demonstrates a batch ETL workflow that removes or reduces sensitive data exposure while preserving useful analytics fields.

## Objectives
- Build a Raw, Bronze, Silver, and Gold ETL pipeline.
- Generate repeatable synthetic product, customer, and transaction data.
- Validate source data before downstream processing.
- Remove, mask, redact, tokenize, and generalize sensitive values.
- Create customer and sales summaries for analysis.
- Load Gold datasets into PostgreSQL.
- Generate validation, quality, metrics, and HTML reports.

## Key features
- Synthetic retail data generation using Faker.
- Configurable row counts through environment variables.
- Required-column, relationship, duplicate, numeric, date, and email validation.
- CVV hard drop in Bronze.
- PII masking, address redaction, and salted SHA-256 tokens in Silver.
- Age groups, amount buckets, postal-code generalization, and summaries in Gold.
- Idempotent PostgreSQL full-refresh loading.
- Docker Compose deployment with an internal PostgreSQL service.
- Pytest coverage for important generation, validation, privacy, and URL-handling rules.

## Architecture
```text
Product master generation
          ↓
Customer data generation
          ↓
Transaction data generation
          ↓
Data validation
          ↓
Raw → Bronze → Silver → Gold → PostgreSQL → Reports
```

The complete workflow is executed with:

```bash
python run_pipeline.py
```

## Technology stack
| Category | Technologies |
|---|---|
| Programming language | Python 3.11 |
| Data processing | Pandas |
| Database | PostgreSQL 16 |
| Database access | SQLAlchemy and psycopg2 |
| Synthetic data | Faker |
| Security | hashlib SHA-256 and python-dotenv |
| Testing | pytest |
| Deployment | Docker and Docker Compose |
| Version control | Git and GitHub |

## Project structure
```text
secure-retail-datalake/
├── config/                     # Environment and path helpers
├── data/{raw,bronze,silver,gold}/
├── master_data/                # Product master copy
├── reports/                    # Text and HTML pipeline reports
├── logs/                       # Pipeline log output
├── backups/                    # Timestamped PostgreSQL dumps
├── database/                   # Database notes
├── deploy/                     # Ubuntu VM setup, deploy, and backup scripts
├── scripts/
│   ├── generators/             # Product, customer, transaction, validation modules
│   ├── bronze_layer.py
│   ├── silver_layer.py
│   ├── gold_layer.py
│   ├── database_loader.py
│   └── generate_reports.py
├── tests/                      # Pytest business-rule tests
├── run_pipeline.py             # Complete pipeline entry point
├── health_check.py             # Environment and database readiness check
├── backup_database.py          # PostgreSQL backup utility
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

## Medallion pipeline
### Raw layer
The Raw layer stores the generated source data exactly as created. It is restricted source-system data and must not be exposed to analytics users.

Files:
- `data/raw/customers.csv`
- `data/raw/products.csv`
- `data/raw/transactions.csv`

### Bronze layer
Bronze is the first security and lineage boundary. It removes CVV, adds a UTC ingestion timestamp, and adds a timestamp-based pipeline `run_id`.

Files:
- `data/bronze/customers_bronze.csv`
- `data/bronze/products_bronze.csv`
- `data/bronze/transactions_bronze.csv`

### Silver layer
Silver protects PII while preserving data needed for later analytics. Names, emails, phone numbers, and card numbers are masked. Full addresses and exact dates of birth are removed. Email and phone tokens are created with SHA-256 and the `HASH_SALT` environment variable.

Files:
- `data/silver/customers_silver.csv`
- `data/silver/products_silver.csv`
- `data/silver/transactions_silver.csv`

### Gold layer
Gold contains analytics-ready datasets. It calculates age from the retained birth year, creates age groups and transaction amount buckets, generalizes postal codes such as `560103` to `560XXX`, and creates customer and sales summaries.

Files:
- `data/gold/customers_gold.csv`
- `data/gold/transactions_gold.csv`
- `data/gold/customer_summary.csv`
- `data/gold/sales_summary.csv`

## Privacy strategy
| Technique | Purpose | Status |
|---|---|---|
| Hard drop | Remove CVV before it reaches Bronze | Implemented |
| Data masking | Reduce visibility of names, emails, phones, and cards | Implemented |
| Data redaction | Remove the full customer address | Implemented |
| SHA-256 tokenization | Create deterministic email and phone identifiers | Implemented |
| Generalization | Remove exact DOB and generalize postal codes | Implemented |
| Aggregation | Create business summaries | Implemented |

Gold does not contain `date_of_birth`, CVV, card number, full address, raw email, or raw phone columns. This is an educational privacy implementation for synthetic data; it is not a claim of production-grade security.

## PostgreSQL integration
The Gold datasets are loaded into the following PostgreSQL tables using SQLAlchemy:

| Table | Description |
|---|---|
| `customers_gold` | Privacy-reduced customer analytics dataset |
| `transactions_gold` | Privacy-reduced transaction dataset |
| `customer_summary` | Spending and transaction summary by customer |
| `sales_summary` | Sales summary by product category |

The project uses `replace` mode for a simple, idempotent full-refresh load. It is appropriate for this internship project but not a replacement for production database migrations or incremental loading.

## Reports
The pipeline creates these files under `reports/`:

| Report | Purpose |
|---|---|
| `validation_report.txt` | Source validation findings before Bronze processing |
| `data_quality_report.txt` | Row counts, columns, missing values, duplicates, and quality status |
| `pipeline_metrics_report.txt` | Run ID, timing, layer row counts, and database load counts |
| `pipeline_summary.html` | Basic HTML execution summary |

Reports do not include database passwords, `HASH_SALT`, CVV, or raw payment details.

## Local setup
Prerequisites: Python 3.11+, Docker Desktop for the Docker option, and PostgreSQL only when running outside Docker.

### Windows PowerShell
```powershell
cd "C:\path\to\secure-retail-datalake"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set non-empty database credentials and `HASH_SALT` in `.env`. The file is ignored by Git and must never be committed.

Run the pipeline:
```powershell
python run_pipeline.py
python health_check.py
python -m pytest -q
```

The supported complete entry point is `python run_pipeline.py`. The internal modules are designed for reuse by the pipeline; running every layer script directly is not the supported workflow.

## Docker usage
Docker Compose starts PostgreSQL internally and runs the pipeline in a separate Python container. PostgreSQL has no host port mapping.

```bash
cp .env.example .env
# Edit .env and set secure values.

docker compose -p secure-retail-datalake build
docker compose -p secure-retail-datalake up -d postgres
docker compose -p secure-retail-datalake run --rm retail_pipeline python run_pipeline.py
docker compose -p secure-retail-datalake run --rm retail_pipeline python health_check.py
```

Create a backup:
```bash
docker compose -p secure-retail-datalake run --rm retail_pipeline python backup_database.py
```

The `postgres_data` volume persists the Secure Retail database. To stop only this project while preserving the database volume:
```bash
docker compose -p secure-retail-datalake down
```
Never use `down -v` unless deleting this project database is intentional.

## Azure Ubuntu VM deployment
This project is designed to coexist with other Docker applications on an Azure VM. Every command uses the isolated Compose project name `secure-retail-datalake`; the project does not stop, remove, or modify unrelated containers, volumes, networks, Fabric services, Nginx sites, or certificates.

```bash
git clone https://github.com/THE-S0HAM/secure-retail-datalake.git
cd secure-retail-datalake
chmod +x deploy/*.sh
./deploy/setup_vm.sh
```

Sign out and sign in again after Docker installation, then configure and deploy:
```bash
cp .env.example .env
nano .env
./deploy/deploy.sh
```

Azure recommendations:
- Use SSH keys and restrict port 22 to trusted IP ranges in the NSG.
- Do not expose PostgreSQL port 5432 publicly.
- Keep `.env` only on the VM.
- Use strong, unique database passwords and a long `HASH_SALT`.
- Do not overwrite `/etc/nginx/nginx.conf` or unrelated Nginx sites. This batch project does not require Nginx.

## Security notes
- Secrets are supplied through `.env`, never Python source code.
- `.env`, backups, logs, caches, and generated data are excluded from the Docker build context.
- `.env` and backup SQL files are ignored by Git.
- The Docker image includes `postgresql-client` so `pg_dump` is available for backups.
- PostgreSQL stays on the private Compose network; containers use the hostname `postgres`, not `localhost`.

## Learning outcomes and future scope
This project demonstrates Medallion Architecture, synthetic data generation, data quality validation, PII protection, SHA-256 tokenization, feature engineering, SQLAlchemy loading, PostgreSQL backups, Docker deployment, and automated reporting.

Possible future improvements include incremental loads, richer quality rules, Power BI/Tableau dashboards, Azure Key Vault, managed PostgreSQL, role-based access control, CI/CD, and monitoring.

## Author
**Soham Deshmukh**  
Celebal Excellence Internship 2026

## Acknowledgements
Thanks to Celebal Technologies, internship mentors, and the open-source communities behind Python, Pandas, SQLAlchemy, Faker, PostgreSQL, and Docker.

## License
Developed for educational and internship purposes. You may explore and adapt it for academic learning.
