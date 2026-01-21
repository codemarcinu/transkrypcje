import sys
import os
import unittest

# Dodaj src do path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.writer import ReportWriter

class TestWriterRobustness(unittest.TestCase):
    def setUp(self):
        self.writer = ReportWriter()

    def test_invalid_input_string(self):
        """Test with a string instead of a list."""
        with self.assertRaises(ValueError) as cm:
            self.writer.generate_chapter("Test", "not a list")
        self.assertIn("Dane wejściowe do ReportWriter muszą być listą obiektów JSON", str(cm.exception))

    def test_invalid_input_dict(self):
        """Test with a dict (like a raw transcript) instead of a list."""
        with self.assertRaises(ValueError) as cm:
            self.writer.generate_chapter("Test", {"language": "pl", "segments": []})
        self.assertIn("Dane wejściowe do ReportWriter muszą być listą obiektów JSON", str(cm.exception))

    def test_list_of_strings(self):
        """Test with a list of strings instead of list of dicts."""
        with self.assertRaises(ValueError) as cm:
            self.writer.generate_chapter("Test", ["string1", "string2"])
        self.assertIn("Dane wejściowe do ReportWriter muszą być listą obiektów JSON", str(cm.exception))

    def test_empty_list(self):
        """Empty list should be valid (technically) but result in minimal output."""
        # Mocking LLM engine to avoid actual API calls
        from unittest.mock import MagicMock
        self.writer.llm.generate = MagicMock(return_value="Treść")
        
        result = self.writer.generate_chapter("Test", [])
        self.assertIn("Treść", result)
        self.assertNotIn("Indeks Źródłowy", result) # Should be suppressed if empty

if __name__ == '__main__':
    unittest.main()
