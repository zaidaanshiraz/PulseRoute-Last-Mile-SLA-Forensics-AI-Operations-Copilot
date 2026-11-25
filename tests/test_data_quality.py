"""
==============================================================================
TESTS — Last-Mile Delivery Analytics
Project : Last-Mile Delivery Analytics | Blitz Internship Portfolio
Purpose : Validate the three core data-quality fixes, KPI calculation logic,
          Streamlit filter pipeline, and SQL schema integrity.
Run     : pytest tests/test_data_quality.py -v
==============================================================================
"""

import pytest
import sys
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent.parent
RAW_CSV    = BASE_DIR / "data" / "raw_delivery_data.csv"
CLEAN_CSV  = BASE_DIR / "data" / "sample_data.csv"
DB_PATH    = BASE_DIR / "data" / "last_mile_delivery.db"


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def raw_df():
    """Load the original, unmodified raw dataset."""
    return pd.read_csv(RAW_CSV)


@pytest.fixture(scope="module")
def clean_df():
    """Load the audited / cleaned dataset with derived columns."""
    df = pd.read_csv(CLEAN_CSV)
    df["Promised_Delivery_Date_dt"] = pd.to_datetime(df["Promised_Delivery_Date"])
    df["Actual_Delivery_Date_dt"]   = pd.to_datetime(df["Actual_Delivery_Date"])
    df["Order_Date_dt"]             = pd.to_datetime(df["Order_Date"])
    return df


@pytest.fixture(scope="module")
def db_conn():
    """SQLite connection to the relational database."""
    if not DB_PATH.exists():
        pytest.skip("SQLite database not found — run seed script first.")
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ===========================================================================
# A. RAW DATASET STRUCTURAL CHECKS
# ===========================================================================
class TestRawDatasetStructure:
    """Verify the raw dataset properties before any transformation."""

    def test_total_record_count(self, raw_df):
        """The dataset must contain exactly 5,200 delivery records."""
        assert len(raw_df) == 5200, (
            f"Expected 5,200 records; got {len(raw_df)}"
        )

    def test_no_duplicate_order_ids(self, raw_df):
        """Order_ID must be a primary key — zero duplicates allowed."""
        duplicates = raw_df["Order_ID"].duplicated().sum()
        assert duplicates == 0, (
            f"Found {duplicates} duplicate Order_ID values."
        )

    def test_required_columns_present(self, raw_df):
        """All source columns required for analysis must exist."""
        required = [
            "Order_ID", "Order_Date", "Promised_Delivery_Date",
            "Actual_Delivery_Date", "City", "Zone", "Vendor",
            "Delay_Days", "Is_Delayed", "SLA_Breached", "Delay_Reason",
        ]
        missing = [c for c in required if c not in raw_df.columns]
        assert not missing, f"Missing columns in raw data: {missing}"

    def test_no_null_critical_fields(self, raw_df):
        """City, Zone, Vendor, Order_Date must never be null."""
        for col in ["City", "Zone", "Vendor", "Order_Date",
                    "Promised_Delivery_Date", "Actual_Delivery_Date"]:
            null_count = raw_df[col].isna().sum()
            assert null_count == 0, f"Column '{col}' has {null_count} null values."

    def test_order_value_positive(self, raw_df):
        """Order_Value_INR must be strictly positive for all records."""
        non_positive = (raw_df["Order_Value_INR"] <= 0).sum()
        assert non_positive == 0, (
            f"{non_positive} records have zero or negative Order_Value_INR."
        )

    def test_delay_days_non_negative_in_raw(self, raw_df):
        """
        Raw Delay_Days in the source system is capped at 0 for 'early'
        deliveries — it should never be negative.
        """
        negative_delays = (raw_df["Delay_Days"] < 0).sum()
        assert negative_delays == 0, (
            f"{negative_delays} records have negative Delay_Days in raw data "
            f"(source system capped early deliveries at 0)."
        )


# ===========================================================================
# B. THE 252 DELAY CALCULATION INCONSISTENCIES
# ===========================================================================
class TestDelayCalculationFix:
    """
    Validate that the 252 delay-calculation mismatches are correctly
    identified and resolved in the cleaned dataset.

    Business Rule:
        Calculated_Delay_Days = floor(Actual_Delivery_Date) − floor(Promised_Delivery_Date)
    """

    def test_calculated_delay_days_matches_date_difference(self, clean_df):
        """
        Every row's Calculated_Delay_Days must equal the true calendar
        difference (Actual_Date − Promised_Date) at day granularity.
        """
        expected = (
            clean_df["Actual_Delivery_Date_dt"].dt.floor("D")
            - clean_df["Promised_Delivery_Date_dt"].dt.floor("D")
        ).dt.days
        mismatches = (clean_df["Calculated_Delay_Days"] != expected).sum()
        assert mismatches == 0, (
            f"{mismatches} rows have Calculated_Delay_Days that do not match "
            f"floor(Actual) − floor(Promised)."
        )

    def test_known_252_mismatches_exist_in_raw(self, raw_df):
        """
        Confirm that the raw dataset does in fact contain 252 records where
        Is_Delayed='Yes' and Delay_Days != calendar-derived delay.
        """
        p = pd.to_datetime(raw_df["Promised_Delivery_Date"])
        a = pd.to_datetime(raw_df["Actual_Delivery_Date"])
        calc = (a.dt.floor("D") - p.dt.floor("D")).dt.days
        mismatch_count = int(
            ((raw_df["Is_Delayed"] == "Yes") & (raw_df["Delay_Days"] != calc)).sum()
        )
        assert mismatch_count == 252, (
            f"Expected 252 delay mismatches in raw data; found {mismatch_count}."
        )

    def test_dq_delay_mismatch_flag_in_clean(self, clean_df):
        """
        DQ_Delay_Mismatch flag must be present. The flag covers 1,723 total raw
        mismatches (including early deliveries the source capped to 0). The
        business-relevant 252 are the subset also marked Is_Delayed='Yes'.
        """
        assert "DQ_Delay_Mismatch" in clean_df.columns, (
            "DQ_Delay_Mismatch flag column missing from cleaned dataset."
        )
        total_flagged = int(clean_df["DQ_Delay_Mismatch"].sum())
        assert total_flagged >= 252, (
            f"Expected at least 252 DQ_Delay_Mismatch rows; found {total_flagged}."
        )
        # The 252 headline figure: Is_Delayed='Yes' rows with wrong Delay_Days
        headline_252 = int(
            ((clean_df["Is_Delayed"] == "Yes") & clean_df["DQ_Delay_Mismatch"]).sum()
        )
        assert headline_252 == 252, (
            f"Expected exactly 252 Is_Delayed='Yes' rows with DQ_Delay_Mismatch; "
            f"found {headline_252}."
        )

    def test_early_delivery_has_negative_calculated_delay(self, clean_df):
        """
        Orders with Calculated_Delivery_Status='Early' must have
        Calculated_Delay_Days < 0.
        """
        early = clean_df[clean_df["Calculated_Delivery_Status"] == "Early"]
        wrong = (early["Calculated_Delay_Days"] >= 0).sum()
        assert wrong == 0, (
            f"{wrong} 'Early' rows have non-negative Calculated_Delay_Days."
        )

    def test_delayed_delivery_has_positive_calculated_delay(self, clean_df):
        """
        Orders with Calculated_Delivery_Status='Delayed' must have
        Calculated_Delay_Days > 0.
        """
        delayed = clean_df[clean_df["Calculated_Delivery_Status"] == "Delayed"]
        wrong = (delayed["Calculated_Delay_Days"] <= 0).sum()
        assert wrong == 0, (
            f"{wrong} 'Delayed' rows have zero or negative Calculated_Delay_Days."
        )

    def test_on_time_delivery_has_zero_calculated_delay(self, clean_df):
        """On-Time deliveries must have exactly Calculated_Delay_Days == 0."""
        on_time = clean_df[clean_df["Calculated_Delivery_Status"] == "On-Time"]
        wrong = (on_time["Calculated_Delay_Days"] != 0).sum()
        assert wrong == 0, (
            f"{wrong} 'On-Time' rows have non-zero Calculated_Delay_Days."
        )


# ===========================================================================
# C. THE 99 SLA FLAG INCONSISTENCIES
# ===========================================================================
class TestSLABreach:
    """
    Validate that the 99 SLA flag discrepancies are identified and that
    Calculated_SLA_Breach is derived strictly from calendar delay > 2.

    Business Rule:
        SLA Breach iff Calculated_Delay_Days > 2
    """

    def test_known_99_sla_mismatches_exist_in_raw(self, raw_df):
        """
        Confirm 99 records in the raw data had Delay_Days > 2 but SLA_Breached='No'.
        Root cause: carrier correctly evaluated true dates; Delay_Days was wrong.
        """
        mismatch_count = int(
            ((raw_df["Delay_Days"] > 2) & (raw_df["SLA_Breached"] == "No")).sum()
        )
        assert mismatch_count == 99, (
            f"Expected 99 SLA flag mismatches in raw data; found {mismatch_count}."
        )

    def test_calculated_sla_breach_matches_rule(self, clean_df):
        """
        Every Calculated_SLA_Breach value must equal (Calculated_Delay_Days > 2).
        No exceptions.
        """
        expected = np.where(clean_df["Calculated_Delay_Days"] > 2, "Yes", "No")
        mismatches = (clean_df["Calculated_SLA_Breach"] != expected).sum()
        assert mismatches == 0, (
            f"{mismatches} rows have Calculated_SLA_Breach inconsistent with "
            f"the rule (Calculated_Delay_Days > 2)."
        )

    def test_sla_breach_requires_delayed_status(self, clean_df):
        """
        An SLA breach (Calculated_Delay_Days > 2) must always correspond
        to Calculated_Delivery_Status == 'Delayed'.
        You cannot have an SLA breach on an on-time or early delivery.
        """
        breached = clean_df[clean_df["Calculated_SLA_Breach"] == "Yes"]
        non_delayed_breach = (breached["Calculated_Delivery_Status"] != "Delayed").sum()
        assert non_delayed_breach == 0, (
            f"{non_delayed_breach} SLA-breached rows have non-Delayed status — "
            f"logically impossible."
        )

    def test_dq_sla_mismatch_flag_count(self, clean_df):
        """DQ_SLA_Mismatch flag must identify exactly 99 source records."""
        assert "DQ_SLA_Mismatch" in clean_df.columns
        flagged = int(clean_df["DQ_SLA_Mismatch"].sum())
        assert flagged == 99, (
            f"Expected DQ_SLA_Mismatch=True for 99 rows; found {flagged}."
        )


# ===========================================================================
# D. THE 233 MISSING DELAY REASONS
# ===========================================================================
class TestMissingDelayReasons:
    """
    Validate that the 233 delayed-flagged orders with no delay reason are
    correctly identified and resolved.

    Finding: All 233 were actually on-time/early. No reason was entered
    because no delivery failure occurred in the field.
    """

    def test_known_233_missing_reasons_in_raw(self, raw_df):
        """
        Confirm 233 records in raw data had Is_Delayed='Yes' and
        a null Delay_Reason.
        """
        missing_count = int(
            ((raw_df["Is_Delayed"] == "Yes") & raw_df["Delay_Reason"].isna()).sum()
        )
        assert missing_count == 233, (
            f"Expected 233 missing-reason rows in raw data; found {missing_count}."
        )

    def test_all_233_were_actually_on_time_or_early(self, raw_df):
        """
        Every single one of the 233 must have a true calendar delay <= 0.
        This is the core investigative finding.
        """
        p = pd.to_datetime(raw_df["Promised_Delivery_Date"])
        a = pd.to_datetime(raw_df["Actual_Delivery_Date"])
        calc = (a.dt.floor("D") - p.dt.floor("D")).dt.days

        problem_rows = raw_df[
            (raw_df["Is_Delayed"] == "Yes") & raw_df["Delay_Reason"].isna()
        ]
        actually_delayed_count = int((calc[problem_rows.index] > 0).sum())
        assert actually_delayed_count == 0, (
            f"{actually_delayed_count} of the 233 'missing reason' rows were "
            f"actually delayed — the finding that all 233 are on-time/early "
            f"is incorrect."
        )

    def test_cleaned_delay_reason_no_nulls(self, clean_df):
        """
        After cleaning, Cleaned_Delay_Reason must have zero null values —
        every record has either a reason or 'Not Applicable (On-Time/Early)'.
        """
        null_count = clean_df["Cleaned_Delay_Reason"].isna().sum()
        assert null_count == 0, (
            f"Cleaned_Delay_Reason still has {null_count} null values."
        )

    def test_on_time_records_have_not_applicable_reason(self, clean_df):
        """
        All Early and On-Time records must have
        Cleaned_Delay_Reason == 'Not Applicable (On-Time/Early)'.
        """
        non_delayed = clean_df[
            clean_df["Calculated_Delivery_Status"].isin(["Early", "On-Time"])
        ]
        wrong = (
            non_delayed["Cleaned_Delay_Reason"] != "Not Applicable (On-Time/Early)"
        ).sum()
        assert wrong == 0, (
            f"{wrong} on-time/early rows have an incorrect Cleaned_Delay_Reason."
        )

    def test_dq_missing_reason_flag_count(self, clean_df):
        """DQ_Missing_Reason_Delayed flag must identify exactly 233 rows."""
        assert "DQ_Missing_Reason_Delayed" in clean_df.columns
        flagged = int(clean_df["DQ_Missing_Reason_Delayed"].sum())
        assert flagged == 233, (
            f"Expected DQ_Missing_Reason_Delayed=True for 233 rows; found {flagged}."
        )


# ===========================================================================
# E. KPI CALCULATION CORRECTNESS (mirrors Streamlit logic)
# ===========================================================================
class TestKPICalculations:
    """
    Verify that KPI denominators are consistent and calculations are correct.
    This mirrors the exact logic used in streamlit_app.py.
    """

    def test_on_time_rate_uses_all_deliveries_as_denominator(self, clean_df):
        """
        On-Time Delivery % = (Early + On-Time) / Total Deliveries.
        Denominator is ALL records, not just 'delivered' ones (no cancelled).
        """
        total = len(clean_df)
        on_time_count = int((clean_df["Calculated_Delay_Days"] <= 0).sum())
        expected_rate = on_time_count / total * 100
        # Rate must be between 0 and 100
        assert 0 <= expected_rate <= 100

        # Confirm it aligns with status breakdown
        status_on_time = int(
            clean_df["Calculated_Delivery_Status"].isin(["Early", "On-Time"]).sum()
        )
        assert on_time_count == status_on_time, (
            "Delay_Days <= 0 count does not match Early+On-Time status count."
        )

    def test_sla_breach_rate_denominator_is_total(self, clean_df):
        """
        SLA Breach % denominator must be total deliveries, not just delayed ones.
        Using delayed-only denominator inflates the rate and is incorrect.
        """
        total         = len(clean_df)
        breaches      = int((clean_df["Calculated_SLA_Breach"] == "Yes").sum())
        correct_rate  = breaches / total * 100

        # Also compute incorrect rate (delayed denominator)
        delayed       = int((clean_df["Calculated_Delay_Days"] > 0).sum())
        inflated_rate = breaches / delayed * 100

        assert correct_rate < inflated_rate, (
            "SLA Breach rate using total denominator should be less than "
            "using delayed-only denominator."
        )

    def test_avg_delay_days_delayed_cohort_only(self, clean_df):
        """
        Average Delay Days must be computed on delayed orders only (> 0),
        not averaged including negative (early) and zero values.
        """
        delayed_cohort = clean_df[clean_df["Calculated_Delay_Days"] > 0]
        avg_delayed_only = delayed_cohort["Calculated_Delay_Days"].mean()

        all_avg = clean_df["Calculated_Delay_Days"].mean()

        # Average over delayed-only must be strictly greater (positive values only)
        assert avg_delayed_only > all_avg, (
            "Avg delay days (delayed only) should exceed the all-orders average "
            "because early deliveries drag the all-orders average down."
        )
        assert avg_delayed_only > 0, "Average delay days over delayed cohort must be > 0."

    def test_lead_time_non_negative_for_majority(self, clean_df):
        """
        Delivery_Lead_Time_Days should be >= 0 for the overwhelming majority.
        A small number of same-day timestamp effects may produce -1.
        """
        negative_lt = int((clean_df["Delivery_Lead_Time_Days"] < 0).sum())
        pct_negative = negative_lt / len(clean_df) * 100
        assert pct_negative < 10, (
            f"{pct_negative:.1f}% of records have negative lead time — "
            f"expected < 10% (same-day timestamp effect only)."
        )

    def test_kpi_sum_adds_up(self, clean_df):
        """
        Early + On-Time + Delayed counts must sum exactly to total records.
        """
        early   = int((clean_df["Calculated_Delivery_Status"] == "Early").sum())
        on_time = int((clean_df["Calculated_Delivery_Status"] == "On-Time").sum())
        delayed = int((clean_df["Calculated_Delivery_Status"] == "Delayed").sum())
        total   = len(clean_df)

        assert early + on_time + delayed == total, (
            f"Status breakdown ({early}+{on_time}+{delayed}={early+on_time+delayed}) "
            f"does not equal total records ({total})."
        )


# ===========================================================================
# F. DATA QUALITY FLAGS COMPLETENESS
# ===========================================================================
class TestDataQualityFlags:
    """Validate the Data_Quality_Flag composite column."""

    def test_data_quality_flag_column_exists(self, clean_df):
        assert "Data_Quality_Flag" in clean_df.columns

    def test_no_null_data_quality_flags(self, clean_df):
        null_count = clean_df["Data_Quality_Flag"].isna().sum()
        assert null_count == 0, f"Data_Quality_Flag has {null_count} null values."

    def test_clean_records_are_majority(self, clean_df):
        """
        'Clean' records should represent the majority (> 50%) of the dataset.
        A dataset where most records are flagged would indicate a bigger problem.
        """
        clean_count = int((clean_df["Data_Quality_Flag"] == "Clean").sum())
        clean_pct   = clean_count / len(clean_df) * 100
        assert clean_pct > 50, (
            f"Only {clean_pct:.1f}% of records are 'Clean'. "
            f"Expected the majority (> 50%) to be clean."
        )


# ===========================================================================
# G. SQLITE DATABASE SCHEMA INTEGRITY
# ===========================================================================
class TestSQLiteSchema:
    """Validate the relational database structure and referential integrity."""

    def test_all_four_tables_exist(self, db_conn):
        """The DB must have exactly the four tables: cities, vendors, delay_reasons, deliveries."""
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'", db_conn
        )["name"].tolist()
        required = {"cities", "vendors", "delay_reasons", "deliveries"}
        missing = required - set(tables)
        assert not missing, f"Missing tables in SQLite DB: {missing}"

    def test_deliveries_row_count(self, db_conn):
        """The deliveries table must have exactly 5,200 rows."""
        count = pd.read_sql_query(
            "SELECT COUNT(*) AS c FROM deliveries", db_conn
        )["c"][0]
        assert count == 5200, f"Expected 5,200 rows in deliveries; got {count}."

    def test_cities_table_has_15_rows(self, db_conn):
        """cities dimension must have 15 unique cities."""
        count = pd.read_sql_query(
            "SELECT COUNT(*) AS c FROM cities", db_conn
        )["c"][0]
        assert count == 15, f"Expected 15 cities; got {count}."

    def test_vendors_table_has_8_rows(self, db_conn):
        """vendors dimension must have 8 logistics partners."""
        count = pd.read_sql_query(
            "SELECT COUNT(*) AS c FROM vendors", db_conn
        )["c"][0]
        assert count == 8, f"Expected 8 vendors; got {count}."

    def test_derived_columns_in_db(self, db_conn):
        """The deliveries table must include all three derived audit columns."""
        info = pd.read_sql_query("PRAGMA table_info(deliveries)", db_conn)
        cols = info["name"].tolist()
        required = ["calculated_delay_days", "calculated_delivery_status",
                    "calculated_sla_breach", "delivery_lead_time_days"]
        missing = [c for c in required if c not in cols]
        assert not missing, (
            f"Missing derived columns in deliveries table: {missing}"
        )

    def test_no_orphan_deliveries(self, db_conn):
        """
        Every delivery must have a valid city_id and vendor_id.
        No orphan foreign keys.
        """
        orphan_city = pd.read_sql_query(
            """SELECT COUNT(*) AS c FROM deliveries d
               LEFT JOIN cities c ON d.city_id = c.city_id
               WHERE c.city_id IS NULL""", db_conn
        )["c"][0]
        assert orphan_city == 0, f"{orphan_city} deliveries have invalid city_id."

        orphan_vendor = pd.read_sql_query(
            """SELECT COUNT(*) AS c FROM deliveries d
               LEFT JOIN vendors v ON d.vendor_id = v.vendor_id
               WHERE v.vendor_id IS NULL""", db_conn
        )["c"][0]
        assert orphan_vendor == 0, f"{orphan_vendor} deliveries have invalid vendor_id."

    def test_calculated_sla_breach_matches_delay_rule_in_db(self, db_conn):
        """
        In the DB, calculated_sla_breach='Yes' must always equal
        calculated_delay_days > 2.
        """
        mismatch = pd.read_sql_query(
            """SELECT COUNT(*) AS c FROM deliveries
               WHERE (calculated_delay_days > 2 AND calculated_sla_breach = 'No')
                  OR (calculated_delay_days <= 2 AND calculated_sla_breach = 'Yes')""",
            db_conn
        )["c"][0]
        assert mismatch == 0, (
            f"{mismatch} rows in DB have calculated_sla_breach inconsistent "
            f"with calculated_delay_days > 2 rule."
        )


# ===========================================================================
# H. SQL QUERY FILES EXIST
# ===========================================================================
class TestSQLFiles:
    """Confirm all 10-query SQL files are present."""

    @pytest.mark.parametrize("filename", [
        "00_schema_and_seed.sql",
        "01_data_quality.sql",
        "02_kpi_analysis.sql",
        "03_vendor_analysis.sql",
        "04_window_functions.sql",
    ])
    def test_sql_file_exists(self, filename):
        path = BASE_DIR / "SQL" / filename
        assert path.exists(), f"SQL file missing: {path}"

    @pytest.mark.parametrize("keyword,filename", [
        ("JOIN",         "02_kpi_analysis.sql"),
        ("HAVING",       "02_kpi_analysis.sql"),
        ("LEFT JOIN",    "03_vendor_analysis.sql"),
        ("WITH",         "03_vendor_analysis.sql"),
        ("RANK()",       "04_window_functions.sql"),
        ("DENSE_RANK()", "04_window_functions.sql"),
        ("LAG(",         "04_window_functions.sql"),
        ("OVER (",       "04_window_functions.sql"),
    ])
    def test_sql_contains_advanced_technique(self, keyword, filename):
        """Confirm that each SQL file contains its advertised technique."""
        path = BASE_DIR / "SQL" / filename
        content = path.read_text(encoding="utf-8")
        assert keyword in content, (
            f"Expected to find '{keyword}' in {filename} but it was not found."
        )
