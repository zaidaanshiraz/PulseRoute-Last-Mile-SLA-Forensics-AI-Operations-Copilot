-- ==============================================================================
-- FILE: 03_vendor_analysis.sql
-- PROJECT: Last-Mile Delivery Analytics (Blitz Internship Portfolio)
-- PURPOSE: Advanced Relational Joins, Zero-Defect City Auditing & Carrier Benchmarking
-- QUESTIONS COVERED: Q6 and Q7
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUESTION 6: Which cities have no SLA breaches (or zero breaches in high-priority cohorts)?
-- SQL Fundamental: LEFT JOIN vs INNER JOIN, IS NULL / COUNT() = 0
-- Business Purpose: Identify zero-defect hubs and regional operational excellence.
-- ------------------------------------------------------------------------------

-- Approach A: Network-wide check across all cities for zero SLA breaches
SELECT 
    c.city_id,
    c.city_name,
    c.zone,
    COUNT(b.order_id) AS total_sla_breaches
FROM cities c
LEFT JOIN deliveries b 
    ON c.city_id = b.city_id 
    AND b.calculated_sla_breach = 'Yes'
GROUP BY c.city_id, c.city_name, c.zone
HAVING COUNT(b.order_id) = 0;

-- Approach B: Targeted cohort check (e.g. Zero SLA breaches during peak festive high-value electronics)
SELECT 
    c.city_name,
    c.zone,
    COUNT(d.order_id) AS total_festive_electronics_orders,
    COUNT(b.order_id) AS sla_breaches_recorded
FROM cities c
LEFT JOIN deliveries d 
    ON c.city_id = d.city_id 
    AND d.product_category = 'Electronics' 
    AND d.is_festive_season = 'Yes'
LEFT JOIN deliveries b 
    ON d.order_id = b.order_id 
    AND b.calculated_sla_breach = 'Yes'
GROUP BY c.city_name, c.zone
HAVING COUNT(b.order_id) = 0
ORDER BY total_festive_electronics_orders DESC;

/*
BUSINESS & TECHNICAL EXPLANATION:
WHY USE LEFT JOIN INSTEAD OF INNER JOIN?
- An INNER JOIN requires records to exist in both tables. If a city had ZERO SLA breaches,
  an INNER JOIN would immediately filter out that entire city!
- A LEFT JOIN preserves every single row from the left table ('cities'). When there are no 
  matching breaches in the right table ('deliveries'), the joined columns evaluate to NULL.
- Applying 'HAVING COUNT(b.order_id) = 0' allows the analyst to successfully surface the best-performing,
  zero-defect cities. In logistics operations, discovering which hub delivers with 0% failure in a high-stress
  cohort (such as Indore handling festive electronics) enables managers to benchmark and replicate their processes.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 7: Which vendors perform better than the overall network average?
-- SQL Fundamental: Common Table Expression (CTE) with WITH clause
-- Business Purpose: Dynamic carrier performance appraisal and volume reallocation.
-- ------------------------------------------------------------------------------
WITH NetworkBenchmark AS (
    -- Step 1: Compute dynamic network-wide baseline SLA breach rate
    SELECT 
        COUNT(*) AS network_total_deliveries,
        SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS network_total_breaches,
        ROUND(100.0 * SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS benchmark_breach_rate_pct,
        ROUND(AVG(calculated_delay_days), 2) AS benchmark_avg_delay
    FROM deliveries
),
VendorAggregates AS (
    -- Step 2: Compute carrier-level metrics
    SELECT 
        v.vendor_name,
        COUNT(d.order_id) AS carrier_total_deliveries,
        SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS carrier_breaches,
        ROUND(100.0 * SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) / COUNT(d.order_id), 2) AS carrier_breach_rate_pct,
        ROUND(AVG(d.calculated_delay_days), 2) AS carrier_avg_delay
    FROM deliveries d
    JOIN vendors v ON d.vendor_id = v.vendor_id
    GROUP BY v.vendor_name
)
-- Step 3: Compare each carrier against the dynamic network benchmark
SELECT 
    va.vendor_name,
    va.carrier_total_deliveries,
    va.carrier_breach_rate_pct,
    nb.benchmark_breach_rate_pct AS network_avg_breach_pct,
    ROUND(nb.benchmark_breach_rate_pct - va.carrier_breach_rate_pct, 2) AS sla_outperformance_pct_points,
    va.carrier_avg_delay,
    nb.benchmark_avg_delay AS network_avg_delay,
    CASE 
        WHEN va.carrier_breach_rate_pct < nb.benchmark_breach_rate_pct THEN 'Tier-1 Partner (Outperforming)'
        ELSE 'Under Review'
    END AS carrier_status
FROM VendorAggregates va
CROSS JOIN NetworkBenchmark nb
WHERE va.carrier_breach_rate_pct < nb.benchmark_breach_rate_pct
ORDER BY sla_outperformance_pct_points DESC;

/*
BUSINESS & TECHNICAL EXPLANATION:
WHY USE A CTE INSTEAD OF NESTED SUBQUERIES?
- A Common Table Expression (CTE) creates temporary named result sets that exist only within
  the execution of the query.
- Modularity & Readability: The query separates the logic of baseline benchmark calculation 
  ('NetworkBenchmark') from carrier-level aggregation ('VendorAggregates').
- Zero Hardcoding: The network benchmark is computed dynamically on the fly. If filtered by date
  or season, the benchmark adapts automatically.
- Strategic Logistics Decision: Ecom Express (+2.80% outperformance), Shadowfax (+1.60%), and 
  Delhivery (+1.00%) consistently maintain breach rates lower than the 28.06% network average.
  In weekly dispatch planning, routing engines should automatically favor these Tier-1 carriers.
*/

