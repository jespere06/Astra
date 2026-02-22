import unittest
import sys
import os

# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.mining.aligner import SemanticAligner, AlignerConfig


class TestSemanticAligner(unittest.TestCase):

    def test_align_exact_match(self):
        aligner = SemanticAligner(config=AlignerConfig(threshold=0.8))

        transcript = [
            {"text": "Hello world this is a test.", "speaker": "Speaker 1", "start": 0.0, "end": 5.0}
        ]
        xml_blocks = [
            {"text": "Other text content here.", "xml": "<w:p>Other</w:p>", "id": "p1"},
            {"text": "Hello world this is a test.", "xml": "<w:p>Hello world this is a test.</w:p>", "id": "p2"},
        ]

        pairs = aligner.align(transcript, xml_blocks)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["output"], "<w:p>Hello world this is a test.</w:p>")
        self.assertIn("[Speaker 1]: Hello world this is a test.", pairs[0]["input"])
        self.assertGreaterEqual(pairs[0]["score"], 0.99)

    def test_align_fuzzy_match(self):
        aligner = SemanticAligner(config=AlignerConfig(threshold=0.5))

        transcript = [{"text": "Hello world it is um a test.", "speaker": "Speaker 1"}]
        xml_blocks = [{"text": "Hello world it is a test.", "xml": "<w:p>Clean</w:p>", "id": "p1"}]

        pairs = aligner.align(transcript, xml_blocks)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["output"], "<w:p>Clean</w:p>")
        self.assertGreater(pairs[0]["score"], 0.5)

    def test_no_match(self):
        aligner = SemanticAligner(config=AlignerConfig(threshold=0.9))

        transcript = [{"text": "Completely different content.", "speaker": "Speaker 1"}]
        xml_blocks = [{"text": "Hello world test document.", "xml": "<w:p>Hi</w:p>", "id": "p1"}]

        pairs = aligner.align(transcript, xml_blocks)
        self.assertEqual(len(pairs), 0)

    def test_empty_inputs(self):
        aligner = SemanticAligner()
        self.assertEqual(aligner.align([], []), [])
        self.assertEqual(aligner.align([{"text": "hi"}], []), [])
        self.assertEqual(aligner.align([], [{"text": "hi", "xml": "<w:p/>"}]), [])


if __name__ == "__main__":
    unittest.main()
