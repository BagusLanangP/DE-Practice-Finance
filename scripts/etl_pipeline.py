import os
import argparse
import hashlib
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from data_quality import DataQualityValidator, DataQualityError


try:
    from sqlalchemy import create_engine, text
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
    # ini untuk mengecek apakah parameternya sudah di isi
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

def update_processed_csv(df_new, csv_path, pk_cols):
    """Incremental update for CSV files: merge new data, deduplicate by PK, and write back."""
    if df_new is None or df_new.empty:
        return
    if os.path.exists(csv_path):
        df_old = pd.read_csv(csv_path)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        if pk_cols:
            df_combined = df_combined.drop_duplicates(subset=pk_cols, keep='last')
    else:
        df_combined = df_new
    df_combined.to_csv(csv_path, index=False)

def upsert_sqlite(df, table_name, conn, mode="REPLACE"):
    """Execute SQL UPSERT for SQLite table."""
    if df is None or df.empty:
        return
    columns = list(df.columns)
    cols_str = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))
    
    sql = f"INSERT OR {mode} INTO {table_name} ({cols_str}) VALUES ({placeholders})"
    cursor = conn.cursor()
    records = df.to_dict(orient='records')
    for row in records:
        values = [row[col] for col in columns]
        cursor.execute(sql, values)
    conn.commit()

class FintechETLPipeline:
    def __init__(self, raw_path, processed_dir, db_path, target_date=None, full_load=False):
        self.raw_path = raw_path
        self.processed_dir = processed_dir
        self.db_path = db_path
        self.target_date = target_date  # Format: YYYY-MM-DD
        self.full_load = full_load
        self.df_raw = None
        self.dim_users = None
        self.dim_merchants = None
        self.fact_transactions = None
        self.daily_summary = None

    def extract(self):
        """Extract step: Read raw transaction dataset and filter by target_date if incremental."""
        print("📥 [EXTRACT] Reading raw dataset from CSV...")
        if not os.path.exists(self.raw_path):
            raise FileNotFoundError(f"Raw data file not found at: {self.raw_path}")
        df = pd.read_csv(self.raw_path)
        print(f"   Total raw records read from source: {len(df)}")
        
        # Ensure timestamp is parsed for filtering
        df['temp_timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df['temp_date'] = df['temp_timestamp'].dt.strftime('%Y-%m-%d')

        if not self.full_load and self.target_date:
            print(f"   🎯 [INCREMENTAL FILTER] Filtering records for date: {self.target_date}")
            df = df[df['temp_date'] == self.target_date].copy()
            print(f"   Delta records for {self.target_date}: {len(df)}")
        
        df = df.drop(columns=['temp_timestamp', 'temp_date'])
        self.df_raw = df

    def transform(self):
        """Transform step: Clean, mask PII, and build dimensional model."""
        print("🔄 [TRANSFORM] Cleaning & Transforming Data...")
        if self.df_raw is None or self.df_raw.empty:
            print("   ⚠️ No records to transform for the selected window.")
            return

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
        df['transaction_date'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        df['amount'] = df['amount'].astype(float)
        df['status'] = df['status'].astype(str).str.upper()

        # 5. Data Privacy & Masking (PII Protection)
        print("   Applying PII Data Masking & Hashing...")
        df['masked_phone'] = df['phone_number'].apply(mask_phone_number)
        df['masked_user_name'] = df['user_name'].apply(mask_name)
        df['phone_hash'] = df['phone_number'].apply(hash_pii)

        # 6. Build Dimension Tables (Star Schema)
        self.dim_users = df[['user_id', 'masked_user_name', 'masked_phone', 'phone_hash']].drop_duplicates(subset=['user_id'])
        self.dim_merchants = df[['merchant_id', 'merchant_name', 'merchant_category']].drop_duplicates(subset=['merchant_id'])

        # Fact Table: Transactions
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
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

    def validate(self):
        print("🛡️ [DATA QUALITY] Running Pre-Load Data Quality Validations...")
        validator = DataQualityValidator()
        validator.validate_all(
            self.dim_users, 
            self.dim_merchants, 
            self.fact_transactions
        )
        print("✅ [DATA QUALITY] All 5 Gold Rules PASSED!")

    def load(self):
        """Load step: Persist into Processed CSV files, SQLite Data Warehouse, and PostgreSQL using UPSERT."""
        if self.fact_transactions is None or self.fact_transactions.empty:
            print("💾 [LOAD] No data to load.")
            return

        print("💾 [LOAD] Executing Incremental UPSERT into disk & Data Warehouse...")
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # 1. Update Incremental Processed CSVs
        update_processed_csv(self.dim_users, os.path.join(self.processed_dir, "dim_users.csv"), ['user_id'])
        update_processed_csv(self.dim_merchants, os.path.join(self.processed_dir, "dim_merchants.csv"), ['merchant_id'])
        update_processed_csv(self.fact_transactions, os.path.join(self.processed_dir, "fact_transactions.csv"), ['transaction_id'])
        update_processed_csv(self.daily_summary, os.path.join(self.processed_dir, "daily_merchant_summary.csv"), ['transaction_date', 'merchant_category'])

        # 2. Incremental UPSERT into SQLite DB
        conn = sqlite3.connect(self.db_path)
        upsert_sqlite(self.dim_users, 'dim_users', conn, mode="REPLACE")
        upsert_sqlite(self.dim_merchants, 'dim_merchants', conn, mode="REPLACE")
        upsert_sqlite(self.fact_transactions, 'fact_transactions', conn, mode="IGNORE")
        upsert_sqlite(self.daily_summary, 'daily_merchant_summary', conn, mode="REPLACE")
        conn.close()
        print(f"✅ [SQLite] Incremental load successfully committed to: {os.path.abspath(self.db_path)}")

        # 3. Load into PostgreSQL Data Warehouse (if configured)
        pg_host = os.getenv("POSTGRES_HOST")
        pg_db = os.getenv("POSTGRES_DB", "fintech_dw")
        pg_user = os.getenv("POSTGRES_USER", "fintech_user")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "fintech_pass")
        pg_port = os.getenv("POSTGRES_PORT", "5432")

        if pg_host and create_engine:
            try:
                print(f"🐘 [POSTGRES] Connecting to PostgreSQL Data Warehouse at {pg_host}:{pg_port}/{pg_db}...")
                engine = create_engine(f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}")
                
                # Append strategy for Postgres
                self.dim_users.to_sql('dim_users', engine, if_exists='append', index=False)
                self.dim_merchants.to_sql('dim_merchants', engine, if_exists='append', index=False)
                self.fact_transactions.to_sql('fact_transactions', engine, if_exists='append', index=False)
                self.daily_summary.to_sql('daily_merchant_summary', engine, if_exists='append', index=False)
                print("✅ [POSTGRES] Incremental load committed to PostgreSQL DW!")
            except Exception as e:
                print(f"⚠️ [POSTGRES] Could not load to PostgreSQL: {e}")

    def run(self):
        self.extract()
        self.transform()
        self.validate()
        self.load()

def main():
    parser = argparse.ArgumentParser(description="Fintech Payment ETL Pipeline (Incremental & Full Load)")
    parser.add_argument("--date", type=str, help="Target date for incremental ETL load (YYYY-MM-DD). Default: Yesterday")
    parser.add_argument("--full", action="store_true", help="Execute full load (process all raw records)")
    args = parser.parse_args()

    target_date = args.date
    if not target_date and not args.full:
        # Default to yesterday's date
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_csv = os.path.join(base_dir, "..", "data", "raw", "raw_transactions.csv")
    processed_dir = os.path.join(base_dir, "..", "data", "processed")
    db_file = os.path.join(base_dir, "..", "db", "fintech.db")

    print(f"🚀 Running Fintech ETL Pipeline (Mode: {'FULL LOAD' if args.full else f'INCREMENTAL DATE: {target_date}'})")
    
    # Ensure DWH schema is initialized with PKs
    from initialize_dwh import init_sqlite_dwh
    init_sqlite_dwh(db_file)

    pipeline = FintechETLPipeline(raw_csv, processed_dir, db_file, target_date=target_date, full_load=args.full)
    pipeline.run()

if __name__ == "__main__":
    main()
