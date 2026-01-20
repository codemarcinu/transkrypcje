import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock yt_dlp BEFORE importing Downloader because it's imported at top-level
sys.modules['yt_dlp'] = MagicMock()

import os
from src.core.downloader import Downloader

class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.mock_logger = MagicMock()
        self.mock_stop_event = MagicMock()
        self.mock_stop_event.is_set.return_value = False
        self.mock_progress = MagicMock()
        self.downloader = Downloader(self.mock_logger, self.mock_stop_event, self.mock_progress)

    @patch('src.core.downloader.yt_dlp')
    @patch('os.path.exists')
    @patch('src.core.downloader.get_file_size')
    def test_download_single_video(self, mock_get_size, mock_exists, mock_ytdlp):
        # Setup mocks
        mock_ydl = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl
        
        # Scenario: validate URL - single video
        mock_ydl.extract_info.side_effect = [
            {'id': '123', 'title': 'Video 1'}, # First call (extract info)
            {'id': '123', 'title': 'Video 1'}  # Second call (download)
        ]
        mock_ydl.prepare_filename.return_value = "video.mp4"
        mock_exists.return_value = True
        mock_get_size.return_value = "10 MB"

        files = self.downloader.download_video("http://youtube.com/watch?v=123", ".", "best")
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], "video.mp4")
        self.assertEqual(mock_ydl.extract_info.call_count, 2)

    @patch('src.core.downloader.yt_dlp')
    @patch('os.path.exists')
    @patch('src.core.downloader.get_file_size')
    def test_download_playlist(self, mock_get_size, mock_exists, mock_ytdlp):
        # Setup mocks
        mock_ydl = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl
        
        # Scenario: Playlist with 2 videos
        playlist_info = {
            'entries': [
                {'url': 'http://yt.com/1', 'title': 'V1'},
                {'url': 'http://yt.com/2', 'title': 'V2'}
            ],
            'title': 'My Playlist'
        }
        
        mock_ydl.extract_info.side_effect = [
            playlist_info, # First call: info extraction
            {'id': '1', 'title': 'V1'}, # Download V1
            {'id': '2', 'title': 'V2'}  # Download V2
        ]
        
        mock_ydl.prepare_filename.side_effect = ["v1.mp4", "v2.mp4"]
        mock_exists.return_value = True
        
        files = self.downloader.download_video("http://youtube.com/playlist?list=123", ".", "best")
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0], "v1.mp4")
        self.assertEqual(files[1], "v2.mp4")
        
if __name__ == "__main__":
    unittest.main()
