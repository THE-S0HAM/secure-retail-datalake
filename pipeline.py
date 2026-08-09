"""Secure Retail Data Lakehouse: Raw to Bronze to Silver to Gold."""
import hashlib
import logging
import os
import random
import time
import uuid
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from faker import Faker

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR = ROOT / "logs"

CATEGORIES = ["Electronics", "Home & Kitchen", "Clothing", "Grocery", "Beauty"]
PRODUCT_NAMES = ["Headphones", "Bottle", "T-Shirt", "Coffee", "Lamp", "Backpack", "Notebook"]
PAYMENT_METHODS = ["Credit Card", "Debit Card", "UPI", "Cash"]


def ensure_directories():
    for path in [RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, REPORTS_DIR, LOGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def get_count(name, default):
    value = int(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def get_run_id():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{stamp}_{uuid.uuid4().hex[:8]}"

def generate_products(count=None):
    count = get_count("PRODUCT_COUNT", 100) if count is None else count
    if count <= 0:
        raise ValueError("Product count must be greater than zero")
    random.seed(42)
    rows = []
    for number in range(1, count + 1):
        rows.append({
            "product_id": f"P{number:04d}",
            "product_name": f"{random.choice(['Classic', 'Premium', 'Everyday', 'Smart'])} {random.choice(PRODUCT_NAMES)} {number}",
            "category": CATEGORIES[(number - 1) % len(CATEGORIES)],
            "unit_price": round(random.uniform(50, 5000), 2),
        })
    return pd.DataFrame(rows)


def generate_customers(count=None):
    count = get_count("CUSTOMER_COUNT", 1000) if count is None else count
    if count <= 0:
        raise ValueError("Customer count must be greater than zero")
    Faker.seed(42)
    random.seed(42)
    fake = Faker("en_IN")
    rows = []
    for number in range(1, count + 1):
        first_name = fake.first_name()
        last_name = fake.last_name()
        rows.append({
            "customer_id": f"C{number:05d}", "first_name": first_name, "last_name": last_name,
            "email": f"{first_name.lower()}.{last_name.lower()}{number}@example.com",
            "phone": fake.msisdn()[-10:], "address": fake.street_address(),
            "city": fake.city(), "state": fake.state(),
            "postal_code": fake.postcode()[-6:].zfill(6),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=75).isoformat(),
            "loyalty_tier": random.choice(["Bronze", "Silver", "Gold", "Platinum"]),
        })
    return pd.DataFrame(rows)

def generate_transactions(customers, products, count=None):
    count = get_count("TRANSACTION_COUNT", 5000) if count is None else count
    if count <= 0 or customers.empty or products.empty:
        raise ValueError("Transactions need positive counts and non-empty master data")
    Faker.seed(84)
    random.seed(84)
    fake = Faker("en_IN")
    customer_ids = customers["customer_id"].tolist()
    product_prices = products.set_index("product_id")["unit_price"].to_dict()
    rows = []
    for number in range(1, count + 1):
        product_id = random.choice(list(product_prices))
        quantity = random.randint(1, 5)
        unit_price = float(product_prices[product_id])
        rows.append({
            "transaction_id": f"T{number:07d}",
            "customer_id": random.choice(customer_ids),
            "product_id": product_id,
            "transaction_date": fake.date_between(start_date="-2y", end_date="today").isoformat(),
            "quantity": quantity, "unit_price": unit_price,
            "transaction_amount": round(quantity * unit_price, 2),
            "payment_method": random.choice(PAYMENT_METHODS),
            "card_number": fake.credit_card_number(),
            "cvv": fake.credit_card_security_code(),
        })
    return pd.DataFrame(rows)


def generate_data():
    """Generate and save source data without changing it."""
    ensure_directories()
    products = generate_products()
    customers = generate_customers()
    transactions = generate_transactions(customers, products)
    raw = {"customers": customers, "products": products, "transactions": transactions}
    for name, frame in raw.items():
        frame.to_csv(RAW_DIR / f"{name}.csv", index=False)
    return raw


def create_bronze(customers, products, transactions, run_id):
    """Remove CVV and add lineage columns."""
    outputs = {
        "customers": customers.copy(),
        "products": products.copy(),
        "transactions": transactions.drop(columns=["cvv"], errors="ignore").copy(),
    }
    ingested_at = datetime.now(timezone.utc).isoformat()
    for name, frame in outputs.items():
        frame["ingestion_timestamp"] = ingested_at
        frame["run_id"] = run_id
        frame.to_csv(BRONZE_DIR / f"{name}_bronze.csv", index=False)
    return outputs

def _text(value):
    return "" if pd.isna(value) else str(value).strip()


def mask_email(value):
    value = _text(value)
    if "@" not in value:
        return ""
    local, domain = value.split("@", 1)
    return f"{local[:1]}***@{domain}"


def mask_last_four(value):
    value = _text(value)
    return "" if not value else "*" * max(0, len(value) - 4) + value[-4:]


def create_token(value):
    value = _text(value).lower()
    salt = os.getenv("HASH_SALT", "")
    if not value:
        return ""
    if not salt:
        raise ValueError("HASH_SALT must be set")
    return hashlib.sha256(f"{salt}{value}".encode("utf-8")).hexdigest()


def create_silver(bronze):
    """Mask PII, redact addresses, and create secure tokens."""
    customers = bronze["customers"].copy()
    products = bronze["products"].copy()
    transactions = bronze["transactions"].copy()
    if "cvv" in transactions.columns:
        raise ValueError("CVV must not enter Silver")

    customers["email_token"] = customers["email"].apply(create_token)
    customers["phone_token"] = customers["phone"].apply(create_token)
    customers["first_name"] = customers["first_name"].map(lambda value: "***" if _text(value) else "")
    customers["last_name"] = customers["last_name"].map(lambda value: "***" if _text(value) else "")
    customers["email"] = customers["email"].apply(mask_email)
    customers["phone"] = customers["phone"].apply(mask_last_four)
    customers["birth_year"] = pd.to_datetime(customers["date_of_birth"], errors="raise").dt.year
    customers = customers.drop(columns=["address", "date_of_birth"])
    transactions["card_number"] = transactions["card_number"].apply(mask_last_four)

    outputs = {"customers": customers, "products": products, "transactions": transactions}
    for name, frame in outputs.items():
        frame.to_csv(SILVER_DIR / f"{name}_silver.csv", index=False)
    return outputs


def age_group(age):
    for upper, label in [(25, "18-25"), (35, "26-35"), (45, "36-45"), (55, "46-55"), (65, "56-65")]:
        if age <= upper:
            return label
    return "66+"

def amount_bucket(amount):
    if amount <= 500:
        return "0-500"
    if amount <= 1000:
        return "501-1000"
    if amount <= 5000:
        return "1001-5000"
    return "5001+"


def generalize_postal_code(value):
    value = _text(value).split(".")[0]
    return f"{value[:3]}XXX" if value else ""


def create_gold(silver):
    """Create privacy-reduced analytical datasets and summaries."""
    customers = silver["customers"].copy()
    products = silver["products"].copy()
    transactions = silver["transactions"].copy()

    birth_year = pd.to_numeric(customers.pop("birth_year"), errors="raise")
    customers["age"] = date.today().year - birth_year
    customers["age_group"] = customers["age"].apply(age_group)
    customers["postal_code"] = customers["postal_code"].apply(generalize_postal_code)
    customers = customers.drop(columns=["first_name", "last_name", "email", "phone"], errors="ignore")

    transactions["transaction_amount_bucket"] = transactions["transaction_amount"].apply(amount_bucket)
    transactions = transactions.drop(columns=["card_number"], errors="ignore")
    transactions = transactions.merge(products[["product_id", "category"]], on="product_id", how="left")
    if transactions["category"].isna().any():
        raise ValueError("A transaction has no matching product category")

    customer_summary = transactions.groupby("customer_id", as_index=False).agg(
        total_spending=("transaction_amount", "sum"),
        average_transaction_amount=("transaction_amount", "mean"),
        transaction_count=("transaction_id", "count"),
    )
    customer_summary = customer_summary.merge(
        customers[["customer_id", "loyalty_tier"]], on="customer_id", how="left"
    )
    sales_summary = transactions.groupby("category", as_index=False).agg(
        number_of_transactions=("transaction_id", "count"),
        quantity_sold=("quantity", "sum"),
        total_sales=("transaction_amount", "sum"),
        average_sales=("transaction_amount", "mean"),
    )

    for frame in [customer_summary, sales_summary]:
        frame["run_id"] = customers["run_id"].iloc[0]
        frame["ingestion_timestamp"] = customers["ingestion_timestamp"].iloc[0]

    outputs = {
        "customers_gold": customers,
        "transactions_gold": transactions,
        "customer_summary": customer_summary,
        "sales_summary": sales_summary,
    }
    for name, frame in outputs.items():
        frame.to_csv(GOLD_DIR / f"{name}.csv", index=False)
    return outputs


def _dataset_quality(raw):
    lines = []
    for name, frame in raw.items():
        lines.extend([
            f"Dataset: {name}",
            f"Rows: {len(frame)}",
            f"Missing values: {int(frame.isna().sum().sum())}",
            f"Duplicate rows: {int(frame.duplicated().sum())}",
            "",
        ])
    return lines


def generate_reports(raw, validation, privacy, metrics):
    """Write validation, quality, metrics, and HTML reports."""
    ensure_directories()
    validation_lines = [
        "SECURE RETAIL DATA LAKEHOUSE - VALIDATION REPORT", "",
        f"Pipeline run ID: {metrics['pipeline_run_id']}",
        f"Validation status: {validation['status']}", "", *validation["findings"],
    ]
    (REPORTS_DIR / "validation_report.txt").write_text("\n".join(validation_lines), encoding="utf-8")

    quality_lines = [
        "SECURE RETAIL DATA LAKEHOUSE - DATA QUALITY REPORT", "",
        f"Pipeline run ID: {metrics['pipeline_run_id']}", "",
        *_dataset_quality(raw),
        f"Validation status: {validation['status']}",
        f"Privacy status: {privacy['status']}",
        f"Overall status: {'PASS' if validation['status'] == privacy['status'] == 'PASS' else 'FAIL'}",
    ]
    (REPORTS_DIR / "data_quality_report.txt").write_text("\n".join(quality_lines), encoding="utf-8")

    metric_lines = ["SECURE RETAIL DATA LAKEHOUSE - PIPELINE METRICS", ""]
    for key, value in metrics.items():
        metric_lines.append(f"{key}: {value}")
    (REPORTS_DIR / "pipeline_metrics_report.txt").write_text("\n".join(metric_lines), encoding="utf-8")

    gold_items = "".join(
        f"<li>{escape(name)}: {count}</li>" for name, count in metrics["gold_row_counts"].items()
    )
    database_items = "".join(
        f"<li>{escape(name)}: {count}</li>" for name, count in metrics["database_load_counts"].items()
    ) or "<li>Skipped</li>"

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Pipeline Summary</title>
<style>body{{font-family:Arial;margin:40px;color:#213547}}.pass{{color:#16803c}}</style></head>
<body><h1>Secure Retail Data Lakehouse</h1>
<p>Run ID: <b>{escape(metrics['pipeline_run_id'])}</b></p>
<p class="pass">Status: SUCCESS</p>
<p>Execution time: {metrics['execution_time_seconds']} seconds</p>
<h2>Gold row counts</h2><ul>{gold_items}</ul>
<h2>Database load counts</h2><ul>{database_items}</ul>
<p>Validation: {validation['status']} | Privacy: {privacy['status']}</p>
</body></html>"""
    (REPORTS_DIR / "pipeline_summary.html").write_text(html, encoding="utf-8")


def configure_logging():
    ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOGS_DIR / "pipeline.log"), logging.StreamHandler()],
        force=True,
    )
    return logging.getLogger("secure_retail")


def run_pipeline():
    """Run the complete batch pipeline in a clear stage order."""
    from database import load_to_postgres
    from validation import privacy_checks, validate_data

    started = time.perf_counter()
    run_id = get_run_id()
    logger = configure_logging()
    logger.info("Pipeline started | run_id=%s", run_id)
    try:
        raw = generate_data()
        validation = validate_data(raw["customers"], raw["products"], raw["transactions"])
        if validation["status"] != "PASS":
            raise ValueError("; ".join(validation["errors"]))

        bronze = create_bronze(raw["customers"], raw["products"], raw["transactions"], run_id)
        silver = create_silver(bronze)
        gold = create_gold(silver)
        privacy = privacy_checks(bronze, silver, gold)
        if privacy["status"] != "PASS":
            raise ValueError("; ".join(privacy["errors"]))

        database_counts = {}
        if os.getenv("DB_REQUIRED", "true").lower() == "true":
            database_counts = load_to_postgres(gold)
        metrics = {
            "pipeline_run_id": run_id,
            "execution_time_seconds": round(time.perf_counter() - started, 2),
            "raw_row_counts": {name: len(frame) for name, frame in raw.items()},
            "bronze_row_counts": {name: len(frame) for name, frame in bronze.items()},
            "silver_row_counts": {name: len(frame) for name, frame in silver.items()},
            "gold_row_counts": {name: len(frame) for name, frame in gold.items()},
            "database_load_counts": database_counts,
            "validation_status": validation["status"],
            "privacy_status": privacy["status"],
        }
        generate_reports(raw, validation, privacy, metrics)
        logger.info("Pipeline completed | run_id=%s", run_id)
        print(f"Pipeline completed successfully. Run ID: {run_id}")
        return 0
    except Exception:
        logger.exception("Pipeline failed | run_id=%s", run_id)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_pipeline())
