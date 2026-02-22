import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.evaluation.metrics import MetricsEngine
from src.evaluation.evaluator import ModelEvaluator

class TestMetricsEngine:
    @pytest.fixture
    def engine(self):
        # Mockeamos sentence-transformers
        with patch("src.evaluation.metrics.SentenceTransformer") as MockST:
            # Mock encode para retornar vectores dummy
            mock_model = MagicMock()
            # Retorna tensores dummy (numpy arrays)
            mock_model.encode.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])
            MockST.return_value = mock_model
            
            # Mock util.pairwise_cos_sim
            with patch("src.evaluation.metrics.util") as mock_util:
                mock_util.pairwise_cos_sim.return_value = np.array([0.5]) # Similitud fija media
                return MetricsEngine()

    def test_xml_validation_valid(self, engine):
        valid_xml = "<w:p><w:r><w:t>Texto correcto</w:t></w:r></w:p>"
        assert engine.validate_xml_structure(valid_xml) is True

    def test_xml_validation_invalid(self, engine):
        invalid_xml = "<w:p>Tag sin cerrar"
        assert engine.validate_xml_structure(invalid_xml) is False

    def test_wer_calculation(self, engine):
        # Si jiwer está instalado usará real, sino 0.0. 
        # Asumimos entorno de test con jiwer.
        ref = ["hola mundo"]
        hyp = ["hola mundo"]
        # Mocking wer function import behavior if needed, but assuming installed
        # Un wer de 0.0 significa perfecto
        score = engine.calculate_wer(ref, hyp)
        assert score == 0.0

        ref_bad = ["hola mundo"]
        hyp_bad = ["adiós mundo"]
        score_bad = engine.calculate_wer(ref_bad, hyp_bad)
        assert score_bad > 0.0

class TestModelEvaluatorLogic:
    @pytest.fixture
    def evaluator(self):
        # Mock dependencies
        with patch("src.evaluation.evaluator.MetricsEngine") as MockMetrics:
            eng = MockMetrics.return_value
            eng.calculate_wer.return_value = 0.1
            eng.calculate_semantic_similarity.return_value = 0.95
            eng.validate_xml_structure.return_value = True
            
            ev = ModelEvaluator()
            ev.metrics_engine = eng
            ev.s3_client = MagicMock()
            
            # Mock internal _load_model to return mocks
            mock_model = MagicMock()
            mock_tok = MagicMock()
            # Mock generate output decoding
            mock_tok.batch_decode.return_value = ["### Response:\n<w:p>Output</w:p>"]
            
            ev._load_model = MagicMock(return_value=(mock_model, mock_tok))
            
            return ev

    @patch("src.evaluation.evaluator.load_dataset")
    def test_evaluate_promotion_success(self, mock_load_data, evaluator):
        # Setup: Dataset dummy
        mock_load_data.return_value = [
            {"instruction": "i", "input": "in", "output": "out"}
        ] * 5

        # Setup: Baseline malo (fácil de superar)
        baseline = {"wer": 0.5, "semantic_similarity": 0.5}

        # Ejecutar
        result = evaluator.evaluate("path", "data.jsonl", baseline, "tenant1", "job1")

        assert result.status == "PROMOTED"
        assert not result.reasons

    @patch("src.evaluation.evaluator.load_dataset")
    def test_evaluate_rejection_xml(self, mock_load_data, evaluator):
        mock_load_data.return_value = [{"instruction": "i", "input": "in", "output": "out"}]
        
        # Simular XML inválido en todas las respuestas
        evaluator.metrics_engine.validate_xml_structure.return_value = False
        
        baseline = {"wer": 0.5} # Irrelevante si XML falla
        result = evaluator.evaluate("path", "data.jsonl", baseline, "tenant1", "job1")

        assert result.status == "REJECTED"
        assert any("Fallo estructural" in r for r in result.reasons)

    @patch("src.evaluation.evaluator.load_dataset")
    def test_evaluate_rejection_wer_regression(self, mock_load_data, evaluator):
        mock_load_data.return_value = [{"instruction": "i", "input": "in", "output": "out"}]
        
        # Simular WER alto (0.8)
        evaluator.metrics_engine.calculate_wer.return_value = 0.8
        
        # Baseline muy bueno (0.1) -> Regresión clara
        baseline = {"wer": 0.1}
        
        result = evaluator.evaluate("path", "data.jsonl", baseline, "tenant1", "job1")

        assert result.status == "REJECTED"
        assert any("Regresión WER" in r for r in result.reasons)