import instructor
import ollama
from openai import OpenAI
from pydantic import ValidationError

from src.core.schema import KnowledgeGraph
from src.utils.config import MODEL_EXTRACTOR, OLLAMA_URL

def extract_knowledge(chunk_text: str) -> KnowledgeGraph:
    """
    Faza MAP: Zamienia tekst na ustrukturyzowane dane używając biblioteki instructor.
    Zwraca obiekt KnowledgeGraph (Pydantic model) zamiast dict/stringa.
    """
    
    # Konfiguracja klienta Instructor (patchowanie OpenAI client dla Ollama)
    client = instructor.from_openai(
        OpenAI(
            base_url=f"{OLLAMA_URL}/v1",
            api_key="ollama",  # wymagane, ale ignorowane przez lokalną Ollamę
        ),
        mode=instructor.Mode.JSON,
    )

    system_prompt = """
    Jesteś analitykiem technicznym. Analizujesz transkrypcję szkolenia OSINT/Cybersec.
    Twoim celem jest wyciągnięcie twardych danych i zwrócenie ich w ściśle zdefiniowanym formacie JSON.
    
    Ignoruj: 
    - Sprawy organizacyjne ("czy słychać", "przerwa").
    - Żarty i dygresje niemerytoryczne.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_EXTRACTOR,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analizuj fragment:\n{chunk_text}"},
            ],
            response_model=KnowledgeGraph,
            max_retries=2, 
        )
        return response
    except ValidationError as e:
        print(f"Błąd walidacji danych z LLM: {e}")
        # Zwracamy pusty graf w przypadku błędu, by nie wywalić pipeline'u
        return KnowledgeGraph(topics=[], tools=[], key_concepts=[], tips=[])
    except Exception as e:
        print(f"Błąd krytyczny w extract_knowledge: {e}")
        return KnowledgeGraph(topics=[], tools=[], key_concepts=[], tips=[])
