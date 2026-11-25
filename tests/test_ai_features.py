"""
==============================================================================
AI & MACHINE LEARNING PIPELINE TESTS
Project : Last-Mile Delivery Analytics | Blitz Portfolio (Fortune 500 Edition)
Purpose : Rigorous automated tests for AI/ML features:
          1. Feature Engineering integrity
          2. XGBoost SLA Breach Predictor & SHAP Explainability
          3. Isolation Forest Delivery Anomaly Detector
          4. Holt-Winters Exponential Smoothing Demand Forecaster
          5. Executive Insight Generation Engine
Run     : pytest tests/test_ai_features.py -v
==============================================================================
"""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure app directory is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "app"))

from ai_engine import (
    engineer_features,
    SLABreachPredictor,
    DeliveryAnomalyDetector,
    DeliveryDemandForecaster,
    InsightSummarizer,
    ReadOnlySQLCopilot,
    FEATURE_COLS,
    ML_AVAILABLE
)

SAMPLE_DATA_PATH = BASE_DIR / "data" / "sample_data.csv"


@pytest.fixture(scope="module")
def dataset():
    """Load cleaned delivery dataset."""
    df = pd.read_csv(SAMPLE_DATA_PATH)
    return df


# ============================================================================
# 1. FEATURE ENGINEERING TESTS
# ============================================================================
class TestFeatureEngineering:
    def test_feature_engineering_columns(self, dataset):
        df_feat = engineer_features(dataset)
        for col in FEATURE_COLS:
            assert col in df_feat.columns, f"Engineered feature {col} missing"
        assert "target" in df_feat.columns, "Target column missing"

    def test_feature_engineering_no_nulls_in_features(self, dataset):
        df_feat = engineer_features(dataset)
        for col in FEATURE_COLS:
            assert df_feat[col].isna().sum() == 0, f"Nulls found in engineered feature {col}"

    def test_target_binary_distribution(self, dataset):
        df_feat = engineer_features(dataset)
        unique_targets = set(df_feat["target"].unique())
        assert unique_targets.issubset({0, 1}), f"Invalid target values: {unique_targets}"
        assert len(unique_targets) == 2, "Target must contain both 0 and 1"


# ============================================================================
# 2. SLA BREACH PREDICTOR & SHAP TESTS
# ============================================================================
class TestSLABreachPredictor:
    @pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
    def test_predictor_training_and_metrics(self, dataset):
        predictor = SLABreachPredictor()
        metrics = predictor.train(dataset, test_size=0.2, random_state=42)

        assert "roc_auc" in metrics
        assert metrics["roc_auc"] > 0.50, f"Model AUC {metrics['roc_auc']} is worse than random guessing"
        assert "report" in metrics
        assert "confusion" in metrics
        assert metrics["n_train"] == 4160
        assert metrics["n_test"] == 1040

    @pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
    def test_risk_scoring_output(self, dataset):
        predictor = SLABreachPredictor()
        predictor.train(dataset, test_size=0.2, random_state=42)
        scored = predictor.predict_dataframe(dataset.head(50))

        assert "SLA_Risk_Score" in scored.columns
        assert "SLA_Risk_Label" in scored.columns
        assert (scored["SLA_Risk_Score"] >= 0.0).all() and (scored["SLA_Risk_Score"] <= 1.0).all()
        labels = set(scored["SLA_Risk_Label"].unique())
        assert labels.issubset({"Low Risk", "Medium Risk", "High Risk"})

    @pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
    def test_shap_feature_importance(self, dataset):
        predictor = SLABreachPredictor()
        predictor.train(dataset, test_size=0.2, random_state=42)
        fi_df = predictor.get_feature_importance_df()

        assert not fi_df.empty
        assert "Feature" in fi_df.columns
        assert "Mean_SHAP" in fi_df.columns
        assert (fi_df["Mean_SHAP"] >= 0).all()
        # Ensure top feature has positive importance
        assert fi_df["Mean_SHAP"].iloc[0] > 0


# ============================================================================
# 3. ANOMALY DETECTION TESTS
# ============================================================================
class TestAnomalyDetection:
    @pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
    def test_anomaly_detector_execution(self, dataset):
        detector = DeliveryAnomalyDetector(contamination=0.05)
        df_anom = detector.fit_predict(dataset)

        assert "Anomaly_Score" in df_anom.columns
        assert "Is_Anomaly" in df_anom.columns
        assert "Anomaly_Rank" in df_anom.columns

        # Contamination = 5% of 5,200 = 260 anomalies
        anomaly_count = df_anom["Is_Anomaly"].sum()
        assert 240 <= anomaly_count <= 280, f"Expected ~260 anomalies, got {anomaly_count}"

    @pytest.mark.skipif(not ML_AVAILABLE, reason="ML dependencies not installed")
    def test_anomaly_rank_bounds(self, dataset):
        detector = DeliveryAnomalyDetector(contamination=0.05)
        df_anom = detector.fit_predict(dataset)
        assert df_anom["Anomaly_Rank"].min() >= 0.0
        assert df_anom["Anomaly_Rank"].max() <= 100.0


# ============================================================================
# 4. DEMAND FORECASTING TESTS
# ============================================================================
class TestDemandForecaster:
    def test_forecast_generation(self, dataset):
        forecaster = DeliveryDemandForecaster()
        fc = forecaster.forecast(dataset, periods=6)

        if forecaster.available:
            assert len(fc) == 6, f"Expected 6 forecast rows, got {len(fc)}"
            assert "Month" in fc.columns
            assert "Forecasted_Orders" in fc.columns
            assert "Lower_80" in fc.columns
            assert "Upper_80" in fc.columns
            assert (fc["Forecasted_Orders"] > 0).all()
            assert (fc["Upper_80"] >= fc["Lower_80"]).all()


# ============================================================================
# 5. NLP INSIGHT SUMMARIZER TESTS
# ============================================================================
class TestInsightSummarizer:
    def test_summarizer_structure(self, dataset):
        summarizer = InsightSummarizer()
        insights = summarizer.summarize(dataset)

        expected_keys = [
            "executive_summary",
            "sla_risk",
            "root_cause",
            "city_risk",
            "vendor_highlight",
            "action_items"
        ]
        for key in expected_keys:
            assert key in insights, f"Missing insight section: {key}"
            assert len(insights[key]) > 20, f"Insight {key} is suspiciously short"

    def test_summarizer_empty_cohort_handling(self):
        summarizer = InsightSummarizer()
        empty_df = pd.DataFrame()
        result = summarizer.summarize(empty_df)
        assert "error" in result


# ============================================================================
# 6. READ-ONLY AI SQL COPILOT & FASTAPI ENDPOINT TESTS
# ============================================================================
class TestReadOnlySQLCopilotAndAPI:
    def test_readonly_sql_validator_allows_select_and_cte(self):
        ok1, _ = ReadOnlySQLCopilot.validate_readonly_sql("SELECT * FROM deliveries LIMIT 5;")
        ok2, _ = ReadOnlySQLCopilot.validate_readonly_sql("WITH cte AS (SELECT * FROM cities) SELECT * FROM cte;")
        assert ok1 is True
        assert ok2 is True

    def test_readonly_sql_validator_blocks_ddl_dml_and_chaining(self):
        for bad_sql in [
            "DROP TABLE deliveries;",
            "DELETE FROM deliveries WHERE order_id = 'ORD0001';",
            "UPDATE deliveries SET delay_days = 0;",
            "SELECT * FROM cities; DROP TABLE cities;",
            "PRAGMA table_info(deliveries);",
        ]:
            ok, msg = ReadOnlySQLCopilot.validate_readonly_sql(bad_sql)
            assert ok is False, f"Expected guardrail to block: {bad_sql}"
            assert len(msg) > 5

    def test_copilot_ask_executes_against_sqlite_readonly(self):
        db_path = BASE_DIR / "data" / "last_mile_delivery.db"
        res = ReadOnlySQLCopilot.ask(db_path, "Which delivery zones have the highest SLA breach rate?")
        assert res["valid"] is True
        assert res["row_count"] == 5
        assert "SLA_Breach_Rate_Pct" in res["columns"]

    @pytest.mark.parametrize("intent", ReadOnlySQLCopilot.CURATED_INTENTS, ids=[i["id"] for i in ReadOnlySQLCopilot.CURATED_INTENTS])
    def test_all_7_curated_copilot_intents_execute_cleanly(self, intent):
        db_path = BASE_DIR / "data" / "last_mile_delivery.db"
        res = ReadOnlySQLCopilot.execute_safe_query(db_path, intent["sql"])
        assert res["valid"] is True, f"Intent {intent['id']} failed: {res['status_message']}"
        assert res["row_count"] > 0

    def test_fastapi_endpoints(self):
        from fastapi.testclient import TestClient
        from api_server import app

        client = TestClient(app)
        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["author"] == "Mohammed Zaidaan Shiraz"
        assert r_health.json()["records_loaded"] == 5200

        r_dash = client.get("/api/dashboard?zone=West&rebalance_pct=20")
        assert r_dash.status_code == 200
        assert r_dash.json()["kpis"]["total_orders"] > 0

        r_dq = client.get("/api/data-quality")
        assert r_dq.status_code == 200
        assert r_dq.json()["summary"]["delayed_date_mismatches_252"] == 252
        assert r_dq.json()["summary"]["sla_rule_mismatches_99"] == 99
        assert r_dq.json()["summary"]["missing_delay_reasons_233"] == 233

        r_cop = client.post("/api/copilot/ask", json={"question": "Show data quality audit", "custom_sql": "DROP TABLE deliveries;"})
        assert r_cop.status_code == 200
        assert r_cop.json()["valid"] is False


