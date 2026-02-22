import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os
import torch
from sentence_transformers import util

# Ajustar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.mining.aligner import SemanticAligner, AlignerConfig
from src.config import settings

class TestGlobalAligner(unittest.TestCase):
    
    def setUp(self):
        self.aligner = SemanticAligner(config=AlignerConfig(threshold=0.5))
        self.aligner.embedder = MagicMock()
        
    def test_batching_efficiency(self):
        """
        DoD: Ningún loop debe llamar iterativamente a embed_batch().
        Debe haber exactamente 2 llamadas independientemente de cuántos nodos haya.
        """
        def mock_embed_batch(texts):
            return torch.tensor([[1.0] * 768 for _ in texts], dtype=torch.float32)

        self.aligner.embedder.embed_batch.side_effect = mock_embed_batch

        # 5 Nodos XML y 10 segmentos de audio
        xml_nodes = [{"text": f"XML Node {i}"} for i in range(5)]
        transcript = [{"text": f"Segment {i}", "start": i*10, "end": (i+1)*10} for i in range(10)]

        self.aligner.align(transcript, xml_nodes)

        # ASERCIÓN VITAL: Solo debe llamarse 2 veces (Una para XMLs, otra para todos los candidatos)
        self.assertEqual(self.aligner.embedder.embed_batch.call_count, 2)

    def test_chronological_pathfinding(self):
        """
        DoD: El algoritmo NUNCA asocia a un nodo XML un fragmento de audio 
        que viaje hacia atrás en el tiempo más allá de la tolerancia.
        """
        # En este escenario, configuramos la tolerancia temporal
        # self.aligner.time_tolerance = 5.0  # Atributo deprecado en la nueva arquitectura DP
        
        # 2 Nodos XML
        xml_nodes = [
            {"text": "Apertura de sesión", "xml": "<xml>apertura</xml>"},
            {"text": "Cierre de sesión", "xml": "<xml>cierre</xml>"}
        ]
        
        # 3 Segmentos de audio
        # 0: Inicio real (0s)
        # 1: Final real (100s)
        # 2: Mención tardía falsa de "Cierre" que ocurre ANTES de la apertura (alguien que se equivocó al minuto 10s)
        transcript = [
            {"text": "Iniciamos la sesión", "start": 50.0, "end": 60.0},
            {"text": "Damos por terminada", "start": 100.0, "end": 110.0},
            {"text": "Cierre previo falso", "start": 10.0, "end": 20.0}
        ]

        # Vamos a inyectar una matriz de similitud (simulando la salida de cos_sim)
        # Final scores shape = (N_XML, M_Candidates)
        # Necesitamos simular los candidatos generados. 
        # Con max_lookahead=40, generará muchos candidatos.
        # Simplifiquemos el test mockeando cos_sim para que coincida con la lógica
        
        def mock_cos_sim(a, b):
            # i: xml nodes (2), j: candidates (muchos)
            # Queremos que para XML[0], el candidato con Audio[0] gane
            # Queremos que para XML[1], el candidato con Audio[2] tenga score 1.0, 
            # pero el candidato con Audio[1] sea el elegido por cronología.
            
            # Identificar candidatos por su texto para el mock
            res = torch.zeros((a.shape[0], b.shape[0]))
            
            # Buscamos índices de candidatos específicos para el test
            # Esto es frágil si cambia la generación de candidatos, pero sirve para validar la lógica de pathfinding
            
            return res

        # Es más fácil mockear return_value con una matriz calculada a mano que cubra los candidatos clave
        # Pero el aligner genera ventanas. Vamos a interceptar el cálculo final.
        
        with patch("src.mining.aligner.util.cos_sim") as mock_cos:
            # Necesitamos saber cuántos candidatos se generan para dimensionar la matriz
            # Con 3 segmentos y lookahead=40:
            # i=0: [0], [0,1], [0,1,2] (3)
            # i=1: [1], [1,2] (2)
            # i=2: [2] (1)
            # Total = 6 candidatos
            
            # Cand 0: 50-60
            # Cand 1: 50-110
            # Cand 2: 50-20
            # Cand 3: 100-110
            # Cand 4: 100-20
            # Cand 5: 10-20
            
            # Matriz 2x6
            scores = torch.zeros((2, 6))
            # XML 0 (Apertura) -> Cand 0 (Audio 0) = 0.9
            scores[0, 0] = 0.9
            
            # XML 1 (Cierre) -> Cand 5 (Audio 2 - Falso) = 1.0
            scores[1, 5] = 1.0
            # XML 1 (Cierre) -> Cand 3 (Audio 1 - Real) = 0.8
            scores[1, 3] = 0.8
            
            mock_cos.return_value = scores
            self.aligner.embedder.embed_batch.return_value = torch.zeros((1, 768))

            pairs = self.aligner.align(transcript, xml_nodes)
            
            self.assertEqual(len(pairs), 2)
            # XML 0 -> Audio 0 (start 50.0)
            self.assertEqual(pairs[0]["metadata"]["start_time"], 50.0)
            # El XML 2 debe mapear al Audio 1 (start 100.0), IGNORANDO el Audio 2 que tenía score 1.0 
            # porque Audio 2 (start 10.0) viaja en el tiempo hacia atrás más de 5 segundos respecto a 60.0 (fin del audio anterior).
            self.assertEqual(pairs[1]["metadata"]["start_time"], 100.0)
            self.assertAlmostEqual(pairs[1]["score"], 0.8, places=1) # Usar places=1 para tolerar penalización de longitud

if __name__ == '__main__':
    unittest.main()
