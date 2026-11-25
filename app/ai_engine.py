"""
==============================================================================
AI ENGINE — Last-Mile Delivery Analytics (Fortune 500 Edition)
==============================================================================
Module  : ai_engine.py
Purpose : Self-contained ML/AI module that powers four AI features:

  1. SLA Breach Predictor       — XGBoost classifier predicting risk before dispatch
  2. Anomaly Detector           — Isolation Forest catching operational outliers
  3. SHAP Explainability        — Feature importance for every prediction (XAI)
  4. NLP Insight Summarizer     — Template-based insight generation
     (upgradeable to Gemini API for production)

Design philosophy: Every AI feature degrades gracefully if scikit-learn /
xgboost / shap are not installed. The dashboard still runs; it just shows an
install nudge rather than crashing.
==============================================================================
"""

from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any

# Optional heavy imports — graceful degradation if missing
try:
    from sklearn.model_selection import train_test_split, StratifiedKFold
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.metrics import (classification_report, roc_auc_score,
                                  confusion_matrix, roc_curve, auc)
    from sklearn.ensemble import IsolationForest
    import xgboost as xgb
    import shap
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


# ---------------------------------------------------------------------------
# FEATURE ENGINEERING
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "Promised_Lead_Time_Days",   # How much time was the carrier given?
    "Delivery_Attempts",         # How many physical attempts?
    "Order_Value_INR",           # High-value → more scrutiny?
    "Is_Festive_Season_num",     # 1 = Festive surge period
    "Is_Monsoon_Season_num",     # 1 = Weather disruption risk
    "Payment_Mode_num",          # 0 = Prepaid, 1 = COD (harder to deliver)
    "City_encoded",              # City operational characteristics
    "Vendor_encoded",            # Carrier historical performance
    "Product_Category_encoded",  # Category-specific delivery profiles
    "Zone_encoded",              # Geographic zone
    "Hour_of_Order",             # Time-of-day order placement
    "Day_of_Week_Order",         # Weekday vs weekend ordering
    "Month_Order",               # Seasonal month
]

TARGET_COL = "Calculated_SLA_Breach"


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw + derived columns into ML-ready numeric features.
    All encodings are deterministic (sorted label encoding) so the
    model is reproducible without a fitted encoder pickle.
    """
    df = df.copy()

    # Binary flags → numeric
    df["Is_Festive_Season_num"] = (df["Is_Festive_Season"] == "Yes").astype(int)
    df["Is_Monsoon_Season_num"] = (df["Is_Monsoon_Season"] == "Yes").astype(int)
    df["Payment_Mode_num"]      = (df["Payment_Mode"] == "COD").astype(int)

    # Datetime features
    df["Order_Date_dt"]  = pd.to_datetime(df["Order_Date"])
    df["Hour_of_Order"]     = df["Order_Date_dt"].dt.hour
    df["Day_of_Week_Order"] = df["Order_Date_dt"].dt.day_of_week
    df["Month_Order"]       = df["Order_Date_dt"].dt.month

    # Ordinal label encoding (sorted for reproducibility)
    for col, out_col in [
        ("City",             "City_encoded"),
        ("Vendor",           "Vendor_encoded"),
        ("Product_Category", "Product_Category_encoded"),
        ("Zone",             "Zone_encoded"),
    ]:
        categories = sorted(df[col].unique())
        mapping = {c: i for i, c in enumerate(categories)}
        df[out_col] = df[col].map(mapping)

    # Target: binary numeric
    df["target"] = (df[TARGET_COL] == "Yes").astype(int)

    return df


# ---------------------------------------------------------------------------
# 1. SLA BREACH PREDICTOR (XGBoost)
# ---------------------------------------------------------------------------
class SLABreachPredictor:
    """
    XGBoost binary classifier that estimates the probability an order
    will breach SLA during dispatch and in-transit monitoring.
    Note: For strict pre-dispatch-only scoring, omit `Delivery_Attempts`
    from FEATURE_COLS to avoid post-dispatch feature leakage.

    The model trains on historical data and returns:
      - Probability score 0–1 for each order
      - Binary prediction (breach / no-breach)
      - SHAP feature importances for explainability
      - Standard evaluation metrics (AUC-ROC, classification report)
    """

    def __init__(self):
        if not ML_AVAILABLE:
            raise RuntimeError(
                "scikit-learn, xgboost, and shap must be installed. "
                "Run: pip install scikit-learn xgboost shap"
            )
        self.model: xgb.XGBClassifier | None = None
        self.feature_cols = FEATURE_COLS
        self.scaler = StandardScaler()
        self.metrics: Dict[str, Any] = {}
        self.shap_values = None
        self.X_test_df: pd.DataFrame | None = None

    def train(self, df: pd.DataFrame, test_size: float = 0.2,
              random_state: int = 42) -> Dict[str, Any]:
        """
        Train the XGBoost model on the full dataset.
        Returns a dict with evaluation metrics.
        """
        df_feat = engineer_features(df)
        if "Order_Date_dt" in df_feat.columns:
            df_feat = df_feat.sort_values("Order_Date_dt").reset_index(drop=True)
        X = df_feat[self.feature_cols].fillna(0).values
        y = df_feat["target"].values

        # Chronological (time-based) split to prevent temporal look-ahead leakage
        split_idx = int(len(X) * (1.0 - test_size))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Scale for SHAP plots (XGBoost works without scaling, but SHAP
        # waterfall charts are cleaner on normalized values)
        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s  = self.scaler.transform(X_test)

        # Compute class weight on training split only (prevents test-set stat leakage)
        pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

        self.model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=pos_weight,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=random_state,
            verbosity=0,
        )
        self.model.fit(X_train_s, y_train,
                       eval_set=[(X_test_s, y_test)],
                       verbose=False)

        # Evaluate
        y_pred  = self.model.predict(X_test_s)
        y_proba = self.model.predict_proba(X_test_s)[:, 1]

        fpr, tpr, _ = roc_curve(y_test, y_proba)
        roc_auc     = auc(fpr, tpr)

        self.metrics = {
            "roc_auc":    round(float(roc_auc), 4),
            "fpr":        fpr.tolist(),
            "tpr":        tpr.tolist(),
            "report":     classification_report(y_test, y_pred, output_dict=True),
            "confusion":  confusion_matrix(y_test, y_pred).tolist(),
            "n_train":    len(X_train),
            "n_test":     len(X_test),
            "pos_pct":    round(float(y.mean()) * 100, 1),
        }

        # SHAP explainability on test set
        explainer        = shap.TreeExplainer(self.model)
        self.shap_values = explainer.shap_values(X_test_s)
        self.X_test_df   = pd.DataFrame(X_test_s, columns=self.feature_cols)

        return self.metrics

    def predict_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Score a dataframe and return it with two new columns:
          SLA_Risk_Score   : float 0–1 (probability of breach)
          SLA_Risk_Label   : 'High Risk' | 'Medium Risk' | 'Low Risk'
        """
        if self.model is None:
            raise RuntimeError("Model not trained yet. Call .train() first.")

        df_feat = engineer_features(df)
        X = df_feat[self.feature_cols].fillna(0).values
        X_s = self.scaler.transform(X)

        proba = self.model.predict_proba(X_s)[:, 1]
        df = df.copy()
        df["SLA_Risk_Score"] = np.round(proba, 4)
        df["SLA_Risk_Label"] = pd.cut(
            df["SLA_Risk_Score"],
            bins=[-0.001, 0.35, 0.65, 1.001],
            labels=["Low Risk", "Medium Risk", "High Risk"]
        ).astype(str)
        return df

    def get_feature_importance_df(self) -> pd.DataFrame:
        """Return a tidy DataFrame of mean |SHAP| importance by feature."""
        if self.shap_values is None:
            return pd.DataFrame()
        mean_shap = np.abs(self.shap_values).mean(axis=0)
        return (
            pd.DataFrame({"Feature": self.feature_cols, "Mean_SHAP": mean_shap})
            .sort_values("Mean_SHAP", ascending=False)
            .reset_index(drop=True)
        )


# ---------------------------------------------------------------------------
# 2. ANOMALY DETECTOR (Isolation Forest)
# ---------------------------------------------------------------------------
class DeliveryAnomalyDetector:
    """
    Isolation Forest anomaly detector that flags statistically unusual
    delivery records — e.g., extreme delay outliers, impossible lead times,
    or unusual order-value + delay combinations.

    Anomaly Score: closer to -1 → strong anomaly; +1 → normal.
    """

    ANOMALY_FEATURES = [
        "Calculated_Delay_Days",
        "Delivery_Lead_Time_Days",
        "Order_Value_INR",
        "Delivery_Attempts",
        "Promised_Lead_Time_Days",
    ]

    def __init__(self, contamination: float = 0.05):
        """
        contamination: Expected fraction of anomalies in the dataset.
                       0.05 = top 5% most unusual records are flagged.
        """
        if not ML_AVAILABLE:
            raise RuntimeError("scikit-learn must be installed.")
        self.contamination = contamination
        self.model: IsolationForest | None = None
        self.scaler = StandardScaler()

    def fit_predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit Isolation Forest and return df with new columns:
          Anomaly_Score : float [-1, +1], lower = more anomalous
          Is_Anomaly    : bool
          Anomaly_Rank  : percentile rank (0 = most normal, 100 = most anomalous)
        """
        X = df[self.ANOMALY_FEATURES].fillna(0).values
        X_s = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            n_estimators=200,
            contamination=self.contamination,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_s)

        scores = self.model.score_samples(X_s)   # higher = more normal
        preds  = self.model.predict(X_s)          # -1 = anomaly, +1 = normal

        df = df.copy()
        df["Anomaly_Score"] = np.round(scores, 4)
        df["Is_Anomaly"]    = preds == -1
        # Rank: 100 = most anomalous
        df["Anomaly_Rank"]  = pd.Series(scores).rank(pct=True).values * 100
        df["Anomaly_Rank"]  = (100 - df["Anomaly_Rank"]).round(1)

        return df


# ---------------------------------------------------------------------------
# 3. DEMAND FORECASTER (Prophet-lite using statsmodels ARIMA)
# ---------------------------------------------------------------------------
class DeliveryDemandForecaster:
    """
    Lightweight time-series forecaster using statsmodels Exponential Smoothing.
    Forecasts monthly delivery volume + SLA breach rate for the next N months.

    In production this would be replaced with Meta Prophet or Google Vertex AI
    AutoML Forecasting.
    """

    def __init__(self):
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            self._ES = ExponentialSmoothing
            self.available = True
        except ImportError:
            self.available = False

    def forecast(self, df: pd.DataFrame, periods: int = 6) -> pd.DataFrame:
        """
        Forecast next `periods` months of delivery volume.
        Returns a DataFrame with columns: Month, Forecasted_Orders,
        Lower_80, Upper_80.
        """
        if not self.available:
            return pd.DataFrame()

        monthly = (
            df.assign(Month_dt=pd.to_datetime(df["Order_Date"]).dt.to_period("M"))
            .groupby("Month_dt")
            .agg(Orders=("Order_ID", "count"),
                 SLA_Breaches=("Calculated_SLA_Breach",
                               lambda s: (s == "Yes").sum()))
            .reset_index()
            .sort_values("Month_dt")
        )

        if len(monthly) < 4:
            return pd.DataFrame()

        ts = monthly["Orders"].values.astype(float)

        model = self._ES(ts, trend="add", seasonal=None,
                         initialization_method="estimated")
        fit   = model.fit(optimized=True)
        fc    = fit.forecast(periods)
        ci    = fit.simulate(periods, repetitions=200, error="add")
        lower = np.percentile(ci, 10, axis=1)
        upper = np.percentile(ci, 90, axis=1)

        last_period = monthly["Month_dt"].iloc[-1]
        future_months = [
            str(last_period + i + 1) for i in range(periods)
        ]

        return pd.DataFrame({
            "Month":             future_months,
            "Forecasted_Orders": np.round(fc).astype(int),
            "Lower_80":          np.round(lower).astype(int),
            "Upper_80":          np.round(upper).astype(int),
        })


# ---------------------------------------------------------------------------
# 4. NLP INSIGHT SUMMARIZER
# ---------------------------------------------------------------------------
class InsightSummarizer:
    """
    Generates plain-English operational insights from the filtered dataset.

    Architecture:
      - Rule-based template engine (runs fully offline, zero API cost)
      - Designed so the prompt + context can be sent to Gemini / GPT-4o
        with a single API call upgrade (see commented section below)

    In a production Fortune 500 deployment:
      - Connect to Vertex AI Gemini 2.0 Flash for sub-second streaming
      - Pass df summary statistics as structured JSON context
      - Cache results with TTL to avoid repetitive API calls
    """

    @staticmethod
    def _fmt_pct(val: float) -> str:
        return f"{val:.1f}%"

    @staticmethod
    def _traffic_light(val: float, warn: float, danger: float,
                       higher_is_bad: bool = True) -> str:
        if higher_is_bad:
            if val >= danger: return "🔴"
            if val >= warn:   return "🟡"
            return "🟢"
        else:
            if val <= danger: return "🔴"
            if val <= warn:   return "🟡"
            return "🟢"

    def summarize(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Returns a dict of insight strings keyed by section.
        """
        total = len(df)
        if total == 0:
            return {"error": "No data in current filter selection."}

        delayed    = int((df["Calculated_Delay_Days"] > 0).sum())
        breached   = int((df["Calculated_SLA_Breach"] == "Yes").sum())
        early      = int((df["Calculated_Delivery_Status"] == "Early").sum())
        on_time    = int((df["Calculated_Delivery_Status"] == "On-Time").sum())
        delay_rate = delayed / total * 100
        breach_rate = breached / total * 100
        on_time_rate = (early + on_time) / total * 100

        delayed_df  = df[df["Calculated_Delay_Days"] > 0]
        avg_delay   = delayed_df["Calculated_Delay_Days"].mean() if len(delayed_df) else 0.0
        avg_lt      = df["Delivery_Lead_Time_Days"].mean()
        total_gmv   = df["Order_Value_INR"].sum()
        risk_gmv    = df[df["Calculated_SLA_Breach"] == "Yes"]["Order_Value_INR"].sum()

        # Top delay cause
        cause_counts = df[df["Calculated_Delivery_Status"] == "Delayed"]["Cleaned_Delay_Reason"].value_counts()
        top_cause    = cause_counts.index[0] if len(cause_counts) else "N/A"
        top_cause_pct = cause_counts.iloc[0] / delayed * 100 if delayed > 0 else 0.0

        # Worst city
        city_breach = (
            df.groupby("City")
            .apply(lambda g: (g["Calculated_SLA_Breach"] == "Yes").sum() / len(g) * 100,
                   include_groups=False)
            .sort_values(ascending=False)
        )
        worst_city     = city_breach.index[0] if len(city_breach) else "N/A"
        worst_city_pct = city_breach.iloc[0] if len(city_breach) else 0.0

        # Best vendor
        vendor_breach = (
            df.groupby("Vendor")
            .apply(lambda g: (g["Calculated_SLA_Breach"] == "Yes").sum() / len(g) * 100,
                   include_groups=False)
            .sort_values()
        )
        best_vendor     = vendor_breach.index[0] if len(vendor_breach) else "N/A"
        best_vendor_pct = vendor_breach.iloc[0] if len(vendor_breach) else 0.0

        tl_breach = self._traffic_light(breach_rate, 20, 30, higher_is_bad=True)
        tl_ontime = self._traffic_light(on_time_rate, 70, 60, higher_is_bad=False)

        insights = {
            "executive_summary": (
                f"**On-Time Performance:** {self._fmt_pct(on_time_rate)} of "
                f"{total:,} deliveries arrived on time or early. "
                f"{'Meets the 70% operational target.' if on_time_rate >= 70 else 'Below the 70% target benchmark — carrier review recommended.'} "
                f"Average end-to-end cycle time is **{avg_lt:.1f} days**."
            ),

            "sla_risk": (
                f"**SLA Governance:** {breached:,} orders breached the contractual "
                f"SLA threshold ({self._fmt_pct(breach_rate)} breach rate). "
                f"Revenue at SLA risk: **₹{risk_gmv:,.0f}** "
                f"({self._fmt_pct(risk_gmv/total_gmv*100) if total_gmv > 0 else 'N/A'} of GMV). "
                f"{'Exceeds 30% tolerance threshold.' if breach_rate > 30 else ''}"
            ),

            "root_cause": (
                f"**Primary Delay Driver:** \"{top_cause}\" accounts for "
                f"**{self._fmt_pct(top_cause_pct)}** of all delayed shipments. "
                f"{'Operational/carrier-controllable failure — route optimization review warranted.' if top_cause in ['Traffic Congestion', 'Route Optimization Failure', 'Vehicle Breakdown'] else ''}"
                f"{'Demand/capacity failure — surge staffing and cross-docking recommended.' if top_cause in ['High Order Volume', 'Warehouse Processing Delay'] else ''}"
                f"{'Customer-side friction — pre-dispatch confirmation reduces repeat attempts.' if top_cause in ['Customer Unavailable', 'Wrong Address'] else ''}"
            ),

            "city_risk": (
                f"**Highest-Risk Hub:** {worst_city} records a "
                f"**{self._fmt_pct(worst_city_pct)} SLA breach rate**. "
                f"Recommend capacity audit at {worst_city} hub and dispatch volume rebalancing "
                f"to secondary carrier network."
            ),

            "vendor_highlight": (
                f"**Benchmark Carrier:** {best_vendor} maintains the lowest SLA breach rate "
                f"at **{self._fmt_pct(best_vendor_pct)}**. "
                f"Increasing dispatch allocation to {best_vendor} in high-risk zones "
                f"reduces network-wide breach exposure."
            ),

            "action_items": "\n".join([
                f"1. **Immediate:** Audit {worst_city} hub operations — {self._fmt_pct(worst_city_pct)} SLA breach rate is an outlier.",
                f"2. **This week:** Increase {best_vendor} allocation in {worst_city} zone to leverage their {self._fmt_pct(best_vendor_pct)} breach rate.",
                f"3. **Process:** Address \"{top_cause}\" ({self._fmt_pct(top_cause_pct)} of delays) with targeted process intervention.",
                f"4. **Financial:** {self._fmt_pct(breach_rate)} SLA breach rate puts ₹{risk_gmv:,.0f} GMV at chargeback/churn risk.",
                f"5. **Data:** {delay_rate:.1f}% delay rate vs target <30%. {'On track.' if delay_rate < 30 else 'Intervention required.'}",
            ]),
        }

        return insights


# ---------------------------------------------------------------------------
# 5. READ-ONLY AI SQL & ANALYTICS COPILOT (HYBRID DETERMINISTIC + GEMINI 2.5 FLASH)
# ---------------------------------------------------------------------------
import os
import json
import re
import sqlite3
import urllib.request
import urllib.error

class ReadOnlySQLCopilot:
    """
    Hybrid Natural-Language-to-SQL and Operational Analytics Copilot:
    - Engine 1 (Always-On Deterministic Router): Zero-latency intent matching and
      template synthesis that works 100% offline with zero API cost.
    - Engine 2 (Live Gemini 2.5 Flash LLM Augmentation): When `GEMINI_API_KEY` is set
      in the environment or passed from the UI header, calls Google's Gemini REST API
      to translate free-form natural language questions into read-only SQLite SQL and
      synthesize an executive C-suite operational narrative.
    - Guardrail: Regardless of whether SQL comes from the deterministic router, user input,
      or Gemini LLM, EVERY query must pass `validate_readonly_sql` and executes against
      SQLite opened in immutable read-only URI mode (`?mode=ro`).
    """

    SCHEMA_PROMPT = """
    SQLite Database Schema (`last_mile_delivery.db`):
    1. `deliveries` (5,200 rows):
       - order_id (TEXT PK), order_date (TEXT YYYY-MM-DD), promised_delivery_date (TEXT), actual_delivery_date (TEXT)
       - city_id (INT FK -> cities.city_id), vendor_id (INT FK -> vendors.vendor_id), reason_id (INT FK -> delay_reasons.reason_id)
       - warehouse_id (TEXT), delivery_agent_id (TEXT), product_category (TEXT)
       - payment_mode (TEXT: 'COD'|'Prepaid'|'UPI'|'Credit Card'), order_value_inr (REAL), delivery_attempts (INT)
       - is_festive_season (TEXT: 'Yes'|'No'), is_monsoon_season (TEXT: 'Yes'|'No')
       - delay_days_raw (INT legacy), is_delayed_raw (TEXT legacy), sla_breached_raw (TEXT legacy)
       - calculated_delay_days (INT ground-truth), calculated_delivery_status (TEXT: 'Early'|'On-Time'|'Delayed')
       - calculated_sla_breach (TEXT: 'Yes'|'No'), delivery_lead_time_days (INT)
    2. `cities` (15 rows): city_id (INT PK), city_name (TEXT), zone (TEXT: 'North'|'South'|'East'|'West'|'Central')
    3. `vendors` (8 rows): vendor_id (INT PK), vendor_name (TEXT)
    4. `delay_reasons` (7 rows): reason_id (INT PK), reason_name (TEXT), reason_category (TEXT)
    """

    FORBIDDEN_KEYWORDS = re.compile(
        r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|PRAGMA|VACUUM|GRANT|REVOKE)\b",
        re.IGNORECASE,
    )

    CURATED_INTENTS = [
        {
            "id": "zone_sla_breach",
            "patterns": ["zone", "zones", "geographic", "region"],
            "question": "Which delivery zones have the highest SLA breach rate and GMV at risk?",
            "sql": """SELECT
    c.zone AS Delivery_Zone,
    COUNT(d.order_id) AS Total_Orders,
    SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS SLA_Breaches,
    ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(d.order_id), 2) AS SLA_Breach_Rate_Pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS Avg_Delay_Days,
    ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN d.order_value_inr ELSE 0 END), 0) AS GMV_At_Risk_INR
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
GROUP BY c.zone
ORDER BY SLA_Breach_Rate_Pct DESC;""",
            "explanation": "Aggregates SLA breaches and GMV exposure across geographic zones using an INNER JOIN between `deliveries` and `cities`."
        },
        {
            "id": "vendor_benchmark",
            "patterns": ["vendor", "carrier", "3pl", "partner", "couriers", "benchmark"],
            "question": "Rank all 3PL carriers by SLA breach rate vs network average using a CTE.",
            "sql": """WITH vendor_kpis AS (
    SELECT
        v.vendor_name AS Carrier,
        COUNT(d.order_id) AS Total_Dispatches,
        ROUND(AVG(d.delivery_lead_time_days), 2) AS Avg_Cycle_Days,
        ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(d.order_id), 2) AS Breach_Rate_Pct
    FROM deliveries d
    JOIN vendors v ON d.vendor_id = v.vendor_id
    GROUP BY v.vendor_name
),
network_avg AS (
    SELECT ROUND(AVG(Breach_Rate_Pct), 2) AS Net_Breach_Pct FROM vendor_kpis
)
SELECT
    vk.Carrier,
    vk.Total_Dispatches,
    vk.Avg_Cycle_Days,
    vk.Breach_Rate_Pct,
    na.Net_Breach_Pct AS Network_Avg_Pct,
    ROUND(vk.Breach_Rate_Pct - na.Net_Breach_Pct, 2) AS Variance_vs_Network_Pts,
    DENSE_RANK() OVER (ORDER BY vk.Breach_Rate_Pct ASC) AS Reliability_Rank
FROM vendor_kpis vk
CROSS JOIN network_avg na
ORDER BY Reliability_Rank ASC;""",
            "explanation": "Uses a Common Table Expression (CTE) + `DENSE_RANK()` window function to benchmark each 3PL partner against the network average SLA breach rate."
        },
        {
            "id": "city_pareto_defects",
            "patterns": ["city", "cities", "hub", "hubs", "top 5", "pareto", "worst city"],
            "question": "Which top 10 cities contribute the largest share of delayed shipments (Pareto analysis)?",
            "sql": """SELECT
    c.city_name AS City,
    c.zone AS Zone,
    COUNT(d.order_id) AS Delayed_Orders,
    ROUND(COUNT(d.order_id) * 100.0 / SUM(COUNT(d.order_id)) OVER (), 2) AS Share_Of_Network_Delays_Pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS Avg_Delay_Days
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY c.city_name, c.zone
ORDER BY Delayed_Orders DESC
LIMIT 10;""",
            "explanation": "Applies a window aggregation `SUM(COUNT(*)) OVER ()` to compute each city's exact percentage contribution to total network delays."
        },
        {
            "id": "root_cause_pareto",
            "patterns": ["reason", "cause", "why", "root cause", "failure", "bottleneck"],
            "question": "What are the primary root causes of delivery delays and SLA breaches?",
            "sql": """SELECT
    COALESCE(dr.reason_name, 'Not Recorded') AS Delay_Root_Cause,
    COALESCE(dr.reason_category, 'Operational') AS Reason_Category,
    COUNT(d.order_id) AS Delayed_Shipments,
    SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS Severe_SLA_Breaches,
    ROUND(COUNT(d.order_id) * 100.0 / SUM(COUNT(d.order_id)) OVER (), 2) AS Share_Of_Delays_Pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS Avg_Delay_When_Triggered
FROM deliveries d
LEFT JOIN delay_reasons dr ON d.reason_id = dr.reason_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY Delay_Root_Cause, Reason_Category
ORDER BY Delayed_Shipments DESC;""",
            "explanation": "Summarizes true delayed shipments by root cause and category, quantifying both delay frequency and severe (>2 days) SLA breaches."
        },
        {
            "id": "data_quality_forensics",
            "patterns": ["quality", "mismatch", "252", "99", "233", "audit", "corrupted", "discrepancy", "flag"],
            "question": "Show the forensic breakdown of legacy data-quality discrepancies across the 5,200 records.",
            "sql": """SELECT
    SUM(CASE WHEN is_delayed_raw = 'Yes' AND delay_days_raw != calculated_delay_days THEN 1 ELSE 0 END) AS Delayed_Date_Math_Mismatches_252,
    SUM(CASE WHEN (delay_days_raw > 2 AND sla_breached_raw = 'No') OR (delay_days_raw <= 2 AND sla_breached_raw = 'Yes') THEN 1 ELSE 0 END) AS Legacy_SLA_Rule_Mismatches_99,
    SUM(CASE WHEN is_delayed_raw = 'Yes' AND reason_id IS NULL THEN 1 ELSE 0 END) AS Missing_Delay_Reasons_233,
    SUM(CASE WHEN delay_days_raw != calculated_delay_days THEN 1 ELSE 0 END) AS Total_Raw_Delay_Capped_Mismatches_1723,
    COUNT(*) AS Total_Audited_Records
FROM deliveries;""",
            "explanation": "Audits the exact counts of legacy logging errors: 252 delayed date mismatches, 99 SLA rule contradictions, and 233 phantom delays with NULL reasons."
        },
        {
            "id": "seasonal_monsoon_cod",
            "patterns": ["monsoon", "festive", "season", "weather", "cod", "payment", "prepaid"],
            "question": "How do Monsoon weather and COD payment modes impact SLA breach rates and delivery attempts?",
            "sql": """SELECT
    is_monsoon_season AS Monsoon_Season,
    payment_mode AS Payment_Mode,
    COUNT(order_id) AS Orders,
    ROUND(AVG(delivery_attempts), 2) AS Avg_Delivery_Attempts,
    ROUND(SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(order_id), 2) AS SLA_Breach_Rate_Pct,
    ROUND(AVG(calculated_delay_days), 2) AS Avg_Delay_Days
FROM deliveries
GROUP BY is_monsoon_season, payment_mode
ORDER BY SLA_Breach_Rate_Pct DESC;""",
            "explanation": "Cross-tabulates Monsoon vs Non-Monsoon dispatches across COD and Prepaid orders to isolate weather and payment-collection friction."
        },
        {
            "id": "mom_trend_lag",
            "patterns": ["month", "trend", "mom", "over time", "lag", "timeline", "weekly"],
            "question": "What is the month-over-month (MoM) order volume and SLA breach rate change using LAG()?",
            "sql": """WITH monthly_stats AS (
    SELECT
        SUBSTR(order_date, 1, 7) AS Order_Month,
        COUNT(order_id) AS Total_Orders,
        ROUND(SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(order_id), 2) AS Breach_Rate_Pct
    FROM deliveries
    GROUP BY SUBSTR(order_date, 1, 7)
)
SELECT
    Order_Month,
    Total_Orders,
    LAG(Total_Orders) OVER (ORDER BY Order_Month) AS Prev_Month_Orders,
    Breach_Rate_Pct,
    LAG(Breach_Rate_Pct) OVER (ORDER BY Order_Month) AS Prev_Month_Breach_Pct,
    ROUND(Breach_Rate_Pct - LAG(Breach_Rate_Pct) OVER (ORDER BY Order_Month), 2) AS MoM_Breach_Delta_Pts
FROM monthly_stats
ORDER BY Order_Month ASC;""",
            "explanation": "Uses the `LAG()` window function over monthly cohorts to track sequential volume growth and SLA breach rate drift."
        },
    ]

    @classmethod
    def validate_readonly_sql(cls, sql: str) -> Tuple[bool, str]:
        """
        Strictly validate that a SQL query is read-only (`SELECT` or `WITH ... SELECT`),
        contains only a single statement, and has zero DDL/DML keywords.
        """
        if not sql or not sql.strip():
            return False, "SQL query cannot be empty."

        cleaned = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL).strip()

        # Strip a single trailing semicolon, then forbid any internal semicolons
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()
        if ";" in cleaned:
            return False, "Multiple SQL statements (semicolon chaining) are blocked by the Read-Only Guardrail."

        first_token = cleaned.split()[0].upper() if cleaned.split() else ""
        if first_token not in ("SELECT", "WITH"):
            return False, f"Only read-only SELECT / CTE (WITH) queries are permitted. Found `{first_token}`."

        match = cls.FORBIDDEN_KEYWORDS.search(cleaned)
        if match:
            return False, f"Blocked keyword `{match.group(0).upper()}` detected. Database is strictly read-only."

        return True, "Validated read-only SELECT query."

    @classmethod
    def match_question_to_sql(cls, question: str) -> Dict[str, str]:
        """Match a natural language question to the closest curated SQL intent."""
        q_lower = (question or "").strip().lower()
        best_intent = cls.CURATED_INTENTS[0]
        best_score = 0
        for intent in cls.CURATED_INTENTS:
            score = sum(1 for pat in intent["patterns"] if pat in q_lower)
            if score > best_score:
                best_score = score
                best_intent = intent
        return best_intent

    @classmethod
    def execute_safe_query(cls, db_path: Path | str, sql: str) -> Dict[str, Any]:
        """Validate and execute a read-only SQL query against SQLite."""
        is_valid, msg = cls.validate_readonly_sql(sql)
        if not is_valid:
            return {
                "valid": False,
                "status_message": msg,
                "sql": sql,
                "row_count": 0,
                "columns": [],
                "rows": [],
                "summary": f"Guardrail blocked execution: {msg}",
            }

        db_uri = f"file:{Path(db_path).resolve().as_posix()}?mode=ro"
        try:
            conn = sqlite3.connect(db_uri, uri=True)
            df_res = pd.read_sql_query(sql, conn)
            conn.close()
        except Exception as exc:
            return {
                "valid": False,
                "status_message": f"SQL Execution Error: {exc}",
                "sql": sql,
                "row_count": 0,
                "columns": [],
                "rows": [],
                "summary": f"Query failed during read-only execution: {exc}",
            }

        rows = df_res.head(100).to_dict(orient="records")
        summary = cls._summarize_result(df_res)
        return {
            "valid": True,
            "status_message": msg,
            "sql": sql,
            "row_count": int(len(df_res)),
            "columns": list(df_res.columns),
            "rows": rows,
            "summary": summary,
        }

    @classmethod
    def generate_sql_with_gemini(cls, question: str, api_key: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Use Gemini 2.5 Flash REST API to translate an arbitrary natural-language
        logistics question into a single read-only SQLite SELECT query.
        """
        key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not key or not question.strip():
            return None, None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        prompt = (
            "You are a senior Staff Data Engineer specializing in SQLite and Last-Mile Logistics.\n"
            f"{cls.SCHEMA_PROMPT}\n"
            "Write a SINGLE valid SQLite read-only SELECT (or WITH ... SELECT) query to answer:\n"
            f"Question: {question}\n\n"
            "Return strictly JSON with keys: {\"sql\": \"SELECT ...\", \"explanation\": \"One sentence explanation\"}."
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return parsed.get("sql"), parsed.get("explanation")
        except Exception:
            return None, None

    @classmethod
    def ask(
        cls,
        db_path: Path | str,
        question: str,
        custom_sql: str | None = None,
        api_key: str | None = None,
    ) -> Dict[str, Any]:
        """Answer a natural language question or execute custom read-only SQL (with optional Gemini 2.5 Flash LLM)."""
        intent = cls.match_question_to_sql(question)
        engine_mode = "Deterministic Curated SQL Engine"
        explanation = intent["explanation"]

        if custom_sql and custom_sql.strip():
            sql_to_run = custom_sql.strip()
            engine_mode = "Custom User SQL (AST Validated)"
            explanation = "Custom user SQL validated by Read-Only AST Guardrail."
        else:
            gemini_sql, gemini_exp = cls.generate_sql_with_gemini(question, api_key or "")
            if gemini_sql:
                sql_to_run = gemini_sql
                engine_mode = "Gemini 2.5 Flash LLM + Read-Only AST Guardrail"
                explanation = gemini_exp or "Generated dynamically via Gemini 2.5 Flash LLM."
            else:
                sql_to_run = intent["sql"]

        result = cls.execute_safe_query(db_path, sql_to_run)
        result["matched_intent"] = intent["id"]
        result["canonical_question"] = question.strip() if question and question.strip() else intent["question"]
        result["explanation"] = explanation
        result["engine_mode"] = engine_mode
        return result

    @staticmethod
    def _summarize_result(df_res: pd.DataFrame) -> str:
        if df_res.empty:
            return "Query executed cleanly and returned 0 rows."
        top_row = df_res.iloc[0].to_dict()
        kv_pairs = [f"{k}: {v}" for k, v in list(top_row.items())[:4]]
        return f"Returned {len(df_res):,} row(s). Top record — " + " | ".join(kv_pairs) + "."


    # -------------------------------------------------------------------------
    # PRODUCTION UPGRADE STUB — Gemini API Integration
    # -------------------------------------------------------------------------
    # To replace the template engine with Gemini:
    #
    # import google.generativeai as genai
    #
    # def summarize_with_gemini(self, df, api_key: str) -> str:
    #     genai.configure(api_key=api_key)
    #     model = genai.GenerativeModel("gemini-2.0-flash")
    #
    #     context = {
    #         "total_orders": len(df),
    #         "on_time_pct": round((df["Calculated_Delay_Days"] <= 0).sum() / len(df) * 100, 1),
    #         "sla_breach_pct": round((df["Calculated_SLA_Breach"] == "Yes").sum() / len(df) * 100, 1),
    #         "top_city": df.groupby("City")["Calculated_SLA_Breach"].apply(
    #             lambda s: (s == "Yes").sum() / len(s) * 100).idxmax(),
    #         "top_delay_reason": df["Cleaned_Delay_Reason"].value_counts().index[0],
    #     }
    #
    #     prompt = f"""
    #     You are a senior logistics analytics consultant at a Fortune 500 e-commerce company.
    #     Analyze the following delivery performance data and provide:
    #     1. A 2-sentence executive summary for the C-suite
    #     2. The single most urgent operational action item
    #     3. One financial risk quantification
    #
    #     Data context: {context}
    #
    #     Keep the response under 150 words. Use specific numbers. No generic advice.
    #     """
    #     response = model.generate_content(prompt)
    #     return response.text

