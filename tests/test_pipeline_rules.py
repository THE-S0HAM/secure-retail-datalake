import os
from scripts.generators.generate_product_master import generate_products
from scripts.generators.generate_customers import generate_customers
from scripts.generators.generate_transactions import generate_transactions
from scripts.generators.validate_generated_data import validate_data
from scripts.bronze_layer import create_bronze_layer
from scripts.silver_layer import create_silver_layer, mask_email, mask_phone, mask_card, tokenize
from scripts.gold_layer import age_group, transaction_bucket, generalize_postal_code, create_gold_layer
from scripts.generate_reports import privacy_checks


def source_data():
    products = generate_products(3)
    customers = generate_customers(3)
    transactions = generate_transactions(customers, products, 5)
    return customers, products, transactions


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
    result = validate_data(customers, products, transactions)
    assert result["status"] == "PASS"


def test_cvv_hard_drop():
    customers, products, transactions = source_data()
    bronze = create_bronze_layer(customers, products, transactions, "run_test")
    assert "cvv" not in bronze["transactions"].columns
    assert "run_id" in bronze["customers"].columns


def test_email_masking():
    assert mask_email("john.doe@gmail.com") == "j***@gmail.com"
    assert mask_email("") == ""


def test_phone_masking():
    assert mask_phone("9876543210") == "******3210"
    assert mask_phone(None) == ""


def test_card_masking():
    assert mask_card("4111111111111111") == "************1111"


def test_address_redaction(monkeypatch):
    monkeypatch.setenv("HASH_SALT", "test-salt")
    customers, products, transactions = source_data()
    silver = create_silver_layer(create_bronze_layer(customers, products, transactions, "run_test"))
    assert "address" not in silver["customers"].columns


def test_tokenization():
    assert tokenize("same@email.com", "salt") == tokenize("same@email.com", "salt")
    assert tokenize("", "salt") == ""


def test_gold_privacy(monkeypatch):
    monkeypatch.setenv("HASH_SALT", "test-salt")
    customers, products, transactions = source_data()
    bronze = create_bronze_layer(customers, products, transactions, "run_test")
    silver = create_silver_layer(bronze)
    gold = create_gold_layer(silver)
    result = privacy_checks(bronze, silver, gold)
    assert result["status"] == "PASS"
    assert "date_of_birth" not in gold["customers_gold"].columns


def test_age_group():
    assert age_group(25) == "18-25"
    assert age_group(26) == "26-35"
    assert age_group(66) == "66+"


def test_transaction_bucket():
    assert transaction_bucket(500) == "0-500"
    assert transaction_bucket(501) == "501-1000"
    assert transaction_bucket(1001) == "1001-5000"
    assert transaction_bucket(5001) == "5001+"


def test_postal_code_generalization():
    assert generalize_postal_code("560103") == "560XXX"
    assert generalize_postal_code(400001) == "400XXX"
