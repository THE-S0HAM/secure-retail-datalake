"""Data-quality and privacy checks for the retail pipeline."""
import hashlib
import os
import re

import pandas as pd

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TOKEN_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REQUIRED_COLUMNS = {
    "customers": {
        "customer_id", "first_name", "last_name", "email", "phone", "address",
        "city", "state", "postal_code", "date_of_birth", "loyalty_tier",
    },
    "products": {"product_id", "product_name", "category", "unit_price"},
    "transactions": {
        "transaction_id", "customer_id", "product_id", "transaction_date",
        "quantity", "unit_price", "transaction_amount", "payment_method",
        "card_number", "cvv",
    },
}


def _add_basic_errors(name, frame, required, errors):
    missing = required - set(frame.columns)
    if missing:
        errors.append(f"{name}: missing columns {sorted(missing)}")
        return
    if frame.empty:
        errors.append(f"{name}: dataset is empty")
    if frame.isna().any().any():
        errors.append(f"{name}: missing values found")
    if frame.duplicated().any():
        errors.append(f"{name}: duplicate rows found")


def validate_data(customers, products, transactions):
    datasets = {"customers": customers, "products": products, "transactions": transactions}
    errors = []
    for name, frame in datasets.items():
        _add_basic_errors(name, frame, REQUIRED_COLUMNS[name], errors)
    if errors:
        return _result(errors)

    for frame, column in [(customers, "customer_id"), (products, "product_id"), (transactions, "transaction_id")]:
        if not frame[column].is_unique:
            errors.append(f"{column}: duplicate values found")

    valid_email = customers["email"].astype(str).map(lambda value: bool(EMAIL_PATTERN.match(value)))
    if not valid_email.all():
        errors.append("customers: invalid email format")

    dates = pd.to_datetime(customers["date_of_birth"], errors="coerce")
    if dates.isna().any() or (dates.dt.date >= pd.Timestamp.today().date()).any():
        errors.append("customers: invalid date_of_birth values")

    transaction_dates = pd.to_datetime(transactions["transaction_date"], errors="coerce")
    if transaction_dates.isna().any() or (transaction_dates.dt.date > pd.Timestamp.today().date()).any():
        errors.append("transactions: invalid transaction_date values")

    numeric_rules = [
        (products, "unit_price", "products"),
        (transactions, "quantity", "transactions"),
        (transactions, "unit_price", "transactions"),
        (transactions, "transaction_amount", "transactions"),
    ]
    for frame, column, name in numeric_rules:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or (values <= 0).any():
            errors.append(f"{name}: invalid {column} values")

    if not set(transactions["customer_id"]).issubset(set(customers["customer_id"])):
        errors.append("transactions: unknown customer IDs")
    if not set(transactions["product_id"]).issubset(set(products["product_id"])):
        errors.append("transactions: unknown product IDs")

    expected_amount = pd.to_numeric(transactions["quantity"], errors="coerce") * pd.to_numeric(transactions["unit_price"], errors="coerce")
    actual_amount = pd.to_numeric(transactions["transaction_amount"], errors="coerce")
    if not expected_amount.round(2).equals(actual_amount.round(2)):
        errors.append("transactions: transaction amounts do not match quantity x unit price")
    return _result(errors)


def _result(errors):
    findings = [f"FAIL: {error}" for error in errors]
    if not findings:
        findings.append("PASS: all generated data checks passed")
    return {"status": "FAIL" if errors else "PASS", "errors": errors, "findings": findings}


def privacy_checks(bronze, silver, gold):
    errors = []
    for layer_name, layer in [("Bronze", bronze), ("Silver", silver), ("Gold", gold)]:
        for dataset_name, frame in layer.items():
            if "cvv" in frame.columns:
                errors.append(f"{layer_name} {dataset_name}: CVV found")

    silver_customers = silver.get("customers", pd.DataFrame())
    bronze_customers = bronze.get("customers", pd.DataFrame())
    if {"address", "date_of_birth"} & set(silver_customers.columns):
        errors.append("Silver customers: address or exact DOB found")

    required_masks = {"first_name", "last_name", "email", "phone"}
    if not required_masks.issubset(silver_customers.columns):
        errors.append("Silver customers: masked PII columns missing")
    elif not silver_customers.empty:
        if not silver_customers["first_name"].eq("***").all() or not silver_customers["last_name"].eq("***").all():
            errors.append("Silver customers: names are not fully masked")
        if not silver_customers["email"].astype(str).str.match(r"^.{1}\*{3}@[^@\s]+\.[^@\s]+$").all():
            errors.append("Silver customers: emails are not masked")
        if not silver_customers["phone"].astype(str).str.match(r"^\*+\d{4}$").all():
            errors.append("Silver customers: phone numbers are not masked")

    silver_transactions = silver.get("transactions", pd.DataFrame())
    if "card_number" not in silver_transactions.columns or silver_transactions.empty:
        errors.append("Silver transactions: masked card numbers missing")
    elif not silver_transactions["card_number"].astype(str).str.match(r"^\*+\d{4}$").all():
        errors.append("Silver transactions: card numbers are not masked")

    salt = os.getenv("HASH_SALT", "")
    for column, source_column in [("email_token", "email"), ("phone_token", "phone")]:
        if column not in silver_customers.columns:
            errors.append(f"Silver customers: {column} missing")
        elif not silver_customers[column].astype(str).map(lambda value: bool(TOKEN_PATTERN.fullmatch(value))).all():
            errors.append(f"Silver customers: invalid {column} values")
        elif not salt or source_column not in bronze_customers.columns or len(bronze_customers) != len(silver_customers):
            errors.append(f"Silver customers: unable to verify {column}")
        else:
            expected = bronze_customers[source_column].astype(str).str.strip().str.lower().map(
                lambda value: hashlib.sha256(f"{salt}{value}".encode("utf-8")).hexdigest()
            )
            if not expected.reset_index(drop=True).equals(silver_customers[column].reset_index(drop=True)):
                errors.append(f"Silver customers: {column} does not match Bronze source")

    prohibited = {"date_of_birth", "cvv", "card_number", "email", "phone", "address"}
    for dataset_name, frame in gold.items():
        leaked = prohibited & set(frame.columns)
        if leaked:
            errors.append(f"Gold {dataset_name}: sensitive columns found {sorted(leaked)}")

    gold_customers = gold.get("customers_gold", pd.DataFrame())
    for column in ["email_token", "phone_token"]:
        if column not in gold_customers.columns:
            errors.append(f"Gold customers: {column} missing")
        elif gold_customers.empty or not gold_customers[column].astype(str).map(lambda value: bool(TOKEN_PATTERN.match(value))).all():
            errors.append(f"Gold customers: invalid {column} values")
    return {"status": "FAIL" if errors else "PASS", "errors": errors}
