import requests

class Summarizer:
    def __init__(self, logger, stop_event, progress_callback):
        self.logger = logger
        self.stop_event = stop_event
        self.progress_callback = progress_callback

    def check_ollama_status(self):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    return True, f"Dostępny ({len(models)} modeli)"
                return True, "Dostępny (brak modeli)"
            return False, "Nie odpowiada"
        except requests.exceptions.RequestException:
            return False, "Niedostępny"

    def get_ollama_models(self):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                return models
            return []
        except:
            return []

    def summarize_text(self, text, model_name=None, max_chars=10000, style="Zwięzłe (3 punkty)"):
        if self.stop_event.is_set():
            raise InterruptedError("Operacja anulowana przez użytkownika")
        
        try:
            self.logger.log("Próba połączenia z Ollama...")
            self.progress_callback(0, "summarizing")

            tags_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if tags_response.status_code != 200:
                self.logger.log("Ollama nie odpowiada poprawnie.")
                return None

            models = [m["name"] for m in tags_response.json().get("models", [])]
            if not models:
                self.logger.log("Brak modeli w Ollama.")
                return None

            if model_name and model_name in models:
                selected_model = model_name
            else:
                selected_model = models[0]
                for m in models:
                    if "llama3" in m or "mistral" in m:
                        selected_model = m
                        break

            self.logger.log(f"Używam modelu: {selected_model} do podsumowania.")
            self.progress_callback(20, "summarizing")

            text_to_summarize = text[:max_chars]
            if len(text) > max_chars:
                self.logger.log(f"Tekst został obcięty do {max_chars} znaków")

            if "Krótkie" in style:
                prompt_text = "Napisz krótkie streszczenie tego tekstu w jednym akapicie (po polsku)"
            elif "Szczegółowe" in style:
                prompt_text = "Sporządź szczegółowe podsumowanie, uwzględniając najważniejsze wątki i detale (po polsku)"
            else:
                prompt_text = "Stwórz zwięzłe podsumowanie w 3 punktach (po polsku)"

            prompt = f"{prompt_text} poniższego tekstu:\n\n{text_to_summarize}"

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": selected_model, "prompt": prompt, "stream": False},
                timeout=300,
            )

            self.progress_callback(100, "summarizing")

            if response.status_code == 200:
                return response.json().get("response")
            else:
                self.logger.log(f"Błąd Ollama: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            self.logger.log("Timeout przy połączeniu z Ollama.")
            return None
        except Exception as e:
            self.logger.log(f"Nie udało się połączyć z Ollama: {e}")
            return None
