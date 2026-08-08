"""Bronze layer: remove CVV and add basic lineage metadata."""
from datetime import datetime, timezone
import pandas as pd
from config.settings import BRONZE_DIR, ensure_directories


def create_bronze_layer(customers, products, transactions, run_id):
    """Write Bronze CSVs. CVV must never pass this boundary."""
    ensure_directories()
    ingested_at = datetime.now(timezone.utc).isoformat()
    bronze_transactions = transactions.drop(columns=["cvv"], errors="ignore").copy()
    if "cvv" in bronze_transactions.columns:
        raise ValueError("CVV hard-drop failed in Bronze layer")
    outputs = {"customers": customers.copy(), "products": products.copy(), "transactions": bronze_transactions}
    for name, frame in outputs.items():
        frame["ingestion_timestamp"] = ingested_at
        frame["run_id"] = run_id
        frame.to_csv(BRONZE_DIR / f"{name}_bronze.csv", index=False)
    return outputs


def load_bronze_layer():
    return {name: pd.read_csv(BRONZE_DIR / f"{name}_bronze.csv") for name in ("customers", "products", "transactions")}
