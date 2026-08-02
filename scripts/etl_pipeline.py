import os
import hashlib
import sqlite3
import pandas as pd
from datetime import datetime
try:
    from sqlalchemy import create_engine
except ImportError:
    create_engine = None

def mask_phone_number(phone_str):
    """Mask phone number for data privacy (PII compliance).
    e.g., '+628123456789' or '081234567890' -> '0812****7890'
    """
    if not isinstance(phone_str, str):
        return "UNKNOWN"
    digits = ''.join(filter(str.isdigit, phone_str))
    if len(digits) < 7:
        return "****"
    prefix = digits[:4]
    suffix = digits[-4:]
    return f"{prefix}****{suffix}"

def mask_name(name_str):
    """Mask user name for data privacy.
    e.g., 'Bagus Lanang Purbhawa' -> 'B**** L**** P****'
    """
    if not isinstance(name_str, str):
        return "Anonymous"
    parts = name_str.strip().split()
    masked_parts = [p[0] + "****" for p in parts if len(p) > 0]
    return " ".join(masked_parts)

def hash_pii(text_str):
    """Generate SHA-256 hash for sensitive identifiers."""
    if not isinstance(text_str, str):
        return ""
    return hashlib.sha256(text_str.encode('utf-8')).hexdigest()

class FintechETLPipeline:
    def __init__(self, raw_path, processed_dir, db_path):
        self.raw_path = raw_path
        self.processed_dir = processed_dir
        self.db_path = db_path
        self.df_raw = None
        self.dim_users = None
        self.dim_merchants = None
        self.fact_transactions = None
        self.daily_summary = None

    def extract(self):
        """Extract step: Read raw transaction dataset."""
        print("📥 [EXTRACT] Reading raw dataset from CSV...")
        if not os.path.exists(self.raw_path):
            raise FileNotFoundError(f"Raw data file not found at: {self.raw_path}")
        self.df_raw = pd.read_csv(self.raw_path)
        print(f"   Raw records read: {len(self.df_raw)}")

    def transform(self):
        """Transform step: Clean, mask PII, and build dimensional model."""
        print("🔄 [TRANSFORM] Cleaning & Transforming Data...")
        df = self.df_raw.copy()
        
        # 1. Remove Exact Duplicates
        initial_count = len(df)
        df = df.drop_duplicates(subset=['transaction_id'])
        print(f"   Removed {initial_count - len(df)} duplicate records.")

        # 2. Filter invalid / missing critical fields
        before_null_clean = len(df)
        df = df.dropna(subset=['transaction_id', 'user_id', 'amount', 'status'])
        print(f"   Dropped {before_null_clean - len(df)} rows with missing critical attributes.")

        # 3. Filter invalid transaction amounts (must be > 0)
        before_amount_clean = len(df)
        df = df[df['amount'] > 0]
        print(f"   Dropped {before_amount_clean - len(df)} rows with invalid amount (<= 0).")

        # 4. Standardize Data Types & Formats
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['transaction_date'] = df['timestamp'].dt.date
        df['amount'] = df['amount'].astype(float)
        df['status'] = df['status'].astype(str).str.upper()

        # 5. Data Privacy & Masking (PII Protection)
        print("   Applying PII Data Masking & Hashing...")
        df['masked_phone'] = df['phone_number'].apply(mask_phone_number)
        df['masked_user_name'] = df['user_name'].apply(mask_name)
        df['phone_hash'] = df['phone_number'].apply(hash_pii)

        # 6. Build Dimension Tables (Star Schema)
        # Dimension: Users
        self.dim_users = df[['user_id', 'masked_user_name', 'masked_phone', 'phone_hash']].drop_duplicates(subset=['user_id'])

        # Dimension: Merchants
        self.dim_merchants = df[['merchant_id', 'merchant_name', 'merchant_category']].drop_duplicates(subset=['merchant_id'])

        # Fact Table: Transactions
        self.fact_transactions = df[[
            'transaction_id', 'user_id', 'merchant_id', 
            'amount', 'payment_method', 'status', 'timestamp', 'transaction_date'
        ]]

        # 7. Aggregate Table: Daily Merchant Performance
        print("   Calculating Daily Merchant Category Performance...")
        daily = df.groupby(['transaction_date', 'merchant_category']).agg(
            total_transactions=('transaction_id', 'count'),
            successful_transactions=('status', lambda x: (x == 'SUCCESS').sum()),
            failed_transactions=('status', lambda x: (x == 'FAILED').sum()),
            total_volume_idr=('amount', 'sum'),
            successful_volume_idr=('amount', lambda x: df.loc[x.index][df.loc[x.index, 'status'] == 'SUCCESS']['amount'].sum())
        ).reset_index()
        
        daily['success_rate_pct'] = round((daily['successful_transactions'] / daily['total_transactions']) * 100, 2)
        self.daily_summary = daily

        print("✅ [TRANSFORM] Transformation complete.")

    def load(self):
        """Load step: Persist into Processed CSV files, SQLite Data Warehouse, and PostgreSQL (if configured)."""
        print("💾 [LOAD] Saving clean data to disk & Data Warehouse...")
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # 1. Save Processed CSVs
        self.dim_users.to_csv(os.path.join(self.processed_dir, "dim_users.csv"), index=False)
        self.dim_merchants.to_csv(os.path.join(self.processed_dir, "dim_merchants.csv"), index=False)
        self.fact_transactions.to_csv(os.path.join(self.processed_dir, "fact_transactions.csv"), index=False)
        self.daily_summary.to_csv(os.path.join(self.processed_dir, "daily_merchant_summary.csv"), index=False)

        # 2. Load into SQLite Database (Local Fallback)
        conn = sqlite3.connect(self.db_path)
        self.dim_users.to_sql('dim_users', conn, if_exists='replace', index=False)
        self.dim_merchants.to_sql('dim_merchants', conn, if_exists='replace', index=False)
        self.fact_transactions.to_sql('fact_transactions', conn, if_exists='replace', index=False)
        self.daily_summary.to_sql('daily_merchant_summary', conn, if_exists='replace', index=False)
        conn.commit()
        conn.close()
        print(f"✅ Data successfully loaded into SQLite DB at: {os.path.abspath(self.db_path)}")

        # 3. Load into PostgreSQL Data Warehouse (if PostgreSQL env vars are set)
        pg_host = os.getenv("POSTGRES_HOST")
        pg_db = os.getenv("POSTGRES_DB", "fintech_dw")
        pg_user = os.getenv("POSTGRES_USER", "fintech_user")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "fintech_pass")
        pg_port = os.getenv("POSTGRES_PORT", "5432")

        if pg_host and create_engine:
            try:
                print(f"🐘 [POSTGRES] Connecting to PostgreSQL Data Warehouse at {pg_host}:{pg_port}/{pg_db}...")
                engine = create_engine(f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}")
                
                self.dim_users.to_sql('dim_users', engine, if_exists='replace', index=False)
                self.dim_merchants.to_sql('dim_merchants', engine, if_exists='replace', index=False)
                self.fact_transactions.to_sql('fact_transactions', engine, if_exists='replace', index=False)
                self.daily_summary.to_sql('daily_merchant_summary', engine, if_exists='replace', index=False)
                
                print("✅ [POSTGRES] Successfully loaded all Star Schema tables into PostgreSQL DW!")
            except Exception as e:
                print(f"⚠️ [POSTGRES] Could not load to PostgreSQL: {e}")

    def run(self):
        self.extract()
        self.transform()
        self.load()

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_csv = os.path.join(base_dir, "..", "data", "raw", "raw_transactions.csv")
    processed_dir = os.path.join(base_dir, "..", "data", "processed")
    db_file = os.path.join(base_dir, "..", "db", "fintech.db")

    pipeline = FintechETLPipeline(raw_csv, processed_dir, db_file)
    pipeline.run()

if __name__ == "__main__":
    main()
