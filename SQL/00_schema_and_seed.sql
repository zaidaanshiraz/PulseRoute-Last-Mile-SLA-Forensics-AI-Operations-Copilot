-- ==============================================================================
-- FILE: 00_schema_and_seed.sql
-- PROJECT: Last-Mile Delivery Analytics (Blitz Internship Portfolio)
-- PURPOSE: Relational Schema DDL & Integrity Constraints
-- ==============================================================================

-- 1. Dimension Table: Cities
DROP TABLE IF EXISTS deliveries;
DROP TABLE IF EXISTS delay_reasons;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS cities;

CREATE TABLE cities (
    city_id INTEGER PRIMARY KEY,
    city_name VARCHAR(50) NOT NULL UNIQUE,
    zone VARCHAR(20) NOT NULL
);

-- 2. Dimension Table: 3PL Vendors / Courier Partners
CREATE TABLE vendors (
    vendor_id INTEGER PRIMARY KEY,
    vendor_name VARCHAR(50) NOT NULL UNIQUE
);

-- 3. Dimension Table: Delay Root Causes
CREATE TABLE delay_reasons (
    reason_id INTEGER PRIMARY KEY,
    reason_name VARCHAR(100) NOT NULL UNIQUE,
    reason_category VARCHAR(50) NOT NULL
);

-- 4. Fact Table: Deliveries
CREATE TABLE deliveries (
    order_id VARCHAR(20) PRIMARY KEY,
    order_date TIMESTAMP NOT NULL,
    promised_delivery_date DATE NOT NULL,
    actual_delivery_date DATE NOT NULL,
    city_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    reason_id INTEGER,
    warehouse_id VARCHAR(20) NOT NULL,
    delivery_agent_id VARCHAR(20) NOT NULL,
    product_category VARCHAR(50) NOT NULL,
    order_value_inr NUMERIC(10, 2) NOT NULL,
    payment_mode VARCHAR(20) NOT NULL,
    delivery_attempts INTEGER NOT NULL,
    is_festive_season VARCHAR(3) NOT NULL,
    is_monsoon_season VARCHAR(3) NOT NULL,
    -- Source system legacy fields (preserved for audit)
    delay_days_raw INTEGER NOT NULL,
    is_delayed_raw VARCHAR(3) NOT NULL,
    sla_breached_raw VARCHAR(3) NOT NULL,
    -- Derived ground-truth audit fields
    calculated_delay_days INTEGER NOT NULL,
    calculated_delivery_status VARCHAR(20) NOT NULL,
    calculated_sla_breach VARCHAR(3) NOT NULL,
    delivery_lead_time_days INTEGER NOT NULL,
    -- Referential Integrity Constraints
    CONSTRAINT fk_deliveries_city FOREIGN KEY (city_id) REFERENCES cities (city_id),
    CONSTRAINT fk_deliveries_vendor FOREIGN KEY (vendor_id) REFERENCES vendors (vendor_id),
    CONSTRAINT fk_deliveries_reason FOREIGN KEY (reason_id) REFERENCES delay_reasons (reason_id)
);

-- Create Indexes for Query Performance Optimization
CREATE INDEX idx_deliveries_city ON deliveries (city_id);
CREATE INDEX idx_deliveries_vendor ON deliveries (vendor_id);
CREATE INDEX idx_deliveries_status ON deliveries (calculated_delivery_status);
CREATE INDEX idx_deliveries_sla ON deliveries (calculated_sla_breach);
CREATE INDEX idx_deliveries_order_date ON deliveries (order_date);

