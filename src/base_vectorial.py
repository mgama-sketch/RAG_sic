"""
Índice vectorial y persistencia.

Se implementa un índice plano de similitud coseno. Si ``faiss`` está
disponible se usa ``IndexFlatIP`` (búsqueda exacta); en caso contrario se
resuelve con NumPy. Para un corpus de decenas o cientos de fragmentos, la
búsqueda exacta es apropiada y evita aproximaciones que sesgarían la evaluación.

El índice se cachea en resultados/indices/ y se invalida si cambian el corpus,
el modelo de embeddings o los parámetros de fragmentación.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .carga_documentos import cargar_documentos
from .config import DIR_INDICES, ConfiguracionRAG
from .embeddings import codificar_textos
from .procesamiento_texto import (
    estadisticas_fragmentos,
    fragmentar_documentos,
    huella_configuracion,
)

try:
    import faiss  # type: ignore

    _FAISS_DISPONIBLE = True
except Exception:  # pragma: no cover - depende del entorno
    faiss = None
    _FAISS_DISPONIBLE = False


def huella_corpus(directorio=None) -> str:
    """Huella de los archivos del corpus (nombre, tamaño y fecha de modificación)."""
    from .config import DIR_DOCUMENTOS

    directorio = Path(directorio or DIR_DOCUMENTOS)
    partes = []
    for ruta in sorted(p for p in directorio.iterdir() if p.is_file()):
        stat = ruta.stat()
        partes.append(f"{ruta.name}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()[:12]


class IndiceVectorial:
    """Índice de fragmentos con metadatos y búsqueda coseno exacta."""

    def __init__(self, config: ConfiguracionRAG, directorio=None):
        self.config = config
        self.directorio = Path(directorio or DIR_INDICES)
        self.directorio.mkdir(parents=True, exist_ok=True)
        self.huella = huella_configuracion(
            config.chunk_tokens, config.chunk_overlap, config.modelo_embeddings
        )
        self.ruta_npz = self.directorio / f"indice_{self.huella}.npz"
        self.fragmentos: list[dict] = []
        self.matriz: np.ndarray | None = None
        self.meta: dict = {}
        self._faiss = None

    # ------------------------------------------------------------------
    # Construcción / carga
    # ------------------------------------------------------------------
    def construir(self, forzar: bool = False) -> "IndiceVectorial":
        corpus = huella_corpus()
        if not forzar and self.ruta_npz.exists():
            try:
                self.cargar()
                if self.meta.get("corpus") == corpus:
                    return self
            except Exception:
                pass  # caché corrupta: se reconstruye

        documentos = cargar_documentos()
        fragmentos = fragmentar_documentos(
            documentos,
            max_tokens=self.config.chunk_tokens,
            overlap=self.config.chunk_overlap,
        )
        textos = [f.texto for f in fragmentos]
        vectores = codificar_textos(
            textos, self.config.modelo_embeddings, mostrar_progreso=False
        )

        self.fragmentos = [f.como_dict() for f in fragmentos]
        self.matriz = vectores
        self.meta = {
            "corpus": corpus,
            "modelo_embeddings": self.config.modelo_embeddings,
            "chunk_tokens": self.config.chunk_tokens,
            "chunk_overlap": self.config.chunk_overlap,
            "dimension": int(vectores.shape[1]),
            "documentos": len(documentos),
            "fragmentos": len(fragmentos),
            "formatos": sorted({d.formato for d in documentos}),
            "estadisticas": {
                k: v
                for k, v in estadisticas_fragmentos(fragmentos).items()
                if k != "por_archivo"
            },
            "por_archivo": estadisticas_fragmentos(fragmentos)["por_archivo"],
            "faiss": _FAISS_DISPONIBLE,
        }
        self.guardar()
        return self

    def guardar(self) -> None:
        if self.matriz is None:
            raise RuntimeError("El índice no tiene embeddings")
        np.savez_compressed(
            self.ruta_npz,
            embeddings=self.matriz,
            fragmentos=np.array(json.dumps(self.fragmentos, ensure_ascii=False)),
            meta=np.array(json.dumps(self.meta, ensure_ascii=False)),
        )

    def cargar(self) -> "IndiceVectorial":
        with np.load(self.ruta_npz, allow_pickle=False) as datos:
            self.matriz = np.asarray(datos["embeddings"], dtype=np.float32)
            self.fragmentos = json.loads(str(datos["fragmentos"].item()))
            self.meta = json.loads(str(datos["meta"].item()))
        return self

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------
    def _construir_faiss(self):
        if not _FAISS_DISPONIBLE or self.matriz is None:
            return None
        if self._faiss is None:
            self._faiss = faiss.IndexFlatIP(self.matriz.shape[1])
            self._faiss.add(self.matriz)
        return self._faiss

    def buscar(self, vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Devuelve (índice, similitud coseno) de los k fragmentos más cercanos."""
        if self.matriz is None or not len(self.fragmentos):
            raise RuntimeError("Índice vacío: llame primero a construir()")
        vector = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        k = max(1, min(k, len(self.fragmentos)))
        indice = self._construir_faiss()
        if indice is not None:
            scores, indices = indice.search(vector, k)
            return [
                (int(i), float(s))
                for i, s in zip(indices[0], scores[0])
                if int(i) >= 0
            ]
        similitudes = (self.matriz @ vector.T).ravel()
        orden = np.argsort(-similitudes)[:k]
        return [(int(i), float(similitudes[i])) for i in orden]


def cargar_indice(config: ConfiguracionRAG, forzar: bool = False) -> IndiceVectorial:
    """Fachada usada por recuperación, evaluación y notebook."""
    return IndiceVectorial(config).construir(forzar=forzar)
