"""Run the Secure Retail Data Lakehouse batch pipeline."""
import os
import sys
import time
from datetime import datetime
from config.settings import RAW_DIR, REPORTS_DIR, ensure_directories, get_run_id, configure_logging
from scripts.generators.generate_product_master import generate_products, save_products
from scripts.generators.generate_customers import generate_customers, save_customers
from scripts.generators.generate_transactions import generate_transactions, save_transactions
from scripts.generators.validate_generated_data import validate_data
from scripts.bronze_layer import create_bronze_layer
from scripts.silver_layer import create_silver_layer
from scripts.gold_layer import create_gold_layer
from scripts.database_loader import load_gold_data
from scripts.generate_reports import privacy_checks, write_data_quality_report, write_pipeline_reports
from health_check import run_health_check


def print_summary(run_id, stages, success, failed_stage="", reason=""):
    print("\n" + "=" * 56 + "\nSECURE RETAIL DATA LAKEHOUSE\n" + "=" * 56)
    print(f"Run ID: {run_id}")
    for name, status in stages.items(): print(f"{name:<28} {status}")
    print("=" * 56)
    if success: print("PIPELINE STATUS: SUCCESS")
    else: print(f"PIPELINE STATUS: FAILED\nFailed Stage: {failed_stage}\nReason: {reason}\nCheck: logs/pipeline.log")
    print("=" * 56)


def run_pipeline():
    ensure_directories()
    logger, run_id, started = configure_logging(), get_run_id(), time.perf_counter()
    started_at, stages = datetime.now().isoformat(), {}
    logger.info("Pipeline started | run_id=%s", run_id)
    raw = bronze = silver = gold = None
    database_status = "NOT RUN"
    current_stage = "Product Generation"
    try:
        products = generate_products(); save_products(products); stages["Product Generation"] = "PASS"
        current_stage = "Customer Generation"
        customers = generate_customers(); save_customers(customers); stages["Customer Generation"] = "PASS"
        current_stage = "Transaction Generation"
        transactions = generate_transactions(customers, products); save_transactions(transactions); stages["Transaction Generation"] = "PASS"
        raw = {"customers": customers, "products": products, "transactions": transactions}
        logger.info("Raw data written | customers=%s products=%s transactions=%s", len(customers), len(products), len(transactions))
        current_stage = "Validation"
        validation = validate_data(customers, products, transactions)
        if validation["status"] != "PASS":
            write_data_quality_report(raw, validation, {"status": "NOT RUN", "errors": []})
            raise ValueError("; ".join(validation["errors"]))
        stages["Validation"] = "PASS"
        current_stage = "Bronze Layer"
        bronze = create_bronze_layer(customers, products, transactions, run_id); stages["Bronze Layer"] = "PASS"
        current_stage = "Silver Layer"
        silver = create_silver_layer(bronze); stages["Silver Layer"] = "PASS"
        current_stage = "Gold Layer"
        gold = create_gold_layer(silver); stages["Gold Layer"] = "PASS"
        current_stage = "Privacy Checks"
        privacy = privacy_checks(bronze, silver, gold)
        if privacy["status"] != "PASS": raise ValueError("; ".join(privacy["errors"]))
        stages["Privacy Checks"] = "PASS"
        current_stage = "PostgreSQL Load"
        if os.getenv("DB_REQUIRED", "true").lower() == "true":
            database_counts = load_gold_data(gold)
            database_status = "PASS"
            stages["PostgreSQL Load"] = "PASS"
            logger.info("Database loaded | %s", database_counts)
            current_stage = "Final Health Check"
            if not run_health_check(): raise ValueError("PostgreSQL health check failed")
            stages["Final Health Check"] = "PASS"
        else:
            database_counts = {}
            database_status = "SKIPPED (DB_REQUIRED=false)"
            stages["PostgreSQL Load"] = "SKIPPED"
            stages["Final Health Check"] = "SKIPPED"
        current_stage = "Reports"
        metrics = {"run_id": run_id, "start_time": started_at, "end_time": datetime.now().isoformat(), "total_duration_seconds": round(time.perf_counter() - started, 2), "customers_generated": len(customers), "products_generated": len(products), "transactions_generated": len(transactions), "bronze_rows": sum(len(frame) for frame in bronze.values()), "silver_rows": sum(len(frame) for frame in silver.values()), "gold_rows": sum(len(frame) for frame in gold.values()), "database_rows_loaded": sum(database_counts.values()), "validation_status": validation["status"], "pipeline_status": "SUCCESS"}
        files = [str(path.relative_to(RAW_DIR.parent.parent)) for path in [RAW_DIR / "customers.csv", RAW_DIR / "products.csv", RAW_DIR / "transactions.csv"]]
        write_data_quality_report(raw, validation, privacy)
        write_pipeline_reports(metrics, raw, validation, privacy, database_status, files)
        stages["Reports"] = "PASS"
        logger.info("Pipeline completed | run_id=%s", run_id)
        print_summary(run_id, stages, True)
        return 0
    except Exception as error:
        (REPORTS_DIR / "pipeline_failure_report.txt").write_text(
            f"run_id: {run_id}\nfailed_stage: {current_stage}\nreason: {error}\n", encoding="utf-8"
        )
        logger.exception("Pipeline failed | run_id=%s | %s", run_id, error)
        print_summary(run_id, stages, False, current_stage, str(error))
        return 1


if __name__ == "__main__":
    sys.exit(run_pipeline())
