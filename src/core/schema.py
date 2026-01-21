from typing import List, Optional
from pydantic import BaseModel, Field

class ToolInfo(BaseModel):
    """Informacje o narzędziu znalezionym w tekście."""
    name: str = Field(..., description="Nazwa narzędzia")
    description: str = Field(..., description="Opis narzędzia")
    url: Optional[str] = Field(None, description="URL narzędzia, jeśli dostępny")

class Concept(BaseModel):
    """Kluczowe pojęcie i jego definicja."""
    term: str = Field(..., description="Nazwa pojęcia")
    definition: str = Field(..., description="Definicja pojęcia")

class KnowledgeGraph(BaseModel):
    """Struktura wiedzy wyekstrahowana z tekstu."""
    topics: List[str] = Field(..., description="Lista głównych tematów")
    tools: List[ToolInfo] = Field(..., description="Lista narzędzi wspomnianych w tekście")
    key_concepts: List[Concept] = Field(..., description="Kluczowe pojęcia i definicje")
    tips: List[str] = Field(..., description="Praktyczne wskazówki")
    time_range: Optional[str] = Field(default=None, description="Zakres czasowy lub indeks fragmentu (np. Part 1)")
