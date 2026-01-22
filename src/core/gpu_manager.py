"""
GPU Memory Manager - centralne zarządzanie pamięcią VRAM.

Użycie jako context manager:
    with GPUMemoryManager() as gpu:
        # operacje na GPU
        model = load_model()
        result = model.process(data)
    # VRAM automatycznie wyczyszczona po wyjściu

Użycie funkcji bezpośrednio:
    clear_gpu_memory()  # jednorazowe czyszczenie
"""

import gc
from contextlib import contextmanager
from typing import Optional

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def clear_gpu_memory(verbose: bool = False) -> None:
    """
    Czyści pamięć GPU (VRAM) i uruchamia garbage collector.

    Args:
        verbose: Jeśli True, wypisuje informacje o czyszczeniu.
    """
    gc.collect()

    if TORCH_AVAILABLE and torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

        if verbose:
            allocated = torch.cuda.memory_allocated() / (1024**3)
            reserved = torch.cuda.memory_reserved() / (1024**3)
            print(f"[GPU] Wyczyszczono. Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB")
    elif verbose:
        print("[GPU] CUDA niedostępna - tylko gc.collect()")


def get_gpu_memory_info() -> dict:
    """
    Zwraca informacje o pamięci GPU.

    Returns:
        dict z kluczami: available, allocated_gb, reserved_gb, total_gb, free_gb
    """
    if not TORCH_AVAILABLE or not torch.cuda.is_available():
        return {"available": False}

    props = torch.cuda.get_device_properties(0)
    total = props.total_memory / (1024**3)
    allocated = torch.cuda.memory_allocated() / (1024**3)
    reserved = torch.cuda.memory_reserved() / (1024**3)

    return {
        "available": True,
        "device_name": props.name,
        "total_gb": round(total, 2),
        "allocated_gb": round(allocated, 2),
        "reserved_gb": round(reserved, 2),
        "free_gb": round(total - reserved, 2)
    }


class GPUMemoryManager:
    """
    Context manager do zarządzania pamięcią GPU.

    Automatycznie czyści VRAM przed i po operacjach.
    Przydatne przy ładowaniu dużych modeli (Whisper, LLM).

    Przykład:
        with GPUMemoryManager(clear_before=True, clear_after=True) as gpu:
            model = WhisperModel("large-v3")
            result = model.transcribe(audio)
        # Model zwolniony, VRAM wyczyszczona
    """

    def __init__(self, clear_before: bool = True, clear_after: bool = True, verbose: bool = False):
        """
        Args:
            clear_before: Czy czyścić VRAM przed wejściem do bloku.
            clear_after: Czy czyścić VRAM po wyjściu z bloku.
            verbose: Czy wypisywać informacje o stanie pamięci.
        """
        self.clear_before = clear_before
        self.clear_after = clear_after
        self.verbose = verbose

    def __enter__(self):
        if self.clear_before:
            if self.verbose:
                print("[GPU] Czyszczenie pamięci przed operacją...")
            clear_gpu_memory(verbose=self.verbose)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.clear_after:
            if self.verbose:
                print("[GPU] Czyszczenie pamięci po operacji...")
            clear_gpu_memory(verbose=self.verbose)
        return False  # Nie tłumimy wyjątków


@contextmanager
def gpu_memory_scope(clear_before: bool = True, clear_after: bool = True, verbose: bool = False):
    """
    Alternatywny context manager jako funkcja.

    Przykład:
        with gpu_memory_scope():
            heavy_model = load_heavy_model()
            result = heavy_model.run()
    """
    if clear_before:
        clear_gpu_memory(verbose=verbose)
    try:
        yield
    finally:
        if clear_after:
            clear_gpu_memory(verbose=verbose)
