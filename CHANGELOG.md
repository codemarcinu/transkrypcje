# Changelog - Wersja 3.0

## 🎉 Wszystkie ulepszenia zostały zaimplementowane!

### ✅ Funkcjonalność

#### 1. **Przycisk "Anuluj" i obsługa przerwania**
- Dodano przycisk "ANULUJ" który zastępuje "START" podczas operacji
- Pełna implementacja `stop_event` - można przerwać operację w dowolnym momencie
- Bezpieczne czyszczenie plików tymczasowych przy anulowaniu

#### 2. **Walidacja ścieżki zapisu**
- Sprawdzanie czy katalog istnieje (tworzenie jeśli nie istnieje)
- Sprawdzanie uprawnień do zapisu
- Sprawdzanie dostępnego miejsca na dysku z ostrzeżeniem
- Walidacja URL podczas wpisywania (podświetlanie na czerwono jeśli nieprawidłowy)

#### 3. **Obsługa duplikatów plików**
- Automatyczne dodawanie numeracji do duplikatów (plik_1.mp4, plik_2.mp4)
- Funkcja `check_file_exists()` zwraca unikalną nazwę

#### 4. **Poprawiona obsługa błędów**
- Timeouty dla żądań sieciowych (30s dla yt-dlp, 5min dla Ollama)
- Konkretne typy wyjątków zamiast `except:`
- Lepsze komunikaty błędów z szczegółami
- Obsługa przerwanych pobierań

#### 5. **Wybór języka transkrypcji**
- Dropdown z dostępnymi językami (Auto, Polski, Angielski, Niemiecki, Francuski, Hiszpański, Włoski, Rosyjski, Japoński, Chiński)
- Auto-detekcja języka jeśli wybrano "Auto"

#### 6. **Wybór rozmiaru modelu Whisper**
- Dropdown z dostępnymi modelami: tiny, base, small, medium, large-v2, large-v3
- Domyślnie "medium"

#### 7. **Wybór formatu wyjściowego**
- **txt** - z timestampami (domyślnie)
- **txt_no_timestamps** - czysty tekst bez timestampów
- **srt** - format napisów SubRip
- **vtt** - format WebVTT

#### 8. **Wybór jakości audio**
- Opcja dostępna gdy wybrano "audio_only"
- Dostępne wartości: 128, 192, 256, 320 kbps
- Domyślnie 192 kbps

#### 9. **Opcja usunięcia wideo po transkrypcji**
- Checkbox "Usuń wideo po transkrypcji"
- Przydatne gdy potrzebna tylko transkrypcja

#### 10. **Sprawdzanie FFmpeg**
- Automatyczne sprawdzanie przy starcie aplikacji
- Ostrzeżenie jeśli FFmpeg nie jest zainstalowany

#### 11. **Status Ollama**
- Wskaźnik statusu Ollama w interfejsie
- Sprawdzanie przy starcie aplikacji
- Wyświetlanie liczby dostępnych modeli

#### 12. **Informacje o rozmiarze pliku**
- Wyświetlanie rozmiaru pobranego pliku
- Format czytelny (B, KB, MB, GB)

---

### 🎨 UX (User Experience)

#### 1. **Przycisk "Wklej"**
- Szybkie wklejanie URL ze schowka

#### 2. **Walidacja URL na bieżąco**
- Podświetlanie pola URL na czerwono jeśli nieprawidłowy
- Białe tło jeśli prawidłowy

#### 3. **Przyciski akcji po zakończeniu**
- "📁 Otwórz folder" - otwiera folder z plikami
- "📄 Otwórz plik" - otwiera konkretny plik (transkrypcja, podsumowanie)
- Automatycznie pokazują się po zakończeniu operacji

#### 4. **Kopiowanie logów**
- Przycisk "Kopiuj" w sekcji logów
- Kopiuje całą zawartość logów do schowka

#### 5. **Czyszczenie logów**
- Przycisk "Wyczyść" w sekcji logów
- Usuwa wszystkie logi z widoku

#### 6. **Lepszy layout**
- Więcej opcji w przejrzystym układzie
- LabelFrame dla lepszej organizacji
- Większe okno (800x750 zamiast 700x650)

#### 7. **Lepsze komunikaty**
- Szczegółowe komunikaty błędów
- Informacje o postępie z procentami
- Statusy systemowe przy starcie

#### 8. **Wskaźniki statusu**
- Status Ollama w czasie rzeczywistym
- Informacje o rozmiarze pliku
- Lepsze etykiety postępu

---

### 🔧 Poprawki kodu

#### 1. **Usunięto nieużywany import**
- Usunięto `json` (nie był używany)

#### 2. **Poprawiono `except:` bez typu**
- Wszystkie `except:` zamienione na `except Exception:` lub konkretne typy

#### 3. **Dodano sanityzację nazw plików**
- Funkcja `sanitize_filename()` usuwa niebezpieczne znaki
- Ogranicza długość nazw plików do 200 znaków

#### 4. **Lepsze zarządzanie wątkami**
- Proper cleanup przy anulowaniu
- Bezpieczne zakończenie wątków

#### 5. **Dodano timeouty**
- Timeout dla yt-dlp (30s)
- Timeout dla Ollama (5min)
- Timeout dla sprawdzania FFmpeg (5s)

#### 6. **Lepsze metadane transkrypcji**
- Poprawione użycie atrybutów `info` z Whisper
- Bezpieczne sprawdzanie czy atrybuty istnieją

#### 7. **Filtr VAD**
- Dodano `vad_filter=True` do transkrypcji dla lepszej jakości

---

### 📋 Nowe funkcje pomocnicze

- `validate_path()` - walidacja ścieżki zapisu
- `check_disk_space()` - sprawdzanie miejsca na dysku
- `check_ffmpeg()` - sprawdzanie FFmpeg
- `check_file_exists()` - sprawdzanie duplikatów
- `sanitize_filename()` - sanityzacja nazw plików
- `get_file_size()` - czytelny format rozmiaru
- `check_ollama_status()` - status Ollama
- `get_ollama_models()` - lista modeli Ollama
- `save_transcription()` - zapis w różnych formatach
- `_save_txt()`, `_save_srt()`, `_save_vtt()`, `_save_txt_no_timestamps()` - formaty wyjściowe
- `_format_time()`, `_format_srt_time()`, `_format_vtt_time()` - formatowanie czasu
- `open_folder()`, `open_file()` - otwieranie plików/folderów (cross-platform)

---

### 🐛 Naprawione błędy

1. ✅ `stop_event` teraz faktycznie używane
2. ✅ `info.title` bezpieczne sprawdzanie
3. ✅ `except:` bez typu naprawione
4. ✅ Brak walidacji ścieżki - naprawione
5. ✅ Brak obsługi duplikatów - naprawione
6. ✅ Brak timeoutów - naprawione
7. ✅ Hardcoded język - naprawione
8. ✅ Hardcoded rozmiar modelu - naprawione
9. ✅ Tylko format txt - naprawione
10. ✅ Brak możliwości anulowania - naprawione

---

### 📝 Uwagi techniczne

- Aplikacja wymaga FFmpeg dla konwersji wideo (sprawdzane przy starcie)
- Ollama jest opcjonalny (dla podsumowań)
- Wszystkie operacje są thread-safe
- Cross-platform (Windows, Linux, macOS)
- Obsługuje Unicode i specjalne znaki w nazwach plików

---

### 🚀 Jak używać nowych funkcji

1. **Wybór języka**: Wybierz język z dropdown "Język" (domyślnie Polski)
2. **Wybór modelu**: Wybierz rozmiar modelu Whisper (większy = lepsza jakość, ale wolniej)
3. **Format wyjściowy**: Wybierz format transkrypcji (txt, srt, vtt, lub txt bez timestampów)
4. **Jakość audio**: Dostępna tylko dla "audio_only" (128-320 kbps)
5. **Anulowanie**: Kliknij "ANULUJ" aby przerwać operację
6. **Otwieranie plików**: Po zakończeniu kliknij "📁 Otwórz folder" lub "📄 Otwórz plik"
7. **Logi**: Użyj "Kopiuj" aby skopiować logi lub "Wyczyść" aby je wyczyścić

---

**Wersja**: 3.0  
**Data**: 2024  
**Autor**: Marcin

