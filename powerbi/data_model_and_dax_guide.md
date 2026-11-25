# 📊 Power BI Architecture & DAX Implementation Manual
## Last-Mile Delivery Analytics & SLA Governance

> **Project Target:** Blitz Operations Analytics Portfolio  
> **Data Model Design:** Star Schema (1 Fact Table, 4 Dimension Tables)  
> **Report Structure:** 4 Distinct Executive & Analytical Pages  

---

## 1. Relational Star Schema Data Model

Instead of relying on a monolithic flat table, the enterprise architecture follows Kimball dimensional modeling best practices:

```
                  ┌──────────────────────┐
                  │      Dim_Cities      │
                  │──────────────────────│
                  │ * City_ID (PK)       │
                  │   City_Name          │
                  │   Zone               │
                  └──────────┬───────────┘
                             │ 1
                             │
                             │ *
┌──────────────────────┐     │     ┌──────────────────────┐
│     Dim_Vendors      │     │     │   Dim_DelayReasons   │
│──────────────────────│     │     │──────────────────────│
│ * Vendor_ID (PK)     │     │     │ * Reason_ID (PK)     │
│   Vendor_Name        │     │     │   Reason_Name        │
└──────────┬───────────┘     │     │   Reason_Category    │
           │ 1               │     └───────────┬──────────┘
           │                 │                 │ 1
           │ *               │                 │ *
  ┌────────┴─────────────────┴─────────────────┴────────┐
  │                   Fact_Deliveries                   │
  │─────────────────────────────────────────────────────│
  │ * Order_ID (PK)                                     │
  │   Order_Date (FK -> Dim_Date)                       │
  │   Promised_Delivery_Date                            │
  │   Actual_Delivery_Date                              │
  │   City_ID (FK -> Dim_Cities)                        │
  │   Vendor_ID (FK -> Dim_Vendors)                     │
  │   Reason_ID (FK -> Dim_DelayReasons)                │
  │   Warehouse_ID, Delivery_Agent_ID                   │
  │   Product_Category, Payment_Mode                    │
  │   Order_Value_INR, Delivery_Attempts                │
  │   Calculated_Delay_Days, Calculated_Delivery_Status │
  │   Calculated_SLA_Breach, Delivery_Lead_Time_Days    │
  └──────────────────────────┬──────────────────────────┘
                             │ *
                             │
                             │ 1
                  ┌──────────┴───────────┐
                  │       Dim_Date       │
                  │──────────────────────│
                  │ * Date (PK)          │
                  │   Year, Quarter      │
                  │   Month_Name, Month_No│
                  │   Day_of_Week        │
                  └──────────────────────┘
```

### Table Relationships & Cardinality:
- **`Dim_Cities` $\rightarrow$ `Fact_Deliveries`**: `1-to-Many` (`1:*`), Cross-filter direction: **Single** (`Dim_Cities` filters `Fact_Deliveries`).
- **`Dim_Vendors` $\rightarrow$ `Fact_Deliveries`**: `1-to-Many` (`1:*`), Cross-filter direction: **Single**.
- **`Dim_DelayReasons` $\rightarrow$ `Fact_Deliveries`**: `1-to-Many` (`1:*`), Cross-filter direction: **Single**.
- **`Dim_Date` $\rightarrow$ `Fact_Deliveries`**: `1-to-Many` (`1:*`) on `Fact_Deliveries[Order_Date_Date]`, Cross-filter direction: **Single**.

---

## 2. Core Concepts: Filter Context, Row Context & Slicers

In an interview (especially with senior analytics leaders at Blitz), being able to clearly explain why and how DAX evaluates expressions distinguishes top analysts:

### A. What is Filter Context?
- **Definition:** The set of active filters applied to the data model at the moment a measure is evaluated.
- **Sources of Filter Context:**
  1. **Visual headers / coordinates:** Row and column headers in a matrix, axis categories in a bar chart, data points in a scatter plot.
  2. **Report Slicers:** User selections on City, Vendor, or Date Range slicers.
  3. **Visual-Level, Page-Level, and Report-Level Filters** in the Filter Pane.
  4. **DAX Overrides via `CALCULATE()`:** Explicit filter arguments that inject, overwrite, or remove filters.

### B. What is Row Context?
- **Definition:** The concept of "current row" during an iteration.
- Row context exists automatically in **Calculated Columns** and inside **Iterator Functions** (`SUMX`, `AVERAGEX`, `FILTER`, `COUNTX`).
- **Crucial Distinction:** Row context does *not* filter other tables or measures on its own. For a row context to filter the data model, **Context Transition** must be triggered by wrapping an expression in `CALCULATE()`.

### C. Why Does a Measure Change When a Slicer is Selected?
- Unlike calculated columns (which are static, evaluated once at data refresh, and stored in RAM), **DAX measures are dynamic query-time formulas**.
- When a user selects a slicer (e.g., `City = "Bangalore"`):
  1. The slicer applies a filter on `Dim_Cities[City_Name] = "Bangalore"`.
  2. Through the active `1:*` relationship, this filter propagates downstream to `Fact_Deliveries`.
  3. The VertiPaq storage engine filters the rows of `Fact_Deliveries` down to only those where `City_ID` matches Bangalore.
  4. The DAX measure (e.g. `[On-Time Delivery %]`) is re-evaluated across this reduced active row partition.

---

## 3. Four-Page Report Specification

### Page 1 — Executive Overview
- **Objective:** High-level strategic health check for C-suite and Logistics VPs.
- **Visuals Layout:**
  - **Top Row KPI Cards (5 Cards):**
    1. `[Total Deliveries]` (Formatted `#,##0`)
    2. `[On-Time Delivery %]` (Target KPI with Callout Value and indicator vs 70% threshold)
    3. `[SLA Breach %]` (Conditional formatting: Red if > 25%, Green if < 20%)
    4. `[Average Delay Days (Delayed Deliveries Only)]` (Callout value in Days)
    5. `[Total GMV]` (Formatted `₹#,##0`)
  - **Main Visual (Left 60%):** Combined Line and Clustered Column Chart:
    - Shared Axis: `Dim_Date[Month_Name]` (Jan – Dec)
    - Column Values: `[Total Deliveries]`
    - Line Values: `[SLA Breach %]` and Constant Target Reference Line at 20%
  - **Right Visual (Top 40%):** Donut Chart:
    - Legend: `Fact_Deliveries[Calculated_Delivery_Status]` (`Early`, `On-Time`, `Delayed`)
    - Values: `[Total Deliveries]`
  - **Right Visual (Bottom 40%):** Clustered Bar Chart:
    - Y-Axis: `Fact_Deliveries[Product_Category]`
    - X-Axis: `[Total GMV]`
    - Tooltip: `[SLA Breach %]`

---

### Page 2 — City Performance
- **Objective:** Regional logistics management and hub capacity diagnostics.
- **Visuals Layout:**
  - **Top Slicers:** `Dim_Cities[Zone]` (Multi-select), `Dim_Date[Date]` (Date Range Slider).
  - **Primary Visual (Top 55%):** Clustered Bar Chart of Cities Ranked:
    - Y-Axis: `Dim_Cities[City_Name]`
    - X-Axis: `[On-Time Delivery %]` (Ranked descending)
    - Data Labels: On
    - Constant Line: Network Average On-Time %
  - **Secondary Visual (Bottom Left 45%):** Treemap / Donut of Regional Delay Contribution:
    - Group: `Dim_Cities[City_Name]`
    - Values: `[Delay Contribution %]` (Using `ALLSELECTED`)
  - **Secondary Visual (Bottom Right 45%):** Matrix Table:
    - Rows: `Dim_Cities[Zone]`, `Dim_Cities[City_Name]`
    - Values: `[Total Deliveries]`, `[On-Time Delivery %]`, `[SLA Breach %]`, `[Average Delay Days (Delayed Deliveries Only)]`, `[Average Delivery Lead Time Days]`
    - Conditional Formatting: Background color scales on `[SLA Breach %]`.

---

### Page 3 — Vendor Performance
- **Objective:** 3PL carrier scorecarding, contract renegotiation, and volume rebalancing.
- **Visuals Layout:**
  - **Top Row KPI Cards:** Top Performing Vendor, Lowest Breach Vendor, Highest GMV Carrier.
  - **Main Visual (Top Left 50%):** Clustered Column Chart:
    - X-Axis: `Dim_Vendors[Vendor_Name]`
    - Y-Axis: `[SLA Breach %]`
    - Reference Line: `[SLA Target Benchmark %]` (20%)
  - **Main Visual (Top Right 50%):** Scatter Chart (Carrier Efficiency Matrix):
    - X-Axis: `[Average Delivery Lead Time Days]` (Speed)
    - Y-Axis: `[SLA Breach %]` (Reliability)
    - Size: `[Total Deliveries]` (Volume)
    - Legend: `Dim_Vendors[Vendor_Name]`
    - Quadrant Lines: Average Lead Time & Benchmark SLA Breach %
  - **Bottom Visual:** 3PL Performance Table:
    - Columns: Vendor Name, Deliveries Handled, SLA Breach %, Variance to Network, Revenue at Risk.

---

### Page 4 — Root Cause Analysis & Data Quality
- **Objective:** Tactical troubleshooting, operational failure mitigation, and data integrity transparency.
- **Visuals Layout:**
  - **Top Left Visual:** Pareto Chart of Failure Causes:
    - X-Axis: `Dim_DelayReasons[Reason_Name]`
    - Column: `[Delayed Deliveries]`
    - Line: Cumulative Delay %
  - **Top Right Visual:** Clustered Column Chart (Seasonal Surge Impact):
    - X-Axis: Season (`Normal`, `Monsoon`, `Festive`)
    - Values: `[Delay Rate %]`, `[SLA Breach %]`
  - **Bottom Left Visual:** Payment Channel Fulfillment Analysis:
    - X-Axis: `Fact_Deliveries[Payment_Mode]` (`COD` vs `Prepaid`)
    - Y-Axis: `[Average Delivery Lead Time Days]` and Multi-attempt delivery count
  - **Bottom Right Visual (Data Quality Profiling Card):**
    - Audit Scorecard: Total Records (5,200), Uniqueness (100%), Legacy Delay Mismatches Reconciled (252), Legacy SLA Mismatches Reconciled (99), Unrecorded Reasons Resolved (233).

---

## 4. Power BI Palette & Corporate Theme JSON (`theme.json`)

To apply the modern logistics color palette to Power BI:
1. Open Power BI Desktop.
2. Go to **View** ribbon $\rightarrow$ **Themes** $\rightarrow$ **Browse for themes**.
3. Select `powerbi/theme.json`.

```json
{
  "name": "BlitzLogisticsTheme",
  "dataColors": [
    "#1E88E5",
    "#2E7D32",
    "#D32F2F",
    "#FB8C00",
    "#8E24AA",
    "#00ACC1",
    "#3949AB",
    "#7CB342"
  ],
  "background": "#FFFFFF",
  "foreground": "#212121",
  "tableAccent": "#1E88E5",
  "visualStyles": {
    "*": {
      "*": {
        "outspace": [{ "color": { "solid": { "color": "#FAFAFA" } } }],
        "border": [{ "show": true, "color": { "solid": { "color": "#E0E0E0" } }, "radius": 6 }]
      }
    }
  }
}
```

