"""Check local prerequisites and PostgreSQL readiness."""
import os
import sys
from config.settings import ensure_directories, RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, REPORTS_DIR
from scripts.database_loader import required_tables_exist, verify_connection


def mark(label, result):
    print(f"{label:<22} {'PASS' if result else 'FAIL'}")
    return result


def run_health_check():
    ensure_directories()
    print("SECURE RETAIL DATA LAKEHOUSE HEALTH CHECK")
    checks = []
    checks.append(mark("Python", sys.version_info >= (3, 10)))
    checks.append(mark("Directories", all(path.exists() for path in [RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, REPORTS_DIR])))
    required_env = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "HASH_SALT"]
    checks.append(mark("Environment", all(os.getenv(name) for name in required_env)))
    try:
        checks.append(mark("PostgreSQL", verify_connection()))
        checks.append(mark("Tables", required_tables_exist()))
    except Exception as error:
        print(f"PostgreSQL             FAIL ({error})")
        print("Tables                 FAIL (database unavailable)")
        checks.extend([False, False])
    passed = all(checks)
    print(f"Overall Status: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    sys.exit(0 if run_health_check() else 1)
