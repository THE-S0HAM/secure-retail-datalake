"""Generate repeatable synthetic retail customers."""
import random
import pandas as pd
from faker import Faker
from config.settings import RAW_DIR, get_count, ensure_directories

LOYALTY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]


def generate_customers(customer_count=None):
    """Create only adult customers so Gold age bands begin at 18."""
    customer_count = customer_count or get_count("CUSTOMER_COUNT", 1000)
    Faker.seed(42)
    random.seed(42)
    fake = Faker("en_IN")
    rows = []
    for number in range(1, customer_count + 1):
        first_name, last_name = fake.first_name(), fake.last_name()
        rows.append({
            "customer_id": f"C{number:05d}", "first_name": first_name, "last_name": last_name,
            "email": f"{first_name.lower()}.{last_name.lower()}{number}@example.com",
            "phone": fake.msisdn()[-10:], "address": fake.street_address(), "city": fake.city(),
            "state": fake.state(), "postal_code": fake.postcode()[-6:].zfill(6),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=75).isoformat(),
            "loyalty_tier": random.choice(LOYALTY_TIERS),
        })
    return pd.DataFrame(rows)


def save_customers(customers):
    ensure_directories()
    customers.to_csv(RAW_DIR / "customers.csv", index=False)


if __name__ == "__main__":
    save_customers(generate_customers())
    print("Generated customers")
