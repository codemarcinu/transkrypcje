
import os
import sys
import unittest
import shutil
from src.utils.config import DATA_RAW, DATA_PROCESSED, DATA_OUTPUT
from main_pipeline import run_pipeline

class TestSystemSmall(unittest.TestCase):
    def setUp(self):
        self.test_filename = "test_dummy.txt"
        self.raw_path = os.path.join(DATA_RAW, self.test_filename)
        
        # Ensure directories exist
        os.makedirs(DATA_RAW, exist_ok=True)
        os.makedirs(DATA_PROCESSED, exist_ok=True)
        os.makedirs(DATA_OUTPUT, exist_ok=True)
        
        # Create a dummy file with some OSINT content
        with open(self.raw_path, "w", encoding="utf-8") as f:
            f.write("Dzień dobry. Witam na szkoleniu z OSINT.\n")
            f.write("Dzisiaj omówimy narzędzie o nazwie Maltego.\n")
            f.write("Maltego służy do wizualizacji powiązań.\n")
            f.write("Kolejnym narzędziem jest SpiderFoot, który automatyzuje zbieranie danych.\n")
            f.write("Pamiętajcie o OPSEC - zawsze używajcie VPN.\n")
            f.write("To tyle na wstęp. Dziękuję.\n")

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.raw_path):
            os.remove(self.raw_path)
        
        # Clean up processed files (optional, maybe we want to inspect them)
        processed_kb = os.path.join(DATA_PROCESSED, f"{self.test_filename}_kb.json")
        if os.path.exists(processed_kb):
            os.remove(processed_kb)

        # Output file
        output_md = os.path.join(DATA_OUTPUT, f"Podrecznik_{self.test_filename.replace('.txt', '.md')}")
        # if os.path.exists(output_md):
        #     os.remove(output_md)

    def test_pipeline_execution(self):
        """Test that the pipeline runs through without errors on a small file."""
        print(f"\n[TEST] Running pipeline on {self.test_filename}...")
        try:
            run_pipeline(self.test_filename)
            pass
        except Exception as e:
            self.fail(f"Pipeline failed with exception: {e}")
        
        # Verify output exists
        output_md = os.path.join(DATA_OUTPUT, f"Podrecznik_{self.test_filename.replace('.txt', '.md')}")
        self.assertTrue(os.path.exists(output_md), "Output markdown file should exist")
        
        # Verify content has some length
        with open(output_md, "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"\n[TEST] Generated content length: {len(content)}")
        self.assertGreater(len(content), 0, "Output file should not be empty")
        self.assertIn("Narzędzi", content, "Output should mention tools")

if __name__ == "__main__":
    unittest.main()
