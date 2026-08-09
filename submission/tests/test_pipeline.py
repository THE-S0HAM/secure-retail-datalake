"""Tests for generation, validation, privacy, reports, and database URLs."""
import hashlib
import re

import pandas as pd
import pipeline
from sqlalchemy.engine import make_url
from database import build_database_url
from validation import privacy_checks, validate_data


def sample_data(customers=5, products=3, transactions=10):
    product_data = pipeline.generate_products(products)
    customer_data = pipeline.generate_customers(customers)
    transaction_data = pipeline.generate_transactions(customer_data, product_data, transactions)
    return customer_data, product_data, transaction_data


def use_temp_outputs(monkeypatch, tmp_path):
    for name in ["RAW_DIR", "BRONZE_DIR", "SILVER_DIR", "GOLD_DIR", "REPORTS_DIR", "LOGS_DIR"]:
        path = tmp_path / name.lower()
        path.mkdir()
        monkeypatch.setattr(pipeline, name, path)


def test_dynamic_generation_and_validation():
    customers, products, transactions = sample_data(7, 4, 13)
    assert (len(customers), len(products), len(transactions)) == (7, 4, 13)
    assert validate_data(customers, products, transactions)["status"] == "PASS"


def test_validation_rejects_bad_values():
    customers, products, transactions = sample_data()
    transactions["quantity"] = transactions["quantity"].astype(object)
    transactions.loc[0, "quantity"] = "bad"
    transactions.loc[1, "customer_id"] = "missing"
    result = validate_data(customers, products, transactions)
    assert result["status"] == "FAIL"
    assert any("quantity" in error for error in result["errors"])
    assert any("customer" in error for error in result["errors"])


def test_special_characters_in_database_password(monkeypatch):
    values = {"DB_HOST": "postgres", "DB_PORT": "5432", "DB_NAME": "retail", "DB_USER": "user@name", "DB_PASSWORD": "p@ss:/?#[]!$&'()*+,;="}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    url = build_database_url()
    assert "p%40ss%3A%2F%3F%23%5B%5D" in url
    assert "@postgres:5432/retail" in url
    parsed = make_url(url)
    assert parsed.username == values["DB_USER"]
    assert parsed.password == values["DB_PASSWORD"]

def test_medallion_privacy_and_tokens(monkeypatch, tmp_path):
    use_temp_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "unit-test-salt")
    customers, products, transactions = sample_data()
    raw_copy = transactions.copy(deep=True)
    bronze = pipeline.create_bronze(customers, products, transactions, "run_test")
    silver = pipeline.create_silver(bronze)
    gold = pipeline.create_gold(silver)

    assert transactions.equals(raw_copy)
    assert "cvv" not in bronze["transactions"]
    assert {"ingestion_timestamp", "run_id"}.issubset(bronze["customers"])
    assert silver["customers"]["first_name"].eq("***").all()
    assert silver["customers"]["email"].str.contains(r"^.{1}\*{3}@", regex=True).all()
    assert silver["transactions"]["card_number"].str.startswith("*").all()
    assert "address" not in silver["customers"]
    assert privacy_checks(bronze, silver, gold)["status"] == "PASS"

    tampered = {name: frame.copy() for name, frame in silver.items()}
    tampered["customers"].loc[0, "email_token"] = "0" * 64
    result = privacy_checks(bronze, tampered, gold)
    assert result["status"] == "FAIL"
    assert any("does not match Bronze source" in error for error in result["errors"])


def test_tokens_are_sha256_deterministic(monkeypatch):
    monkeypatch.setenv("HASH_SALT", "secret")
    expected = hashlib.sha256("secretperson@example.com".encode()).hexdigest()
    assert pipeline.create_token("Person@Example.com") == expected
    assert pipeline.create_token("person@example.com") == expected
    assert re.fullmatch(r"[a-f0-9]{64}", expected)


def test_gold_features(monkeypatch, tmp_path):
    use_temp_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "unit-test-salt")
    customers, products, transactions = sample_data()
    gold = pipeline.create_gold(pipeline.create_silver(pipeline.create_bronze(customers, products, transactions, "run_test")))
    customer_columns = set(gold["customers_gold"].columns)
    transaction_columns = set(gold["transactions_gold"].columns)
    assert {"age", "age_group"}.issubset(customer_columns)
    assert {"transaction_amount_bucket", "category"}.issubset(transaction_columns)
    assert gold["customers_gold"]["postal_code"].str.endswith("XXX").all()
    prohibited = {"date_of_birth", "cvv", "card_number", "email", "phone", "address"}
    assert not any(prohibited & set(frame.columns) for frame in gold.values())


def test_reports_do_not_expose_secrets(monkeypatch, tmp_path):
    use_temp_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "do-not-report-this")
    raw = {"customers": pd.DataFrame({"id": [1]}), "products": pd.DataFrame({"id": [1]}), "transactions": pd.DataFrame({"id": [1]})}
    validation = {"status": "PASS", "findings": ["PASS"], "errors": []}
    privacy = {"status": "PASS", "errors": []}
    metrics = {"pipeline_run_id": "run_test", "execution_time_seconds": 1.0, "gold_row_counts": {"customers_gold": 1}, "database_load_counts": {}}
    pipeline.generate_reports(raw, validation, privacy, metrics)
    text = "\n".join(path.read_text(encoding="utf-8") for path in pipeline.REPORTS_DIR.iterdir())
    assert "do-not-report-this" not in text
    assert "DB_PASSWORD" not in text


def test_amount_and_postal_buckets():
    assert pipeline.amount_bucket(500) == "0-500"
    assert pipeline.amount_bucket(501) == "501-1000"
    assert pipeline.amount_bucket(5001) == "5001+"
    assert pipeline.generalize_postal_code("560103") == "560XXX"

def test_full_file_pipeline_without_database(monkeypatch, tmp_path):
    use_temp_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "unit-test-salt")
    monkeypatch.setenv("DB_REQUIRED", "false")
    monkeypatch.setenv("CUSTOMER_COUNT", "6")
    monkeypatch.setenv("PRODUCT_COUNT", "4")
    monkeypatch.setenv("TRANSACTION_COUNT", "12")
    assert pipeline.run_pipeline() == 0
    assert len(pd.read_csv(pipeline.RAW_DIR / "customers.csv")) == 6
    assert len(pd.read_csv(pipeline.RAW_DIR / "products.csv")) == 4
    assert len(pd.read_csv(pipeline.RAW_DIR / "transactions.csv")) == 12
    assert {path.name for path in pipeline.REPORTS_DIR.iterdir()} == {
        "validation_report.txt", "data_quality_report.txt",
        "pipeline_metrics_report.txt", "pipeline_summary.html",
    }
