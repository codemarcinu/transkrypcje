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
from src.core.transcriber import Transcriber
from src.core.gpu_manager import clear_gpu_memory
from src.agents.extractor import KnowledgeExtractor
from src.agents.writer import ReportWriter
from src.core.llm_engine import unload_model


def run_pipeline(input_path: str, output_dir: str = DATA_OUTPUT, topic: str = "Narzędzia OSINT, Krypto i Techniki Śledcze", whisper_model: str = "large-v3"):
    if not os.path.exists(input_path):
        print(f"Błąd: Nie znaleziono pliku {input_path}")
        return

    filename = os.path.basename(input_path)
    print(f"\n🚀 {'='*60}")
    print(f"🚀 ROZPOCZYNAM PRZETWARZANIE: {filename}")
    print(f"🚀 {'='*60}")

    # --- KROK 1: Transkrypcja (jeśli plik nie jest .txt) ---
    txt_path = input_path
    if not input_path.endswith('.txt'):
        print(f"\n🎙️ [KROK 1] Transkrypcja Whisper (Model: {whisper_model})...")
        transcriber = Transcriber(logger=None, stop_event=None, progress_callback=lambda p, s: None)
        
        # Miejscowa definicja mock-loggera i stop_event dla Transcribera
        class SimpleLogger:
            def log(self, m): print(f"  [Whisper] {m}")
        
        class SimpleStopEvent:
            def is_set(self): return False

        transcriber.logger = SimpleLogger()
        transcriber.stop_event = SimpleStopEvent()
        transcriber.progress_callback = lambda p, s: None

        segments, info = transcriber.transcribe_video(input_path, language=None, model_size=whisper_model)
        txt_path, _ = transcriber.save_transcription(segments, info, input_path, output_format="txt", language=None)
        
        # --- KROK 1.5: WYMUSZONE CZYSZCZENIE VRAM ---
        print("\n🧹 [CZYSZCZENIE] Zwalnianie VRAM po Whisperze...")
        del transcriber
        clear_gpu_memory(verbose=True)
        print("✅ VRAM gotowy na LLM.")

    # 2. Wczytywanie i czyszczenie
    with open(txt_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    clean_text = clean_transcript(raw_text)
    chunks = smart_split_text(clean_text, chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP)
    print(f"\n📦 Podzielono na {len(chunks)} fragmentów.")

    # 3. Mapowanie (Ekstrakcja)
    knowledge_base = []
    failed_chunks = 0
    stats = {
        "tools": 0,
        "concepts": 0,
        "topics": 0,
        "tips": 0
    }
    
    print(f"\n🕵️ [KROK 2] Ekstrakcja wiedzy (Model: {MODEL_EXTRACTOR}, num_ctx: 4096)...")
    
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
        
        stats["tools"] += len(graph.tools)
        stats["concepts"] += len(graph.key_concepts)
        stats["topics"] += len(graph.topics)
        stats["tips"] += len(graph.tips)
        
        knowledge_base.append(graph.model_dump())
        
        # Backup co 5 fragmentów
        if i % 5 == 0:
            os.makedirs(DATA_PROCESSED, exist_ok=True)
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
    kb_name = os.path.basename(txt_path)
    kb_path = os.path.join(DATA_PROCESSED, f"{kb_name}_kb.json")
    os.makedirs(DATA_PROCESSED, exist_ok=True)
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

    unload_model(MODEL_EXTRACTOR)

    # 4. Redukcja (Pisanie)
    if not knowledge_base or (failed_chunks == len(chunks)):
        print("❌ Błąd krytyczny: Brak danych do napisania podręcznika.")
        return

    print(f"\n✍️ [KROK 3] Pisanie treści (Model: {MODEL_WRITER})...")
    writer = ReportWriter()
    
    # Generujemy treść (bez tagów na razie)
    content_only = writer.generate_chapter(topic, knowledge_base, mode="deep_dive", tags=[])
    
    # --- CZYSZCZENIE VRAM po Pisarzu ---
    print("\n🧹 [CZYSZCZENIE] Zwalnianie VRAM po Bieliku...")
    from src.core.llm_engine import unload_model
    unload_model(MODEL_WRITER)
    
    # 5. Tagowanie (Nowy Krok)
    print(f"\n🏷️ [KROK 4] Generowanie tagów (Model: Qwen)...")
    from src.agents.tagger import TaggerAgent
    tagger = TaggerAgent()
    tags = tagger.generate_tags(content_only)
    print(f"✅ Wygenerowano tagi: {', '.join(tags)}")
    
    # --- CZYSZCZENIE VRAM po Taggerze ---
    unload_model("qwen2.5:7b") # Zakładając że to extractor
    
    # 6. Składanie finalne
    # Ponownie używamy ReportWriter tylko do złożenia YAML (bez ponownego generowania treści)
    # Tu mały hack: ReportWriter.generate_chapter generuje treść...
    # Musimy zaktualizować frontmatter w content_only lub dodać metodę do ReportWriter.
    
    # Poprawka: Zaktualizujmy frontmatter mechanicznie lub dodajmy metodę do writer.py
    # Zróbmy to porządnie w ReportWriter.
    
    final_output = content_only.replace("tags: []", f"tags: {tags}")
    
    final_content = f"# Podręcznik: {topic}\n\n{final_output}"
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"Podrecznik_{filename.split('.')[0]}.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"\n🎉 SUKCES! Plik zapisany: {output_path}")

    # Eksport do Obsidian Vault
    if OBSIDIAN_EXPORT_ENABLED:
        export_to_obsidian(output_path)


if __name__ == "__main__":
    # Obsługa wielu plików i różnych formatów
    supported_extensions = ('.txt', '.mp3', '.mp4', '.m4a', '.wav')
    files = [f for f in os.listdir(DATA_RAW) if f.lower().endswith(supported_extensions)]
    
    if files:
        print(f"Found {len(files)} files to process in {DATA_RAW}")
        for file in files:
            try:
                run_pipeline(os.path.join(DATA_RAW, file))
            except Exception as e:
                print(f"❌ Error processing {file}: {e}")
    else:
        print(f"Brak wspieranych plików w {DATA_RAW}")

