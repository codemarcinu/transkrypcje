import os

# Konfiguracja modeli
# Konfiguracja modeli
MODEL_EXTRACTOR = "qwen2.5:14b"
MODEL_WRITER = "bielik-writer"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Parametry przetwarzania
CHUNK_SIZE = 8000  # Znaków na fragment (Qwen ma duże okno kontekstowe)
OVERLAP = 200      # Zakładka, żeby nie uciąć kontekstu

# Ścieżki
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(BASE_DIR, 'data', 'raw')
DATA_PROCESSED = os.path.join(BASE_DIR, 'data', 'processed')
DATA_OUTPUT = os.path.join(BASE_DIR, 'data', 'output')
