import sys
import os
import pytest
import pandas as pd

# Add scripts directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from data_quality import DataQualityValidator, DataQualityError

@pytest.fixture
def valid_dim_users():
    return pd.DataFrame([
        {"user_id": "USR-0001", "masked_user_name": "B**** P****", "masked_phone": "0812****5678", "phone_hash": "abc123hash"},
        {"user_id": "USR-0002", "masked_user_name": "A**** W****", "masked_phone": "0819****1234", "phone_hash": "def456hash"}
    ])

@pytest.fixture
def valid_dim_merchants():
    return pd.DataFrame([
        {"merchant_id": "MCH-001", "merchant_name": "Kopi Kenangan", "merchant_category": "F&B"},
        {"merchant_id": "MCH-002", "merchant_name": "Indomaret", "merchant_category": "Retail"}
    ])

@pytest.fixture
def valid_fact_transactions():
    return pd.DataFrame([
        {
            "transaction_id": "TX-1001", "user_id": "USR-0001", "merchant_id": "MCH-001",
            "amount": 50000.0, "payment_method": "QRIS", "status": "SUCCESS",
            "timestamp": "2026-08-01 10:00:00", "transaction_date": "2026-08-01"
        },
        {
            "transaction_id": "TX-1002", "user_id": "USR-0002", "merchant_id": "MCH-002",
            "amount": 125000.0, "payment_method": "E-WALLET_BALANCE", "status": "FAILED",
            "timestamp": "2026-08-01 11:30:00", "transaction_date": "2026-08-01"
        }
    ])

def test_uniqueness_validation(valid_dim_users):
    validator = DataQualityValidator()
    # 1. Valid unique case (should pass)
    validator.check_uniqueness(valid_dim_users, 'user_id', table_name='dim_users')

    # 2. Duplicate case (should raise DataQualityError)
    duplicate_users = pd.concat([valid_dim_users, valid_dim_users.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataQualityError, match="Uniqueness check failed"):
        validator.check_uniqueness(duplicate_users, 'user_id', table_name='dim_users')

def test_completeness_validation(valid_fact_transactions):
    validator = DataQualityValidator()
    # 1. Valid complete case (should pass)
    validator.check_completeness(valid_fact_transactions, ['transaction_id', 'amount', 'status'])

    # 2. Missing/Null case (should raise DataQualityError)
    incomplete_facts = valid_fact_transactions.copy()
    incomplete_facts.loc[0, 'amount'] = None
    with pytest.raises(DataQualityError, match="Completeness check failed"):
        validator.check_completeness(incomplete_facts, ['transaction_id', 'amount', 'status'])

def test_validity_amount_and_status(valid_fact_transactions):
    validator = DataQualityValidator()
    # 1. Valid case (should pass)
    validator.check_validity(valid_fact_transactions)

    # 2. Invalid amount <= 0 (should raise DataQualityError)
    invalid_amount_facts = valid_fact_transactions.copy()
    invalid_amount_facts.loc[0, 'amount'] = -10000.0
    with pytest.raises(DataQualityError, match="amount <= 0"):
        validator.check_validity(invalid_amount_facts)

    # 3. Invalid status (should raise DataQualityError)
    invalid_status_facts = valid_fact_transactions.copy()
    invalid_status_facts.loc[0, 'status'] = 'UNKNOWN_STATUS'
    with pytest.raises(DataQualityError, match="invalid status"):
        validator.check_validity(invalid_status_facts)

def test_pii_masking_validation(valid_dim_users):
    validator = DataQualityValidator()
    # 1. Valid masked case (should pass)
    validator.check_pii_masking(valid_dim_users)

    # 2. Unmasked phone number leakage (should raise DataQualityError)
    leaked_pii_users = valid_dim_users.copy()
    leaked_pii_users.loc[0, 'masked_phone'] = '081234567890'
    with pytest.raises(DataQualityError, match="PII"):
        validator.check_pii_masking(leaked_pii_users)

def test_validate_all_end_to_end(valid_dim_users, valid_dim_merchants, valid_fact_transactions):
    validator = DataQualityValidator()
    # Should pass without throwing exceptions
    validator.validate_all(valid_dim_users, valid_dim_merchants, valid_fact_transactions)

if __name__ == "__main__":
    pytest.main(["-v", __file__])

