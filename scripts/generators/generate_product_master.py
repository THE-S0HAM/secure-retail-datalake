"""Generate a small, repeatable retail product master."""
import random
from pathlib import Path
import pandas as pd
from config.settings import RAW_DIR, MASTER_DATA_DIR, get_count, ensure_directories

CATEGORIES = ["Electronics", "Home & Kitchen", "Clothing", "Grocery", "Beauty"]
ADJECTIVES = ["Classic", "Premium", "Everyday", "Smart", "Comfort"]
ITEMS = ["Headphones", "Bottle", "T-Shirt", "Coffee", "Lamp", "Backpack", "Notebook"]


def generate_products(product_count=None):
    """Return products with stable IDs and realistic, bounded prices."""
    random.seed(42)
    product_count = product_count or get_count("PRODUCT_COUNT", 100)
    rows = []
    for number in range(1, product_count + 1):
        category = CATEGORIES[(number - 1) % len(CATEGORIES)]
        rows.append({
            "product_id": f"P{number:04d}",
            "product_name": f"{random.choice(ADJECTIVES)} {random.choice(ITEMS)} {number}",
            "category": category,
            "unit_price": round(random.uniform(50, 5000), 2),
        })
    return pd.DataFrame(rows)


def save_products(products):
    ensure_directories()
    products.to_csv(RAW_DIR / "products.csv", index=False)
    products.to_csv(MASTER_DATA_DIR / "products.csv", index=False)


if __name__ == "__main__":
    save_products(generate_products())
    print(f"Generated products at {Path(RAW_DIR) / 'products.csv'}")
