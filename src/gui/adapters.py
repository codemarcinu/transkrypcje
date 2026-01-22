"""
Adaptery łączące backend z Gradio UI.
- GradioProgressAdapter: tłumaczy progress_callback na gr.Progress
- CancellableStopEvent: thread-safe event do anulowania operacji
- LogCapture: przechwytuje logi do wyświetlenia w UI
"""

import threading
from datetime import datetime
from typing import Optional, List, Callable
import gradio as gr


class GradioProgressAdapter:
    """
    Adapter tłumaczący sygnaturę progress_callback(percent, stage)
    na format gr.Progress().

    Używany przez Processor i jego komponenty (Downloader, Transcriber).
    """

    STAGE_LABELS = {
        "downloading": "Pobieranie materialu...",
        "converting": "Konwersja audio...",
        "transcribing": "Transkrypcja Whisper...",
        "extracting": "Ekstrakcja wiedzy...",
        "writing": "Generowanie tresci (Bielik)...",
        "tagging": "Generowanie tagow (Qwen)...",
        "saving": "Zapisywanie wynikow...",
        "summarizing": "Generowanie podsumowania...",
        "cleaning": "Porzadkowanie plikow...",
    }

    def __init__(self, gradio_progress: gr.Progress):
        """
        Args:
            gradio_progress: Instancja gr.Progress z dekoratora funkcji
        """
        self.progress = gradio_progress
        self._current_stage = ""
        self._last_percent = 0.0

    def update(self, percent: float, stage: str, extra_info: Optional[str] = None) -> None:
        """
        Aktualizuje progress bar w UI.

        Args:
            percent: Procent ukończenia (0-100)
            stage: Identyfikator etapu (klucz z STAGE_LABELS)
            extra_info: Opcjonalne dodatkowe info (np. rozmiar pliku)
        """
        # Normalizacja do zakresu 0-1
        normalized = min(max(percent / 100.0, 0.0), 1.0)

        # Pobierz przyjazną etykietę lub użyj oryginalnej
        label = self.STAGE_LABELS.get(stage.lower(), f"Przetwarzanie: {stage}")

        # Dodaj extra info jeśli podane
        if extra_info:
            label = f"{label} | {extra_info}"

        self._current_stage = stage
        self._last_percent = percent

        # Wywołaj Gradio progress
        self.progress(normalized, desc=label)

    def __call__(self, percent: float, stage: str) -> None:
        """Pozwala używać instancji jako callback bezpośrednio."""
        self.update(percent, stage)

    @property
    def current_stage(self) -> str:
        """Zwraca aktualny etap."""
        return self._current_stage

    @property
    def last_percent(self) -> float:
        """Zwraca ostatni procent."""
        return self._last_percent


class CancellableStopEvent:
    """
    Thread-safe event do anulowania długotrwałych operacji.
    Kompatybilny z interfejsem stop_event używanym przez Processor.
    """

    def __init__(self):
        self._event = threading.Event()
        self._cancel_requested = False
        self._lock = threading.Lock()

    def is_set(self) -> bool:
        """Sprawdza czy żądano anulowania."""
        return self._event.is_set()

    def set(self) -> None:
        """Żąda anulowania operacji."""
        with self._lock:
            self._cancel_requested = True
            self._event.set()

    def clear(self) -> None:
        """Resetuje event dla nowej operacji."""
        with self._lock:
            self._cancel_requested = False
            self._event.clear()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Czeka na sygnał anulowania."""
        return self._event.wait(timeout)

    @property
    def cancel_requested(self) -> bool:
        """Czy żądano anulowania (bez blokowania)."""
        return self._cancel_requested


# Globalna instancja stop event dla UI
_global_stop_event = CancellableStopEvent()


def get_stop_event() -> CancellableStopEvent:
    """Zwraca globalną instancję stop event."""
    return _global_stop_event


def request_cancel() -> str:
    """
    Wywoływane przez przycisk anulowania.

    Returns:
        Komunikat statusu
    """
    _global_stop_event.set()
    return "Anulowanie... Poczekaj na zakonczenie biezacej operacji."


def reset_cancel() -> None:
    """Resetuje stop event przed nową operacją."""
    _global_stop_event.clear()


class LogCapture:
    """
    Przechwytuje komunikaty logów do wyświetlenia w UI.
    Thread-safe akumulacja wpisów logów.

    Implementuje interfejs logger używany przez Processor:
    - log(message)
    - info(message)
    - error(message)
    - warning(message)
    """

    def __init__(self, max_lines: int = 100):
        """
        Args:
            max_lines: Maksymalna liczba przechowywanych linii
        """
        self._lines: List[str] = []
        self._max_lines = max_lines
        self._lock = threading.Lock()

    def _add_line(self, prefix: str, message: str) -> None:
        """Dodaje linię z timestampem."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {prefix}{message}"

        with self._lock:
            self._lines.append(formatted)
            # Ogranicz liczbę linii
            if len(self._lines) > self._max_lines:
                self._lines = self._lines[-self._max_lines:]

    def log(self, message: str) -> None:
        """Dodaje komunikat logu."""
        self._add_line("", message)

    def info(self, message: str) -> None:
        """Dodaje komunikat informacyjny."""
        self._add_line("INFO: ", message)

    def error(self, message: str) -> None:
        """Dodaje komunikat błędu."""
        self._add_line("BLAD: ", message)

    def warning(self, message: str) -> None:
        """Dodaje ostrzeżenie."""
        self._add_line("UWAGA: ", message)

    def debug(self, message: str) -> None:
        """Dodaje komunikat debug (pomijany w UI)."""
        pass  # Debug nie jest pokazywany w UI

    def get_logs(self) -> str:
        """
        Zwraca wszystkie logi jako jeden string.

        Returns:
            Połączone linie logów
        """
        with self._lock:
            return "\n".join(self._lines)

    def clear(self) -> None:
        """Czyści wszystkie logi."""
        with self._lock:
            self._lines.clear()

    def get_last_n(self, n: int = 10) -> str:
        """
        Zwraca ostatnie N linii.

        Args:
            n: Liczba linii do zwrócenia

        Returns:
            Ostatnie N linii jako string
        """
        with self._lock:
            return "\n".join(self._lines[-n:])


class DummyProgress:
    """
    Dummy progress dla operacji bez progress bar.
    Implementuje interfejs gr.Progress ale nic nie robi.
    """

    def __call__(self, value: float, desc: str = "") -> None:
        pass

    def tqdm(self, iterable, desc: str = "", total: Optional[int] = None):
        """Zwraca iterator bez progress tracking."""
        return iterable


def create_progress_adapter(progress: Optional[gr.Progress] = None) -> GradioProgressAdapter:
    """
    Tworzy adapter progress - prawdziwy lub dummy.

    Args:
        progress: Opcjonalna instancja gr.Progress

    Returns:
        GradioProgressAdapter (prawdziwy lub z DummyProgress)
    """
    if progress is None:
        return GradioProgressAdapter(DummyProgress())
    return GradioProgressAdapter(progress)
