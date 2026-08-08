# [FEAT]: Implement Automated Data Quality (DQ) Testing Suite & Pre-Load Validations

## 📌 Problem Statement / Current Limitation
Saat ini, pembersihan data dilakukan secara langsung di dalam kelas ETL (`etl_pipeline.py`) dengan manipulasi Pandas sederhana (`dropna()`, `df[amount > 0]`). 

Namun:
1. Tidak ada pengujian kualitas data (*Data Quality Test Suite*) yang berdiri sendiri secara otomatis sebelum data dimasukkan ke Data Warehouse.
2. Jika ada bug baru pada aplikasi hulu yang memasukkan data anomali (misal: PII polos lolos atau Primary Key duplikat), pipeline tidak memiliki mekanisme **Fail-Fast / Circuit Breaker** untuk menghentikan proses *load*.
3. Belum ada pelaporan *Data Quality Check* yang memenuhi standar posisi **Data Quality Engineer** di industri Fintech (seperti DANA).

---

## 🎯 Proposed Feature & Overview
Membangun modul **Automated Data Quality (DQ) Testing Suite** yang terintegrasi dengan pipeline ETL:
* Membuat modul pengujian kualitas data khusus menggunakan **`pytest`** dan pustaka **Data Assertion**.
* Menguji 5 Aturan Emas Data Quality (*5 Gold Rules of DQ*) sebelum proses *Load* ke Data Warehouse:
  1. **Uniqueness Check**: Memastikan Primary Key (`transaction_id`, `user_id`, `merchant_id`) unik 100%.
  2. **Completeness Check**: Memastikan kolom kritis tidak memiliki nilai `NULL`.
  3. **Validity Check**: Memastikan nominal `amount > 0` dan kolom `status` berada pada enum yang valid (`SUCCESS`, `FAILED`, `PENDING`).
  4. **PII Privacy Check**: Memastikan tidak ada nomor telepon polos (10+ digit angka) atau nama lengkap yang bocor ke Data Warehouse.
  5. **Freshness Check**: Memastikan tanggal transaksi valid dan tidak berada pada rentang masa depan (*future date anomaly*).
* **Circuit Breaker Mechanism**: Jika salah satu uji DQ gagal, pipeline akan menghentikan proses *load* dan mengeluarkan peringatan error (*Fail-Fast*).

---

## 📋 Step-by-Step Implementation Tasks

### Phase 1: Data Quality Module & Test Suite Setup
- [ ] Buat struktur folder pengujian `tests/` dan modul `scripts/data_quality.py`.
- [ ] Implementasikan kelas `DataQualityValidator` dengan fungsi assertion untuk 5 Aturan Emas Data Quality.

### Phase 2: Implementation of Gold Rules
- [ ] Implementasikan `check_uniqueness(df, pk_column)`
- [ ] Implementasikan `check_completeness(df, required_columns)`
- [ ] Implementasikan `check_validity(df)` (amount > 0 & valid status)
- [ ] Implementasikan `check_pii_masking(df)` (regex validation untuk nomor HP & nama)
- [ ] Implementasikan `check_freshness(df)`

### Phase 3: ETL Pipeline Integration & Fail-Fast Mechanism
- [ ] Integrasikan `DataQualityValidator` ke dalam skrip `etl_pipeline.py` di antara tahap `transform()` dan `load()`.
- [ ] Tambahkan konfigurasi `raise_on_failure=True` agar proses *load* terhenti jika validasi gagal.

### Phase 4: Automated Testing & Documentation
- [ ] Buat file test `tests/test_etl_dq.py` yang bisa dijalankan dengan perintah `pytest`.
- [ ] Perbarui dokumentasi `README.md` dengan instruksi cara menjalankan pengujian Data Quality.

---

## ✅ Acceptance Criteria
1. Perintah `pytest` dapat mengeksekusi seluruh pengujian Data Quality secara otomatis.
2. Pipeline ETL akan sengaja memicu error (*Fail-Fast*) dan menolak memasukkan data ke PostgreSQL/SQLite jika ditemukan data kotor/anomali.
3. Semua data yang lolos ke Data Warehouse terverifikasi 100% mematuhi 5 Aturan Emas Data Quality.
