"""
==============================================================================
PULSEROUTE — LAST-MILE SLA FORENSICS & AI OPERATIONS COPILOT
FastAPI Backend & REST API Server
==============================================================================
Author : Mohammed Zaidaan Shiraz
Stack  : Python 3.12 | FastAPI | SQLite | Pandas | Statsmodels | Scikit-Learn
==============================================================================
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_engine import (
    DeliveryAnomalyDetector,
    DeliveryDemandForecaster,
    InsightSummarizer,
    ReadOnlySQLCopilot,
)

DATA_PATH = BASE_DIR / "data" / "sample_data.csv"
DB_PATH = BASE_DIR / "data" / "last_mile_delivery.db"
DQ_REPORT_PATH = BASE_DIR / "data" / "data_quality_report.json"
WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="PulseRoute — Last-Mile SLA Forensics & AI Operations Copilot",
    description="Enterprise Logistics Operations Analytics, Forensic Data Quality Engine & Read-Only AI SQL Copilot by Mohammed Zaidaan Shiraz",
    version="2.7.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_static_cache(request: Request, call_next):
    response: Response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static") or request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# ---------------------------------------------------------------------------
# IN-MEMORY CACHED DATASET & PRECOMPUTED ARTIFACTS
# ---------------------------------------------------------------------------
_DF_CACHE: pd.DataFrame | None = None
_ANOMALY_CACHE: pd.DataFrame | None = None
_FORECAST_CACHE: List[Dict[str, Any]] | None = None


def get_df() -> pd.DataFrame:
    global _DF_CACHE
    if _DF_CACHE is None:
        df = pd.read_csv(DATA_PATH)
        df["Order_Date_dt"] = pd.to_datetime(df["Order_Date"])
        df["Order_Month"] = df["Order_Date_dt"].dt.strftime("%Y-%m")
        _DF_CACHE = df
    return _DF_CACHE


def filter_dataframe(
    df: pd.DataFrame,
    zone: Optional[str] = None,
    city: Optional[str] = None,
    vendor: Optional[str] = None,
    category: Optional[str] = None,
    payment_mode: Optional[str] = None,
    season: Optional[str] = None,
) -> pd.DataFrame:
    res = df
    if zone and zone != "All":
        res = res[res["Zone"] == zone]
    if city and city != "All":
        res = res[res["City"] == city]
    if vendor and vendor != "All":
        res = res[res["Vendor"] == vendor]
    if category and category != "All":
        res = res[res["Product_Category"] == category]
    if payment_mode and payment_mode != "All":
        res = res[res["Payment_Mode"] == payment_mode]
    if season and season != "All":
        if season == "Monsoon":
            res = res[res["Is_Monsoon_Season"] == "Yes"]
        elif season == "Festive":
            res = res[res["Is_Festive_Season"] == "Yes"]
        elif season == "Normal":
            res = res[(res["Is_Monsoon_Season"] == "No") & (res["Is_Festive_Season"] == "No")]
    return res


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------
class CopilotQueryRequest(BaseModel):
    question: str = ""
    custom_sql: Optional[str] = None
    api_key: Optional[str] = None


# ---------------------------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    df = get_df()
    return {
        "status": "healthy",
        "application": "PulseRoute — Last-Mile SLA Forensics & AI Operations Copilot",
        "author": "Mohammed Zaidaan Shiraz",
        "records_loaded": int(len(df)),
        "database_connected": DB_PATH.exists(),
    }


@app.get("/api/filters")
def get_filter_options() -> Dict[str, Any]:
    df = get_df()
    return {
        "zones": ["All"] + sorted(df["Zone"].dropna().unique().tolist()),
        "cities": ["All"] + sorted(df["City"].dropna().unique().tolist()),
        "vendors": ["All"] + sorted(df["Vendor"].dropna().unique().tolist()),
        "categories": ["All"] + sorted(df["Product_Category"].dropna().unique().tolist()),
        "payment_modes": ["All"] + sorted(df["Payment_Mode"].dropna().unique().tolist()),
        "seasons": ["All", "Monsoon", "Festive", "Normal"],
    }


@app.get("/api/dashboard")
def get_dashboard_data(
    zone: str = Query("All"),
    city: str = Query("All"),
    vendor: str = Query("All"),
    category: str = Query("All"),
    payment_mode: str = Query("All"),
    season: str = Query("All"),
    rebalance_pct: int = Query(15, ge=0, le=50),
) -> Dict[str, Any]:
    df_all = get_df()
    df = filter_dataframe(df_all, zone, city, vendor, category, payment_mode, season)

    total = int(len(df))
    if total == 0:
        return {"empty": True, "total_orders": 0}

    early = int((df["Calculated_Delivery_Status"] == "Early").sum())
    on_time = int((df["Calculated_Delivery_Status"] == "On-Time").sum())
    delayed = int((df["Calculated_Delivery_Status"] == "Delayed").sum())
    breached = int((df["Calculated_SLA_Breach"] == "Yes").sum())

    on_time_rate = round((early + on_time) / total * 100, 2)
    delay_rate = round(delayed / total * 100, 2)
    breach_rate = round(breached / total * 100, 2)

    delayed_df = df[df["Calculated_Delay_Days"] > 0]
    avg_delay_when_delayed = round(float(delayed_df["Calculated_Delay_Days"].mean()), 2) if len(delayed_df) else 0.0
    avg_lead_time = round(float(df["Delivery_Lead_Time_Days"].mean()), 2)
    avg_promised_time = round(float(df["Promised_Lead_Time_Days"].mean()), 2)

    total_gmv = round(float(df["Order_Value_INR"].sum()), 0)
    gmv_at_risk = round(float(df[df["Calculated_SLA_Breach"] == "Yes"]["Order_Value_INR"].sum()), 0)
    avg_order_val = round(float(df["Order_Value_INR"].mean()), 0)

    # Monthly trend
    monthly_df = (
        df.groupby("Order_Month")
        .agg(
            orders=("Order_ID", "count"),
            delayed=("Calculated_Delivery_Status", lambda s: (s == "Delayed").sum()),
            breached=("Calculated_SLA_Breach", lambda s: (s == "Yes").sum()),
            on_time=("Calculated_Delivery_Status", lambda s: s.isin(["Early", "On-Time"]).sum()),
            gmv=("Order_Value_INR", "sum"),
        )
        .reset_index()
        .sort_values("Order_Month")
    )
    monthly_df["breach_rate"] = (monthly_df["breached"] / monthly_df["orders"] * 100).round(2)
    monthly_df["on_time_rate"] = (monthly_df["on_time"] / monthly_df["orders"] * 100).round(2)

    # Vendor benchmark
    vendor_df = (
        df.groupby("Vendor")
        .agg(
            orders=("Order_ID", "count"),
            on_time=("Calculated_Delivery_Status", lambda s: s.isin(["Early", "On-Time"]).sum()),
            delayed=("Calculated_Delivery_Status", lambda s: (s == "Delayed").sum()),
            breached=("Calculated_SLA_Breach", lambda s: (s == "Yes").sum()),
            avg_lead_time=("Delivery_Lead_Time_Days", "mean"),
            avg_delay=("Calculated_Delay_Days", "mean"),
            gmv=("Order_Value_INR", "sum"),
        )
        .reset_index()
    )
    vendor_df["on_time_rate"] = (vendor_df["on_time"] / vendor_df["orders"] * 100).round(2)
    vendor_df["breach_rate"] = (vendor_df["breached"] / vendor_df["orders"] * 100).round(2)
    vendor_df["avg_lead_time"] = vendor_df["avg_lead_time"].round(2)
    vendor_df["avg_delay"] = vendor_df["avg_delay"].round(2)
    vendor_df = vendor_df.sort_values("breach_rate", ascending=True)

    # Prescriptive Carrier Rebalancing Simulation
    if len(vendor_df) >= 2:
        bottom_vendors = vendor_df.tail(2)
        top_vendors = vendor_df.head(3)
        bottom_orders = int(bottom_vendors["orders"].sum())
        bottom_breach_rate = float(bottom_vendors["breached"].sum() / max(bottom_orders, 1))
        top_breach_rate = float(top_vendors["breached"].sum() / max(int(top_vendors["orders"].sum()), 1))
        shifted_orders = int(round(bottom_orders * (rebalance_pct / 100.0)))
        breaches_avoided = max(0, int(round(shifted_orders * (bottom_breach_rate - top_breach_rate))))
        gmv_protected = round(breaches_avoided * avg_order_val, 0)
        new_network_breach_rate = round(max(0.0, (breached - breaches_avoided) / total * 100), 2)
    else:
        shifted_orders = 0
        breaches_avoided = 0
        gmv_protected = 0.0
        new_network_breach_rate = breach_rate

    # City Pareto
    city_df = (
        df.groupby(["City", "Zone"])
        .agg(
            orders=("Order_ID", "count"),
            delayed=("Calculated_Delivery_Status", lambda s: (s == "Delayed").sum()),
            breached=("Calculated_SLA_Breach", lambda s: (s == "Yes").sum()),
            avg_lead_time=("Delivery_Lead_Time_Days", "mean"),
            gmv_risk=("Order_Value_INR", lambda s: s[df.loc[s.index, "Calculated_SLA_Breach"] == "Yes"].sum()),
        )
        .reset_index()
    )
    city_df["breach_rate"] = (city_df["breached"] / city_df["orders"] * 100).round(2)
    city_df["delay_share_pct"] = (city_df["delayed"] / max(delayed, 1) * 100).round(2)
    city_df["avg_lead_time"] = city_df["avg_lead_time"].round(2)
    city_df = city_df.sort_values("delayed", ascending=False)

    # Root cause breakdown (only on truly delayed orders)
    if len(delayed_df) > 0:
        rc_df = (
            delayed_df.groupby("Cleaned_Delay_Reason")
            .agg(
                delayed_orders=("Order_ID", "count"),
                sla_breaches=("Calculated_SLA_Breach", lambda s: (s == "Yes").sum()),
                avg_delay_days=("Calculated_Delay_Days", "mean"),
            )
            .reset_index()
            .rename(columns={"Cleaned_Delay_Reason": "reason"})
            .sort_values("delayed_orders", ascending=False)
        )
        rc_df["share_pct"] = (rc_df["delayed_orders"] / len(delayed_df) * 100).round(2)
        rc_df["avg_delay_days"] = rc_df["avg_delay_days"].round(2)
        root_causes = rc_df.to_dict(orient="records")
    else:
        root_causes = []

    # Zone breakdown
    zone_df = (
        df.groupby("Zone")
        .agg(
            orders=("Order_ID", "count"),
            breached=("Calculated_SLA_Breach", lambda s: (s == "Yes").sum()),
            on_time=("Calculated_Delivery_Status", lambda s: s.isin(["Early", "On-Time"]).sum()),
        )
        .reset_index()
    )
    zone_df["breach_rate"] = (zone_df["breached"] / zone_df["orders"] * 100).round(2)
    zone_df["on_time_rate"] = (zone_df["on_time"] / zone_df["orders"] * 100).round(2)

    # AI Executive Insights
    summarizer = InsightSummarizer()
    insights = summarizer.summarize(df)

    return {
        "empty": False,
        "kpis": {
            "total_orders": total,
            "early_orders": early,
            "on_time_orders": on_time,
            "delayed_orders": delayed,
            "sla_breaches": breached,
            "on_time_rate": on_time_rate,
            "delay_rate": delay_rate,
            "sla_breach_rate": breach_rate,
            "avg_delay_when_delayed": avg_delay_when_delayed,
            "avg_lead_time": avg_lead_time,
            "avg_promised_time": avg_promised_time,
            "total_gmv_inr": total_gmv,
            "gmv_at_risk_inr": gmv_at_risk,
        },
        "rebalance_simulation": {
            "rebalance_pct": rebalance_pct,
            "shifted_orders": shifted_orders,
            "breaches_avoided": breaches_avoided,
            "gmv_protected_inr": gmv_protected,
            "baseline_breach_rate": breach_rate,
            "projected_breach_rate": new_network_breach_rate,
            "bps_improvement": round((breach_rate - new_network_breach_rate) * 100, 0),
        },
        "monthly_trend": monthly_df.to_dict(orient="records"),
        "vendors": vendor_df.to_dict(orient="records"),
        "cities": city_df.to_dict(orient="records"),
        "root_causes": root_causes,
        "zones": zone_df.to_dict(orient="records"),
        "insights": insights,
    }


@app.get("/api/data-quality")
def get_data_quality_audit(
    zone: str = Query("All"),
    city: str = Query("All"),
    vendor: str = Query("All"),
    category: str = Query("All"),
    payment_mode: str = Query("All"),
    season: str = Query("All"),
) -> Dict[str, Any]:
    df_all = get_df()
    df = filter_dataframe(df_all, zone, city, vendor, category, payment_mode, season)
    if len(df) == 0:
        df = df_all
    report_data = {}
    if DQ_REPORT_PATH.exists():
        with open(DQ_REPORT_PATH, "r", encoding="utf-8") as f:
            report_data = json.load(f)

    # Sample flagged rows showing before/after reconciliation
    flagged = df[
        (df["Is_Delayed"] == "Yes") & (df["Delay_Days"] != df["Calculated_Delay_Days"])
    ][
        [
            "Order_ID",
            "City",
            "Vendor",
            "Promised_Delivery_Date",
            "Actual_Delivery_Date",
            "Delay_Days",
            "Calculated_Delay_Days",
            "Is_Delayed",
            "Calculated_Delivery_Status",
            "SLA_Breached",
            "Calculated_SLA_Breach",
            "Delay_Reason",
            "Cleaned_Delay_Reason",
            "Data_Quality_Flag",
        ]
    ].head(30).fillna("NULL")

    return {
        "summary": {
            "total_records": int(len(df)),
            "duplicate_order_ids": int(df["Order_ID"].duplicated().sum()),
            "delayed_date_mismatches_252": int(
                ((df["Is_Delayed"] == "Yes") & (df["Delay_Days"] != df["Calculated_Delay_Days"])).sum()
            ),
            "sla_rule_mismatches_99": int(
                (((df["Delay_Days"] > 2) & (df["SLA_Breached"] == "No"))
                 | ((df["Delay_Days"] <= 2) & (df["SLA_Breached"] == "Yes"))).sum()
            ),
            "missing_delay_reasons_233": int(
                ((df["Is_Delayed"] == "Yes") & (df["Delay_Reason"].isna() | (df["Delay_Reason"] == ""))).sum()
            ),
            "raw_early_capped_mismatches_1723": int(df["DQ_Delay_Mismatch"].sum()),
            "clean_records": int((df["Data_Quality_Flag"] == "Clean").sum()),
        },
        "report_json": report_data,
        "sample_reconciled_records": flagged.to_dict(orient="records"),
    }


@app.get("/api/anomalies-and-forecast")
def get_anomalies_and_forecast(
    zone: str = Query("All"),
    city: str = Query("All"),
    vendor: str = Query("All"),
    category: str = Query("All"),
    payment_mode: str = Query("All"),
    season: str = Query("All"),
) -> Dict[str, Any]:
    global _ANOMALY_CACHE, _FORECAST_CACHE
    df_all = get_df()

    if _ANOMALY_CACHE is None:
        detector = DeliveryAnomalyDetector(contamination=0.05)
        _ANOMALY_CACHE = detector.fit_predict(df_all)

    is_filtered = any(v != "All" for v in (zone, city, vendor, category, payment_mode, season))
    if not is_filtered:
        if _FORECAST_CACHE is None:
            forecaster = DeliveryDemandForecaster()
            fc_df = forecaster.forecast(df_all, periods=6)
            _FORECAST_CACHE = fc_df.to_dict(orient="records") if not fc_df.empty else []
        forecast_list = _FORECAST_CACHE
        anom_source = _ANOMALY_CACHE
    else:
        df_sub = filter_dataframe(df_all, zone, city, vendor, category, payment_mode, season)
        if len(df_sub) >= 30:
            forecaster = DeliveryDemandForecaster()
            fc_df = forecaster.forecast(df_sub, periods=6)
            forecast_list = fc_df.to_dict(orient="records") if not fc_df.empty else (_FORECAST_CACHE or [])
        else:
            forecast_list = _FORECAST_CACHE or []
        anom_source = filter_dataframe(_ANOMALY_CACHE, zone, city, vendor, category, payment_mode, season)

    anom_df = anom_source[anom_source["Is_Anomaly"]].sort_values("Anomaly_Rank", ascending=False)
    top_anomalies = anom_df[
        [
            "Order_ID",
            "City",
            "Vendor",
            "Order_Value_INR",
            "Promised_Lead_Time_Days",
            "Delivery_Lead_Time_Days",
            "Calculated_Delay_Days",
            "Delivery_Attempts",
            "Anomaly_Score",
            "Anomaly_Rank",
        ]
    ].head(25).to_dict(orient="records")

    return {
        "total_anomalies_flagged": int(anom_df.shape[0]),
        "contamination_rate_pct": 5.0,
        "top_anomalies": top_anomalies,
        "forecast_6m": forecast_list,
    }


@app.get("/api/copilot/presets")
def get_copilot_presets() -> Dict[str, Any]:
    return {
        "presets": [
            {
                "id": item["id"],
                "question": item["question"],
                "sql": item["sql"],
                "explanation": item["explanation"],
            }
            for item in ReadOnlySQLCopilot.CURATED_INTENTS
        ]
    }


@app.post("/api/copilot/ask")
def ask_copilot(req: CopilotQueryRequest) -> Dict[str, Any]:
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail="SQLite database not found.")
    return ReadOnlySQLCopilot.ask(DB_PATH, req.question, req.custom_sql, req.api_key)


# ---------------------------------------------------------------------------
# SERVE MODERN FRONTEND (SPA)
# ---------------------------------------------------------------------------
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_spa_index():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>PulseRoute API Running. Frontend index.html not found.</h1>")
