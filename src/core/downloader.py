import os
import yt_dlp
import subprocess
import time
from src.utils.helpers import get_file_size

class Downloader:
    def __init__(self, logger, stop_event, progress_callback):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback

    def download_video(self, url, save_path, quality, audio_quality="192"):
        """Pobiera wideo z YouTube (obsługuje playlisty)"""
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        self.logger.log("Analizowanie URL...")
        
        # 1. Konfiguracja wstępna (tylko do pobrania info)
        common_opts = {
            "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),
            "writethumbnail": False,
            "writeinfojson": False,
            "keepvideo": False,
            "noplaylist": True, # Najpierw sprawdzamy, potem decydujemy
            "socket_timeout": 300,
            "quiet": True,
            "no_warnings": True
        }

        # 2. Sprawdzenie czy to playlista
        try:
            with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                
            entries = []
            if 'entries' in info:
                self.logger.log(f"Wykryto playlistę: {info.get('title', 'Nieznana')}")
                entries = list(info['entries']) # Flat entries
            else:
                entries = [info]

        except Exception as e:
            raise Exception(f"Błąd analizy URL: {str(e)}")

        # 3. Przygotowanie opcji pobierania właściwego
        final_opts = common_opts.copy()
        final_opts["noplaylist"] = True # Pobieramy pojedynczo w pętli
        final_opts["quiet"] = False
        final_opts["no_warnings"] = False
        # Remove default hook, we will add custom one per item
        # final_opts["progress_hooks"] = ... (added locally)

        if quality == "best":
            final_opts.update({
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            })
        elif quality == "worst":
            final_opts.update({
                "format": "worst",
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            })
        elif quality == "audio_only":
            final_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }],
            })

        downloaded_files = []
        total_items = len(entries)

        for i, entry in enumerate(entries, 1):
            if self.stop_event.is_set():
                break
            
            video_url = entry.get('url') or entry.get('webpage_url')
            if not video_url:
                video_url = url 
            
            title = entry.get('title', f"Wideo {i}")
            self.logger.log(f"Pobieranie [{i}/{total_items}]: {title} ({quality})...")
            
            # Custom hook for this item
            def item_progress_hook(d):
                if self.stop_event.is_set(): raise InterruptedError("Anulowano")
                if d["status"] == "downloading":
                    try:
                        p = d.get("_percent_str", "0%").replace("%", "")
                        percent = float(p)
                        # Scale to global progress
                        global_percent = ((i - 1) / total_items * 100) + (percent / total_items)
                        self.progress_callback(global_percent, "downloading")
                    except: pass
                elif d["status"] == "finished":
                    # Item finished
                    global_percent = (i / total_items) * 100
                    self.progress_callback(global_percent, "downloading")

            # Update opts with local hook
            current_opts = final_opts.copy()
            current_opts["progress_hooks"] = [item_progress_hook]

            try:
                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    # Pobieranie pojedynczego elementu
                    item_info = ydl.extract_info(video_url, download=True)
                    filename = ydl.prepare_filename(item_info)
                    
                    # Korekta rozszerzenia
                    base = os.path.splitext(filename)[0]
                    if quality == "audio_only":
                        filename = base + ".mp3"
                    else:
                        filename = base + ".mp4"
                    
                    if os.path.exists(filename):
                        size_str = get_file_size(filename)
                        self.logger.log(f"Pobrano: {os.path.basename(filename)} ({size_str})")
                        downloaded_files.append(filename)

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                self.logger.log(f"Błąd pobierania elementu {i}: {error_msg}")
                
                # Check for common signatures of outdated version
                if "Sign in to confirm you’re not a bot" in error_msg or "HTTP Error 403" in error_msg:
                    self.logger.log("KRYTYCZNY BŁĄD: Prawdopodobnie Twoja wersja 'yt-dlp' jest przestarzała.")
                    self.logger.log("ROZWIĄZANIE: Zaktualizuj biblioteki komendą: pip install -U yt-dlp")
                
                continue
            except Exception as e:
                self.logger.log(f"Błąd pobierania elementu {i}: {e}")
                continue

        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")

        return downloaded_files

    # Removed old `yt_dlp_hook` method as we use closure now
    
    def convert_to_mp3(self, input_path, output_path=None):
        """Konwertuje plik audio do MP3 używając FFmpeg"""
        if self.stop_event.is_set():
            raise InterruptedError("Anulowano")

        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = base + ".mp3"

        self.logger.log(f"Konwersja do MP3: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        self.progress_callback(0, "converting")

        try:
            # Używamy ffmpeg do konwersji
            cmd = [
                "ffmpeg", "-y",  # Nadpisz jeśli istnieje
                "-loglevel", "error", "-nostats",
                "-i", input_path,
                "-codec:a", "libmp3lame",
                "-qscale:a", "2",  # Dobra jakość VBR (~190kbps)
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            
            # Czekamy na zakończenie, sprawdzając stop_event
            while process.poll() is None:
                if self.stop_event.is_set():
                    process.terminate()
                    raise InterruptedError("Anulowano konwersję")
                time.sleep(0.1)
            
            if process.returncode != 0:
                _, stderr = process.communicate()
                raise Exception(f"Błąd FFmpeg: {stderr}")

            self.progress_callback(100, "converting")
            return output_path

        except Exception as e:
            raise Exception(f"Błąd konwersji: {str(e)}")
