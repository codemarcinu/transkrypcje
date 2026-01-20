import os
import re
import shutil
import subprocess

def validate_url(url):
    """Walidacja URL YouTube"""
    if not url or not url.strip():
        return False
    youtube_regex = (
        r"(https?://)?(www\.)?"
        r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
        r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    )
    return re.match(youtube_regex, url.strip())

def validate_path(path):
    """Walidacja ścieżki zapisu"""
    if not path or not path.strip():
        return False, "Ścieżka nie może być pusta"
    
    path = path.strip()
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            return False, f"Nie można utworzyć katalogu: {e}"
    
    if not os.access(path, os.W_OK):
        return False, "Brak uprawnień do zapisu w tym katalogu"
    
    return True, "OK"

def check_disk_space(path, min_gb=1):
    """Sprawdza dostępne miejsce na dysku"""
    try:
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024**3)
        if free_gb < min_gb:
            return False, f"Za mało miejsca na dysku ({free_gb:.2f} GB dostępne, wymagane: {min_gb} GB)"
        return True, f"{free_gb:.2f} GB dostępne"
    except Exception as e:
        return True, "Nie można sprawdzić miejsca"

def check_ffmpeg():
    """Sprawdza czy FFmpeg jest zainstalowany"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return True, "FFmpeg dostępny"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False, "FFmpeg nie jest zainstalowany lub nie jest w PATH"

def sanitize_filename(filename):
    """Sanityzuje nazwę pliku"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def get_file_size(filepath):
    """Zwraca rozmiar pliku w czytelnej formie"""
    try:
        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    except:
        return "Nieznany"

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def format_srt_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_vtt_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
