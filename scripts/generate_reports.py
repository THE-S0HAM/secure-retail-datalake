"""Create text and HTML reports from pipeline results."""
from datetime import datetime
from config.settings import REPORTS_DIR, ensure_directories


def privacy_checks(bronze, silver, gold):
    errors = []
    for name, data in [("Bronze", bronze), ("Silver", silver), ("Gold", gold)]:
        for frame_name, frame in data.items():
            if "cvv" in frame.columns: errors.append(f"{name} {frame_name} contains CVV")
    prohibited = {"date_of_birth", "card_number", "address", "email", "phone"}
    for frame_name, frame in gold.items():
        found = prohibited & set(frame.columns)
        if found: errors.append(f"Gold {frame_name} contains {sorted(found)}")
    customers = gold["customers_gold"]
    token_columns = {"email_token", "phone_token"}
    if not token_columns.issubset(customers.columns):
        errors.append("Gold customer tokens are missing")
    elif customers.empty or customers[list(token_columns)].isna().any().any() or (customers[list(token_columns)] == "").any().any():
        errors.append("Gold customer tokens contain empty values")
    return {"status": "FAIL" if errors else "PASS", "errors": errors}


def write_validation_report(validation):
    """Write source validation findings before Bronze processing."""
    ensure_directories()
    lines = ["SECURE RETAIL DATA LAKEHOUSE - VALIDATION REPORT", "", f"Validation status: {validation['status']}", "", *validation["findings"]]
    (REPORTS_DIR / "validation_report.txt").write_text("\n".join(lines), encoding="utf-8")


def write_data_quality_report(raw, validation, privacy):
    ensure_directories()
    lines = ["SECURE RETAIL DATA LAKEHOUSE - DATA QUALITY REPORT", ""]
    for name, frame in raw.items():
        lines += [f"Dataset: {name}", f"Rows: {len(frame)}", f"Columns: {len(frame.columns)}", f"Missing values: {int(frame.isna().sum().sum())}", f"Duplicates: {int(frame.duplicated().sum())}", ""]
    lines += ["Validation status: " + validation["status"], "Privacy checks: " + privacy["status"], "Overall status: " + ("PASS" if validation["status"] == privacy["status"] == "PASS" else "FAIL"), "", *validation["findings"], *privacy["errors"]]
    (REPORTS_DIR / "data_quality_report.txt").write_text("\n".join(lines), encoding="utf-8")


def write_pipeline_reports(metrics, raw, validation, privacy, database_status, output_files):
    metrics_lines = ["PIPELINE METRICS REPORT"] + [f"{key}: {value}" for key, value in metrics.items()] + [f"database status: {database_status}"]
    (REPORTS_DIR / "pipeline_metrics_report.txt").write_text("\n".join(metrics_lines), encoding="utf-8")
    statistics = "".join(f"<li>{name}: {len(frame)} rows</li>" for name, frame in raw.items())
    files = "".join(f"<li>{item}</li>" for item in output_files)
    status = "SUCCESS" if validation["status"] == privacy["status"] == "PASS" else "FAILED"
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Pipeline Summary</title><style>body{{font-family:Arial;margin:40px;color:#213547}}.pass{{color:#16803c;font-weight:bold}}li{{margin:6px 0}}</style></head><body><h1>Secure Retail Data Lakehouse</h1><p>Run ID: <b>{metrics['run_id']}</b></p><p class='pass'>Execution status: {status}</p><p>Execution time: {metrics['total_duration_seconds']} seconds</p><h2>Dataset statistics</h2><ul>{statistics}</ul><h2>Checks</h2><p>Data quality: {validation['status']} | Privacy: {privacy['status']} | Database: {database_status}</p><h2>Output files</h2><ul>{files}</ul><p>Generated: {datetime.now().isoformat()}</p></body></html>"""
    (REPORTS_DIR / "pipeline_summary.html").write_text(html, encoding="utf-8")
