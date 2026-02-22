import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Ajustar path para importar src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.mining.aligner import SemanticAligner, AlignerConfig
from src.config import settings

class TestAlignerRegression(unittest.TestCase):
    
    def setUp(self):
        # Configuración para el test: Penalización agresiva para evidenciar el efecto
        self.original_penalty = settings.ALIGNER_LENGTH_PENALTY
        settings.ALIGNER_LENGTH_PENALTY = 0.5 
        settings.ALIGNER_MAX_LOOKAHEAD = 5
        
        self.aligner = SemanticAligner(config=AlignerConfig(threshold=0.5))
        
        # Mock del Embedder para no cargar modelos pesados
        self.aligner.embedder = MagicMock()
        
    def tearDown(self):
        # Restaurar configuración original
        settings.ALIGNER_LENGTH_PENALTY = self.original_penalty

    def test_giant_block_rejection(self):
        """
        Caso: El audio es masivamente más largo que el texto XML.
        Aunque la similitud semántica base sea alta (porque el texto está contenido en el audio),
        la penalización debe bajar el score por debajo del umbral.
        """
        # Audio candidato (simulado como concatenación de muchos segmentos)
        # 100 palabras "bla"
        audio_text = "bla " * 100 
        # XML target corto (5 palabras)
        xml_text = "bla " * 5
        
        # Simulamos que el embedder retorna vectores idénticos (Similitud base = 1.0)
        # Esto aísla la prueba para verificar SOLO la penalización de longitud
        vector_dim = 768
        mock_vector = np.ones(vector_dim)
        
        # El aligner llama a embed_batch dos veces: una para target, otra para candidatos
        self.aligner.embedder.embed_batch.side_effect = [
            [mock_vector], # Target XML
            [mock_vector]  # Candidato Audio (Ventana)
        ]

        # Datos de entrada simulados
        transcript = [{"text": "bla " * 20, "start": 0, "end": 1}] * 5 # 5 segmentos de 20 palabras = 100 palabras
        xml_nodes = [{"text": xml_text, "xml": "<p>xml</p>"}]

        # Ejecutar alineación
        pairs = self.aligner.align(transcript, xml_nodes)

        # ASERCIÓN: Debe ser rechazado (lista vacía) debido a la penalización
        # Cálculo esperado:
        # Base Score = 1.0
        # Diff Ratio = abs(100 - 5) / 100 = 0.95
        # Penalty = 0.95 * 0.5 (factor) = 0.475
        # Final Score = 1.0 - 0.475 = 0.525
        # Si el threshold es > 0.525, debería fallar. O si subimos el penalty.
        # Ajustemos el threshold del test a 0.6 para asegurar fallo
        # self.aligner.threshold = 0.6  # Deprecado en Favor de config
        self.aligner.config.threshold = 0.6
        
        self.assertEqual(len(pairs), 0, "El 'bloque gigante' no fue rechazado por penalización de longitud.")

    def test_perfect_length_match_accepted(self):
        """
        Caso: Longitudes similares. Debe ser aceptado sin penalización significativa.
        """
        text = "palabra " * 10
        mock_vector = np.ones(768)
        
        self.aligner.embedder.embed_batch.side_effect = [
            [mock_vector],
            [mock_vector]
        ]
        
        transcript = [{"text": "palabra " * 10, "start": 0, "end": 1}]
        xml_nodes = [{"text": text, "xml": "<p>ok</p>"}]

        pairs = self.aligner.align(transcript, xml_nodes)
        
        self.assertEqual(len(pairs), 1)
        # Score debe ser muy cercano a 1.0
        self.assertGreater(pairs[0]['score'], 0.9)

    def test_max_lookahead_constraint(self):
        """
        Caso: Validar que no agrupa más segmentos de los permitidos por config.
        """
        # Configurar lookahead
        # self.aligner.max_lookahead = 2 # Deprecado
        
        # 4 segmentos disponibles
        transcript = [{"text": "seg", "start": i, "end": i+1} for i in range(4)]
        xml_nodes = [{"text": "target", "xml": "<p>t</p>"}]
        
        # Mockear embeddings: el aligner llamará embed_batch con los candidatos.
        # Con lookahead=2, debería generar 2 candidatos: "seg", "seg seg".
        # NO debería generar "seg seg seg".
        
        def side_effect(texts):
            # Verificar que ningún candidato tenga más de 2 'seg'
            for t in texts:
                if t.strip().count("seg") > 2:
                    raise ValueError(f"Lookahead violado! Candidato generado: {t}")
            return [np.ones(768) for _ in texts]

        self.aligner.embedder.embed_batch.side_effect = side_effect
        
        try:
            self.aligner.align(transcript, xml_nodes)
        except ValueError as e:
            self.fail(str(e))

if __name__ == '__main__':
    unittest.main()