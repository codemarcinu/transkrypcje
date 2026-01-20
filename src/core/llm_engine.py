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
