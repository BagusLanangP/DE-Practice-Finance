# [FEAT]: Refactor ETL Pipeline to Support Incremental Daily Load (UPSERT / Delta Update)

## 📌 Problem Statement / Current Limitation
Saat ini, `etl_pipeline.py` menggunakan metode **Full Load** (`if_exists='replace'`). 
Setiap kali skrip ETL dijalankan:
1. Seluruh tabel di Data Warehouse (PostgreSQL & SQLite) akan **dihapus/di-drop** dan dibuat ulang dari awal.
2. Data historis hari-hari sebelumnya akan hilang jika data mentah hanya berisi log hari ini.
3. Metode ini tidak efisien untuk skala produksi (*production environment*) dan tidak mencerminkan praktik terbaik di industri (seperti yang diterapkan di DANA / Fintech).

---

## 🎯 Proposed Feature & Overview
Mengubah pipeline dari **Full Overwrite Load** menjadi **Incremental / Delta Load** yang berjalan secara harian (batch `T-1`):
* Pipeline hanya akan mengekstrak dan mentransformasi data transaksi dari **tanggal tertentu** (misal: hari kemarin atau via argumen CLI `--date YYYY-MM-DD`).
* Data Warehouse akan di-inisialisasi dengan **Primary Key (PK)** dan batasan (*constraints*) yang jelas.
* **Proses Load akan menggunakan logika UPSERT / Append**:
  * `dim_users` & `dim_merchants`: **UPSERT** (Insert jika baru, Update jika ada perubahan data).
  * `fact_transactions`: **APPEND** (Menambahkan transaksi baru tanpa menghapus transaksi historis).
  * `daily_merchant_summary`: **UPSERT / RECALCULATE** untuk tanggal yang bersangkutan.

---

## 📋 Step-by-Step Implementation Tasks

### Phase 1: DWH Schema Initialization (DDL)
- [ ] Buat skrip inisialisasi skema database (`initialize_dwh.py` / DDL SQL) yang menetapkan batasan Primary Key:
  - `dim_users` (`user_id` PK)
  - `dim_merchants` (`merchant_id` PK)
  - `fact_transactions` (`transaction_id` PK, FK to users & merchants)
  - `daily_merchant_summary` (Composite PK: `transaction_date`, `merchant_category`)

### Phase 2: Pipeline CLI Argument & Delta Extraction
- [ ] Tambahkan `argparse` pada `etl_pipeline.py` untuk menerima parameter tanggal `--date YYYY-MM-DD` (default: kemarin / `T-1`).
- [ ] Modifikasi tahap `extract()` agar melakukan filtering data mentah berdasarkan `transaction_date` yang dipilih.

### Phase 3: Incremental Load & UPSERT Engine
- [ ] Implementasikan logika **UPSERT** untuk SQLite (`INSERT OR REPLACE` / `INSERT OR IGNORE`).
- [ ] Implementasikan logika **UPSERT** untuk PostgreSQL (`ON CONFLICT (id) DO UPDATE / NOTHING`).
- [ ] Modifikasi penulisan file CSV di `data/processed/` agar mendukung mode Append / Deduplicate.

### Phase 4: Generator & Verification
- [ ] Modifikasi `generate_data.py` agar dapat memicu pembuatan log transaksi sintetis per tanggal spesifik untuk pengujian.
- [ ] Lakukan verifikasi skenario:
  1. Run pipeline untuk tanggal `2026-08-01` $\rightarrow$ Cek isi DB.
  2. Run pipeline untuk tanggal `2026-08-02` $\rightarrow$ Pastikan data `2026-08-01` tidak hilang dan data `2026-08-02` bertambah.

---

## ✅ Acceptance Criteria
1. Menjalankan `python scripts/etl_pipeline.py --date 2026-08-02` **TIDAK menghapus** data tanggal sebelumnya di database.
2. Tidak ada duplikasi baris pada `dim_users` atau `dim_merchants`.
3. Tabel `fact_transactions` bertambah secara kumulatif (*incremental*).
4. Kode terdokumentasi dengan baik untuk kemudahan kolaborasi tim.
