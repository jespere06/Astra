import pytest
import numpy as np
from sklearn.datasets import make_blobs
from src.core.analytics.cluster_engine import ClusterEngine

class TestClusterEngine:

    @pytest.fixture
    def engine(self):
        return ClusterEngine()

    def test_security_violation_missing_tenant(self, engine):
        """Debe lanzar ValueError si no se provee tenant_id."""
        vectors = np.random.rand(10, 768)
        with pytest.raises(ValueError, match="Violación de Seguridad"):
            engine.perform_clustering(vectors.tolist(), tenant_id="")
        
        with pytest.raises(ValueError, match="Violación de Seguridad"):
            engine.perform_clustering(vectors.tolist(), tenant_id=None)

    def test_empty_dataset(self, engine):
        """Debe manejar dataset vacío sin error."""
        result = engine.perform_clustering([], tenant_id="test_tenant")
        assert result.total_samples == 0
        assert result.num_clusters == 0
        assert result.is_successful is False

    def test_insufficient_samples(self, engine):
        """
        Si N < min_cluster_size, todo debe ser marcado como ruido (-1) 
        o manejado gracefully sin clusters.
        """
        vectors = np.random.rand(2, 768).tolist() # Solo 2 muestras
        result = engine.perform_clustering(
            vectors, 
            tenant_id="test_tenant", 
            min_cluster_size=5
        )
        assert result.total_samples == 2
        assert result.num_clusters == 0
        assert result.noise_count == 2
        assert all(l == -1 for l in result.labels)

    def test_clustering_logic_synthetic_data(self, engine):
        """
        Prueba E2E con datos sintéticos (Blobs).
        Generamos 3 clusters claros en 100 dimensiones.
        HDBSCAN debería encontrar 3 clusters y poco ruido.
        """
        # Generar datos sintéticos: 100 muestras, 3 centros, 50 features
        X, y_true = make_blobs(n_samples=100, centers=3, n_features=50, random_state=42, cluster_std=0.5)
        
        result = engine.perform_clustering(
            X.tolist(), 
            tenant_id="test_tenant",
            min_cluster_size=5,
            min_samples=2
        )

        # Verificaciones
        assert result.tenant_id == "test_tenant"
        assert result.total_samples == 100
        # HDBSCAN es robusto, debería encontrar los 3 clusters (o muy cerca)
        assert result.num_clusters >= 2, f"Se esperaban al menos 2 clusters, hallados {result.num_clusters}"
        
        # Verificar que el Silhouette Score es positivo (indica buena separación)
        assert result.silhouette_score > 0.5, f"Score bajo: {result.silhouette_score}"
        
        # Verificar distribución de etiquetas
        # No debe haber excesivo ruido en datos sintéticos limpios
        assert result.noise_count < 20 

    def test_memory_cleanup(self, engine):
        """
        Verificación simple de que no explota al correr múltiples veces.
        (La verificación real de GC es compleja en unit tests, esto es smoke test).
        """
        X = np.random.rand(50, 10)
        for _ in range(5):
            engine.perform_clustering(X.tolist(), tenant_id="gc_test")
        assert True