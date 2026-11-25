-- ==============================================================================
-- FILE: 02_kpi_analysis.sql
-- PROJECT: Last-Mile Delivery Analytics (Blitz Internship Portfolio)
-- PURPOSE: Core Logistics KPIs, Network Dimensions & Vendor Aggregations
-- QUESTIONS COVERED: Q1 to Q5
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUESTION 1: How many total deliveries are there?
-- SQL Fundamental: COUNT()
-- Business Purpose: Measure gross operational dispatch volume across the network.
-- Critical for baseline throughput capacity planning and unit economics.
-- ------------------------------------------------------------------------------
SELECT 
    COUNT(*) AS total_deliveries,
    COUNT(order_id) AS total_orders,
    ROUND(SUM(order_value_inr), 2) AS total_gmv_inr
FROM deliveries;

/*
BUSINESS EXPLANATION:
- COUNT(*) counts every processed order row in the deliveries fact table.
- In logistics operations, delivery count is the primary driver of fleet sizing, 
  hub sortation labor requirements, and fuel expense forecasting.
- We also compute total Gross Merchandise Value (GMV) to evaluate total delivery exposure.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 2: How many unique cities and vendors are active in the delivery network?
-- SQL Fundamental: COUNT(DISTINCT ...)
-- Business Purpose: Assess geographic reach and vendor ecosystem diversity.
-- ------------------------------------------------------------------------------
SELECT 
    COUNT(DISTINCT city_id) AS total_active_cities,
    COUNT(DISTINCT vendor_id) AS total_active_vendors,
    COUNT(DISTINCT delivery_agent_id) AS total_delivery_executives,
    COUNT(DISTINCT warehouse_id) AS total_fulfillment_hubs
FROM deliveries;

/*
BUSINESS EXPLANATION:
- DISTINCT removes duplicate occurrences before aggregation, returning unique operational entities.
- If a delivery network relies too heavily on a single carrier or single hub, 
  concentration risk increases significantly. Tracking distinct partners ensures balanced allocation.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 3: What is the average delivery delay by city?
-- SQL Fundamental: GROUP BY, AVG(), ROUND()
-- Business Purpose: Pinpoint regional fulfillment friction and infrastructure bottlenecks.
-- ------------------------------------------------------------------------------
SELECT 
    c.city_name,
    c.zone,
    COUNT(d.order_id) AS total_deliveries,
    ROUND(AVG(d.calculated_delay_days), 2) AS network_avg_delay_days,
    ROUND(AVG(CASE WHEN d.calculated_delay_days > 0 THEN d.calculated_delay_days END), 2) AS avg_delay_when_late,
    ROUND(100.0 * SUM(CASE WHEN d.calculated_delivery_status = 'Delayed' THEN 1 ELSE 0 END) / COUNT(d.order_id), 2) AS delay_rate_pct
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
GROUP BY c.city_name, c.zone
ORDER BY network_avg_delay_days DESC;

/*
BUSINESS EXPLANATION:
- We group by city_name and zone to evaluate local delivery performance across regions.
- Notice the dual average calculation:
    1. 'network_avg_delay_days': Includes early deliveries (negative numbers) and on-time orders (0).
    2. 'avg_delay_when_late': Evaluates the average severity ONLY when an order is actually late.
- Cities like Nagpur, Surat, and Bhopal show higher average delays, indicating severe last-mile transit
  or local warehouse dispatch bottlenecks requiring route re-planning or secondary 3PL onboarding.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 4: Which vendors have the highest SLA breach rate?
-- SQL Fundamental: Aggregation, HAVING clause
-- Business Purpose: Carrier scorecarding and contractual penalty / chargeback enforcement.
-- ------------------------------------------------------------------------------
SELECT 
    v.vendor_name,
    COUNT(d.order_id) AS total_deliveries_assigned,
    SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS total_sla_breaches,
    ROUND(100.0 * SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) / COUNT(d.order_id), 2) AS sla_breach_rate_pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS avg_carrier_delay_days
FROM deliveries d
JOIN vendors v ON d.vendor_id = v.vendor_id
GROUP BY v.vendor_name
HAVING COUNT(d.order_id) >= 100
ORDER BY sla_breach_rate_pct DESC;

/*
BUSINESS EXPLANATION:
- WHY USE HAVING INSTEAD OF WHERE?
  'WHERE' filters individual rows before the aggregation takes place.
  'HAVING' filters aggregated groups after the GROUP BY is performed.
  Here, HAVING COUNT(d.order_id) >= 100 ensures we do not penalize or reward low-volume 
  carriers whose rates are distorted by small sample sizes (statistical variance).
- High SLA breach vendors (such as DTDC at ~30.4% and Dunzo at ~29.6%) face customer dissatisfaction
  and should receive lower dispatch volume allocation in next quarter's routing engine rules.
*/


-- ------------------------------------------------------------------------------
-- QUESTION 5: What are the most common delay reasons?
-- SQL Fundamental: GROUP BY, ORDER BY, Window Percentage
-- Business Purpose: Root cause analysis to separate carrier controllable failures from external factors.
-- ------------------------------------------------------------------------------
SELECT 
    r.reason_name,
    r.reason_category,
    COUNT(d.order_id) AS failure_occurrences,
    ROUND(SUM(d.order_value_inr), 2) AS gmv_impacted_inr,
    ROUND(100.0 * COUNT(d.order_id) / (
        SELECT COUNT(*) 
        FROM deliveries 
        WHERE calculated_delivery_status = 'Delayed'
    ), 2) AS pct_of_all_delays
FROM deliveries d
JOIN delay_reasons r ON d.reason_id = r.reason_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY r.reason_name, r.reason_category
ORDER BY failure_occurrences DESC;

/*
BUSINESS EXPLANATION:
- Identifies the Pareto distribution of failure mechanisms.
- 'Traffic Congestion' (~13.8%) and 'Warehouse Processing Delay' (~12.8%) represent the top two drivers.
- Categorization reveals:
    1. Operational / Controllable: Warehouse delays and Route optimization failures can be addressed
       through earlier shift handoffs and smarter dispatch routing algorithms.
    2. Customer-Driven: 'Customer Unavailable' and 'Wrong Address' require OTP confirmation and WhatsApp
       address validation prior to last-mile truck dispatch.
*/

