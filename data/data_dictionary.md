# 📖 Data Dictionary: Last-Mile Delivery Analytics

> **Dataset Classification:** Synthetic E-Commerce Delivery Operations Dataset  
> **Total Records:** 5,200 orders  
> **Temporal Coverage:** January 2024 – December 2024  
> **Geographic Scope:** 15 Indian Tier-1 and Tier-2 Cities (5 Zones)  
> **Logistics Partners:** 8 3PL Carriers / Logistics Vendors  

---

## 1. Raw Source Columns

| Column Name | Data Type | Example | Description | Quality & Audit Notes |
| :--- | :--- | :--- | :--- | :--- |
| `Order_ID` | String (Categorical) | `ORD100000` | Unique alphanumeric identifier for each order. | Primary key. Verified 0 duplicate keys across 5,200 records. |
| `Order_Date` | Datetime (`YYYY-MM-DD HH:MM`) | `2024-02-27 00:47` | Timestamp when the customer placed the order. | Datetime granularity with hours and minutes. |
| `Promised_Delivery_Date` | Date (`YYYY-MM-DD`) | `2024-03-01` | Committed delivery date provided to the customer at checkout. | Standard SLA commitment baseline. |
| `Actual_Delivery_Date` | Date (`YYYY-MM-DD`) | `2024-03-03` | Date package was marked delivered by carrier. | Date-level granularity (midnight timestamp `00:00:00`). |
| `City` | String (Categorical) | `Surat` | Delivery destination city (15 unique cities across India). | Clean categorical field, no nulls. |
| `Zone` | String (Categorical) | `West` | Geographical zone: `North`, `South`, `East`, `West`, `Central`. | Macro operational region. |
| `Warehouse_ID` | String (Categorical) | `WH_SRT_01` | Origin fulfillment fulfillment center / warehouse ID. | Format `WH_<CITY_CODE>_<SEQ>`. |
| `Delivery_Agent_ID` | String (Categorical) | `AGT_0008` | Unique ID of the last-mile delivery executive. | 150 unique delivery agents tracked. |
| `Vendor` | String (Categorical) | `BlueDart` | 3PL logistics service provider (e.g., Delhivery, BlueDart, Ekart, Dunzo, etc.). | 8 active courier partners. |
| `Product_Category` | String (Categorical) | `Beauty` | Merchandise category (Electronics, Fashion, Groceries, Beauty, Books, etc.). | 8 retail categories. |
| `Order_Value_INR` | Float (Monetary) | `10198.99` | Gross order value in Indian Rupees (₹). | Min ₹155.10, Max ₹14,998.63. Zero negatives. |
| `Payment_Mode` | String (Categorical) | `Prepaid` | Customer payment channel: `Prepaid` or `COD` (Cash on Delivery). | Crucial factor in driver cash handling and delivery attempts. |
| `Promised_Delivery_Days`| Integer | `3` | Promised delivery window in days (`Promised_Delivery_Date - Order_Date`). | Pre-calculated in source system. |
| `Actual_Delivery_Days` | Integer | `5` | Total elapsed delivery days from order placement. | **Data Quality Issue:** Stored as `Promised_Delivery_Days + Delay_Days` rather than true date difference. |
| `Delay_Days` | Integer | `2` | Recorded delay days in raw system. | **Data Quality Issue:** 252 mismatches vs true calendar difference ($\text{Actual} - \text{Promised}$). Capped at 0 for early deliveries. |
| `Is_Delayed` | String (`Yes`/`No`) | `Yes` | Raw binary flag indicating delayed delivery. | **Data Quality Issue:** 233 orders with early/on-time dates were falsely flagged as `Yes`. |
| `Delay_Reason` | String (Nullable) | `Wrong Address` | Root cause assigned by carrier when delivery was delayed. | Null for on-time deliveries. Had 233 nulls among rows marked `Is_Delayed = 'Yes'`. |
| `SLA_Breached` | String (`Yes`/`No`) | `No` | Raw binary flag indicating SLA breach (>2 days late). | **Data Quality Issue:** 99 records had `Delay_Days = 3` but `SLA_Breached = 'No'` because true date delay was $\le 0$. |
| `Delivery_Attempts` | Integer | `1` | Number of physical delivery attempts made by agent (1 to 3). | Multi-attempt deliveries directly correlate with customer availability delays. |
| `Month` | String | `February` | Month name of the order placement. | Used for seasonal trend analysis. |
| `Quarter` | String | `Q1` | Quarter (`Q1`, `Q2`, `Q3`, `Q4`) of the order placement. | Fiscal/operational quarterly aggregation. |
| `Is_Festive_Season` | String (`Yes`/`No`) | `No` | Flag indicating major Indian festive shopping peak (October–November). | Captures volume surges (Diwali, Dussehra, Big Billion Days). |
| `Is_Monsoon_Season` | String (`Yes`/`No`) | `No` | Flag indicating peak monsoon season (June–September). | Captures weather and road disruption impacts. |

---

## 2. Derived & Enriched Columns (Calculated for Audit & Reporting)

These derived columns are computed deterministically from the ground-truth calendar dates rather than relying on flawed source-system flags:

| Derived Column Name | Data Type | Business Formula / Logic | Description |
| :--- | :--- | :--- | :--- |
| `Calculated_Delay_Days` | Integer | `DATEDIFF(day, Promised_Delivery_Date, Actual_Delivery_Date)` | True operational delay in calendar days. Positive = days late; 0 = on promised date; Negative = days early. |
| `Calculated_Delivery_Status`| String | `CASE WHEN Calculated_Delay_Days < 0 THEN 'Early' WHEN Calculated_Delay_Days = 0 THEN 'On-Time' ELSE 'Delayed' END` | Operational classification of delivery timing. Both Early and On-Time meet customer commitments. |
| `Calculated_SLA_Breach` | String (`Yes`/`No`)| `CASE WHEN Calculated_Delay_Days > 2 THEN 'Yes' ELSE 'No' END` | Strict adherence to the SLA contract: breached if package arrives > 2 calendar days after promised date. |
| `Delivery_Lead_Time_Days`| Integer | `DATEDIFF(day, CAST(Order_Date AS DATE), Actual_Delivery_Date)` | Total end-to-end fulfillment cycle time from placement to doorstep. Normalized to calendar day. |
| `Promised_Lead_Time_Days`| Integer | `DATEDIFF(day, CAST(Order_Date AS DATE), Promised_Delivery_Date)` | Total promised fulfillment window from placement date. |
| `Cleaned_Delay_Reason` | String | If Early/On-Time $\rightarrow$ `'Not Applicable (On-Time/Early)'`; If Delayed & Null $\rightarrow$ `'Unrecorded / Operational Delay'`; Else keep Reason. | Resolves misleading nulls in business reporting. |
| `Data_Quality_Flag` | String | Multi-condition audit classification tagging source anomalies. | Explicit tag categorizing specific data discrepancies found in the record. |
| `DQ_Delay_Mismatch` | Boolean | `Delay_Days != Calculated_Delay_Days` | Boolean audit flag detecting delay calculation discrepancies (1,723 total; 252 among marked delays). |
| `DQ_SLA_Mismatch` | Boolean | `SLA_Breached != (Delay_Days > 2)` | Boolean audit flag detecting the 99 records where stored SLA flag disagreed with stored delay days. |
| `DQ_Missing_Reason_Delayed`| Boolean | `Is_Delayed = 'Yes' AND Delay_Reason IS NULL` | Boolean audit flag pinpointing the 233 falsely delayed deliveries. |
| `DQ_Same_Day_Timestamp_Effect`| Boolean | `(Actual_Delivery_Date - Order_Date) < 0` at timestamp level | Captures the 324 same-day deliveries where order timestamp was after midnight date truncation. |

---

## 3. Business Definitions & Operational Rules

### Delivery On-Time Rule:
- **Early Delivery:** $\text{Actual Delivery Date} < \text{Promised Delivery Date}$ ($\text{Delay} < 0$)
- **On-Time Delivery:** $\text{Actual Delivery Date} = \text{Promised Delivery Date}$ ($\text{Delay} = 0$)
- **Delayed Delivery:** $\text{Actual Delivery Date} > \text{Promised Delivery Date}$ ($\text{Delay} > 0$)

### SLA Breach Rule:
- Contractual agreement permits up to 2 grace days beyond the promised date before a penalty is assessed.
- An order is **SLA Breached** if and only if $\text{Delay Days} > 2$ ($\ge 3$ days late).

### KPI Denominator Consistency:
- **Total Deliveries:** Count of all completed delivery dispatches within the selected scope.
- **On-Time Delivery %:** $\frac{\text{Orders with Calculated\_Delay\_Days} \le 0}{\text{Total Eligible Deliveries}} \times 100$
- **Delayed Delivery %:** $\frac{\text{Orders with Calculated\_Delay\_Days} > 0}{\text{Total Eligible Deliveries}} \times 100$
- **SLA Breach %:** $\frac{\text{Orders with Calculated\_Delay\_Days} > 2}{\text{Total Eligible Deliveries}} \times 100$
- **Average Delay Days (Delayed Only):** Mean delay days calculated strictly over the cohort of orders that experienced delays ($\text{Calculated\_Delay\_Days} > 0$).
- **Average Lead Time:** Mean total days from order placement date to actual delivery date across eligible orders.

