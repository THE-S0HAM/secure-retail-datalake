"""Generate synthetic transactions that always reference supplied master data."""
import random
import pandas as pd
from faker import Faker
from config.settings import RAW_DIR, get_count, ensure_directories

PAYMENT_METHODS = ["Credit Card", "Debit Card", "UPI", "Cash"]


def generate_transactions(customers, products, transaction_count=None):
    transaction_count = transaction_count or get_count("TRANSACTION_COUNT", 5000)
    Faker.seed(84)
    random.seed(84)
    fake = Faker("en_IN")
    product_lookup = products.set_index("product_id")["unit_price"].to_dict()
    rows = []
    for number in range(1, transaction_count + 1):
        product_id = random.choice(products["product_id"].tolist())
        quantity = random.randint(1, 5)
        unit_price = float(product_lookup[product_id])
        rows.append({
            "transaction_id": f"T{number:07d}", "customer_id": random.choice(customers["customer_id"].tolist()),
            "product_id": product_id, "transaction_date": fake.date_between(start_date="-2y", end_date="today").isoformat(),
            "quantity": quantity, "unit_price": unit_price, "transaction_amount": round(quantity * unit_price, 2),
            "payment_method": random.choice(PAYMENT_METHODS), "card_number": fake.credit_card_number(), "cvv": fake.credit_card_security_code(),
        })
    return pd.DataFrame(rows)


def save_transactions(transactions):
    ensure_directories()
    transactions.to_csv(RAW_DIR / "transactions.csv", index=False)


if __name__ == "__main__":
    print("Run this module through run_pipeline.py so source keys are available.")
