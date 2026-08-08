import scripts.bronze_layer as bronze_layer
import scripts.gold_layer as gold_layer
import scripts.silver_layer as silver_layer
from config.settings import db_url
from scripts.generators.generate_product_master import generate_products
from scripts.generators.generate_customers import generate_customers
from scripts.generators.generate_transactions import generate_transactions
from scripts.generators.validate_generated_data import validate_data
from scripts.generate_reports import privacy_checks


def source_data():
    products = generate_products(3)
    customers = generate_customers(3)
    transactions = generate_transactions(customers, products, 5)
    return customers, products, transactions


def configure_layer_outputs(monkeypatch, tmp_path):
    bronze_dir, silver_dir, gold_dir = tmp_path / "bronze", tmp_path / "silver", tmp_path / "gold"
    for directory in [bronze_dir, silver_dir, gold_dir]: directory.mkdir()
    monkeypatch.setattr(bronze_layer, "BRONZE_DIR", bronze_dir)
    monkeypatch.setattr(silver_layer, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(gold_layer, "GOLD_DIR", gold_dir)


def test_customer_generation():
    customers, _, _ = source_data()
    assert len(customers) == 3
    assert customers["customer_id"].is_unique
    assert {"email", "address", "date_of_birth"}.issubset(customers.columns)


def test_transaction_generation():
    customers, products, transactions = source_data()
    assert len(transactions) == 5
    assert set(transactions["customer_id"]).issubset(customers["customer_id"])
    assert set(transactions["product_id"]).issubset(products["product_id"])
    assert (transactions["transaction_amount"] > 0).all()


def test_validation():
    customers, products, transactions = source_data()
    assert validate_data(customers, products, transactions)["status"] == "PASS"


def test_validation_rejects_invalid_numeric_values():
    customers, products, transactions = source_data()
    transactions["quantity"] = transactions["quantity"].astype(object)
    transactions.loc[0, "quantity"] = "not-a-number"
    result = validate_data(customers, products, transactions)
    assert result["status"] == "FAIL"
    assert any("invalid quantity" in error for error in result["errors"])


def test_cvv_hard_drop(monkeypatch, tmp_path):
    configure_layer_outputs(monkeypatch, tmp_path)
    customers, products, transactions = source_data()
    bronze = bronze_layer.create_bronze_layer(customers, products, transactions, "run_test")
    assert "cvv" not in bronze["transactions"].columns
    assert {"run_id", "ingestion_timestamp"}.issubset(bronze["customers"].columns)


def test_email_masking():
    assert silver_layer.mask_email("john.doe@gmail.com") == "j***@gmail.com"
    assert silver_layer.mask_email("") == ""


def test_phone_masking():
    assert silver_layer.mask_phone("9876543210") == "******3210"
    assert silver_layer.mask_phone(None) == ""


def test_card_masking():
    assert silver_layer.mask_card("4111111111111111") == "************1111"


def test_address_redaction(monkeypatch, tmp_path):
    configure_layer_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "test-salt")
    customers, products, transactions = source_data()
    bronze = bronze_layer.create_bronze_layer(customers, products, transactions, "run_test")
    silver = silver_layer.create_silver_layer(bronze)
    assert "address" not in silver["customers"].columns
    assert "date_of_birth" not in silver["customers"].columns


def test_tokenization():
    assert silver_layer.tokenize("same@email.com", "salt") == silver_layer.tokenize("same@email.com", "salt")
    assert silver_layer.tokenize("", "salt") == ""


def test_database_url_encodes_special_characters(monkeypatch):
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "retail")
    monkeypatch.setenv("DB_USER", "retail_user")
    monkeypatch.setenv("DB_PASSWORD", "safe@password:with-special")
    url = db_url()
    assert url.password == "safe@password:with-special"
    assert "%40" in url.render_as_string(hide_password=False)


def test_gold_privacy(monkeypatch, tmp_path):
    configure_layer_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "test-salt")
    customers, products, transactions = source_data()
    bronze = bronze_layer.create_bronze_layer(customers, products, transactions, "run_test")
    silver = silver_layer.create_silver_layer(bronze)
    gold = gold_layer.create_gold_layer(silver)
    assert privacy_checks(bronze, silver, gold)["status"] == "PASS"
    assert "date_of_birth" not in gold["customers_gold"].columns


def test_privacy_rejects_empty_tokens(monkeypatch, tmp_path):
    configure_layer_outputs(monkeypatch, tmp_path)
    monkeypatch.setenv("HASH_SALT", "test-salt")
    customers, products, transactions = source_data()
    bronze = bronze_layer.create_bronze_layer(customers, products, transactions, "run_test")
    gold = gold_layer.create_gold_layer(silver_layer.create_silver_layer(bronze))
    gold["customers_gold"].loc[0, "phone_token"] = ""
    assert privacy_checks(bronze, {}, gold)["status"] == "FAIL"


def test_age_group():
    assert gold_layer.age_group(25) == "18-25"
    assert gold_layer.age_group(26) == "26-35"
    assert gold_layer.age_group(66) == "66+"


def test_transaction_bucket():
    assert gold_layer.transaction_bucket(500) == "0-500"
    assert gold_layer.transaction_bucket(501) == "501-1000"
    assert gold_layer.transaction_bucket(1001) == "1001-5000"
    assert gold_layer.transaction_bucket(5001) == "5001+"


def test_postal_code_generalization():
    assert gold_layer.generalize_postal_code("560103") == "560XXX"
    assert gold_layer.generalize_postal_code(400001) == "400XXX"
