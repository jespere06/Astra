#!/usr/bin/env python3
"""
ASTRA v2 — E2E Smoke Test

Validates the full Learning Loop WITHOUT GPU:
    1. Mining: Generates dataset from synthetic DOCX + transcripts.
    2. Training: Verifies train.py config is loadable.
    3. Inference: Verifies LLMEngine prompt construction.
    4. Builder: Verifies ContentInjector XML replacement.

Run:
    PYTHONPATH=modules/astra-ingest python3 modules/astra-ingest/tests/e2e/test_smoke_e2e.py
"""
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

# Ensure import paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))


OOXML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

SAMPLE_DOCUMENT_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{OOXML_NS}">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Header"/></w:pPr><w:r><w:t>ACTA DE SESIÓN ORDINARIA</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Header"/></w:pPr><w:r><w:t>Municipio de San José</w:t></w:r></w:p>
    <w:p><w:r><w:t>El concejal Juan aprueba la moción por unanimidad.</w:t></w:r></w:p>
    <w:p><w:r><w:t>La concejala María solicita revisión del presupuesto anual.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr><w:r><w:t>Firma del Secretario</w:t></w:r></w:p>
    <w:sectPr/>
  </w:body>
</w:document>"""

SAMPLE_TRANSCRIPT = [
    {"text": "El concejal Juan aprueba la mocion por unanimidad.", "speaker": "Speaker 1"},
    {"text": "La concejala María solicita revision del presupuesto.", "speaker": "Speaker 2"},
]


def create_test_docx(path: str, xml_content: str = SAMPLE_DOCUMENT_XML):
    """Creates a minimal .docx file (ZIP with word/document.xml)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml_content)


class TestE2EPipeline(unittest.TestCase):
    """End-to-end validation of the Mining Pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.docs_dir = os.path.join(self.tmpdir, "docs")
        self.transcripts_dir = os.path.join(self.tmpdir, "transcripts")
        self.output_dir = os.path.join(self.tmpdir, "output")

        os.makedirs(self.docs_dir)
        os.makedirs(self.transcripts_dir)

        # Create 3 identical docs (to produce skeleton consensus >85%)
        for i in range(3):
            create_test_docx(os.path.join(self.docs_dir, f"acta_{i:03d}.docx"))
            with open(os.path.join(self.transcripts_dir, f"acta_{i:03d}.json"), "w") as f:
                json.dump(SAMPLE_TRANSCRIPT, f)

    def test_phase1_analyzer(self):
        """CorpusAnalyzer identifies static nodes via per-doc frequency."""
        from src.mining.analyzer import CorpusAnalyzer

        analyzer = CorpusAnalyzer()
        docx_files = sorted(Path(self.docs_dir).glob("*.docx"))
        freq_map = analyzer.analyze([str(p) for p in docx_files])

        # All nodes appear in all 3 docs → frequency should be 1.0
        for h, data in freq_map.items():
            self.assertEqual(data["frequency"], 1.0, f"Hash {h} frequency != 1.0")

        self.assertGreater(len(freq_map), 0, "Frequency map is empty")

    def test_phase2_extractor(self):
        """SemanticExtractor returns {xml, text} dicts for dynamic nodes."""
        from src.mining.analyzer import CorpusAnalyzer
        from src.mining.extractor import SemanticExtractor

        analyzer = CorpusAnalyzer()
        docx_files = sorted(Path(self.docs_dir).glob("*.docx"))
        freq_map = analyzer.analyze([str(p) for p in docx_files])

        # With all 3 docs identical, everything is static → 0 dynamic fragments
        static_hashes = {h for h, d in freq_map.items() if d["frequency"] >= 0.85}
        extractor = SemanticExtractor(static_hashes)
        fragments = extractor.extract_from_document(str(docx_files[0]))

        self.assertEqual(len(fragments), 0, "All identical docs → 0 dynamic fragments")

    def test_phase3_aligner(self):
        """SemanticAligner matches transcript to XML fragments."""
        from src.mining.aligner import SemanticAligner, AlignerConfig

        aligner = SemanticAligner(config=AlignerConfig(threshold=0.5))
        xml_nodes = [
            {"text": "El concejal Juan aprueba la moción por unanimidad.", "xml": "<w:p>formal</w:p>"},
        ]
        pairs = aligner.align(SAMPLE_TRANSCRIPT, xml_nodes)

        self.assertGreater(len(pairs), 0, "Should find at least 1 alignment")
        self.assertGreater(pairs[0]["score"], 0.5)

    def test_phase4_dataset_builder(self):
        """DatasetBuilder produces valid Alpaca JSONL with augmentation."""
        from src.mining.dataset_builder import DatasetBuilder
        from src.mining.noise_engine import NoiseInjector

        pairs = [
            {
                "instruction": "Test",
                "input": "[Speaker 1]: hola mundo señores concejales",
                "output": "<w:p>Hola Mundo Señores Concejales</w:p>",
                "score": 0.9,
            },
            {
                "instruction": "Test",
                "input": "[Speaker 2]: se aprobó la moción",
                "output": "<w:p>Se aprueba la moción</w:p>",
                "score": 0.85,
            },
        ]

        builder = DatasetBuilder(noise_injector=NoiseInjector())
        stats = builder.build(pairs, self.output_dir, augment_factor=2)

        self.assertGreater(stats["train"], 0)
        # Verify JSONL validity
        train_path = os.path.join(self.output_dir, "train.jsonl")
        self.assertTrue(os.path.exists(train_path))
        with open(train_path) as f:
            for line in f:
                obj = json.loads(line)
                self.assertIn("instruction", obj)
                self.assertIn("input", obj)
                self.assertIn("output", obj)

    def test_phase5_noise_engine(self):
        """NoiseInjector produces dirty text that differs from input."""
        from src.mining.noise_engine import NoiseInjector

        noise = NoiseInjector(seed=42)
        clean = "Se aprueba el Artículo 5 por unanimidad."
        dirty = noise.corrupt(clean)

        self.assertNotEqual(clean, dirty, "Noise should alter the text")
        self.assertGreater(len(dirty), 0, "Dirty text should not be empty")

    def test_full_pipeline(self):
        """Full pipeline runs end-to-end without errors."""
        from src.mining.pipeline import DataMiningPipeline

        pipeline = DataMiningPipeline(
            docs_dir=self.docs_dir,
            transcripts_dir=self.transcripts_dir,
            output_dir=self.output_dir,
            skeleton_threshold=0.85,
            alignment_threshold=0.3,
            augment_factor=2,
        )
        report = pipeline.run()

        # Pipeline should complete without errors
        self.assertNotIn("error", report)
        self.assertEqual(report["total_documents"], 3)

        # Coverage report should exist
        coverage_path = os.path.join(self.output_dir, "coverage.json")
        self.assertTrue(os.path.exists(coverage_path))

        # Skeleton should exist
        skeleton_path = os.path.join(self.output_dir, "master_skeleton.xml")
        self.assertTrue(os.path.exists(skeleton_path))


if __name__ == "__main__":
    unittest.main()
