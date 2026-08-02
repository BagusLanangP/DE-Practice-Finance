-- ====================================================================
-- FINTECH DATA ENGINEERING PORTFOLIO - ANALYTICAL QUERIES (SQL)
-- Target Database: SQLite / PostgreSQL / BigQuery
-- ====================================================================

-- --------------------------------------------------------------------
-- Query 1: Daily Gross Transaction Value (GTV) and Transaction Volume
-- Goal: Track daily financial performance and volume metrics.
-- --------------------------------------------------------------------
SELECT 
    transaction_date,
    COUNT(transaction_id) AS total_transactions,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful_transactions,
    ROUND(SUM(CASE WHEN status = 'SUCCESS' THEN amount ELSE 0 END), 2) AS total_gtv_idr,
    ROUND((SUM(CASE WHEN status = 'SUCCESS' THEN 1.0 ELSE 0 END) / COUNT(transaction_id)) * 100, 2) AS overall_success_rate_pct
FROM fact_transactions
GROUP BY transaction_date
ORDER BY transaction_date ASC;


-- --------------------------------------------------------------------
-- Query 2: Merchant Category Performance Ranking
-- Goal: Rank merchant categories based on total successful volume using Window Functions.
-- --------------------------------------------------------------------
WITH category_metrics AS (
    SELECT 
        m.merchant_category,
        COUNT(t.transaction_id) AS total_tx_count,
        SUM(CASE WHEN t.status = 'SUCCESS' THEN t.amount ELSE 0 END) AS total_volume_idr
    FROM fact_transactions t
    JOIN dim_merchants m ON t.merchant_id = m.merchant_id
    GROUP BY m.merchant_category
)
SELECT 
    merchant_category,
    total_tx_count,
    total_volume_idr,
    DENSE_RANK() OVER (ORDER BY total_volume_idr DESC) AS rank_by_volume
FROM category_metrics
ORDER BY rank_by_volume;


-- --------------------------------------------------------------------
-- Query 3: Payment Method Reliability & Health Check
-- Goal: Analyze transaction success rate per payment channel to detect payment gateway anomalies.
-- --------------------------------------------------------------------
SELECT 
    payment_method,
    COUNT(transaction_id) AS total_attempts,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful_tx,
    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_tx,
    SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_tx,
    ROUND((SUM(CASE WHEN status = 'SUCCESS' THEN 1.0 ELSE 0 END) / COUNT(transaction_id)) * 100, 2) AS success_rate_pct
FROM fact_transactions
GROUP BY payment_method
ORDER BY success_rate_pct DESC;


-- --------------------------------------------------------------------
-- Query 4: Top 10 High-Value Users (Whale Customers)
-- Goal: Identify top spenders using masked PII data from dim_users.
-- --------------------------------------------------------------------
SELECT 
    u.user_id,
    u.masked_user_name,
    u.masked_phone,
    COUNT(t.transaction_id) AS total_transactions,
    ROUND(SUM(t.amount), 2) AS total_spent_idr
FROM fact_transactions t
JOIN dim_users u ON t.user_id = u.user_id
WHERE t.status = 'SUCCESS'
GROUP BY u.user_id, u.masked_user_name, u.masked_phone
ORDER BY total_spent_idr DESC
LIMIT 10;
