import ollama
import json
import re

def clean_json_string(response: str) -> str:
    """Czyści odpowiedź modelu z formatowania Markdown (np. ```json ... ```)."""
    if "```" in response:
        pattern = r"```(?:json)?(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
    return response

def call_ollama(model: str, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str | dict:
    """Uniwersalna funkcja do wywoływania Ollama."""
    try:
        response = ollama.chat(model=model, messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ], format='json' if json_mode else '')
        
        content = response['message']['content']
        
        if json_mode:
            content = clean_json_string(content)
            return json.loads(content)
        
        return content
    except Exception as e:
        print(f"❌ Błąd LLM ({model}): {e}")
        return {} if json_mode else ""

def unload_model(model_name: str):
    """
    Wymusza zwolnienie modelu z pamięci VRAM (ważne dla kart z <24GB VRAM).
    Wysyła pusty request z keep_alive=0 oraz czyści cache CUDA.
    """
    import gc
    try:
        ollama.generate(model=model_name, prompt="", keep_alive=0)
        gc.collect()
        
        # Próba czyszczenia cache CUDA jeśli torch jest dostępny
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print(f"[INFO] Zwolniono model i wyczyszczono CUDA: {model_name}")
            else:
                print(f"[INFO] Zwolniono model: {model_name} (CUDA niedostępne)")
        except ImportError:
            print(f"[INFO] Zwolniono model: {model_name} (Torch niedostępny)")
            
    except Exception as e:
        print(f"[WARNING] Nie udało się zwolnić modelu {model_name}: {e}")

class LLMEngine:
    """Klasa silnika LLM wspierająca ustrukturyzowane i zwykłe generowanie."""
    def __init__(self, model_type: str):
        from src.utils.config import MODEL_EXTRACTOR, MODEL_WRITER, OLLAMA_URL
        import instructor
        from openai import OpenAI
        
        self.model = MODEL_EXTRACTOR if model_type == "extractor" else MODEL_WRITER
        self.raw_client = OpenAI(
            base_url=f"{OLLAMA_URL}/v1",
            api_key="ollama",
        )
        self.client = instructor.from_openai(
            self.raw_client,
            mode=instructor.Mode.JSON,
        )

    def generate_structured(self, system_prompt: str, user_prompt: str, response_model: type) -> any:
        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=response_model,
            temperature=0.1,
            extra_body={"options": {"num_ctx": 8192}}
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.raw_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    def generate_stream(self, system_prompt: str, user_prompt: str):
        """
        Generator streamujący odpowiedź token po tokenie.
        Użycie: for chunk in llm.generate_stream(...): print(chunk, end="")
        """
        response = self.raw_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
