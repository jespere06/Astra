import unittest
import json
import os
import shutil
import sys

# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.ml.data.formatter import DatasetFormatter

class TestDatasetFormatter(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = "tests/temp_data"
        os.makedirs(self.test_dir, exist_ok=True)
        self.output_path = os.path.join(self.test_dir, "test.jsonl")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_format_as_alpaca(self):
        pairs = [
            {"input": "Input 1", "output": "Output 1"},
            {"input": "Input 2", "output": "Output 2"}
        ]
        
        DatasetFormatter.format_as_alpaca(pairs, self.output_path)
        
        # Verify file existence
        self.assertTrue(os.path.exists(self.output_path))
        
        # Verify content
        with open(self.output_path, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 2)
            
            data1 = json.loads(lines[0])
            self.assertEqual(data1["input"], "Input 1")
            self.assertEqual(data1["output"], "Output 1")
            self.assertEqual(data1["instruction"], DatasetFormatter.SYSTEM_INSTRUCTION)

    def test_split_train_val(self):
        pairs = [{"id": i} for i in range(10)]
        train, val = DatasetFormatter.split_train_val(pairs, train_ratio=0.8)
        
        self.assertEqual(len(train), 8)
        self.assertEqual(len(val), 2)

if __name__ == '__main__':
    unittest.main()
