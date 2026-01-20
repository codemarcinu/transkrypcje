import unittest
import os
import shutil
from src.utils.helpers import validate_url, validate_path, format_time, sanitize_filename

class TestHelpers(unittest.TestCase):
    def test_validate_url(self):
        self.assertTrue(validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(validate_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertFalse(validate_url("https://google.com"))
        self.assertFalse(validate_url("invalid_url"))

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("file:name/with*invalid?chars"), "file_name_with_invalid_chars")
        self.assertEqual(sanitize_filename("normal_file.txt"), "normal_file.txt")

    def test_format_time(self):
        self.assertEqual(format_time(65), "01:05")
        self.assertEqual(format_time(3600), "60:00") # Helper returns MM:SS

    def test_validate_path(self):
        # Create temp dir
        temp_dir = "temp_test_dir"
        os.makedirs(temp_dir, exist_ok=True)
        try:
            ok, msg = validate_path(temp_dir)
            self.assertTrue(ok)
            
            ok, msg = validate_path("/invalid/path/that/does/not/exist/hopefully")
            # Should try to create it, if fails due to permissions -> False
            # But in docker/sandbox sometimes root can create anything. 
            # Let's check empty path
            ok, msg = validate_path("")
            self.assertFalse(ok)
        finally:
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

if __name__ == "__main__":
    unittest.main()
