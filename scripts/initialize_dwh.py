import os
import sqlite3

try:
    from sqlalchemy import create_engine, text
except ImportError:
    create_engine = None

def get_ddl_queries():
    """Returns DDL queries for initializing DWH Star Schema with Primary Keys."""
    return {
        "dim_users": """
            CREATE TABLE IF NOT EXISTS dim_users (
                user_id TEXT PRIMARY KEY,
                masked_user_name TEXT,
                masked_phone TEXT,
                phone_hash TEXT
            );
        """,
        "dim_merchants": """
            CREATE TABLE IF NOT EXISTS dim_merchants (
                merchant_id TEXT PRIMARY KEY,
                merchant_name TEXT,
                merchant_category TEXT
            );
        """,
        "fact_transactions": """
            CREATE TABLE IF NOT EXISTS fact_transactions (
                transaction_id TEXT PRIMARY KEY,
                user_id TEXT,
                merchant_id TEXT,
                amount REAL,
                payment_method TEXT,
                status TEXT,
                timestamp TEXT,
                transaction_date TEXT,
                FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
                FOREIGN KEY (merchant_id) REFERENCES dim_merchants(merchant_id)
            );
        """,
        "daily_merchant_summary": """
            CREATE TABLE IF NOT EXISTS daily_merchant_summary (
                transaction_date TEXT,
                merchant_category TEXT,
                total_transactions INTEGER,
                successful_transactions INTEGER,
                failed_transactions INTEGER,
                total_volume_idr REAL,
                successful_volume_idr REAL,
                success_rate_pct REAL,
                PRIMARY KEY (transaction_date, merchant_category)
            );
        """
    }

def init_sqlite_dwh(db_path):
    """Initialize DWH schema in SQLite."""
    print(f"📦 [SQLite] Initializing DWH Schema at: {os.path.abspath(db_path)}...")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    ddl = get_ddl_queries()
    for table_name, query in ddl.items():
        cursor.execute(query)
        print(f"   ✓ Table `{table_name}` verified/created.")
    
    conn.commit()
    conn.close()
    print("✅ [SQLite] DWH Schema initialization complete.")

def init_postgres_dwh():
    """Initialize DWH schema in PostgreSQL if configured."""
    pg_host = os.getenv("POSTGRES_HOST")
    pg_db = os.getenv("POSTGRES_DB", "fintech_dw")
    pg_user = os.getenv("POSTGRES_USER", "fintech_user")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "fintech_pass")
    pg_port = os.getenv("POSTGRES_PORT", "5432")

    if pg_host and create_engine:
        try:
            print(f"🐘 [PostgreSQL] Initializing DWH Schema at {pg_host}:{pg_port}/{pg_db}...")
            engine = create_engine(f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}")
            with engine.connect() as conn:
                ddl = get_ddl_queries()
                for table_name, query in ddl.items():
                    # Adapt SQLite DDL types for Postgres if necessary
                    pg_query = query.replace("TEXT PRIMARY KEY", "VARCHAR(255) PRIMARY KEY") \
                                    .replace("TEXT", "VARCHAR(255)") \
                                    .replace("REAL", "DOUBLE PRECISION")
                    conn.execute(text(pg_query))
                    print(f"   ✓ PostgreSQL Table `{table_name}` verified/created.")
                conn.commit()
            print("✅ [PostgreSQL] DWH Schema initialization complete.")
        except Exception as e:
            print(f"⚠️ [PostgreSQL] Initialization skipped/failed: {e}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "..", "db", "fintech.db")
    init_sqlite_dwh(db_path)
    init_postgres_dwh()

if __name__ == "__main__":
    main()
