import logging
import gc
import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from sklearn.cluster import HDBSCAN
from sklearn.metrics import silhouette_score

# Configuración de Logging
logger = logging.getLogger(__name__)

@dataclass
class ClusteringResult:
    """Estructura de retorno estandarizada para el proceso de clustering."""
    tenant_id: str
    total_samples: int
    num_clusters: int
    noise_count: int
    labels: List[int]
    silhouette_score: float
    cluster_distribution: Dict[int, int] = field(default_factory=dict)
    
    @property
    def is_successful(self) -> bool:
        return self.num_clusters > 0

class ClusterEngine:
    """
    Motor de agrupamiento no supervisado basado en HDBSCAN.
    Diseñado para descubrir patrones (plantillas) en vectores de documentos.
    
    Características:
    - Aislamiento por Tenant (Validación estricta).
    - Optimización de memoria (Garbage Collection explícito).
    - Cálculo de métricas de calidad (Silhouette Score).
    """

    # Configuración por defecto de HDBSCAN para documentos de texto
    DEFAULT_MIN_CLUSTER_SIZE = 3  # Detectar grupos pequeños (ej. actas raras)
    DEFAULT_MIN_SAMPLES = 2       # Sensibilidad al ruido (más bajo = menos conservador)
    METRIC = 'euclidean'          # Asumiendo vectores normalizados (equivale a cosine)

    def __init__(self):
        pass

    def _validate_inputs(self, vectors: np.ndarray, tenant_id: str):
        """Validaciones de seguridad y estructura."""
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("Violación de Seguridad: 'tenant_id' es obligatorio para el aislamiento.")
        
        if vectors is None or len(vectors) == 0:
            logger.warning(f"Tenant {tenant_id}: Dataset de vectores vacío.")
            return False
            
        return True

    def _calculate_quality_metrics(self, vectors: np.ndarray, labels: np.ndarray) -> float:
        """
        Calcula el Silhouette Score. 
        Si N > 10,000, usa sampling para evitar bloqueo de CPU O(N^2).
        """
        n_samples = len(vectors)
        unique_labels = set(labels)
        
        # Silhouette no se puede calcular si hay < 2 clusters o solo ruido (-1)
        if len(unique_labels - {-1}) < 1:
            return 0.0

        try:
            # Sampling para datasets grandes
            if n_samples > 10000:
                sample_size = 10000
                return silhouette_score(vectors, labels, metric=self.METRIC, sample_size=sample_size)
            else:
                return silhouette_score(vectors, labels, metric=self.METRIC)
        except Exception as e:
            logger.error(f"Error calculando Silhouette Score: {e}")
            return 0.0

    def perform_clustering(
        self, 
        vectors: List[List[float]], 
        tenant_id: str, 
        **kwargs
    ) -> ClusteringResult:
        """
        Ejecuta el pipeline de clustering.

        Args:
            vectors: Lista de vectores (embeddings).
            tenant_id: ID del inquilino para contexto de seguridad.
            **kwargs: Overrides para hiperparámetros de HDBSCAN.

        Returns:
            ClusteringResult con etiquetas y métricas.
        """
        # 1. Conversión y Validación
        # Convertimos a numpy array para eficiencia
        np_vectors = np.array(vectors)

        if not self._validate_inputs(np_vectors, tenant_id):
            return ClusteringResult(
                tenant_id=tenant_id, total_samples=0, num_clusters=0,
                noise_count=0, labels=[], silhouette_score=0.0
            )

        n_samples = len(np_vectors)
        
        # Configuración de Hiperparámetros
        min_cluster_size = kwargs.get('min_cluster_size', self.DEFAULT_MIN_CLUSTER_SIZE)
        min_samples = kwargs.get('min_samples', self.DEFAULT_MIN_SAMPLES)

        # 2. Manejo de Casos Borde (Pocos datos)
        if n_samples < min_cluster_size:
            logger.info(f"Tenant {tenant_id}: Insuficientes datos ({n_samples}) para clustering. Retornando ruido.")
            return ClusteringResult(
                tenant_id=tenant_id,
                total_samples=n_samples,
                num_clusters=0,
                noise_count=n_samples,
                labels=[-1] * n_samples,
                silhouette_score=0.0
            )

        try:
            # 3. Ejecución de HDBSCAN
            logger.info(f"Tenant {tenant_id}: Ejecutando HDBSCAN sobre {n_samples} vectores.")
            
            clusterer = HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                metric=self.METRIC,
                cluster_selection_method='eom' # Excess of Mass (bueno para clusters variables)
            )
            
            labels = clusterer.fit_predict(np_vectors)
            
            # 4. Post-Procesamiento
            unique_labels = set(labels)
            # El label -1 es ruido en HDBSCAN
            n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
            n_noise = list(labels).count(-1)
            
            # Distribución
            distribution = {
                int(lbl): int(np.sum(labels == lbl)) 
                for lbl in unique_labels
            }

            # 5. Métricas de Calidad
            score = self._calculate_quality_metrics(np_vectors, labels)

            logger.info(
                f"Tenant {tenant_id}: Clustering completado. "
                f"Clusters: {n_clusters}, Ruido: {n_noise}, Score: {score:.3f}"
            )

            return ClusteringResult(
                tenant_id=tenant_id,
                total_samples=n_samples,
                num_clusters=n_clusters,
                noise_count=n_noise,
                labels=labels.tolist(),
                silhouette_score=score,
                cluster_distribution=distribution
            )

        except Exception as e:
            logger.error(f"Tenant {tenant_id}: Error crítico en clustering: {e}")
            raise
        
        finally:
            # 6. Gestión de Memoria Explícita
            # HDBSCAN puede generar árboles de distancia grandes en memoria
            if 'clusterer' in locals():
                del clusterer
            # Forzar recolección de basura para limpiar estructuras numpy temporales
            gc.collect()