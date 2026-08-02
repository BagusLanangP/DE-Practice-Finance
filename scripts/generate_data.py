import os
import random
import uuid
from datetime import datetime, timedelta
import pandas as pd

try:
    from faker import Faker
    fake = Faker('id_ID')
    Faker.seed(42)
except ImportError:
    fake = None

random.seed(42)

FIRST_NAMES = ["Bagus", "Ayu", "Rizky", "Budi", "Dewi", "Siti", "Andi", "Fajar", "Dian", "Eka", "Putra", "Nadia"]
LAST_NAMES = ["Purbhawa", "Santoso", "Saputra", "Wibowo", "Kusuma", "Lestari", "Nugroho", "Pratama", "Hidayat", "Wijaya"]

def get_random_name():
    if fake:
        return fake.name()
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def get_random_phone():
    if fake:
        return fake.phone_number()
    return f"08{random.randint(11, 99)}{random.randint(1000, 9999)}{random.randint(100, 999)}"

def get_random_email(name):
    if fake:
        return fake.email()
    clean_name = name.lower().replace(" ", ".")
    return f"{clean_name}@example.com"

def generate_users(num_users=100):
    """Generate master user list."""
    users = []
    for i in range(1, num_users + 1):
        user_id = f"USR-{i:04d}"
        name = get_random_name()
        users.append({
            "user_id": user_id,
            "full_name": name,
            "phone_number": get_random_phone(),
            "email": get_random_email(name),
            "registration_date": "2025-01-15"
        })
    return users

def generate_merchants():
    """Generate merchant categories and merchant profiles."""
    merchant_categories = {
        "F&B": ["Kopi Kenangan Local", "Gacoan Noodle", "Starbucks MTR", "Bakmi GM"],
        "Retail": ["Indomaret Fresh", "Alfamart Express", "Transmart Supermarket"],
        "E-Commerce": ["Tokopedia Official", "Shopee Pay", "Blibli Store"],
        "Bill Payment": ["PLN Electricity", "PDAM Water", "Telkomsel Bill"],
        "Transport": ["Gojek Ride", "Grab Pay", "KAI Access"]
    }
    
    merchants = []
    m_idx = 1
    for category, name_list in merchant_categories.items():
        for name in name_list:
            merchants.append({
                "merchant_id": f"MCH-{m_idx:03d}",
                "merchant_name": name,
                "category": category
            })
            m_idx += 1
    return merchants

def generate_transactions(num_records=2500):
    """Generate synthetic fintech transaction raw data with intentional messy data for ETL practice."""
    users = generate_users(100)
    merchants = generate_merchants()
    
    payment_methods = ["QRIS", "E-WALLET_BALANCE", "VIRTUAL_ACCOUNT", "CREDIT_CARD", "DEBIT_CARD"]
    statuses = ["SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "FAILED", "PENDING"]  # ~66% Success rate
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    records = []
    
    for _ in range(num_records):
        user = random.choice(users)
        merchant = random.choice(merchants)
        status = random.choice(statuses)
        payment_method = random.choice(payment_methods)
        
        # Transaction timestamp within the last 30 days
        random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
        tx_timestamp = start_date + timedelta(seconds=random_seconds)
        
        # Amount in IDR (ranging from 10,000 to 2,500,000 IDR)
        amount = round(random.uniform(10000, 2500000), -2)
        
        records.append({
            "transaction_id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "user_name": user["full_name"],
            "phone_number": user["phone_number"],
            "merchant_id": merchant["merchant_id"],
            "merchant_name": merchant["merchant_name"],
            "merchant_category": merchant["category"],
            "amount": amount,
            "payment_method": payment_method,
            "status": status,
            "timestamp": tx_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    df = pd.DataFrame(records)
    
    # Inject intentional anomalies/dirty data for ETL cleaning demonstration
    # 1. Inject duplicate rows (5 rows)
    duplicates = df.sample(n=5, random_state=42)
    df = pd.concat([df, duplicates], ignore_index=True)
    
    # 2. Inject missing values (null amounts & null status)
    df.loc[df.sample(n=10, random_state=10).index, 'amount'] = None
    df.loc[df.sample(n=5, random_state=15).index, 'status'] = None
    
    # 3. Inject invalid/negative amounts (dirty data)
    df.loc[df.sample(n=3, random_state=20).index, 'amount'] = -50000.0
    
    return df

def main():
    print("🚀 Generating synthetic fintech transaction data...")
    df = generate_transactions(num_records=2500)
    
    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "raw_transactions.csv")
    
    df.to_csv(output_file, index=False)
    print(f"✅ Generated {len(df)} raw transaction records saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()
