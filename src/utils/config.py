import torch

# Konfiguracja modelu AI - domyślne wartości
DEFAULT_MODEL_SIZE = "medium"
DEFAULT_LANGUAGE = "pl"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
import os
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# Tutaj wpisz nazwę modelu dokładnie taką, jaką masz w 'ollama list'
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "SpeakLeash/bielik-11b-v3.0-instruct:Q5_K_M")

# Dostępne języki dla Whisper
WHISPER_LANGUAGES = {
    "Auto": None,
    "Polski": "pl",
    "Angielski": "en",
    "Niemiecki": "de",
    "Francuski": "fr",
    "Hiszpański": "es",
    "Włoski": "it",
    "Rosyjski": "ru",
    "Japoński": "ja",
    "Chiński": "zh",
}

# Dostępne rozmiary modeli Whisper
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
