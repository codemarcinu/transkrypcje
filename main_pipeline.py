import os
import json
from tqdm import tqdm
from src.utils.config import DATA_RAW, DATA_PROCESSED, DATA_OUTPUT, CHUNK_SIZE, OVERLAP, MODEL_EXTRACTOR, MODEL_WRITER
from src.core.text_cleaner import clean_transcript
from src.utils.text_processing import smart_split_text
from src.agents.extractor import KnowledgeExtractor
from src.agents.writer import ReportWriter
from src.core.llm_engine import unload_model
from src.utils.validator import verify_url

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
    
    print(f"\n🕵️ Ekstrakcja wiedzy (Model: {MODEL_EXTRACTOR})...")
    
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
        
        # Walidacja URLi i zbieranie statystyk
        for tool in graph.tools:
            stats["tools"] += 1
            if tool.url and not verify_url(tool.url):
                tool.url = None
        
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

if __name__ == "__main__":
    files = [f for f in os.listdir(DATA_RAW) if f.endswith('.txt')]
    if files:
        run_pipeline(os.path.join(DATA_RAW, files[0]))
    else:
        print("Brak plików .txt w data/raw")
