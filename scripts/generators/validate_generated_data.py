"""Validate source data before it is allowed into Bronze."""
import re
import pandas as pd

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED = {
    "customers": {"customer_id", "first_name", "last_name", "email", "phone", "address", "city", "state", "postal_code", "date_of_birth", "loyalty_tier"},
    "products": {"product_id", "product_name", "category", "unit_price"},
    "transactions": {"transaction_id", "customer_id", "product_id", "transaction_date", "quantity", "unit_price", "transaction_amount", "payment_method", "card_number", "cvv"},
}


def validate_data(customers, products, transactions):
    """Return readable findings. Errors are critical and stop the pipeline."""
    findings, errors, warnings = [], [], []
    datasets = {"customers": customers, "products": products, "transactions": transactions}
    for name, frame in datasets.items():
        missing_columns = REQUIRED[name] - set(frame.columns)
        if missing_columns:
            errors.append(f"{name}: missing columns {sorted(missing_columns)}")
    if errors:
        findings.extend(f"FAIL: {item}" for item in errors)
        return {"status": "FAIL", "findings": findings, "errors": errors, "warnings": warnings}
    for name, frame in datasets.items():
        if frame.isnull().any().any(): errors.append(f"{name}: null values found")
        if frame.duplicated().any(): warnings.append(f"{name}: duplicate full records found")
    for frame, id_name in [(customers, "customer_id"), (products, "product_id"), (transactions, "transaction_id")]:
        if not frame[id_name].is_unique: errors.append(f"{id_name}: values are not unique")
    if not customers["email"].fillna("").map(lambda value: bool(EMAIL_PATTERN.match(str(value)))).all(): errors.append("customers: invalid email format")
    for column, frame, label, allow_zero in [("unit_price", products, "products", False), ("unit_price", transactions, "transactions", False), ("transaction_amount", transactions, "transactions", True), ("quantity", transactions, "transactions", False)]:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or ((values < 0) if allow_zero else (values <= 0)).any(): errors.append(f"{label}: invalid {column} values found")
    if not set(transactions["customer_id"]).issubset(set(customers["customer_id"])): errors.append("transactions: invalid customer relationship")
    if not set(transactions["product_id"]).issubset(set(products["product_id"])): errors.append("transactions: invalid product relationship")
    if pd.to_datetime(transactions["transaction_date"], errors="coerce").isna().any(): errors.append("transactions: invalid dates found")
    findings.extend([f"FAIL: {item}" for item in errors] + [f"WARNING: {item}" for item in warnings])
    if not findings: findings.append("PASS: all raw data checks passed")
    return {"status": "FAIL" if errors else "PASS", "findings": findings, "errors": errors, "warnings": warnings}
