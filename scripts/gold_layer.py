"""Create analytics-ready Gold datasets without direct PII."""
from datetime import date
import pandas as pd
from config.settings import GOLD_DIR, ensure_directories


def age_group(age):
    for upper, label in [(25, "18-25"), (35, "26-35"), (45, "36-45"), (55, "46-55"), (65, "56-65")]:
        if age <= upper: return label
    return "66+"


def transaction_bucket(amount):
    if amount <= 500: return "0-500"
    if amount <= 1000: return "501-1000"
    if amount <= 5000: return "1001-5000"
    return "5001+"


def generalize_postal_code(value):
    value = str(value).split(".")[0]
    return value[:3] + "XXX" if value and value != "nan" else ""


def create_gold_layer(silver):
    ensure_directories()
    customers, products, transactions = silver["customers"].copy(), silver["products"].copy(), silver["transactions"].copy()
    birth_year = pd.to_numeric(customers.pop("birth_year"), errors="coerce")
    customers["age"] = (pd.Timestamp.today().year - birth_year).fillna(0).astype(int)
    customers["age_group"] = customers["age"].apply(age_group)
    customers["postal_code"] = customers["postal_code"].apply(generalize_postal_code)
    customers = customers.drop(columns=["email", "phone"], errors="ignore")
    transactions["transaction_amount_bucket"] = transactions["transaction_amount"].apply(transaction_bucket)
    transactions = transactions.drop(columns=["card_number"], errors="ignore")
    category_lookup = products[["product_id", "category"]]
    analytics_transactions = transactions.merge(category_lookup, on="product_id", how="left")
    customer_summary = analytics_transactions.groupby("customer_id", as_index=False).agg(total_spending=("transaction_amount", "sum"), average_transaction_amount=("transaction_amount", "mean"), transaction_count=("transaction_id", "count"))
    customer_summary = customer_summary.merge(customers[["customer_id", "loyalty_tier"]], on="customer_id", how="left")
    sales_summary = analytics_transactions.groupby("category", as_index=False).agg(number_of_transactions=("transaction_id", "count"), quantity_sold=("quantity", "sum"), total_sales=("transaction_amount", "sum"), average_sales=("transaction_amount", "mean"))
    # Aggregates receive the same lineage fields as the detailed Gold datasets.
    for frame in [customer_summary, sales_summary]:
        frame["run_id"] = customers["run_id"].iloc[0]
        frame["ingestion_timestamp"] = customers["ingestion_timestamp"].iloc[0]
    outputs = {"customers_gold": customers, "transactions_gold": analytics_transactions, "customer_summary": customer_summary, "sales_summary": sales_summary}
    for name, frame in outputs.items(): frame.to_csv(GOLD_DIR / f"{name}.csv", index=False)
    return outputs
