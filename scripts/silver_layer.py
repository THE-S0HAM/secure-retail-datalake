"""Silver layer privacy transformations."""
import hashlib
import os
import pandas as pd
from config.settings import SILVER_DIR, ensure_directories


def _value_or_empty(value):
    return "" if pd.isna(value) else str(value).strip()


def mask_email(value):
    value = _value_or_empty(value)
    if not value or "@" not in value: return ""
    local, domain = value.split("@", 1)
    return f"{local[:1]}***@{domain}"


def mask_phone(value):
    value = _value_or_empty(value)
    return "" if not value else "*" * max(0, len(value) - 4) + value[-4:]


def mask_card(value):
    value = _value_or_empty(value)
    return "" if not value else "*" * max(0, len(value) - 4) + value[-4:]


def tokenize(value, salt=None):
    value = _value_or_empty(value)
    salt = salt or os.getenv("HASH_SALT")
    if not value: return ""
    if not salt: raise ValueError("HASH_SALT must be set in .env")
    return hashlib.sha256(f"{salt}{value}".encode("utf-8")).hexdigest()


def create_silver_layer(bronze):
    ensure_directories()
    customers, products, transactions = bronze["customers"].copy(), bronze["products"].copy(), bronze["transactions"].copy()
    if "cvv" in transactions.columns: raise ValueError("CVV exists before Silver transformation")
    customers["email_token"] = customers["email"].apply(tokenize)
    customers["phone_token"] = customers["phone"].apply(tokenize)
    customers["first_name"] = customers["first_name"].apply(lambda item: "***" if _value_or_empty(item) else "")
    customers["last_name"] = customers["last_name"].apply(lambda item: "***" if _value_or_empty(item) else "")
    customers["email"] = customers["email"].apply(mask_email)
    customers["phone"] = customers["phone"].apply(mask_phone)
    # Keep only a birth year for later age analysis; remove the full birth date.
    customers["birth_year"] = pd.to_datetime(customers["date_of_birth"], errors="coerce").dt.year
    customers = customers.drop(columns=["address", "date_of_birth"], errors="ignore")
    transactions["card_number"] = transactions["card_number"].apply(mask_card)
    outputs = {"customers": customers, "products": products, "transactions": transactions}
    for name, frame in outputs.items(): frame.to_csv(SILVER_DIR / f"{name}_silver.csv", index=False)
    return outputs
