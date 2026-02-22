import unittest
import shutil
import tempfile
import json
import os
from pathlib import Path

# Ajustar path si es necesario según estructura de ejecución de tests
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.dataset_builder import DatasetBuilder

class TestDatasetBuilderLeakage(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.builder = DatasetBuilder()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_mock_pairs(self, num_docs=10, pairs_per_doc=5):
        """Genera datos sintéticos con doc_id en metadata."""
        pairs = []
        for i in range(num_docs):
            doc_id = f"acta_municipal_{i}.docx"
            for j in range(pairs_per_doc):
                pairs.append({
                    "input": f"Contenido audio {j} del doc {i}",
                    "output": f"<xml>Contenido {j}</xml>",
                    "score": 0.95,
                    "metadata": {
                        "source_doc_id": doc_id,
                        "timestamp": j
                    }
                })
        return pairs

    def test_data_leakage_prevention(self):
        """
        DTM Requisito: 0% de fuga de datos.
        La intersección de Document IDs entre train y val debe ser vacía.
        """
        # Generar 10 documentos con 10 fragmentos cada uno (100 total)
        pairs = self._create_mock_pairs(num_docs=10, pairs_per_doc=10)
        
        # Build con 80/20 split
        stats = self.builder.build(
            pairs, 
            self.test_dir, 
            train_ratio=0.8, 
            seed=123 # Seed fija para reproducibilidad
        )

        # 1. Verificar conteos de documentos
        self.assertEqual(stats['train_docs'], 8)
        self.assertEqual(stats['val_docs'], 2)
        
        # 2. Leer archivos generados
        train_ids = set()
        val_ids = set()

        with open(os.path.join(self.test_dir, "train.jsonl"), 'r') as f:
            for line in f:
                data = json.loads(line)
                doc_id = data['metadata']['source_doc_id']
                train_ids.add(doc_id)

        with open(os.path.join(self.test_dir, "val.jsonl"), 'r') as f:
            for line in f:
                data = json.loads(line)
                doc_id = data['metadata']['source_doc_id']
                val_ids.add(doc_id)

        # 3. ASERCIÓN CRÍTICA: Intersección debe ser vacía
        intersection = train_ids.intersection(val_ids)
        
        self.assertEqual(len(intersection), 0, 
            f"FATAL: Fuga de datos detectada. Docs en ambos sets: {intersection}")
        
        # Verificar que todos los docs están presentes
        self.assertEqual(len(train_ids) + len(val_ids), 10)

    def test_alpaca_format_schema(self):
        """Valida que el JSON tenga las llaves correctas."""
        pairs = self._create_mock_pairs(num_docs=1, pairs_per_doc=1)
        self.builder.build(pairs, self.test_dir)
        
        with open(os.path.join(self.test_dir, "train.jsonl"), 'r') as f:
            line = f.readline()
            data = json.loads(line)
            
            self.assertIn("instruction", data)
            self.assertIn("input", data)
            self.assertIn("output", data)
            
            # Verificar que instruction sea una de las del sistema
            self.assertIn(data["instruction"], DatasetBuilder.SYSTEM_INSTRUCTIONS)

    def test_unknown_doc_id_handling(self):
        """Si no hay doc_id, debe agrupar en 'unknown'."""
        pairs = [
            {"input": "a", "output": "b", "metadata": {}}, # Sin doc_id
            {"input": "c", "output": "d", "metadata": {"doc_id": "doc1"}}
        ]
        
        # Con 2 'documentos' (uno 'unknown' y 'doc1'), y 0.5 split,
        # uno debería ir a train y otro a val.
        stats = self.builder.build(pairs, self.test_dir, train_ratio=0.5)
        
        self.assertEqual(stats['train_docs'], 1)
        self.assertEqual(stats['val_docs'], 1)

if __name__ == '__main__':
    unittest.main()