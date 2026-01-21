from pydantic import BaseModel, Field
from typing import List, Optional

class KeyConcept(BaseModel):
    term: str = Field(..., description="Termin lub pojęcie")
    definition: str = Field(..., description="Definicja lub wyjaśnienie")

class Tool(BaseModel):
    name: str = Field(..., description="Nazwa narzędzia")
    description: str = Field(..., description="Opis zastosowania")

class KnowledgeGraph(BaseModel):
    topics: List[str] = Field(description="Główne tematy poruszone w fragmencie")
    tools: List[Tool] = Field(description="Wymienione narzędzia i ich zastosowanie")
    key_concepts: List[KeyConcept] = Field(description="Kluczowe pojęcia i definicje")
    tips: List[str] = Field(description="Praktyczne porady i wskazówki")
    
    # ZMIANA: Dodajemy time_range z wartością domyślną None.
    # Dzięki temu stare pliki JSON (bez tego pola) nadal będą działać.
    time_range: Optional[str] = Field(default=None, description="Znacznik czasowy (np. 01:04) lub indeks fragmentu")
