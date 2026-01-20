import re

def smart_split_text(text: str, max_length: int = 6000, overlap: int = 500) -> list[str]:
    """
    Dzieli tekst na fragmenty, szukając semantycznych przerw (akapity, zdania).
    Bielik ma okno kontekstowe ~8k tokenów. Bezpieczny chunk to ok. 6000 znaków (zostawia miejsce na prompt i odpowiedź).
    """
    if not text:
        return []
    
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_pos = 0
    text_len = len(text)
    
    # Priorytety podziału: Podwójny enter > Enter > Koniec zdania > Przecinek/Spacja
    separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]
    
    while current_pos < text_len:
        target_end = min(current_pos + max_length, text_len)
        
        if target_end == text_len:
            chunks.append(text[current_pos:])
            break

        # Szukamy najlepszego punktu cięcia w ostatnich 15% chunka
        best_split = -1
        search_zone_start = max(current_pos, target_end - int(max_length * 0.15))
        chunk_candidate = text[search_zone_start:target_end]
        
        for sep in separators:
            last_sep_index = chunk_candidate.rfind(sep)
            if last_sep_index != -1:
                # Znaleziono separator - obliczamy absolutną pozycję
                best_split = search_zone_start + last_sep_index + len(sep)
                break
        
        # Fallback: Jeśli nie ma gdzie uciąć, tniemy na sztywno (bardzo rzadkie)
        if best_split == -1:
            best_split = target_end

        # Dodaj chunk
        chunks.append(text[current_pos:best_split])
        
        # Przesuń wskaźnik o overlap (dla zachowania kontekstu między fragmentami)
        # Ale nie cofaj się, jeśli best_split jest za blisko current_pos
        next_pos = max(current_pos + 1, best_split - overlap)
        
        # Zabezpieczenie przed pętlą nieskończoną (gdy overlap > długość chunka)
        if next_pos >= best_split:
            next_pos = best_split
            
        current_pos = next_pos

    return chunks
