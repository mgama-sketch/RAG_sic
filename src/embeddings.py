"""
Generación de embeddings.

Se usa Sentence-Transformers en CPU. El mismo modelo codifica los fragmentos y
las consultas dentro de una configuración, tal como exige el enunciado.
Los vectores se normalizan L2 para que el producto interno sea equivalente a la
similitud coseno.
"""

from __future__ import annotations

import os
from functools import lru_cache

# Evita advertencias de paralelismo en Windows/Colab.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np


@lru_cache(maxsize=4)
def cargar_modelo(nombre: str):
    """Carga perezosa y cacheada de un modelo Sentence-Transformers."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(nombre, device="cpu")


def codificar_textos(
    textos: list[str],
    modelo: str,
    batch_size: int = 32,
    mostrar_progreso: bool = False,
) -> np.ndarray:
    """Codifica una lista de textos y devuelve una matriz float32 normalizada."""
    if not textos:
        raise ValueError("No hay textos para codificar")
    codificador = cargar_modelo(modelo)
    vectores = codificador.encode(
        textos,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=mostrar_progreso,
        convert_to_numpy=True,
    )
    return np.asarray(vectores, dtype=np.float32)


def dimension_modelo(modelo: str) -> int:
    """Dimensión de salida del modelo (se obtiene con una codificación mínima)."""
    return int(codificar_textos(["prueba"], modelo).shape[1])
