"""
CloudPulse AI - ML Service
Unit tests for ML models and services.
"""
import pytest
import numpy as np
from datetime import datetime
from decimal import Decimal

from app.core.config import get_settings


class TestMLSettings:
    """Tests for ML Service Settings."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = get_settings()
        assert settings.app_name == "CloudPulse AI - ML Service"
        assert settings.forecast_days == 30
        assert settings.anomaly_sensitivity == "medium"
    
    def test_prediction_confidence_threshold(self):
        """Test prediction confidence threshold."""
        settings = get_settings()
        assert 0 <= settings.prediction_confidence_threshold <= 1
    
    def test_min_samples_for_training(self):
        """Test minimum samples requirement."""
        settings = get_settings()
        assert settings.min_samples_for_training >= 10


class TestCostPredictor:
    """Tests for Cost Predictor service (Amazon Chronos)."""
    
    def test_predictor_initialization(self):
        """Test predictor initializes correctly."""
        from app.services.cost_predictor import CostPredictor
        
        predictor = CostPredictor()
        assert predictor.pipeline is None  # Lazy loaded
        assert predictor.device in ["cuda", "cpu"]
        assert "chronos" in predictor.model_name.lower()
    
    def test_prepare_data_with_date_column(self):
        """Test data preparation returns a numeric context array."""
        from app.services.cost_predictor import CostPredictor
        
        predictor = CostPredictor()
        test_data = [
            {"date": datetime(2026, 1, 1), "amount": 100},
            {"date": datetime(2026, 1, 2), "amount": 150},
            {"date": datetime(2026, 1, 3), "amount": 120},
        ]
        
        tensor = predictor.prepare_data(test_data)
        
        assert hasattr(tensor, "__len__")
        assert hasattr(tensor, "dtype")
        assert len(tensor) >= 3
    
    def test_prepare_data_fills_missing_dates(self):
        """Test that missing dates are filled with zeros."""
        from app.services.cost_predictor import CostPredictor
        
        predictor = CostPredictor()
        test_data = [
            {"date": datetime(2026, 1, 1), "amount": 100},
            {"date": datetime(2026, 1, 5), "amount": 150},  # Gap of 3 days
        ]
        
        tensor = predictor.prepare_data(test_data)
        
        # Should have 5 days (Jan 1-5)
        assert len(tensor) == 5
    
    def test_prepare_data_missing_columns(self):
        """Test data preparation fails with missing columns."""
        from app.services.cost_predictor import CostPredictor
        import pytest
        
        predictor = CostPredictor()
        test_data = [{"invalid": 100}]
        
        with pytest.raises(ValueError, match="date.*amount"):
            predictor.prepare_data(test_data)
    
    def test_train_insufficient_data(self):
        """Test training fails with insufficient data."""
        from app.services.cost_predictor import CostPredictor
        
        predictor = CostPredictor()
        test_data = [
            {"date": datetime(2026, 1, 1), "amount": 100},
            {"date": datetime(2026, 1, 2), "amount": 150},
        ]
        
        result = predictor.train(test_data)
        
        assert result["success"] is False
        assert "Insufficient" in result.get("error", "")
    
    @pytest.mark.asyncio
    async def test_predict_without_context(self):
        """Test prediction requires cost_data context for Chronos."""
        from app.services.cost_predictor import CostPredictor
        
        predictor = CostPredictor()
        result = await predictor.predict(days=7)  # No cost_data provided
        
        assert result["success"] is False
        assert "context" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_predict_supports_installed_pipeline_signature(self, monkeypatch: pytest.MonkeyPatch):
        """Prediction should support Chronos versions that use `inputs=`."""
        from app.services.cost_predictor import CostPredictor
        import app.services.cost_predictor as predictor_module

        class FakeTensor:
            def __init__(self, values):
                self.values = np.array(values, dtype=np.float32)

            def numpy(self):
                return self.values

            def __getitem__(self, index):
                return FakeTensor(self.values[index])

        class FakeTorch:
            class cuda:
                @staticmethod
                def is_available():
                    return False

            float32 = "float32"

            @staticmethod
            def tensor(values, dtype=None):
                del dtype
                return FakeTensor(values)

            @staticmethod
            def median(tensor, dim=0):
                class Result:
                    values = FakeTensor(np.median(tensor.values, axis=dim))

                return Result()

            @staticmethod
            def quantile(tensor, q, dim=0):
                return FakeTensor(np.quantile(tensor.values, q, axis=dim))

        class FakePipeline:
            def predict(self, inputs=None, prediction_length=None, num_samples=None, **kwargs):
                assert kwargs == {}
                assert inputs is not None
                assert prediction_length == 3
                assert num_samples == 20
                return FakeTensor(
                    [[[101.0, 102.0, 103.0], [111.0, 112.0, 113.0], [121.0, 122.0, 123.0]]]
                )

        monkeypatch.setattr(predictor_module, "_get_torch", lambda: FakeTorch())

        predictor = CostPredictor()
        predictor.pipeline = FakePipeline()

        result = await predictor.predict(
            days=3,
            cost_data=[
                {"date": "2026-01-01", "amount": 100.0},
                {"date": "2026-01-02", "amount": 120.0},
                {"date": "2026-01-03", "amount": 140.0},
            ],
        )

        assert result["success"] is True
        assert len(result["predictions"]) == 3
        assert result["predictions"][0]["predicted_cost"] == 111.0
    
    def test_get_predictor_singleton(self):
        """Test get_predictor returns same instance."""
        from app.services.cost_predictor import get_predictor
        
        predictor1 = get_predictor()
        predictor2 = get_predictor()
        
        assert predictor1 is predictor2
    
    def test_get_trend_components(self):
        """Test trend components returns note about FM limitations."""
        from app.services.cost_predictor import CostPredictor
        
        predictor = CostPredictor()
        result = predictor.get_trend_components()
        
        assert "note" in result


class TestAnomalyDetector:
    """Tests for Anomaly Detector service."""
    
    def test_detector_initialization(self):
        """Test detector initializes correctly."""
        from app.services.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        assert detector.model is None
        assert detector.scaler is None
        assert detector.is_fitted is False
    
    def test_sensitivity_map(self):
        """Test sensitivity levels are defined."""
        from app.services.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        
        assert "low" in detector.SENSITIVITY_MAP
        assert "medium" in detector.SENSITIVITY_MAP
        assert "high" in detector.SENSITIVITY_MAP
        
        assert detector.SENSITIVITY_MAP["low"] < detector.SENSITIVITY_MAP["medium"]
        assert detector.SENSITIVITY_MAP["medium"] < detector.SENSITIVITY_MAP["high"]
    
    def test_prepare_features(self):
        """Test feature preparation."""
        from app.services.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        test_data = [
            {"date": datetime(2026, 1, i), "amount": 100 + i * 10}
            for i in range(1, 31)
        ]
        
        df = detector.prepare_features(test_data)
        
        assert "day_of_week" in df.columns
        assert "day_of_month" in df.columns
        assert "is_weekend" in df.columns
        assert "cost_change" in df.columns
        assert "rolling_mean_7d" in df.columns
    
    def test_train_insufficient_data(self):
        """Test training fails with insufficient data."""
        from app.services.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        test_data = [
            {"date": datetime(2026, 1, 1), "amount": 100},
        ]
        
        result = detector.train(test_data)
        
        assert result["success"] is False
    
    def test_detect_without_training(self):
        """Test detection returns error without training."""
        from app.services.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        test_data = [{"date": datetime(2026, 1, 1), "amount": 100}]
        
        result = detector.detect(test_data)
        
        assert result["success"] is False
    
    def test_detect_single_without_training(self):
        """Test single detection handles untrained state."""
        from app.services.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector()
        result = detector.detect_single({"date": datetime.now(), "amount": 100})
        
        assert result["is_anomaly"] is False
        assert "error" in result
    
    def test_get_detector_singleton(self):
        """Test get_detector returns same instance."""
        from app.services.anomaly_detector import get_detector
        
        detector1 = get_detector()
        detector2 = get_detector()
        
        assert detector1 is detector2


class TestMLSchemas:
    """Tests for ML service schemas."""
    
    def test_cost_data_point_schema(self):
        """Test CostDataPoint schema."""
        from app.models.schemas import CostDataPoint
        
        point = CostDataPoint(
            date=datetime.now(),
            amount=Decimal("123.45"),
            service="EC2",
        )
        assert point.amount == Decimal("123.45")
    
    def test_train_request_schema(self):
        """Test TrainRequest schema."""
        from app.models.schemas import TrainRequest, CostDataPoint
        
        request = TrainRequest(
            cost_data=[
                CostDataPoint(date=datetime.now(), amount=Decimal("100")),
            ],
            retrain=True,
        )
        assert len(request.cost_data) == 1
        assert request.retrain is True
    
    def test_predict_request_defaults(self):
        """Test PredictRequest default values."""
        from app.models.schemas import CostDataPoint, PredictRequest
        
        request = PredictRequest(
            cost_data=[CostDataPoint(date=datetime.now(), amount=Decimal("100"))]
        )
        assert request.days == 30
        assert request.include_history is False
    
    def test_prediction_point_schema(self):
        """Test PredictionPoint schema."""
        from app.models.schemas import PredictionPoint
        
        point = PredictionPoint(
            date="2026-01-15",
            predicted_cost=500.0,
            lower_bound=400.0,
            upper_bound=600.0,
        )
        assert point.predicted_cost == 500.0
    
    def test_anomaly_record_schema(self):
        """Test AnomalyRecord schema."""
        from app.models.schemas import AnomalyRecord
        
        record = AnomalyRecord(
            date="2026-01-10",
            actual_cost=200.0,
            expected_cost=100.0,
            deviation_percent=100.0,
            severity="high",
            anomaly_score=-0.5,
        )
        assert record.severity == "high"
        assert record.deviation_percent == 100.0
