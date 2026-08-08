import re
import pandas as pd

class DataQualityError(Exception):
    """Custom exception raised when a Data Quality rule validation fails."""
    pass

class DataQualityValidator:
    """Engine for validating Data Quality 5 Gold Rules before DWH Load."""

    @staticmethod
    def check_uniqueness(df: pd.DataFrame, column_name: str, table_name: str = "table"):
        """Rule 1: Uniqueness Check - Ensure Primary Keys contain no duplicates."""
        if df is None or df.empty:
            return
        if not df[column_name].is_unique:
            duplicate_count = df[column_name].duplicated().sum()
            raise DataQualityError(
                f"❌ [DQ FAIL] Uniqueness check failed for `{table_name}.{column_name}`. "
                f"Found {duplicate_count} duplicate key(s)!"
            )
        print(f"   ✓ [DQ PASS] Uniqueness verified for `{table_name}.{column_name}`.")

    @staticmethod
    def check_completeness(df: pd.DataFrame, required_columns: list, table_name: str = "table"):
        """Rule 2: Completeness Check - Ensure required critical columns have no NULL values."""
        if df is None or df.empty:
            return
        for col in required_columns:
            if col not in df.columns:
                raise DataQualityError(f"❌ [DQ FAIL] Required column `{col}` missing in `{table_name}`!")
            null_count = df[col].isnull().sum()
            if null_count > 0:
                raise DataQualityError(
                    f"❌ [DQ FAIL] Completeness check failed for `{table_name}.{col}`. "
                    f"Found {null_count} NULL/missing value(s)!"
                )
        print(f"   ✓ [DQ PASS] Completeness verified for `{table_name}` ({', '.join(required_columns)}).")

    @staticmethod
    def check_validity(fact_df: pd.DataFrame):
        """Rule 3 & 5: Validity & Range Check - Ensure amounts are positive and status values are valid."""
        if fact_df is None or fact_df.empty:
            return
        
        # 1. Check positive amount
        invalid_amounts = (fact_df['amount'] <= 0).sum()
        if invalid_amounts > 0:
            raise DataQualityError(
                f"❌ [DQ FAIL] Validity check failed for `fact_transactions.amount`. "
                f"Found {invalid_amounts} record(s) with amount <= 0!"
            )
        
        # 2. Check valid transaction status
        valid_statuses = {'SUCCESS', 'FAILED', 'PENDING'}
        actual_statuses = set(fact_df['status'].dropna().unique())
        invalid_statuses = actual_statuses - valid_statuses
        if invalid_statuses:
            raise DataQualityError(
                f"❌ [DQ FAIL] Validity check failed for `fact_transactions.status`. "
                f"Found invalid status value(s): {invalid_statuses}"
            )
        
        print("   ✓ [DQ PASS] Validity verified for `fact_transactions` (amount > 0 and valid status values).")

    @staticmethod
    def check_pii_masking(users_df: pd.DataFrame):
        """Rule 4: PII Privacy Check - Ensure phone numbers & names are masked and no raw numbers leak."""
        if users_df is None or users_df.empty:
            return
        
        # Regex to detect unmasked raw Indonesian phone numbers (e.g. 08123456789 or 628123456789)
        raw_phone_pattern = re.compile(r'^(?:\+?62|0)\d{8,12}$')
        
        for idx, row in users_df.iterrows():
            phone = str(row.get('masked_phone', ''))
            name = str(row.get('masked_user_name', ''))
            
            # Check 1: Phone must contain masking asterisks
            if '****' not in phone:
                raise DataQualityError(
                    f"❌ [DQ FAIL] PII Privacy check failed for user_id `{row.get('user_id')}`. "
                    f"Phone number is not masked: `{phone}`"
                )
            
            # Check 2: Phone must not be an unmasked raw number
            if raw_phone_pattern.match(phone):
                raise DataQualityError(
                    f"❌ [DQ FAIL] PII Leakage detected for user_id `{row.get('user_id')}`. "
                    f"Raw phone number exposed: `{phone}`!"
                )
            
            # Check 3: Masked name should also contain asterisks or initials
            if '****' not in name:
                raise DataQualityError(
                    f"❌ [DQ FAIL] PII Privacy check failed for user_id `{row.get('user_id')}`. "
                    f"User name is not masked: `{name}`"
                )

        print("   ✓ [DQ PASS] PII Protection verified for `dim_users` (all phones & names masked).")

    def validate_all(self, dim_users: pd.DataFrame, dim_merchants: pd.DataFrame, fact_transactions: pd.DataFrame):
        """Run all 5 Gold Rules validation across Star Schema Data Warehouse tables."""
        print("🛡️ [DQ ENGINE] Starting Data Quality validation checks...")
        
        # 1. Uniqueness Checks
        self.check_uniqueness(dim_users, 'user_id', table_name='dim_users')
        self.check_uniqueness(dim_merchants, 'merchant_id', table_name='dim_merchants')
        self.check_uniqueness(fact_transactions, 'transaction_id', table_name='fact_transactions')
        
        # 2. Completeness Checks
        self.check_completeness(dim_users, ['user_id', 'masked_user_name', 'masked_phone'], table_name='dim_users')
        self.check_completeness(dim_merchants, ['merchant_id', 'merchant_name', 'merchant_category'], table_name='dim_merchants')
        self.check_completeness(fact_transactions, ['transaction_id', 'user_id', 'merchant_id', 'amount', 'status'], table_name='fact_transactions')
        
        # 3. Validity Checks
        self.check_validity(fact_transactions)
        
        # 4. PII Protection Checks
        self.check_pii_masking(dim_users)
        
        print("🛡️ [DQ ENGINE] All Data Quality checks successfully passed!")
