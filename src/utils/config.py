import os

# Konfiguracja modeli
import torch

# Konfiguracja urządzenia
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# Konfiguracja Whisper
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_MODEL_SIZE = "medium"
WHISPER_LANGUAGES = {
    "Polski": "pl",
    "Angielski": "en",
    "Niemiecki": "de",
    "Hiszpański": "es",
    "Francuski": "fr",
    "Włoski": "it"
}

# Konfiguracja modeli LLM
# Konfiguracja modeli
MODEL_EXTRACTOR = "qwen2.5:14b"
MODEL_WRITER = "bielik-writer"
DEFAULT_OLLAMA_MODEL = MODEL_EXTRACTOR
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Parametry przetwarzania
CHUNK_SIZE = 8000  # Znaków na fragment (Qwen ma duże okno kontekstowe)
OVERLAP = 200      # Zakładka, żeby nie uciąć kontekstu

# Ścieżki
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(BASE_DIR, 'data', 'raw')
DATA_PROCESSED = os.path.join(BASE_DIR, 'data', 'processed')
DATA_OUTPUT = os.path.join(BASE_DIR, 'data', 'output')
