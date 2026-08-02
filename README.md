# 💳 Fintech Payment Data Engineering Pipeline (Docker & PostgreSQL DW)

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![SQL](https://img.shields.io/badge/SQL-SQLite%20%2F%20PostgreSQL-orange.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An end-to-end open-source **Data Engineering Pipeline** containerized with **Docker & Docker Compose** for a digital payment / fintech ecosystem. This project simulates raw transaction log generation, implements PII (Personally Identifiable Information) data privacy masking, transforms dirty transaction logs into a clean **Star Schema Data Warehouse** (PostgreSQL & SQLite), and provides business analytics queries.

---

## 📌 Project Overview & Use Case

In a digital payment platform (e.g., e-wallets, QRIS, Virtual Accounts), millions of transactions are generated daily. Data Engineers must ensure:
1. **Data Security & Privacy**: Sensitive PII like phone numbers and names are masked/hashed before storing in analytical warehouses (GDPR / PDP Compliance).
2. **Data Reliability**: Dirty data (duplicates, missing amounts, negative transaction values) must be sanitized.
3. **Infrastructure Isolation (Docker)**: The ETL pipeline and PostgreSQL Data Warehouse run in isolated Docker containers to guarantee zero-dependency execution across environments.
4. **Business Performance**: Analytics-ready tables (Fact & Dimension tables, Daily Merchant Summaries) enable rapid querying for business intelligence.

---

## 🏗️ Architecture & Data Flow

```mermaid
flowchart LR
    subgraph Docker Containers
        A[Python Data Generator] -->|Generate Raw CSV & Dirty Data| B[(data/raw/raw_transactions.csv)]
        B --> C[Python ETL Runner]
        
        subgraph ETL Transformation
            C1[1. Data Cleaning & De-duplication]
            C2[2. PII Masking & SHA-256 Hashing]
            C3[3. Star Schema Modeling]
        end
        
        C --> ETL Transformation
        ETL Transformation --> D[(PostgreSQL DW: fintech_dw)]
        ETL Transformation --> E[(SQLite DW: db/fintech.db)]
    end
    
    D --> F[SQL Analytics & Insights\nanalytics.sql]
```

---

## 📁 Repository Structure

```text
fintech-etl-pipeline/
├── data/
│   ├── raw/                      # Raw incoming transaction logs (CSV)
│   └── processed/                # Cleaned & modeled CSV exports
├── db/
│   └── fintech.db                # SQLite Data Warehouse database file
├── scripts/
│   ├── generate_data.py          # Synthetic transaction data generator
│   ├── etl_pipeline.py           # Core ETL script (Extract, Transform, Load)
│   └── analytics.sql             # SQL analytics queries for business insights
├── Dockerfile                    # Container definition for Python ETL app
├── docker-compose.yml            # Multi-container setup (PostgreSQL + ETL Runner)
├── .gitignore                    # Version control ignore rules
├── requirements.txt              # Python dependency list (Pandas, Faker, SQLAlchemy, Psycopg2)
└── README.md                     # Project documentation
```

---

## 🔒 Data Security & PII Protection

To strictly comply with financial data privacy regulations:
* **Phone Numbers**: Masked to keep only prefix and suffix (e.g., `0812****5678`) and anonymized via **SHA-256 Hashing** (`phone_hash`).
* **User Names**: Anonymized using initials (e.g., `Bagus Purbhawa` $\rightarrow$ `B**** P****`).

---

## 📊 Data Warehouse Schema (Star Schema)

### 1. `dim_users` (User Dimension)
| Column Name | Type | Description |
| :--- | :--- | :--- |
| `user_id` | VARCHAR (PK) | Unique User Identifier |
| `masked_user_name` | VARCHAR | Masked User Full Name |
| `masked_phone` | VARCHAR | Masked Phone Number |
| `phone_hash` | VARCHAR | SHA-256 Hash of Phone Number |

### 2. `dim_merchants` (Merchant Dimension)
| Column Name | Type | Description |
| :--- | :--- | :--- |
| `merchant_id` | VARCHAR (PK) | Unique Merchant Identifier |
| `merchant_name` | VARCHAR | Merchant Business Name |
| `merchant_category` | VARCHAR | Category (F&B, Retail, E-Commerce, etc.) |

### 3. `fact_transactions` (Transaction Fact Table)
| Column Name | Type | Description |
| :--- | :--- | :--- |
| `transaction_id` | VARCHAR (PK) | Unique Transaction UUID |
| `user_id` | VARCHAR (FK) | Foreign Key to `dim_users` |
| `merchant_id` | VARCHAR (FK) | Foreign Key to `dim_merchants` |
| `amount` | FLOAT | Transaction Amount (IDR) |
| `payment_method` | VARCHAR | QRIS, E-WALLET, VIRTUAL_ACCOUNT, etc. |
| `status` | VARCHAR | SUCCESS, FAILED, PENDING |
| `timestamp` | DATETIME | Full Transaction Timestamp |
| `transaction_date` | DATE | Transaction Date |

---

## ⚡ Quickstart: Running with Docker (Recommended)

### 1. Run Everything with Docker Compose (One Command)
Make sure Docker Desktop is running, then run:
```bash
docker compose up --build
```

This single command will:
1. Spin up a **PostgreSQL 16** Data Warehouse container (`fintech_postgres_dw`).
2. Build and run the **Python ETL** container (`fintech_etl_runner`).
3. Generate synthetic raw data, clean dirty records, apply PII masking, and load Star Schema tables into PostgreSQL and SQLite automatically!

---

## 💻 Manual Setup (Without Docker)

### 1. Setup Virtual Environment & Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Execute Data Generation & ETL Pipeline
```bash
python scripts/generate_data.py
python scripts/etl_pipeline.py
```

### 3. Run SQL Analytics
```bash
sqlite3 db/fintech.db < scripts/analytics.sql
```

---

## 📈 Sample Business SQL Analytics

### 1. Payment Method Reliability (Success Rate %)
```sql
SELECT 
    payment_method,
    COUNT(transaction_id) AS total_attempts,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful_tx,
    ROUND((SUM(CASE WHEN status = 'SUCCESS' THEN 1.0 ELSE 0 END) / COUNT(transaction_id)) * 100, 2) AS success_rate_pct
FROM fact_transactions
GROUP BY payment_method
ORDER BY success_rate_pct DESC;
```

---

## 🛠️ Tech Stack & Tools

* **Programming Language**: Python 3.12
* **Containerization**: Docker & Docker Compose
* **Data Processing**: Pandas, SQLAlchemy, Psycopg2
* **Data Generation**: Faker, UUID, Datetime
* **Database / DW**: PostgreSQL 16 (Docker) & SQLite3
* **SQL Querying**: Standard ANSI SQL (Window Functions, CTEs, Aggregations)
* **Version Control**: Git & GitHub

---

## 🚀 Future Enhancements

- [ ] Automate pipeline orchestration using **Apache Airflow** (Astro CLI / Docker Compose).
- [ ] Migrate load destination to **Google BigQuery Sandbox**.
- [ ] Implement data quality testing using **Great Expectations**.
- [ ] Build an interactive monitoring dashboard using **Streamlit** or **Metabase**.
