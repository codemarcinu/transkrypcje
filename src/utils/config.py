import os
from dotenv import load_dotenv

# Wczytaj zmienne środowiskowe z .env
load_dotenv()

# Konfiguracja modeli
import torch

# Konfiguracja urządzenia
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

# Konfiguracja Whisper
WHISPER_MODELS = ["medium", "large-v3"]
DEFAULT_MODEL_SIZE = "large-v3"
WHISPER_LANGUAGES = {
    "Polski": "pl",
    "Angielski": "en",
    "Niemiecki": "de",
    "Hiszpański": "es",
    "Francuski": "fr",
    "Włoski": "it"
}

# Konfiguracja modeli LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama") # "ollama" lub "openai"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Modele Ollama (Zmieniono na 7b dla RTX 3060)
MODEL_EXTRACTOR_OLLAMA = "qwen2.5:7b"
MODEL_WRITER_OLLAMA = "bielik-writer"
MODEL_TAGGER_OLLAMA = "qwen2.5:7b"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Modele OpenAI
MODEL_EXTRACTOR_OPENAI = "gpt-4o-mini"
MODEL_WRITER_OPENAI = "gpt-4o-mini" # Można zmienić na gpt-4o dla lepszej jakości
MODEL_TAGGER_OPENAI = "gpt-4o-mini"

# Wybrany model (zależnie od providera)
if LLM_PROVIDER == "openai":
    MODEL_EXTRACTOR = MODEL_EXTRACTOR_OPENAI
    MODEL_WRITER = MODEL_WRITER_OPENAI
    MODEL_TAGGER = MODEL_TAGGER_OPENAI
else:
    MODEL_EXTRACTOR = MODEL_EXTRACTOR_OLLAMA
    MODEL_WRITER = MODEL_WRITER_OLLAMA
    MODEL_TAGGER = MODEL_TAGGER_OLLAMA

DEFAULT_OLLAMA_MODEL = MODEL_EXTRACTOR

# Parametry przetwarzania
CHUNK_SIZE = 5000  # Zmniejszono z 8000 dla lepszej stabilności VRAM (RTX 3060)
OVERLAP = 300      # Zwiększono zakładkę dla lepszej ciągłości wiedzy

# Ścieżki
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_RAW = os.path.join(BASE_DIR, 'data', 'raw')
DATA_PROCESSED = os.path.join(BASE_DIR, 'data', 'processed')
DATA_OUTPUT = os.path.join(BASE_DIR, 'data', 'output')

# Obsidian Vault - automatyczny eksport notatek
# Ścieżka WSL do Windows: /mnt/c/Users/marci/Documents/Obsidian Vault/2ndBrain
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/mnt/c/Users/marci/Documents/Obsidian Vault/2ndBrain")
OBSIDIAN_EXPORT_ENABLED = os.getenv("OBSIDIAN_EXPORT_ENABLED", "true").lower() == "true"
OBSIDIAN_SUBFOLDER = os.getenv("OBSIDIAN_SUBFOLDER", "Transkrypcje")  # Podfolder w vault
