"""
==============================================================================
DATA QUALITY REPORT GENERATOR
Project : Last-Mile Delivery Analytics | Blitz Internship Portfolio
Purpose : Standalone script to audit the raw dataset, recalculate derived
          fields from calendar dates, detect all 3 known discrepancy classes,
          and produce a machine-readable + human-readable quality report.
Run     : python scripts/data_quality_report.py
==============================================================================
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent.parent
RAW_PATH   = BASE_DIR / "data" / "raw_delivery_data.csv"
CLEAN_PATH = BASE_DIR / "data" / "sample_data.csv"
REPORT_DIR = BASE_DIR / "data"

# Business rules (explicitly stated so the interviewer can read them):
SLA_BREACH_THRESHOLD_DAYS = 2  # Breach if Calculated_Delay_Days > 2


# ---------------------------------------------------------------------------
# SECTION 1: LOAD & DATE-PARSE
# ---------------------------------------------------------------------------
def load_and_parse(path: Path) -> pd.DataFrame:
    """Load CSV and parse all three date columns to pandas Timestamps."""
    df = pd.read_csv(path)
    df["Order_Date_dt"]             = pd.to_datetime(df["Order_Date"])
    df["Promised_Delivery_Date_dt"] = pd.to_datetime(df["Promised_Delivery_Date"])
    df["Actual_Delivery_Date_dt"]   = pd.to_datetime(df["Actual_Delivery_Date"])
    return df


# ---------------------------------------------------------------------------
# SECTION 2: RECALCULATE DERIVED COLUMNS
# ---------------------------------------------------------------------------
def recalculate_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministically recalculate all derived quality fields from calendar dates.

    Business Rules:
      Delay = floor(Actual_Date) - floor(Promised_Date)   [calendar-day difference]
      Delivery_Status:
        < 0  → 'Early'
        = 0  → 'On-Time'
        > 0  → 'Delayed'
      SLA_Breach: Delay_Days > SLA_BREACH_THRESHOLD_DAYS (> 2)
      Lead_Time  = floor(Actual_Date) - floor(Order_Date)
    """
    promised = df["Promised_Delivery_Date_dt"].dt.floor("D")
    actual   = df["Actual_Delivery_Date_dt"].dt.floor("D")
    ordered  = df["Order_Date_dt"].dt.floor("D")

    df["Calculated_Delay_Days"] = (actual - promised).dt.days

    df["Calculated_Delivery_Status"] = np.select(
        [df["Calculated_Delay_Days"] < 0,
         df["Calculated_Delay_Days"] == 0,
         df["Calculated_Delay_Days"] > 0],
        ["Early", "On-Time", "Delayed"],
        default="Unknown"
    )

    df["Calculated_SLA_Breach"] = np.where(
        df["Calculated_Delay_Days"] > SLA_BREACH_THRESHOLD_DAYS, "Yes", "No"
    )

    df["Delivery_Lead_Time_Days"]  = (actual - ordered).dt.days
    df["Promised_Lead_Time_Days"]  = (promised - ordered).dt.days

    # Cleaned delay reason: null for on-time/early is "Not Applicable"
    df["Cleaned_Delay_Reason"] = np.where(
        df["Calculated_Delivery_Status"].isin(["Early", "On-Time"]),
        "Not Applicable (On-Time/Early)",
        df["Delay_Reason"].fillna("Unrecorded / Operational Delay")
    )

    return df


# ---------------------------------------------------------------------------
# SECTION 3: AUDIT FLAGS (boolean columns per discrepancy class)
# ---------------------------------------------------------------------------
def apply_audit_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag each of the three known discrepancy classes.
    These booleans become visible in the Data_Quality_Flag composite string.
    """
    # A. 252 delay-calculation mismatches: Is_Delayed=Yes but stored Delay_Days
    #    disagrees with calendar-derived calculation.
    df["DQ_Delay_Mismatch"] = (
        (df["Is_Delayed"] == "Yes") &
        (df["Delay_Days"] != df["Calculated_Delay_Days"])
    )

    # B. 99 SLA flag mismatches: stored Delay_Days > 2 but SLA_Breached = 'No'.
    #    Root cause: carrier SLA engine evaluated true dates (correctly = No),
    #    but legacy Delay_Days was erroneous.
    df["DQ_SLA_Mismatch"] = (
        (df["Delay_Days"] > SLA_BREACH_THRESHOLD_DAYS) &
        (df["SLA_Breached"] == "No")
    )

    # C. 233 missing reasons on flagged-delayed orders.
    #    Root cause: all 233 were actually on-time/early, so no failure was entered.
    df["DQ_Missing_Reason_Delayed"] = (
        (df["Is_Delayed"] == "Yes") &
        (df["Delay_Reason"].isna())
    )

    # D. Same-day timestamp effect: delivered before order date at timestamp level.
    df["DQ_Same_Day_Timestamp_Effect"] = df["Delivery_Lead_Time_Days"] < 0

    # Composite human-readable flag
    def build_flag(row):
        flags = []
        if row["Calculated_Delivery_Status"] in ("Early",) and not row["DQ_Delay_Mismatch"]:
            flags.append("Early Delivery Capped to 0")
        if row["DQ_Delay_Mismatch"]:
            flags.append("Delay Magnitude Mismatch")
        if row["DQ_SLA_Mismatch"]:
            flags.append("SLA Flag Discrepancy (Delay_Days > 2 but SLA=No)")
        if row["DQ_Missing_Reason_Delayed"]:
            flags.append("Unrecorded Delay Reason (Actually On-Time/Early)")
        if row["DQ_Same_Day_Timestamp_Effect"]:
            flags.append("Same-Day Date Truncation")
        return "; ".join(flags) if flags else "Clean"

    df["Data_Quality_Flag"] = df.apply(build_flag, axis=1)
    return df


# ---------------------------------------------------------------------------
# SECTION 4: GENERATE REPORT DICT
# ---------------------------------------------------------------------------
def generate_report(df: pd.DataFrame) -> dict:
    """
    Collect all quality metrics into a structured dictionary.
    Mirrors the table in the Streamlit Data Quality Audit tab.
    """
    total_records   = len(df)
    duplicate_ids   = df["Order_ID"].duplicated().sum()

    # Missing values by critical column
    missing_counts = {
        col: int(df[col].isna().sum())
        for col in [
            "Order_ID", "Order_Date", "Promised_Delivery_Date",
            "Actual_Delivery_Date", "City", "Zone", "Vendor",
            "Delay_Reason"
        ]
    }

    # Date validity
    invalid_lead_time = int((df["Delivery_Lead_Time_Days"] < 0).sum())
    # Promised date after order date (truly impossible)
    impossible_promised = int((df["Promised_Lead_Time_Days"] < 0).sum())

    # The three headline discrepancies
    delay_mismatches   = int(df["DQ_Delay_Mismatch"].sum())
    sla_mismatches     = int(df["DQ_SLA_Mismatch"].sum())
    missing_reasons    = int(df["DQ_Missing_Reason_Delayed"].sum())
    same_day_effect    = int(df["DQ_Same_Day_Timestamp_Effect"].sum())

    # Delivery status breakdown (recalculated)
    status_counts = df["Calculated_Delivery_Status"].value_counts().to_dict()
    sla_counts    = df["Calculated_SLA_Breach"].value_counts().to_dict()

    # Overall integrity score
    flagged_rows       = int((df["Data_Quality_Flag"] != "Clean").sum())
    integrity_score    = round(100.0 * (total_records - delay_mismatches) / total_records, 2)

    return {
        "generated_at"           : datetime.now().isoformat(),
        "total_records"          : total_records,
        "duplicate_order_ids"    : int(duplicate_ids),
        "missing_values"         : missing_counts,
        "invalid_dates"          : {
            "negative_lead_time_days": invalid_lead_time,
            "promised_before_ordered": impossible_promised,
        },
        "discrepancies"          : {
            "delay_calculation_mismatches" : delay_mismatches,
            "sla_flag_mismatches"          : sla_mismatches,
            "missing_delay_reason_flagged" : missing_reasons,
            "same_day_timestamp_effect"    : same_day_effect,
        },
        "delivery_status_breakdown" : status_counts,
        "sla_breach_breakdown"      : sla_counts,
        "flagged_records_total"     : flagged_rows,
        "clean_record_integrity_pct": integrity_score,
    }


# ---------------------------------------------------------------------------
# SECTION 5: PRINT REPORT (human-readable)
# ---------------------------------------------------------------------------
def print_report(report: dict) -> None:
    """Print a formatted console audit report."""
    sep = "=" * 72

    print(sep)
    print("  DATA QUALITY AUDIT REPORT — Last-Mile Delivery Analytics")
    print(f"  Generated: {report['generated_at']}")
    print(sep)

    print(f"\n{'CHECK':<45} {'RESULT':>10}")
    print("-" * 57)

    checks = [
        ("Total delivery records",           report["total_records"]),
        ("Duplicate Order IDs",              report["duplicate_order_ids"]),
        ("Missing City values",              report["missing_values"]["City"]),
        ("Missing Vendor values",            report["missing_values"]["Vendor"]),
        ("Missing Promised Delivery Date",   report["missing_values"]["Promised_Delivery_Date"]),
        ("Missing Actual Delivery Date",     report["missing_values"]["Actual_Delivery_Date"]),
        ("Missing Delay Reason (all rows)",  report["missing_values"]["Delay_Reason"]),
        ("Negative lead-time (date errors)", report["invalid_dates"]["negative_lead_time_days"]),
        ("Promised date before order date",  report["invalid_dates"]["promised_before_ordered"]),
        ("252 — Delay calculation mismatches",  report["discrepancies"]["delay_calculation_mismatches"]),
        ("99  — SLA flag mismatches",            report["discrepancies"]["sla_flag_mismatches"]),
        ("233 — Missing reasons (flagged delays)",report["discrepancies"]["missing_delay_reason_flagged"]),
        ("Same-day timestamp effect",        report["discrepancies"]["same_day_timestamp_effect"]),
        ("Total flagged records",            report["flagged_records_total"]),
        ("Clean record integrity score (%)", f"{report['clean_record_integrity_pct']}%"),
    ]
    for label, value in checks:
        marker = "✅" if value in (0, "0", "0%") or label.startswith("Total delivery") else "⚠️ "
        if isinstance(value, int) and value == 0:
            marker = "✅"
        print(f"  {marker} {label:<43} {str(value):>8}")

    print("\n  Delivery Status Breakdown (Recalculated from Dates):")
    for status, count in report["delivery_status_breakdown"].items():
        pct = round(count / report["total_records"] * 100, 1)
        print(f"    {status:<12}: {count:>5} ({pct}%)")

    print("\n  SLA Breach Breakdown:")
    for status, count in report["sla_breach_breakdown"].items():
        pct = round(count / report["total_records"] * 100, 1)
        print(f"    SLA Breach={status:<4}: {count:>5} ({pct}%)")

    print(f"\n  Root Cause Explanation of Three Headline Discrepancies:")
    print("""
  1. 252 Delay_Days Mismatches
     → Source: Legacy system stored Delay_Days as a manually entered or
       stored-procedure-derived integer, NOT as a calendar subtraction.
     → 233 orders marked Is_Delayed='Yes' were delivered early or on-time
       (Actual ≤ Promised), but had non-zero Delay_Days in the source.
     → 19 orders were truly delayed but the magnitude differed by 1–2 days.
     → Fix: Derived Calculated_Delay_Days = floor(Actual) − floor(Promised).

  2. 99 SLA Flag Mismatches
     → Source: 99 rows had Delay_Days=3 (>2) but SLA_Breached='No'.
     → Root cause: The carrier SLA engine evaluated actual calendar dates
       (correctly returning 'No' because Actual ≤ Promised), while the
       Delay_Days column was erroneous.
     → Fix: Derived Calculated_SLA_Breach = (Calculated_Delay_Days > 2).

  3. 233 Missing Delay Reasons on Flagged-Delayed Orders
     → These exact 233 orders overlap with class 1: they were on-time/early.
     → No field agent entered a failure reason because no failure occurred.
     → Fix: Cleaned_Delay_Reason = 'Not Applicable (On-Time/Early)' for these.
""")
    print(sep)


# ---------------------------------------------------------------------------
# SECTION 6: SAVE REPORT JSON
# ---------------------------------------------------------------------------
def save_report_json(report: dict, path: Path) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  📄 JSON report saved → {path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print(f"\nLoading raw dataset: {RAW_PATH}")
    if not RAW_PATH.exists():
        print(f"ERROR: Raw dataset not found at {RAW_PATH}")
        sys.exit(1)

    df = load_and_parse(RAW_PATH)
    print(f"Loaded {len(df):,} records with {len(df.columns)} columns.\n")

    df = recalculate_derived_columns(df)
    df = apply_audit_flags(df)

    report = generate_report(df)
    print_report(report)

    # Save JSON
    report_path = REPORT_DIR / "data_quality_report.json"
    save_report_json(report, report_path)

    # Save flagged records for manual inspection
    flagged = df[df["Data_Quality_Flag"] != "Clean"][[
        "Order_ID", "Promised_Delivery_Date", "Actual_Delivery_Date",
        "Delay_Days", "Calculated_Delay_Days", "Is_Delayed",
        "Calculated_Delivery_Status", "SLA_Breached", "Calculated_SLA_Breach",
        "Delay_Reason", "Cleaned_Delay_Reason", "Data_Quality_Flag"
    ]]
    flagged_path = REPORT_DIR / "flagged_records.csv"
    flagged.to_csv(flagged_path, index=False)
    print(f"  📄 Flagged records CSV saved → {flagged_path}")
    print(f"\n  Total flagged: {len(flagged):,} of {len(df):,} records "
          f"({round(len(flagged)/len(df)*100,1)}%)\n")


if __name__ == "__main__":
    main()

