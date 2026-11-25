"""
==============================================================================
LAST-MILE DELIVERY ANALYTICS — FORTUNE 500 EDITION (2026)
==============================================================================
Stack  : Python 3.12 | FastAPI | Next.js / React | Streamlit | XGBoost | SHAP | Plotly | SQLite
Author : Mohammed Zaidaan Shiraz
Target : Blitz Operations Analytics | PulseRoute — Last-Mile SLA Forensics & AI Operations Copilot
==============================================================================
"""

import streamlit as st
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import sys

# ── Path setup ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Blitz Delivery Intelligence Platform",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "PulseRoute — Last-Mile SLA Forensics & AI Operations Copilot | Mohammed Zaidaan Shiraz",
    },
)

# ── CUSTOM DESIGN SYSTEM ──────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #0A0E1A; }
[data-testid="stSidebar"]          { background: #0D1226; border-right: 1px solid #1E2A45; }
[data-testid="stHeader"]           { background: transparent; }
section.main > div                 { padding-top: 1rem; }

/* ── KPI Cards ── */
.kpi-card {
    background: linear-gradient(135deg, #111827 0%, #1a2235 100%);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 10px;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: var(--accent, #3B82F6);
    border-radius: 12px 0 0 12px;
}
.kpi-label  { font-size: 0.75rem; font-weight: 600; color: #64748B;
               text-transform: uppercase; letter-spacing: 0.08em; }
.kpi-value  { font-size: 2rem; font-weight: 700; color: #F1F5F9;
               line-height: 1.1; margin: 4px 0; }
.kpi-delta  { font-size: 0.8rem; color: #94A3B8; }
.kpi-green  { --accent: #10B981; }
.kpi-red    { --accent: #EF4444; }
.kpi-blue   { --accent: #3B82F6; }
.kpi-amber  { --accent: #F59E0B; }
.kpi-purple { --accent: #8B5CF6; }

/* ── Risk Badges ── */
.badge-high   { background:#EF44441A; color:#EF4444; border:1px solid #EF444433;
                 padding:3px 10px; border-radius:20px; font-size:0.75rem; font-weight:700; }
.badge-medium { background:#F59E0B1A; color:#F59E0B; border:1px solid #F59E0B33;
                 padding:3px 10px; border-radius:20px; font-size:0.75rem; font-weight:700; }
.badge-low    { background:#10B9811A; color:#10B981; border:1px solid #10B98133;
                 padding:3px 10px; border-radius:20px; font-size:0.75rem; font-weight:700; }

/* ── Section Headers ── */
.section-header {
    font-size: 1.1rem; font-weight: 700; color: #94A3B8;
    text-transform: uppercase; letter-spacing: 0.1em;
    border-bottom: 1px solid #1E2A45; padding-bottom: 8px; margin-bottom: 16px;
}

/* ── Insight Panel ── */
.insight-panel {
    background: #0F1929; border: 1px solid #1E3A5F; border-radius: 10px;
    padding: 16px 20px; margin-bottom: 10px;
}

/* ── AI Badge ── */
.ai-badge {
    display: inline-block; background: linear-gradient(90deg, #6366F1, #8B5CF6);
    color: white; font-size: 0.65rem; font-weight: 700; padding: 2px 8px;
    border-radius: 10px; letter-spacing: 0.08em; vertical-align: middle; margin-left: 6px;
}

/* ── Streamlit overrides ── */
.stMetric          { background: transparent !important; }
div[data-testid="metric-container"] { background: transparent; }
.stDataFrame       { border-radius: 8px; }
h1, h2, h3        { color: #E2E8F0 !important; }
p, li             { color: #CBD5E1; }
.stMarkdown p     { color: #CBD5E1; }
</style>
""", unsafe_allow_html=True)


# ── DATA LOADING ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    primary  = BASE_DIR / "data" / "sample_data.csv"
    fallback = BASE_DIR / "Dataset" / "Last_Mile_Delivery_Dataset.csv"

    path = primary if primary.exists() else fallback
    df   = pd.read_csv(path)

    # Ensure derived columns (graceful fallback for raw data)
    if "Calculated_Delay_Days" not in df.columns:
        p = pd.to_datetime(df["Promised_Delivery_Date"])
        a = pd.to_datetime(df["Actual_Delivery_Date"])
        o = pd.to_datetime(df["Order_Date"])
        df["Calculated_Delay_Days"] = (a.dt.floor("D") - p.dt.floor("D")).dt.days
        df["Calculated_Delivery_Status"] = np.select(
            [df["Calculated_Delay_Days"] < 0,
             df["Calculated_Delay_Days"] == 0,
             df["Calculated_Delay_Days"] > 0],
            ["Early", "On-Time", "Delayed"], default="Unknown"
        )
        df["Calculated_SLA_Breach"] = np.where(
            df["Calculated_Delay_Days"] > 2, "Yes", "No")
        df["Delivery_Lead_Time_Days"] = (a.dt.floor("D") - o.dt.floor("D")).dt.days
        df["Promised_Lead_Time_Days"] = (p.dt.floor("D") - o.dt.floor("D")).dt.days
        df["Cleaned_Delay_Reason"] = df["Delay_Reason"].fillna(
            "Not Applicable (On-Time/Early)")
        df["Data_Quality_Flag"] = "Clean"

    df["Order_Date_dt"]             = pd.to_datetime(df["Order_Date"])
    df["Promised_Delivery_Date_dt"] = pd.to_datetime(df["Promised_Delivery_Date"])
    df["Actual_Delivery_Date_dt"]   = pd.to_datetime(df["Actual_Delivery_Date"])
    df["Order_Month_Str"]           = df["Order_Date_dt"].dt.strftime("%Y-%m")
    return df


@st.cache_resource(show_spinner=False)
def train_ai_models(df: pd.DataFrame):
    """Train SLA Predictor + Anomaly Detector once and cache in session."""
    try:
        from ai_engine import SLABreachPredictor, DeliveryAnomalyDetector
        predictor = SLABreachPredictor()
        metrics   = predictor.train(df)
        detector  = DeliveryAnomalyDetector(contamination=0.05)
        df_anom   = detector.fit_predict(df)
        return predictor, detector, metrics, df_anom, None
    except Exception as e:
        return None, None, {}, df, str(e)


# ── LOAD DATA ─────────────────────────────────────────────────────────────────
with st.spinner("Loading delivery intelligence platform…"):
    df_master = load_data()

if df_master.empty:
    st.error("Dataset not found.")
    st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 10px 0 20px 0;'>
        <div style='font-size:2rem;'>🚚</div>
        <div style='font-size:1rem; font-weight:700; color:#E2E8F0;'>Blitz Intelligence</div>
        <div style='font-size:0.7rem; color:#64748B;'>Last-Mile Analytics Platform</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🎛️ Operational Filters")
    st.caption("All KPIs and AI models update from these filters.")

    # Date range
    min_d = df_master["Order_Date_dt"].min().date()
    max_d = df_master["Order_Date_dt"].max().date()
    selected_dates = st.date_input("📅 Order Date Range",
                                    value=(min_d, max_d),
                                    min_value=min_d, max_value=max_d)

    # City
    all_cities = sorted(df_master["City"].unique())
    if st.checkbox("All Cities", value=True, key="city_all"):
        sel_cities = st.multiselect("🏙️ Cities", all_cities, default=all_cities)
    else:
        sel_cities = st.multiselect("🏙️ Cities", all_cities, default=all_cities[:1])

    # Vendor
    all_vendors = sorted(df_master["Vendor"].unique())
    if st.checkbox("All Vendors", value=True, key="vendor_all"):
        sel_vendors = st.multiselect("🤝 Vendors", all_vendors, default=all_vendors)
    else:
        sel_vendors = st.multiselect("🤝 Vendors", all_vendors, default=all_vendors[:1])

    # Status
    sel_status = st.selectbox(
        "⏱️ Delivery Status",
        ["All", "Early (< 0 days)", "On-Time (0 days)",
         "Delayed (> 0 days)", "SLA Breached (> 2 days)"]
    )

    with st.expander("⚙️ Advanced Filters"):
        all_zones = sorted(df_master["Zone"].unique())
        sel_zones = st.multiselect("Zone", all_zones, default=all_zones)
        all_cats  = sorted(df_master["Product_Category"].unique())
        sel_cats  = st.multiselect("Category", all_cats, default=all_cats)
        all_pays  = sorted(df_master["Payment_Mode"].unique())
        sel_pays  = st.multiselect("Payment", all_pays, default=all_pays)

    st.divider()
    st.caption("⚡ Powered by XGBoost · SHAP · Streamlit")


# ── FILTER PIPELINE ───────────────────────────────────────────────────────────
fdf = df_master.copy()
if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    s, e = selected_dates
    fdf = fdf[(fdf["Order_Date_dt"].dt.date >= s) &
              (fdf["Order_Date_dt"].dt.date <= e)]
if sel_cities:  fdf = fdf[fdf["City"].isin(sel_cities)]
else:           fdf = fdf.iloc[0:0]
if sel_vendors: fdf = fdf[fdf["Vendor"].isin(sel_vendors)]
else:           fdf = fdf.iloc[0:0]
if sel_status == "Early (< 0 days)":
    fdf = fdf[fdf["Calculated_Delivery_Status"] == "Early"]
elif sel_status == "On-Time (0 days)":
    fdf = fdf[fdf["Calculated_Delivery_Status"] == "On-Time"]
elif sel_status == "Delayed (> 0 days)":
    fdf = fdf[fdf["Calculated_Delivery_Status"] == "Delayed"]
elif sel_status == "SLA Breached (> 2 days)":
    fdf = fdf[fdf["Calculated_SLA_Breach"] == "Yes"]
if sel_zones: fdf = fdf[fdf["Zone"].isin(sel_zones)]
if sel_cats:  fdf = fdf[fdf["Product_Category"].isin(sel_cats)]
if sel_pays:  fdf = fdf[fdf["Payment_Mode"].isin(sel_pays)]

if len(fdf) == 0:
    st.warning("⚠️ No records match the current filters. Widen your selection.")
    st.stop()


# ── KPI CALCULATIONS (single source of truth) ─────────────────────────────────
total      = len(fdf)
n_early    = int((fdf["Calculated_Delivery_Status"] == "Early").sum())
n_ontime   = int((fdf["Calculated_Delivery_Status"] == "On-Time").sum())
n_delayed  = int((fdf["Calculated_Delivery_Status"] == "Delayed").sum())
n_breached = int((fdf["Calculated_SLA_Breach"] == "Yes").sum())
pct_ontime = (n_early + n_ontime) / total * 100
pct_breach = n_breached / total * 100
pct_delay  = n_delayed  / total * 100
delayed_df = fdf[fdf["Calculated_Delay_Days"] > 0]
avg_delay  = delayed_df["Calculated_Delay_Days"].mean() if len(delayed_df) else 0.0
avg_lt     = fdf["Delivery_Lead_Time_Days"].mean()
total_gmv  = fdf["Order_Value_INR"].sum()
risk_gmv   = fdf[fdf["Calculated_SLA_Breach"] == "Yes"]["Order_Value_INR"].sum()


# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='margin-bottom:1.5rem;'>
    <div style='font-size:1.5rem; font-weight:800; color:#E2E8F0;'>
        📦 Last-Mile Delivery Intelligence Platform
        <span class='ai-badge'>AI-POWERED</span>
    </div>
    <div style='color:#64748B; font-size:0.85rem; margin-top:4px;'>
        Blitz Operations Analytics · 5,200 Deliveries · 15 Cities · 8 Carriers · 2024
    </div>
</div>
""", unsafe_allow_html=True)

# ── KPI BANNER ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)

def kpi_card(col, label, value, delta, color_cls, icon):
    col.markdown(f"""
    <div class='kpi-card {color_cls}'>
        <div class='kpi-label'>{icon} {label}</div>
        <div class='kpi-value'>{value}</div>
        <div class='kpi-delta'>{delta}</div>
    </div>""", unsafe_allow_html=True)

kpi_card(c1, "Total Deliveries",    f"{total:,}",           f"Filtered cohort", "kpi-blue",   "📦")
kpi_card(c2, "On-Time Rate",        f"{pct_ontime:.1f}%",   f"Target ≥ 70% {'✓' if pct_ontime>=70 else '✗'}", "kpi-green" if pct_ontime>=70 else "kpi-red", "🟢")
kpi_card(c3, "Delayed Orders",      f"{n_delayed:,}",       f"{pct_delay:.1f}% of total",   "kpi-amber",  "⏱️")
kpi_card(c4, "SLA Breaches",        f"{n_breached:,}",      f"{pct_breach:.1f}% breach rate", "kpi-red" if pct_breach>25 else "kpi-amber", "⚠️")
kpi_card(c5, "Avg Late Delay",      f"{avg_delay:.1f}d",    "Delayed cohort only",          "kpi-amber",  "📉")
kpi_card(c6, "GMV at Risk",         f"₹{risk_gmv/1e5:.1f}L",f"{risk_gmv/total_gmv*100:.1f}% of ₹{total_gmv/1e5:.0f}L GMV", "kpi-purple", "💰")

with st.expander("ℹ️ Metric Definitions & Denominators"):
    st.markdown(f"""
| KPI | Formula | Denominator | Value |
|---|---|---|---|
| **Total Deliveries** | COUNT(orders in filter) | — | **{total:,}** |
| **On-Time Rate** | (Early + On-Time) / Total | All filtered | **{pct_ontime:.2f}%** |
| **Delayed Orders** | Calculated_Delay_Days > 0 | All filtered | **{pct_delay:.2f}%** |
| **SLA Breach %** | Calculated_Delay_Days > 2 | All filtered | **{pct_breach:.2f}%** |
| **Avg Late Delay** | mean(Delay_Days) where Delay > 0 | Delayed cohort | **{avg_delay:.2f} days** |
| **Avg Lead Time** | mean(Actual_Date − Order_Date) | All filtered | **{avg_lt:.2f} days** |
| **GMV at Risk** | SUM(Order_Value) where SLA_Breach=Yes | Breached orders | **₹{risk_gmv:,.0f}** |
    """)

st.divider()

# ── TABS ──────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📈 Executive",
    "🏙️ City Intel",
    "🚚 Vendor Score",
    "🔍 Root Cause",
    "🤖 AI Predictor",
    "🕵️ Anomaly Radar",
    "🧠 AI Insights",
    "🛡️ Data Quality",
    "🗄️ SQL Studio",
])
(tab_exec, tab_city, tab_vendor, tab_cause,
 tab_pred, tab_anom, tab_insight, tab_dq, tab_sql) = tabs


# =============================================================================
# TAB 1 — EXECUTIVE OVERVIEW
# =============================================================================
with tab_exec:
    st.markdown("<div class='section-header'>Executive Performance Dashboard</div>",
                unsafe_allow_html=True)

    monthly = (
        fdf.groupby("Order_Month_Str")
        .agg(Orders=("Order_ID", "count"),
             SLA_Breaches=("Calculated_SLA_Breach",
                            lambda s: (s == "Yes").sum()),
             Avg_Delay=("Calculated_Delay_Days", "mean"))
        .reset_index()
    )
    monthly["Breach_Rate"] = monthly["SLA_Breaches"] / monthly["Orders"] * 100

    col1, col2 = st.columns([6, 4])
    with col1:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=monthly["Order_Month_Str"], y=monthly["Orders"],
                              name="Deliveries", marker_color="#3B82F6",
                              opacity=0.7), secondary_y=False)
        fig.add_trace(go.Scatter(x=monthly["Order_Month_Str"], y=monthly["Breach_Rate"],
                                  name="SLA Breach %", line=dict(color="#EF4444", width=2.5),
                                  mode="lines+markers"), secondary_y=True)
        fig.add_hline(y=20, line_dash="dot", line_color="#F59E0B",
                      annotation_text="Target: 20%", secondary_y=True)
        fig.update_layout(title="Monthly Volume vs SLA Breach Rate",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#94A3B8", height=340,
                          legend=dict(orientation="h", y=1.1))
        fig.update_yaxes(gridcolor="#1E2A45", secondary_y=False)
        fig.update_yaxes(gridcolor="#1E2A45", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        status_d = fdf["Calculated_Delivery_Status"].value_counts().reset_index()
        status_d.columns = ["Status", "Count"]
        fig2 = px.pie(status_d, values="Count", names="Status", hole=0.5,
                      color="Status",
                      color_discrete_map={"Early": "#10B981",
                                           "On-Time": "#3B82F6",
                                           "Delayed": "#EF4444"},
                      title="Fulfillment Breakdown")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#94A3B8",
                            height=340, showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        cat_agg = (fdf.groupby("Product_Category")
                   .agg(GMV=("Order_Value_INR", "sum"),
                        Breach_Rate=("Calculated_SLA_Breach",
                                      lambda s: (s=="Yes").sum()/len(s)*100))
                   .reset_index().sort_values("GMV", ascending=False))
        fig3 = px.bar(cat_agg, x="Product_Category", y="GMV",
                      color="Breach_Rate", color_continuous_scale="RdYlGn_r",
                      title="GMV by Category (colour = SLA Breach %)",
                      labels={"GMV": "GMV (₹)", "Breach_Rate": "Breach %"})
        fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#94A3B8", height=300, xaxis_tickangle=-20)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        pay_agg = (fdf.groupby(["Payment_Mode", "Delivery_Attempts"])
                   .agg(Orders=("Order_ID", "count")).reset_index())
        fig4 = px.bar(pay_agg, x="Payment_Mode", y="Orders",
                      color="Delivery_Attempts", barmode="group",
                      title="Delivery Attempts by Payment Mode",
                      color_discrete_sequence=px.colors.sequential.Blues_r)
        fig4.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#94A3B8", height=300)
        st.plotly_chart(fig4, use_container_width=True)


# =============================================================================
# TAB 2 — CITY INTELLIGENCE
# =============================================================================
with tab_city:
    st.markdown("<div class='section-header'>City & Regional Logistics Intelligence</div>",
                unsafe_allow_html=True)

    city_sum = (
        fdf.groupby(["City", "Zone"])
        .agg(Orders=("Order_ID", "count"),
             OnTime=("Calculated_Delay_Days", lambda d: (d<=0).sum()),
             Delayed=("Calculated_Delay_Days", lambda d: (d>0).sum()),
             Breaches=("Calculated_SLA_Breach", lambda s: (s=="Yes").sum()),
             Avg_Delay=("Calculated_Delay_Days", "mean"),
             Avg_Delay_Late=("Calculated_Delay_Days",
                              lambda d: d[d>0].mean() if (d>0).any() else 0.0),
             Avg_LT=("Delivery_Lead_Time_Days", "mean"))
        .reset_index()
    )
    city_sum["OT_Pct"]     = city_sum["OnTime"]   / city_sum["Orders"] * 100
    city_sum["Breach_Pct"] = city_sum["Breaches"] / city_sum["Orders"] * 100
    city_sum["Delay_Share"] = (city_sum["Delayed"] /
                                city_sum["Delayed"].sum() * 100).round(1)
    city_sum = city_sum.sort_values("OT_Pct", ascending=False)

    c1, c2 = st.columns([6, 4])
    with c1:
        fig = px.bar(city_sum, x="City", y="OT_Pct", color="Zone",
                     text=city_sum["OT_Pct"].map("{:.1f}%".format),
                     title="City On-Time Delivery Rate — Ranked",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.add_hline(y=70, line_dash="dash", line_color="#EF4444",
                      annotation_text="Target: 70%")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#94A3B8", height=380, showlegend=True)
        fig.update_yaxes(gridcolor="#1E2A45")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig2 = px.scatter(city_sum, x="Avg_LT", y="Breach_Pct",
                           size="Orders", color="Zone", text="City",
                           title="City Risk Matrix: Speed vs Reliability",
                           labels={"Avg_LT": "Avg Lead Time (d)",
                                    "Breach_Pct": "SLA Breach %"})
        fig2.update_traces(textposition="top center")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#94A3B8", height=380)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 📋 City League Table")
    disp = city_sum[["City","Zone","Orders","OT_Pct","Breach_Pct",
                      "Avg_Delay_Late","Avg_LT","Delay_Share"]].copy()
    disp.columns = ["City","Zone","Orders","On-Time %","SLA Breach %",
                     "Avg Delay (Late)","Avg Lead Time","Delay Share %"]
    for col in ["On-Time %","SLA Breach %","Delay Share %"]:
        disp[col] = disp[col].map("{:.1f}%".format)
    for col in ["Avg Delay (Late)", "Avg Lead Time"]:
        disp[col] = disp[col].map("{:.2f}d".format)
    st.dataframe(disp, use_container_width=True, height=380)


# =============================================================================
# TAB 3 — VENDOR SCORECARD
# =============================================================================
with tab_vendor:
    st.markdown("<div class='section-header'>3PL Carrier Scorecard & SLA Compliance</div>",
                unsafe_allow_html=True)

    vend_sum = (
        fdf.groupby("Vendor")
        .agg(Orders=("Order_ID", "count"),
             Breaches=("Calculated_SLA_Breach", lambda s: (s=="Yes").sum()),
             Delayed=("Calculated_Delay_Days",  lambda d: (d>0).sum()),
             Avg_Delay=("Calculated_Delay_Days", "mean"),
             Avg_LT=("Delivery_Lead_Time_Days", "mean"),
             GMV=("Order_Value_INR", "sum"))
        .reset_index()
    )
    vend_sum["Breach_Pct"] = vend_sum["Breaches"] / vend_sum["Orders"] * 100
    vend_sum["OT_Pct"]     = 100 - vend_sum["Delayed"] / vend_sum["Orders"] * 100
    net_breach             = pct_breach
    vend_sum["Delta"]      = net_breach - vend_sum["Breach_Pct"]
    vend_sum["Tier"]       = np.where(vend_sum["Delta"] > 0,
                                       "🏆 Tier-1 (Outperforming)",
                                       "⚠️ Under Review")

    c1, c2 = st.columns([6, 4])
    with c1:
        fig = px.bar(vend_sum.sort_values("Breach_Pct"),
                     x="Vendor", y="Breach_Pct", color="Tier",
                     color_discrete_map={"🏆 Tier-1 (Outperforming)": "#10B981",
                                          "⚠️ Under Review": "#EF4444"},
                     text=vend_sum["Breach_Pct"].map("{:.1f}%".format),
                     title=f"Carrier SLA Breach Rate vs Network Avg ({net_breach:.1f}%)")
        fig.add_hline(y=net_breach, line_dash="dash", line_color="#F59E0B",
                      annotation_text=f"Network avg: {net_breach:.1f}%")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#94A3B8", height=380, showlegend=True)
        fig.update_yaxes(gridcolor="#1E2A45")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig2 = px.scatter(vend_sum, x="Avg_LT", y="Breach_Pct",
                           size="Orders", color="Vendor", text="Vendor",
                           title="Carrier Efficiency Matrix",
                           labels={"Avg_LT": "Avg Cycle Time (d)",
                                    "Breach_Pct": "SLA Breach %"})
        fig2.update_traces(textposition="top center")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#94A3B8", height=380)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 📋 Carrier League Table & Contract Terms")
    vdisp = vend_sum[["Vendor", "Tier", "Orders", "OT_Pct", "Breach_Pct", "Delta", "Avg_LT", "GMV"]].copy()
    vdisp.columns = ["Carrier", "Operational Tier", "Dispatches", "On-Time %", "SLA Breach %", "Delta vs Benchmark", "Avg Cycle Time", "Total GMV"]
    vdisp["On-Time %"] = vdisp["On-Time %"].map("{:.1f}%".format)
    vdisp["SLA Breach %"] = vdisp["SLA Breach %"].map("{:.1f}%".format)
    vdisp["Delta vs Benchmark"] = vdisp["Delta vs Benchmark"].map("{:+.2f}%".format)
    vdisp["Avg Cycle Time"] = vdisp["Avg Cycle Time"].map("{:.2f}d".format)
    vdisp["Total GMV"] = vdisp["Total GMV"].map("₹{:,.0f}".format)
    st.dataframe(vdisp, use_container_width=True)

    st.divider()
    st.markdown("### 🔀 Prescriptive What-If: Carrier Volume Rebalancing Simulator")
    st.caption("Simulate real-time routing optimization: Shift dispatches from bottom-tier carriers to Tier-1 carriers to quantify SLA improvement and GMV risk savings.")

    sim_col1, sim_col2 = st.columns([4, 8])
    with sim_col1:
        realloc_pct = st.slider("Dispatch Volume Shift (%)", min_value=5, max_value=35, value=15, step=5,
                                help="Percentage of volume dynamically shifted from carriers with > network breach rate to top-tier partners.")
        tier1_carriers = vend_sum[vend_sum["Tier"].str.contains("Tier-1")]["Vendor"].tolist()
        under_review_carriers = vend_sum[vend_sum["Tier"].str.contains("Under Review")]["Vendor"].tolist()
        st.caption(f"**Beneficiary Carriers (Tier-1):** {', '.join(tier1_carriers) if tier1_carriers else 'None'}")
        st.caption(f"**De-allocated Carriers:** {', '.join(under_review_carriers) if under_review_carriers else 'None'}")

    with sim_col2:
        if tier1_carriers and under_review_carriers:
            under_review_vol = vend_sum[vend_sum["Vendor"].isin(under_review_carriers)]["Orders"].sum()
            shifted_orders = int(under_review_vol * (realloc_pct / 100.0))
            
            avg_tier1_breach = vend_sum[vend_sum["Vendor"].isin(tier1_carriers)]["Breaches"].sum() / max(vend_sum[vend_sum["Vendor"].isin(tier1_carriers)]["Orders"].sum(), 1)
            avg_under_breach = vend_sum[vend_sum["Vendor"].isin(under_review_carriers)]["Breaches"].sum() / max(under_review_vol, 1)
            
            projected_breach_reduction = int(shifted_orders * (avg_under_breach - avg_tier1_breach))
            projected_total_breaches = max(n_breached - projected_breach_reduction, 0)
            projected_breach_rate = (projected_total_breaches / total) * 100.0
            avg_order_value = total_gmv / max(total, 1)
            projected_gmv_saved = projected_breach_reduction * avg_order_value

            s1, s2, s3 = st.columns(3)
            s1.metric("📦 Shifted Dispatches", f"{shifted_orders:,} orders", f"{realloc_pct}% from underperformers")
            s2.metric("📉 New SLA Breach %", f"{projected_breach_rate:.1f}%", f"-{pct_breach - projected_breach_rate:.2f}% improvement")
            s3.metric("💰 GMV Risk Avoided", f"₹{projected_gmv_saved:,.0f}", f"{projected_breach_reduction:,} fewer failures")

            # Comparative Simulation Bar
            sim_df = pd.DataFrame({
                "Scenario": ["Current Network", f"Optimized (+{realloc_pct}% Shift)"],
                "SLA Breach Rate (%)": [pct_breach, projected_breach_rate],
                "SLA Breaches (Count)": [n_breached, projected_total_breaches]
            })
            fig_sim = px.bar(sim_df, x="Scenario", y="SLA Breach Rate (%)", color="Scenario",
                             text=sim_df["SLA Breach Rate (%)"].map("{:.2f}%".format),
                             color_discrete_map={"Current Network": "#EF4444", f"Optimized (+{realloc_pct}% Shift)": "#10B981"},
                             title="Projected Network SLA Breach Rate After Routing Rebalancing")
            fig_sim.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font_color="#94A3B8", height=280, showlegend=False)
            fig_sim.update_yaxes(gridcolor="#1E2A45")
            st.plotly_chart(fig_sim, use_container_width=True)
        else:
            st.info("Both Tier-1 and Under-Review carriers required to run rebalancing simulation.")


# =============================================================================
# TAB 4 — ROOT CAUSE
# =============================================================================
with tab_cause:
    st.markdown("<div class='section-header'>Delay Root Cause Diagnostics</div>",
                unsafe_allow_html=True)

    delayed_sub = fdf[fdf["Calculated_Delivery_Status"] == "Delayed"]
    if len(delayed_sub) == 0:
        st.info("No delayed orders in the current filter selection.")
    else:
        cause_agg = (delayed_sub["Cleaned_Delay_Reason"]
                     .value_counts().reset_index())
        cause_agg.columns = ["Reason", "Count"]
        cause_agg["Pct"]  = cause_agg["Count"] / cause_agg["Count"].sum() * 100
        cause_agg["Cumulative"] = cause_agg["Pct"].cumsum()

        c1, c2 = st.columns([6, 4])
        with c1:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=cause_agg["Reason"], y=cause_agg["Count"],
                                  name="Failure Count", marker_color="#F59E0B"),
                           secondary_y=False)
            fig.add_trace(go.Scatter(x=cause_agg["Reason"],
                                      y=cause_agg["Cumulative"],
                                      name="Cumulative %", mode="lines+markers",
                                      line=dict(color="#8B5CF6", width=2)),
                           secondary_y=True)
            fig.add_hline(y=80, line_dash="dot", line_color="#EF4444",
                           annotation_text="80% Pareto Line", secondary_y=True)
            fig.update_layout(title="Pareto Analysis of Delay Root Causes",
                               paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#94A3B8", height=380)
            fig.update_xaxes(tickangle=-20)
            fig.update_yaxes(gridcolor="#1E2A45", secondary_y=False)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            def cat_reason(r):
                if r in ["Traffic Congestion","Route Optimization Failure","Vehicle Breakdown"]:
                    return "🚛 Transit & Fleet"
                elif r in ["Warehouse Processing Delay","High Order Volume"]:
                    return "🏭 Fulfilment"
                elif r in ["Customer Unavailable","Wrong Address"]:
                    return "👤 Customer"
                elif r == "Weather Conditions":
                    return "🌧️ External"
                return "❓ Other"

            cause_agg["Category"] = cause_agg["Reason"].apply(cat_reason)
            cat_sum = cause_agg.groupby("Category")["Count"].sum().reset_index()
            fig2 = px.pie(cat_sum, values="Count", names="Category", hole=0.45,
                           title="Controllable vs Uncontrollable Delays")
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#94A3B8",
                                height=380)
            st.plotly_chart(fig2, use_container_width=True)

        # Seasonal analysis
        st.markdown("### 🌧️ Seasonal Surge Impact")
        seas = (fdf.groupby(["Is_Festive_Season","Is_Monsoon_Season"])
                .agg(Orders=("Order_ID","count"),
                     Delay_Rate=("Calculated_Delivery_Status",
                                  lambda s: (s=="Delayed").sum()/len(s)*100),
                     SLA_Rate=("Calculated_SLA_Breach",
                                lambda s: (s=="Yes").sum()/len(s)*100))
                .reset_index())
        seas["Season"] = seas.apply(
            lambda r: "🎆 Festive" if r["Is_Festive_Season"]=="Yes"
            else ("🌧️ Monsoon" if r["Is_Monsoon_Season"]=="Yes"
            else "☀️ Normal"), axis=1)
        fig3 = px.bar(seas, x="Season", y=["Delay_Rate","SLA_Rate"],
                       barmode="group", title="Seasonal Operational Degradation",
                       color_discrete_map={"Delay_Rate":"#F59E0B","SLA_Rate":"#EF4444"})
        fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#94A3B8", height=320)
        st.plotly_chart(fig3, use_container_width=True)


# =============================================================================
# TAB 5 — AI SLA BREACH PREDICTOR
# =============================================================================
with tab_pred:
    st.markdown(
        "<div class='section-header'>AI SLA Breach Predictor "
        "<span class='ai-badge'>XGBoost + SHAP</span></div>",
        unsafe_allow_html=True)

    st.markdown("""
    > **What this model does:** Predicts the probability that an order will breach its SLA
    > *before dispatch* — giving operations teams advance warning to reroute or escalate.
    > Uses XGBoost trained on 12 engineered features, with SHAP values for every prediction.
    """)

    with st.spinner("🤖 Training SLA Breach Predictor on historical data…"):
        predictor, detector, metrics, df_with_anom, ai_error = train_ai_models(df_master)

    if ai_error or predictor is None:
        st.error(f"AI model unavailable: {ai_error}")
        st.info("Install: `pip install scikit-learn xgboost shap statsmodels`")
    else:
        # ── Model Performance ───────────────────────────────────────────────
        st.markdown("#### 📊 Model Evaluation")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("AUC-ROC",     f"{metrics['roc_auc']:.4f}",
                   help="Area Under ROC Curve. 1.0 = perfect; 0.5 = random.")
        report = metrics["report"]
        m2.metric("Precision (Breach class)",
                   f"{report.get('1',{}).get('precision',0):.3f}")
        m3.metric("Recall (Breach class)",
                   f"{report.get('1',{}).get('recall',0):.3f}")
        m4.metric("F1 Score",
                   f"{report.get('1',{}).get('f1-score',0):.3f}")

        col_roc, col_shap = st.columns(2)

        with col_roc:
            fig_roc = go.Figure()
            fig_roc.add_trace(go.Scatter(
                x=metrics["fpr"], y=metrics["tpr"],
                mode="lines", name=f"AUC = {metrics['roc_auc']:.4f}",
                line=dict(color="#8B5CF6", width=2.5)
            ))
            fig_roc.add_shape(type="line", x0=0, y0=0, x1=1, y1=1,
                               line=dict(dash="dot", color="#64748B"))
            fig_roc.update_layout(
                title="ROC Curve — SLA Breach Detection",
                xaxis_title="False Positive Rate", yaxis_title="True Positive Rate",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94A3B8", height=320)
            fig_roc.update_xaxes(gridcolor="#1E2A45")
            fig_roc.update_yaxes(gridcolor="#1E2A45")
            st.plotly_chart(fig_roc, use_container_width=True)

        with col_shap:
            fi_df = predictor.get_feature_importance_df()
            fig_fi = px.bar(fi_df.head(10), x="Mean_SHAP", y="Feature",
                             orientation="h",
                             title="SHAP Feature Importance — What Drives SLA Breaches?",
                             color="Mean_SHAP",
                             color_continuous_scale="Bluered_r")
            fig_fi.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)",
                                   font_color="#94A3B8", height=320,
                                   yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_fi, use_container_width=True)

        # ── Score Current Filtered Dataset ──────────────────────────────────
        st.markdown("#### 🎯 Risk Scoring — Current Filtered Orders")
        with st.spinner("Scoring orders…"):
            try:
                fdf_scored = predictor.predict_dataframe(fdf)
            except Exception as e:
                st.error(f"Scoring error: {e}")
                fdf_scored = fdf.copy()
                fdf_scored["SLA_Risk_Score"] = 0.5
                fdf_scored["SLA_Risk_Label"] = "Medium Risk"

        risk_dist = fdf_scored["SLA_Risk_Label"].value_counts()
        r1, r2, r3 = st.columns(3)
        r1.metric("🔴 High Risk Orders",
                   f"{risk_dist.get('High Risk', 0):,}",
                   f"{risk_dist.get('High Risk',0)/len(fdf_scored)*100:.1f}%")
        r2.metric("🟡 Medium Risk Orders",
                   f"{risk_dist.get('Medium Risk', 0):,}",
                   f"{risk_dist.get('Medium Risk',0)/len(fdf_scored)*100:.1f}%")
        r3.metric("🟢 Low Risk Orders",
                   f"{risk_dist.get('Low Risk', 0):,}",
                   f"{risk_dist.get('Low Risk',0)/len(fdf_scored)*100:.1f}%")

        # Risk score distribution
        fig_hist = px.histogram(fdf_scored, x="SLA_Risk_Score", nbins=30,
                                 color="SLA_Risk_Label",
                                 color_discrete_map={"High Risk": "#EF4444",
                                                      "Medium Risk": "#F59E0B",
                                                      "Low Risk": "#10B981"},
                                 title="SLA Risk Score Distribution")
        fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                                 plot_bgcolor="rgba(0,0,0,0)",
                                 font_color="#94A3B8", height=300)
        fig_hist.update_xaxes(gridcolor="#1E2A45")
        fig_hist.update_yaxes(gridcolor="#1E2A45")
        st.plotly_chart(fig_hist, use_container_width=True)

        # High-risk orders table
        st.markdown("#### 🔴 Top High-Risk Orders (Action Required)")
        high_risk = (fdf_scored[fdf_scored["SLA_Risk_Label"] == "High Risk"]
                     [["Order_ID","City","Vendor","Product_Category",
                        "Order_Value_INR","Promised_Delivery_Date",
                        "SLA_Risk_Score","Cleaned_Delay_Reason"]]
                     .sort_values("SLA_Risk_Score", ascending=False)
                     .head(20))
        high_risk["SLA_Risk_Score"] = high_risk["SLA_Risk_Score"].map("{:.1%}".format)
        high_risk["Order_Value_INR"] = high_risk["Order_Value_INR"].map("₹{:,.0f}".format)
        st.dataframe(high_risk, use_container_width=True, height=360)

        st.markdown("""
        > **How to use this in operations:**
        > 1. Run the scorer each morning on today's dispatch queue
        > 2. All 🔴 High Risk orders → flag for proactive carrier escalation
        > 3. SMS/WhatsApp the customer with an estimated delay warning
        > 4. Reroute to Tier-1 carrier if 🔴 risk and high GMV
        """)


# =============================================================================
# TAB 6 — ANOMALY RADAR
# =============================================================================
with tab_anom:
    st.markdown(
        "<div class='section-header'>Anomaly Detection Radar "
        "<span class='ai-badge'>Isolation Forest</span></div>",
        unsafe_allow_html=True)

    st.markdown("""
    > **What this detects:** Statistical outliers in delivery behaviour — extreme delays,
    > impossible lead times, unusual order-value + delay combinations. Isolation Forest
    > flags the top 5% most anomalous records for forensic investigation.
    """)

    if detector is None:
        st.warning("Anomaly detector unavailable. Install scikit-learn.")
    else:
        # Re-score the filtered data with the already-fitted detector
        try:
            from ai_engine import DeliveryAnomalyDetector as _AD
            det_local = _AD(contamination=0.05)
            fdf_anom = det_local.fit_predict(fdf)
        except Exception:
            fdf_anom = df_with_anom[df_with_anom["Order_ID"].isin(fdf["Order_ID"])]

        n_anomalies = int(fdf_anom["Is_Anomaly"].sum()) if "Is_Anomaly" in fdf_anom.columns else 0

        a1, a2, a3 = st.columns(3)
        a1.metric("🕵️ Anomalies Detected",
                   f"{n_anomalies:,}",
                   f"{n_anomalies/len(fdf_anom)*100:.1f}% of cohort")
        a2.metric("📏 Total Inspected", f"{len(fdf_anom):,}")
        a3.metric("✅ Normal Records",
                   f"{len(fdf_anom)-n_anomalies:,}",
                   f"{(len(fdf_anom)-n_anomalies)/len(fdf_anom)*100:.1f}%")

        if "Is_Anomaly" in fdf_anom.columns and "Anomaly_Score" in fdf_anom.columns:
            # Scatter plot: delay vs lead time, coloured by anomaly
            fig = px.scatter(fdf_anom, x="Delivery_Lead_Time_Days",
                              y="Calculated_Delay_Days",
                              color="Is_Anomaly",
                              color_discrete_map={True: "#EF4444", False: "#3B82F6"},
                              size="Order_Value_INR",
                              hover_data=["Order_ID","City","Vendor"],
                              title="Anomaly Scatter: Lead Time vs Delay Days",
                              labels={"Is_Anomaly": "Anomaly"})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#94A3B8", height=380)
            fig.update_xaxes(gridcolor="#1E2A45")
            fig.update_yaxes(gridcolor="#1E2A45")
            st.plotly_chart(fig, use_container_width=True)

            # Anomaly records table
            st.markdown("#### 🔍 Top Anomalous Records")
            anom_records = (
                fdf_anom[fdf_anom["Is_Anomaly"] == True]
                [["Order_ID","City","Vendor","Calculated_Delay_Days",
                   "Delivery_Lead_Time_Days","Order_Value_INR",
                   "Delivery_Attempts","Anomaly_Rank"]]
                .sort_values("Anomaly_Rank", ascending=False)
                .head(20)
            )
            anom_records["Anomaly_Rank"] = anom_records["Anomaly_Rank"].map("{:.1f}".format)
            anom_records["Order_Value_INR"] = anom_records["Order_Value_INR"].map("₹{:,.0f}".format)
            st.dataframe(anom_records, use_container_width=True, height=360)

            st.caption("**Anomaly_Rank**: 100 = most anomalous. Investigate records > 95.")


# =============================================================================
# TAB 7 — AI INSIGHTS (NLP SUMMARIZER)
# =============================================================================
with tab_insight:
    st.markdown(
        "<div class='section-header'>AI Operational Intelligence "
        "<span class='ai-badge'>NLP Insights Engine</span></div>",
        unsafe_allow_html=True)

    st.markdown("""
    > The insight engine analyzes the **currently filtered dataset** and generates
    > plain-English operational intelligence — the same analysis a senior logistics
    > consultant would produce, generated in real time.
    > *(Production version: connects to Gemini 2.0 Flash for natural-language streaming)*
    """)

    try:
        from ai_engine import InsightSummarizer
        summarizer = InsightSummarizer()
        insights   = summarizer.summarize(fdf)

        sections = [
            ("📊 Executive Summary",    "executive_summary"),
            ("⚠️ SLA Risk Assessment",  "sla_risk"),
            ("🔍 Root Cause Analysis",  "root_cause"),
            ("🏙️ City Risk Alert",      "city_risk"),
            ("🏆 Vendor Recommendation","vendor_highlight"),
        ]
        for title, key in sections:
            if key in insights:
                st.markdown(f"""
                <div class='insight-panel'>
                    <strong style='color:#E2E8F0;'>{title}</strong><br><br>
                    <span style='color:#CBD5E1;'>{insights[key]}</span>
                </div>""", unsafe_allow_html=True)

        st.markdown("#### 🎯 Prioritised Action Items")
        if "action_items" in insights:
            for line in insights["action_items"].split("\n"):
                if line.strip():
                    st.markdown(f"- {line.strip()}")

    except Exception as e:
        st.error(f"Insight engine error: {e}")

    st.divider()
    st.markdown("#### 🔮 Demand Forecast (Next 6 Months)")
    try:
        from ai_engine import DeliveryDemandForecaster
        forecaster = DeliveryDemandForecaster()
        forecast_df = forecaster.forecast(fdf, periods=6)

        if not forecast_df.empty:
            fig_fc = go.Figure()
            # Historical
            hist = (fdf.groupby("Order_Month_Str")
                    .agg(Orders=("Order_ID","count")).reset_index()
                    .sort_values("Order_Month_Str"))
            fig_fc.add_trace(go.Scatter(
                x=hist["Order_Month_Str"], y=hist["Orders"],
                name="Historical", line=dict(color="#3B82F6", width=2),
                mode="lines+markers"))
            # Forecast
            fig_fc.add_trace(go.Scatter(
                x=forecast_df["Month"], y=forecast_df["Forecasted_Orders"],
                name="Forecast", line=dict(color="#8B5CF6", width=2, dash="dot"),
                mode="lines+markers"))
            # CI
            fig_fc.add_traces([
                go.Scatter(x=forecast_df["Month"], y=forecast_df["Upper_80"],
                            fill=None, mode="lines",
                            line=dict(color="rgba(139,92,246,0.2)"),
                            showlegend=False),
                go.Scatter(x=forecast_df["Month"], y=forecast_df["Lower_80"],
                            fill="tonexty", mode="lines",
                            line=dict(color="rgba(139,92,246,0.2)"),
                            name="80% CI", fillcolor="rgba(139,92,246,0.1)"),
            ])
            fig_fc.update_layout(
                title="Delivery Volume Forecast (Exponential Smoothing + 80% CI)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94A3B8", height=360)
            fig_fc.update_xaxes(gridcolor="#1E2A45")
            fig_fc.update_yaxes(gridcolor="#1E2A45")
            st.plotly_chart(fig_fc, use_container_width=True)
            st.dataframe(forecast_df, use_container_width=True)
        else:
            st.info("Need at least 4 months of data to generate a forecast.")
    except Exception as e:
        st.warning(f"Forecast unavailable: {e}")


# =============================================================================
# TAB 8 — DATA QUALITY AUDIT
# =============================================================================
with tab_dq:
    st.markdown("<div class='section-header'>Forensic Data Quality Audit</div>",
                unsafe_allow_html=True)
    st.markdown("""
    *Rather than hiding data issues, this audit exposes, categorises, and explains every
    discrepancy found in the legacy dispatch system. This is what separates an analyst
    from a data scientist.*
    """)

    dq = df_master  # always use full master for DQ tab
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("📋 Audited Records", f"{len(dq):,}")
    d2.metric("🔑 Duplicate IDs",   f"{dq['Order_ID'].duplicated().sum()}")
    d3.metric("⚠️ 252 Delay Mismatches",
               f"{((dq['Is_Delayed']=='Yes') & dq['DQ_Delay_Mismatch']).sum()}")
    d4.metric("📉 99 SLA Flags",    f"{dq['DQ_SLA_Mismatch'].sum()}")
    d5.metric("❓ 233 Missing Reasons",
               f"{dq['DQ_Missing_Reason_Delayed'].sum()}")

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("""
        **1 — The 252 Delay Mismatches**
        Legacy system stored Delay_Days as a manually-entered integer, not as
        `Actual − Promised`. 233 were on-time but flagged delayed; 19 had wrong magnitudes.
        **Fix:** `Calculated_Delay_Days = floor(Actual) − floor(Promised)`
        """)
    with c2:
        st.warning("""
        **2 — The 99 SLA Flag Discrepancies**
        99 rows had `Delay_Days = 3` but `SLA_Breached = 'No'`. Root cause:
        the carrier SLA engine correctly used true dates (correctly = No),
        while the stored Delay_Days was erroneous.
        **Fix:** `Calculated_SLA_Breach = (Calculated_Delay_Days > 2)`
        """)
    with c3:
        st.success("""
        **3 — The 233 Missing Delay Reasons**
        233 orders marked `Is_Delayed = 'Yes'` had NULL Delay_Reason.
        Every single one was actually on-time or early. No field agent entered a reason
        because no delivery failure occurred.
        **Fix:** `Cleaned_Delay_Reason = 'Not Applicable (On-Time/Early)'`
        """)

    # DQ comparison table
    st.markdown("### 📊 Legacy vs Reconciled Metrics")
    comp = {
        "Metric": ["Delayed Count","Delay Rate (%)","SLA Breaches","SLA Breach %","Early Deliveries"],
        "Raw Legacy System": [
            f"{(dq['Is_Delayed']=='Yes').sum():,}",
            f"{(dq['Is_Delayed']=='Yes').sum()/len(dq)*100:.2f}%",
            f"{(dq['SLA_Breached']=='Yes').sum():,}",
            f"{(dq['SLA_Breached']=='Yes').sum()/len(dq)*100:.2f}%",
            "0 (capped at 0)",
        ],
        "Cleaned Audit System": [
            f"{(dq['Calculated_Delivery_Status']=='Delayed').sum():,}",
            f"{(dq['Calculated_Delivery_Status']=='Delayed').sum()/len(dq)*100:.2f}%",
            f"{(dq['Calculated_SLA_Breach']=='Yes').sum():,}",
            f"{(dq['Calculated_SLA_Breach']=='Yes').sum()/len(dq)*100:.2f}%",
            f"{(dq['Calculated_Delivery_Status']=='Early').sum():,} identified",
        ],
        "Impact": [
            "−233 false positives removed",
            "−4.5% distortion eliminated",
            "Consistent (1,459 matches)",
            "Audited baseline: 28.1%",
            "+1,596 early deliveries surfaced",
        ],
    }
    st.table(pd.DataFrame(comp))

    # DQ flag explorer
    st.markdown("### 🔍 Flagged Records Explorer")
    flag_filter = st.selectbox("Filter by Flag",
                                ["All Flagged"] + sorted(dq["Data_Quality_Flag"].unique()))
    preview = (dq[dq["Data_Quality_Flag"] != "Clean"]
               if flag_filter == "All Flagged"
               else dq[dq["Data_Quality_Flag"] == flag_filter])
    st.dataframe(
        preview[["Order_ID","Promised_Delivery_Date","Actual_Delivery_Date",
                  "Delay_Days","Calculated_Delay_Days","Is_Delayed",
                  "Calculated_Delivery_Status","SLA_Breached","Calculated_SLA_Breach",
                  "Delay_Reason","Data_Quality_Flag"]].head(20),
        use_container_width=True, height=380
    )


# =============================================================================
# TAB 9 — SQL STUDIO
# =============================================================================
with tab_sql:
    st.markdown("<div class='section-header'>Interactive SQL Analytics Studio</div>",
                unsafe_allow_html=True)
    st.markdown("*Execute all 10 production SQL queries live against the relational schema.*")

    SQL_QUESTIONS = {
        "Q1 — Total Deliveries (COUNT)": """
-- Business: Measure gross operational dispatch volume and GMV exposure
SELECT
    COUNT(*) AS total_deliveries,
    COUNT(DISTINCT order_id) AS unique_orders,
    ROUND(SUM(order_value_inr), 2) AS total_gmv_inr
FROM deliveries;""",

        "Q2 — Unique Cities & Vendors (DISTINCT)": """
-- Business: Assess geographic reach and vendor ecosystem diversity
SELECT
    COUNT(DISTINCT c.city_name)  AS unique_cities,
    COUNT(DISTINCT v.vendor_name) AS unique_vendors,
    COUNT(DISTINCT d.delivery_agent_id) AS unique_agents,
    COUNT(DISTINCT d.warehouse_id) AS fulfilment_hubs
FROM deliveries d
JOIN cities  c ON d.city_id  = c.city_id
JOIN vendors v ON d.vendor_id = v.vendor_id;""",

        "Q3 — Avg Delay by City (GROUP BY)": """
-- Business: Identify regional last-mile friction hotspots
SELECT
    c.city_name, c.zone,
    COUNT(d.order_id) AS total_orders,
    ROUND(AVG(d.calculated_delay_days), 2) AS avg_delay_all,
    ROUND(AVG(CASE WHEN d.calculated_delay_days > 0 THEN d.calculated_delay_days END), 2) AS avg_delay_when_late,
    ROUND(100.0 * SUM(CASE WHEN d.calculated_delivery_status='Delayed' THEN 1 ELSE 0 END) / COUNT(d.order_id), 2) AS delay_rate_pct
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
GROUP BY c.city_name, c.zone
ORDER BY avg_delay_all DESC;""",

        "Q4 — Highest SLA Breach Rate Vendors (HAVING)": """
-- Business: Carrier scorecarding for contractual penalty enforcement
-- WHY HAVING: WHERE filters rows before aggregation;
--             HAVING filters groups after aggregation.
--             HAVING COUNT >= 100 prevents distorting low-volume carriers.
SELECT
    v.vendor_name,
    COUNT(d.order_id) AS total_dispatches,
    SUM(CASE WHEN d.calculated_sla_breach='Yes' THEN 1 ELSE 0 END) AS sla_breaches,
    ROUND(100.0 * SUM(CASE WHEN d.calculated_sla_breach='Yes' THEN 1 ELSE 0 END)
          / COUNT(d.order_id), 2) AS sla_breach_rate_pct
FROM deliveries d
JOIN vendors v ON d.vendor_id = v.vendor_id
GROUP BY v.vendor_name
HAVING COUNT(d.order_id) >= 100
ORDER BY sla_breach_rate_pct DESC;""",

        "Q5 — Most Common Delay Reasons (GROUP BY, ORDER BY)": """
-- Business: Pareto distribution of delivery failure causes
SELECT
    r.reason_name, r.reason_category,
    COUNT(d.order_id) AS failure_count,
    ROUND(100.0 * COUNT(d.order_id) /
        (SELECT COUNT(*) FROM deliveries WHERE calculated_delivery_status='Delayed'), 2) AS pct_of_delays
FROM deliveries d
JOIN delay_reasons r ON d.reason_id = r.reason_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY r.reason_name, r.reason_category
ORDER BY failure_count DESC;""",

        "Q6 — Cities with No SLA Breaches (LEFT JOIN)": """
-- Business: Identify zero-defect hubs to replicate best practices
-- WHY LEFT JOIN: INNER JOIN would silently exclude cities with 0 breaches
--                (they have no matching rows in the right table).
--                LEFT JOIN preserves ALL cities; HAVING COUNT=0 surfaces the winners.
SELECT
    c.city_name, c.zone,
    COUNT(b.order_id) AS sla_breach_count
FROM cities c
LEFT JOIN deliveries b
    ON c.city_id = b.city_id
    AND b.calculated_sla_breach = 'Yes'
GROUP BY c.city_name, c.zone
HAVING COUNT(b.order_id) = 0
ORDER BY c.city_name;""",

        "Q7 — Vendors Better Than Network Average (CTE)": """
-- Business: Dynamic carrier benchmarking — identifies Tier-1 partners for
--           volume reallocation.
-- WHY CTE: Modularity. The benchmark is computed once dynamically;
--           changing the filter auto-updates the benchmark without hardcoding.
WITH NetworkBenchmark AS (
    SELECT ROUND(100.0 * SUM(CASE WHEN calculated_sla_breach='Yes' THEN 1 ELSE 0 END)
                 / COUNT(*), 2) AS benchmark_pct
    FROM deliveries
),
VendorMetrics AS (
    SELECT
        v.vendor_name,
        COUNT(d.order_id) AS total_orders,
        ROUND(100.0 * SUM(CASE WHEN d.calculated_sla_breach='Yes' THEN 1 ELSE 0 END)
              / COUNT(d.order_id), 2) AS vendor_breach_pct
    FROM deliveries d
    JOIN vendors v ON d.vendor_id = v.vendor_id
    GROUP BY v.vendor_name
)
SELECT
    vm.vendor_name,
    vm.total_orders,
    vm.vendor_breach_pct,
    nb.benchmark_pct,
    ROUND(nb.benchmark_pct - vm.vendor_breach_pct, 2) AS outperformance_pts
FROM VendorMetrics vm
CROSS JOIN NetworkBenchmark nb
WHERE vm.vendor_breach_pct < nb.benchmark_pct
ORDER BY outperformance_pts DESC;""",

        "Q8 — City Ranking (RANK, DENSE_RANK)": """
-- Business: League table for hub audits and regional performance reporting
-- RANK vs DENSE_RANK:
--   RANK(): ties both get rank 1, next gets rank 3 (gap)
--   DENSE_RANK(): ties both get rank 1, next gets rank 2 (no gap)
WITH CityPerf AS (
    SELECT
        c.city_name, c.zone,
        COUNT(d.order_id) AS total_orders,
        ROUND(100.0 * SUM(CASE WHEN d.calculated_delivery_status IN ('Early','On-Time')
                               THEN 1 ELSE 0 END) / COUNT(d.order_id), 2) AS on_time_pct
    FROM deliveries d
    JOIN cities c ON d.city_id = c.city_id
    GROUP BY c.city_name, c.zone
)
SELECT
    city_name, zone, total_orders, on_time_pct,
    RANK()       OVER (ORDER BY on_time_pct DESC) AS rank_with_gaps,
    DENSE_RANK() OVER (ORDER BY on_time_pct DESC) AS dense_rank_no_gaps,
    DENSE_RANK() OVER (PARTITION BY zone ORDER BY on_time_pct DESC) AS zone_rank
FROM CityPerf
ORDER BY rank_with_gaps;""",

        "Q9 — Monthly SLA Trend with LAG": """
-- Business: Month-over-Month SLA breach trend to detect seasonal degradation
-- WHY LAG instead of self-join: LAG() accesses the previous row in one pass O(N log N).
--   Self-join requires O(N²) Cartesian comparison and breaks on missing months.
WITH MonthlyAgg AS (
    SELECT
        substr(order_date, 1, 7) AS order_month,
        COUNT(order_id) AS monthly_orders,
        ROUND(100.0 * SUM(CASE WHEN calculated_sla_breach='Yes' THEN 1 ELSE 0 END)
              / COUNT(order_id), 2) AS breach_rate_pct
    FROM deliveries
    GROUP BY substr(order_date, 1, 7)
)
SELECT
    order_month, monthly_orders, breach_rate_pct,
    LAG(breach_rate_pct, 1) OVER (ORDER BY order_month) AS prev_month_pct,
    ROUND(breach_rate_pct - LAG(breach_rate_pct,1) OVER (ORDER BY order_month), 2) AS mom_change,
    ROUND(AVG(breach_rate_pct) OVER (
        ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_3mo_avg
FROM MonthlyAgg
ORDER BY order_month;""",

        "Q10 — City Delay Contribution % (Window SUM)": """
-- Business: Pareto analysis — which cities generate the most network delays?
-- WHY Window Function vs GROUP BY:
--   After GROUP BY, the grand total (denominator) is lost.
--   SUM(COUNT(...)) OVER () computes the total across all groups in-memory
--   while keeping row-level city detail — also enables the cumulative Pareto curve.
SELECT
    c.city_name, c.zone,
    COUNT(d.order_id) AS city_delayed_orders,
    SUM(COUNT(d.order_id)) OVER () AS total_network_delayed,
    ROUND(100.0 * COUNT(d.order_id) / SUM(COUNT(d.order_id)) OVER (), 2) AS pct_of_delays,
    ROUND(SUM(100.0 * COUNT(d.order_id) / SUM(COUNT(d.order_id)) OVER ()) OVER (
        ORDER BY COUNT(d.order_id) DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2) AS cumulative_pct
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY c.city_name, c.zone
ORDER BY city_delayed_orders DESC;""",
    }

    q_key = st.selectbox("Select SQL Business Question:", list(SQL_QUESTIONS.keys()))
    st.code(SQL_QUESTIONS[q_key], language="sql")

    db_path = BASE_DIR / "data" / "last_mile_delivery.db"
    if db_path.exists():
        try:
            conn    = sqlite3.connect(str(db_path))
            res_df  = pd.read_sql_query(SQL_QUESTIONS[q_key], conn)
            conn.close()
            st.success(f"✅ Returned {len(res_df):,} rows")
            st.dataframe(res_df, use_container_width=True, height=380)
        except Exception as e:
            st.error(f"SQL Error: {e}")
    else:
        st.warning("Database `data/last_mile_delivery.db` not found.")


# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
fl, fr = st.columns([7, 3])
fl.caption("🚚 PulseRoute — Last-Mile SLA Forensics & AI Operations Copilot · Built by Mohammed Zaidaan Shiraz · 2026")
fr.caption("⚡ XGBoost · SHAP · Isolation Forest · Plotly · SQLite · Streamlit")
