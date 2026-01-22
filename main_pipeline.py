import os
import json
import shutil
from tqdm import tqdm
from src.utils.config import (
    DATA_RAW, DATA_PROCESSED, DATA_OUTPUT, CHUNK_SIZE, OVERLAP,
    MODEL_EXTRACTOR, MODEL_WRITER, OBSIDIAN_VAULT_PATH,
    OBSIDIAN_EXPORT_ENABLED, OBSIDIAN_SUBFOLDER
)
from src.core.text_cleaner import clean_transcript
from src.utils.text_processing import smart_split_text
from src.agents.extractor import KnowledgeExtractor
from src.agents.writer import ReportWriter
from src.core.llm_engine import unload_model
from src.utils.validator import verify_url


def export_to_obsidian(source_path: str) -> bool:
    """Kopiuje wygenerowany plik .md do Obsidian Vault."""
    if not OBSIDIAN_VAULT_PATH:
        return False

    try:
        # Tworzenie ścieżki docelowej
        obsidian_dir = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_SUBFOLDER)
        os.makedirs(obsidian_dir, exist_ok=True)

        filename = os.path.basename(source_path)
        dest_path = os.path.join(obsidian_dir, filename)

        shutil.copy2(source_path, dest_path)
        print(f"📚 Wyeksportowano do Obsidian: {dest_path}")
        return True
    except Exception as e:
        print(f"⚠️ Nie udało się wyeksportować do Obsidian: {e}")
        return False


def run_pipeline(input_path: str, output_dir: str = DATA_OUTPUT, topic: str = "Narzędzia OSINT, Krypto i Techniki Śledcze"):
    if not os.path.exists(input_path):
        print(f"Błąd: Nie znaleziono pliku {input_path}")
        return

    filename = os.path.basename(input_path)
    print(f"🚀 Rozpoczynam przetwarzanie: {filename}")

    # 1. Wczytywanie i czyszczenie
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    clean_text = clean_transcript(raw_text)
    chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)
    print(f"📦 Podzielono na {len(chunks)} fragmentów.")

    # 2. Mapowanie (Ekstrakcja)
    knowledge_base = []
    failed_chunks = 0
    stats = {
        "tools": 0,
        "concepts": 0,
        "topics": 0,
        "tips": 0
    }
    
    print(f"\n🕵️ Ekstrakcja wiedzy (Model: {MODEL_EXTRACTOR}, num_ctx: 4096)...")
    
    extractor = KnowledgeExtractor()
    total_chunks = len(chunks)
    for i, chunk in enumerate(tqdm(chunks)):
        # Oznaczanie fragmentu (Part X (Y%))
        progress_pct = int(((i + 1) / total_chunks) * 100)
        time_tag = f"Part {i+1} ({progress_pct}%)"
        
        graph = extractor.extract_knowledge(chunk, chunk_id=time_tag)
        
        # Wykrywanie cichego błędu
        is_empty_graph = not any([graph.topics, graph.tools, graph.key_concepts, graph.tips])
        
        if is_empty_graph:
            if len(chunk) > 100:
                failed_chunks += 1
                print(f"\n⚠️ [OSTRZEŻENIE] Fragment {time_tag} zwrócił puste dane.")
        
        for tool in graph.tools:
            stats["tools"] += 1
        
        stats["concepts"] += len(graph.key_concepts)
        stats["topics"] += len(graph.topics)
        stats["tips"] += len(graph.tips)
        
        knowledge_base.append(graph.model_dump())
        
        # Backup co 5 fragmentów
        if i % 5 == 0:
            with open(os.path.join(DATA_PROCESSED, "knowledge_backup.json"), 'w', encoding='utf-8') as f:
                json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    # Raport końcowy ekstrakcji
    print(f"\n📊 RAPORT EKSTRAKCJI:")
    print(f"   - Przetworzono: {len(chunks)} fragmentów")
    print(f"   - Znaleziono narzędzi: {stats['tools']}")
    print(f"   - Zdefiniowano pojęć: {stats['concepts']}")
    print(f"   - Wykryto błędów: {failed_chunks}")
    if failed_chunks > 0:
        print(f"   🚨 UWAGA: Brakuje {failed_chunks} fragmentów wiedzy.")

    # Zapis bazy wiedzy
    kb_path = os.path.join(DATA_PROCESSED, f"{filename}_kb.json")
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    unload_model(MODEL_EXTRACTOR)

    # 3. Redukcja (Pisanie)
    if not knowledge_base or (failed_chunks == len(chunks)):
        print("❌ Błąd krytyczny: Brak danych do napisania podręcznika.")
        return

    print(f"\n✍️ Pisanie podręcznika (Model: {MODEL_WRITER})...")
    writer = ReportWriter()
    chapter_content = writer.generate_chapter(topic, knowledge_base)
    
    final_content = f"# Podręcznik: {topic}\n\n{chapter_content}"
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"Podrecznik_{filename.replace('.txt', '.md')}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"\n🎉 SUKCES! Plik zapisany: {output_path}")

    # Eksport do Obsidian Vault
    if OBSIDIAN_EXPORT_ENABLED:
        export_to_obsidian(output_path)

if __name__ == "__main__":
    files = [f for f in os.listdir(DATA_RAW) if f.endswith('.txt')]
    if files:
        run_pipeline(os.path.join(DATA_RAW, files[0]))
    else:
        print("Brak plików .txt w data/raw")
