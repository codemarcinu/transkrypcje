import unittest
from src.utils.text_processing import smart_split_text

class TestSmartSplitter(unittest.TestCase):
    def test_simple_split(self):
        text = "Zdanie pierwsze. " * 300
        # 300 * ~17 chars = ~5100 chars. Should fit in one chunk of 6000.
        chunks = smart_split_text(text, max_length=6000)
        self.assertEqual(len(chunks), 1)

    def test_split_with_paragraphs(self):
        para = "To jest długi akapit. " * 50
        text = f"{para}\n\n{para}\n\n{para}"
        # 3 paragraphs. If length exceeds max, it should split at \n\n if possible.
        # Let's force a split by making max_length small
        chunks = smart_split_text(text, max_length=len(para) + 10, overlap=0)
        
        # Should be at least 3 chunks
        self.assertTrue(len(chunks) >= 3)
        # Check if splits happen at newlines mostly
        # This is a heuristic check; we just want to ensure it doesn't crash and splits reasonably.

    def test_hard_limit(self):
        # Text with no separators
        text = "A" * 10000
        chunks = smart_split_text(text, max_length=6000, overlap=0)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 6000)
        self.assertEqual(len(chunks[1]), 4000)

if __name__ == '__main__':
    unittest.main()
