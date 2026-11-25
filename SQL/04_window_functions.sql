-- ==============================================================================
-- FILE: 04_window_functions.sql
-- PROJECT: Last-Mile Delivery Analytics (Blitz Internship Portfolio)
-- PURPOSE: Advanced Analytical Window Functions (RANK, DENSE_RANK, LAG, Window Aggregations)
-- QUESTIONS COVERED: Q8, Q9, and Q10
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUESTION 8: Rank cities by delivery performance (On-Time Delivery Rate)
-- SQL Fundamental: RANK(), DENSE_RANK(), OVER (ORDER BY ...)
-- Business Purpose: City league table for operational excellence and hub audits.
-- ------------------------------------------------------------------------------
WITH CityPerformance AS (
    SELECT 
        c.city_name,
        c.zone,
        COUNT(d.order_id) AS total_orders,
        SUM(CASE WHEN d.calculated_delivery_status IN ('Early', 'On-Time') THEN 1 ELSE 0 END) AS on_time_orders,
        ROUND(100.0 * SUM(CASE WHEN d.calculated_delivery_status IN ('Early', 'On-Time') THEN 1 ELSE 0 END) / COUNT(d.order_id), 2) AS on_time_rate_pct,
        ROUND(AVG(d.calculated_delay_days), 2) AS avg_delay_days
    FROM deliveries d
    JOIN cities c ON d.city_id = c.city_id
    GROUP BY c.city_name, c.zone
)
SELECT 
    city_name,
    zone,
    total_orders,
    on_time_orders,
    on_time_rate_pct,
    avg_delay_days,
    -- RANK() assigns ranking with gaps in case of ties
    RANK() OVER (ORDER BY on_time_rate_pct DESC, avg_delay_days ASC) AS rank_with_gaps,
    -- DENSE_RANK() assigns consecutive rankings without gaps
    DENSE_RANK() OVER (ORDER BY on_time_rate_pct DESC, avg_delay_days ASC) AS dense_rank_continuous,
    -- Regional partition ranking to find #1 city within each geographic zone
    DENSE_RANK() OVER (PARTITION BY zone ORDER BY on_time_rate_pct DESC) AS zone_internal_rank
FROM CityPerformance
ORDER BY rank_with_gaps;

/*
BUSINESS & TECHNICAL EXPLANATION:
WHAT IS THE DIFFERENCE BETWEEN RANK() AND DENSE_RANK()?
- RANK(): If two cities tie for rank 1 (e.g., both have 68.25%), both receive rank 1, but the 
  next city receives rank 3 (skipping rank 2).
- DENSE_RANK(): If two cities tie for rank 1, the next city receives rank 2 (no gaps).
- In logistics leaderboards, DENSE_RANK() is preferred for tier assignments (e.g. Tier 1, Tier 2),
  while RANK() is preferred for strict ordinal competitions where tie penalties matter.
- Pune (#1 at 68.25%) and Bangalore (#2 at 67.65%) lead the country in reliability, while Nagpur 
  lags at 54.15%.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 9: How does delivery performance change monthly?
-- SQL Fundamental: LAG(), Window Functions, Time-Series Month-over-Month (MoM) Trend
-- Business Purpose: Track seasonal degradation during Monsoon and Festive surges.
-- ------------------------------------------------------------------------------
WITH MonthlyAggregates AS (
    SELECT 
        substr(order_date, 1, 7) AS order_month,
        COUNT(order_id) AS monthly_orders,
        SUM(CASE WHEN calculated_delivery_status = 'Delayed' THEN 1 ELSE 0 END) AS delayed_orders,
        SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS sla_breaches,
        ROUND(100.0 * SUM(CASE WHEN calculated_delivery_status = 'Delayed' THEN 1 ELSE 0 END) / COUNT(order_id), 2) AS delay_rate_pct,
        ROUND(100.0 * SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) / COUNT(order_id), 2) AS sla_breach_rate_pct,
        ROUND(AVG(calculated_delay_days), 2) AS avg_delay_days
    FROM deliveries
    GROUP BY substr(order_date, 1, 7)
)
SELECT 
    order_month,
    monthly_orders,
    delay_rate_pct,
    sla_breach_rate_pct,
    -- Fetch the previous month's SLA breach rate
    LAG(sla_breach_rate_pct, 1) OVER (ORDER BY order_month) AS prev_month_sla_breach_pct,
    -- Compute Month-over-Month basis-point change
    ROUND(sla_breach_rate_pct - LAG(sla_breach_rate_pct, 1) OVER (ORDER BY order_month), 2) AS mom_breach_rate_change_pct_points,
    -- Rolling 3-month average SLA breach rate
    ROUND(AVG(sla_breach_rate_pct) OVER (
        ORDER BY order_month 
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_3mo_avg_sla_breach_pct,
    CASE 
        WHEN sla_breach_rate_pct - LAG(sla_breach_rate_pct, 1) OVER (ORDER BY order_month) > 1.5 THEN '🔴 Alert: Performance Deteriorating'
        WHEN sla_breach_rate_pct - LAG(sla_breach_rate_pct, 1) OVER (ORDER BY order_month) < -1.5 THEN '🟢 Improvement'
        ELSE '🟡 Stable'
    END AS operational_health_status
FROM MonthlyAggregates
ORDER BY order_month;

/*
BUSINESS & TECHNICAL EXPLANATION:
WHY USE LAG() OVER A SELF-JOIN?
- Prior to window functions, computing MoM changes required joining the table to itself on 
  MONTH(t1.date) = MONTH(t2.date) + 1. That required an expensive $O(N^2)$ Cartesian comparison, 
  was vulnerable to missing calendar months, and required complicated year-boundary logic.
- LAG() accesses the previous row's calculated values directly in a single pass ($O(N \log N)$),
  delivering massive performance gains.
- The output clearly highlights the seasonal spike during the Monsoon (July–August) and Festive season
  (October–November), where breach rates climb due to weather disruption and warehouse volume bottlenecks.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 10: What percentage of total network delays comes from each city?
-- SQL Fundamental: Window Aggregation: SUM(...) OVER () vs GROUP BY
-- Business Purpose: Identify the vital few locations generating the lion's share of network delays.
-- ------------------------------------------------------------------------------
SELECT 
    c.city_name,
    c.zone,
    COUNT(d.order_id) AS city_delayed_orders,
    -- Window function calculates the total delays across the entire network WITHOUT collapsing rows
    SUM(COUNT(d.order_id)) OVER () AS total_network_delayed_orders,
    -- Calculate city contribution percentage
    ROUND(100.0 * COUNT(d.order_id) / SUM(COUNT(d.order_id)) OVER (), 2) AS pct_contribution_to_network_delays,
    -- Cumulative percentage to identify the 80/20 Pareto cutoff
    ROUND(SUM(100.0 * COUNT(d.order_id) / SUM(COUNT(d.order_id)) OVER ()) OVER (
        ORDER BY COUNT(d.order_id) DESC 
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2) AS cumulative_delay_share_pct
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY c.city_name, c.zone
ORDER BY city_delayed_orders DESC;

/*
BUSINESS & TECHNICAL EXPLANATION:
WHY IS A WINDOW FUNCTION PREFERABLE TO A NORMAL GROUP BY HERE?
- In standard SQL GROUP BY, the table collapses into 15 city rows. Once collapsed, the grand total 
  denominator (2,003 total delayed orders) is lost unless you execute a separate subquery or CTE join.
- With 'SUM(COUNT(d.order_id)) OVER ()', SQL computes the grand total across the window frame in memory 
  while retaining row-level city details.
- Furthermore, adding 'ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW' computes the cumulative Pareto curve!
- Management Insight: The top 5 cities (Nagpur, Surat, Bhopal, Chennai, Jaipur) account for ~37.4% of all 
  delayed shipments in the company. Resolving line-haul dispatch into these 5 hubs resolves over a third of
  all delivery failures nationally.
*/

