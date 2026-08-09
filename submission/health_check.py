"""Check pipeline folders, environment, PostgreSQL, and Gold tables."""
import os
import sys

from database import TABLES, get_table_counts, verify_connection
from pipeline import BRONZE_DIR, GOLD_DIR, RAW_DIR, REPORTS_DIR, SILVER_DIR, ensure_directories


def show_check(name, passed, detail=""):
    suffix = f" ({detail})" if detail else ""
    print(f"{name:<22} {'PASS' if passed else 'FAIL'}{suffix}")
    return passed


def run_health_check():
    ensure_directories()
    checks = [show_check("Python", sys.version_info >= (3, 10))]
    folders = [RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, REPORTS_DIR]
    checks.append(show_check("Folders", all(path.is_dir() for path in folders)))
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "HASH_SALT"]
    checks.append(show_check("Environment", all(os.getenv(name) for name in required)))

    try:
        verify_connection()
    except Exception:
        checks.append(show_check("PostgreSQL", False, "connection failed"))
        checks.append(show_check("Gold tables", False, "database unavailable"))
    else:
        checks.append(show_check("PostgreSQL", True))
        try:
            counts = get_table_counts()
            tables_ok = set(counts) == set(TABLES) and all(count > 0 for count in counts.values())
            checks.append(show_check("Gold tables", tables_ok, str(counts)))
        except Exception:
            checks.append(show_check("Gold tables", False, "table check failed"))

    passed = all(checks)
    print(f"Overall Status: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_health_check() else 1)
