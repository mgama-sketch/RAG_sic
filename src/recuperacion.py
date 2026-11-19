"""
Recuperación semántica (y opcionalmente híbrida) y contexto aumentado.

- R0, R1 y los experimentos usan búsqueda densa: similitud coseno entre el
  embedding de la consulta y los embeddings de los fragmentos.
- R2 usa búsqueda híbrida: fusión por rangos recíprocos (RRF) de la lista densa
  y una lista léxica TF-IDF. Así se rescatan códigos, fechas y frases exactas
  que la representación semántica puede diluir, sin abandonar la semántica.

El contexto se numera [F1], [F2], ... y tiene un límite de tokens común a
R0, R1 y R2. Si hay recorte, se registra en la corrida.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .base_vectorial import cargar_indice
from .config import ConfiguracionRAG
from .embeddings import codificar_textos
from .procesamiento_texto import contar_tokens

try:
    import tiktoken

    _CODIFICADOR = tiktoken.get_encoding("o200k_base")
except Exception:  # pragma: no cover
    _CODIFICADOR = None


def recortar_tokens(texto: str, max_tokens: int) -> str:
    """Recorta un texto al número aproximado de tokens indicado."""
    if max_tokens <= 0:
        return ""
    if _CODIFICADOR is None:
        return " ".join(texto.split()[:max_tokens])
    tokens = _CODIFICADOR.encode(texto)
    if len(tokens) <= max_tokens:
        return texto
    return _CODIFICADOR.decode(tokens[:max_tokens]).rstrip()


@dataclass
class ResultadoRecuperacion:
    rank: int
    score: float
    fragmento: dict
    etiqueta: str = ""
    score_denso: float | None = None
    score_lexico: float | None = None
    rank_denso: int | None = None
    rank_lexico: int | None = None

    def como_dict(self) -> dict:
        return {
            "rank": self.rank,
            "score": round(self.score, 6),
            "score_denso": None if self.score_denso is None else round(self.score_denso, 6),
            "score_lexico": None if self.score_lexico is None else round(self.score_lexico, 6),
            "rank_denso": self.rank_denso,
            "rank_lexico": self.rank_lexico,
            "etiqueta": self.etiqueta,
            "chunk_id": self.fragmento["chunk_id"],
            "archivo": self.fragmento["archivo"],
            "localizador": self.fragmento["localizador"],
            "pagina": self.fragmento.get("pagina"),
            "pagina_fin": self.fragmento.get("pagina_fin"),
            "seccion": self.fragmento.get("seccion"),
            "n_tokens": self.fragmento["n_tokens"],
            "texto": self.fragmento["texto"],
        }


class Recuperador:
    """Fachada de búsqueda para una configuración."""

    def __init__(self, config: ConfiguracionRAG, forzar_indice: bool = False):
        self.config = config
        self.indice = cargar_indice(config, forzar=forzar_indice)
        self._tfidf = None
        self._matriz_lexica = None
        if config.tipo_recuperacion == "hibrida":
            self._preparar_tfidf()

    def _preparar_tfidf(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        textos = [f["texto"] for f in self.indice.fragmentos]
        self._tfidf = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            token_pattern=r"(?u)\b\w+\b",
        )
        self._matriz_lexica = self._tfidf.fit_transform(textos)

    def _buscar_densa(self, pregunta: str, k: int) -> list[tuple[int, float]]:
        vector = codificar_textos([pregunta], self.config.modelo_embeddings)[0]
        return self.indice.buscar(vector, k)

    def _buscar_lexica(self, pregunta: str, k: int) -> list[tuple[int, float]]:
        from sklearn.metrics.pairwise import cosine_similarity

        consulta = self._tfidf.transform([pregunta])
        similitudes = cosine_similarity(consulta, self._matriz_lexica).ravel()
        orden = np.argsort(-similitudes)[:k]
        return [(int(i), float(similitudes[i])) for i in orden if similitudes[i] > 0]

    def buscar(self, pregunta: str, k: int | None = None) -> list[ResultadoRecuperacion]:
        k = k or self.config.k
        if self.config.tipo_recuperacion == "densa":
            pares = self._buscar_densa(pregunta, k)
            return [
                ResultadoRecuperacion(
                    rank=rank,
                    score=score,
                    fragmento=self.indice.fragmentos[indice],
                    etiqueta=f"F{rank}",
                    score_denso=score,
                    rank_denso=rank,
                )
                for rank, (indice, score) in enumerate(pares, start=1)
            ]

        # Híbrida: recuperar una lista más amplia de cada mecanismo y fusionar.
        profundidad = max(20, k * 5)
        densos = self._buscar_densa(pregunta, profundidad)
        lexicos = self._buscar_lexica(pregunta, profundidad)
        acumulado: dict[int, dict] = {}
        for rank, (indice, score) in enumerate(densos, start=1):
            acumulado.setdefault(indice, {})["denso"] = (rank, score)
        for rank, (indice, score) in enumerate(lexicos, start=1):
            acumulado.setdefault(indice, {})["lexico"] = (rank, score)

        # Reciprocal Rank Fusion (k=60 es el valor habitual y no requiere calibrar escalas).
        fusionados = []
        for indice, datos in acumulado.items():
            rrf = 0.0
            if "denso" in datos:
                rrf += 1.0 / (60 + datos["denso"][0])
            if "lexico" in datos:
                rrf += 1.0 / (60 + datos["lexico"][0])
            fusionados.append((indice, rrf, datos))
        fusionados.sort(key=lambda x: (-x[1], x[0]))

        resultados = []
        for rank, (indice, rrf, datos) in enumerate(fusionados[:k], start=1):
            resultados.append(
                ResultadoRecuperacion(
                    rank=rank,
                    score=rrf,
                    fragmento=self.indice.fragmentos[indice],
                    etiqueta=f"F{rank}",
                    score_denso=datos.get("denso", (None, None))[1],
                    score_lexico=datos.get("lexico", (None, None))[1],
                    rank_denso=datos.get("denso", (None, None))[0],
                    rank_lexico=datos.get("lexico", (None, None))[0],
                )
            )
        return resultados


def construir_contexto(
    resultados: list[ResultadoRecuperacion],
    max_tokens: int,
) -> dict:
    """Numera y ensambla los fragmentos dentro del presupuesto de tokens."""
    bloques: list[str] = []
    usados: list[dict] = []
    tokens_usados = 0
    truncado = False
    omitidos: list[str] = []
    vistos: set[str] = set()

    for resultado in resultados:
        fragmento = resultado.fragmento
        if fragmento["chunk_id"] in vistos:
            omitidos.append(fragmento["chunk_id"])
            continue
        vistos.add(fragmento["chunk_id"])
        resultado.etiqueta = f"F{len(usados) + 1}"
        cabecera = (
            f"[{resultado.etiqueta}] Archivo: {fragmento['archivo']} | "
            f"Ubicación: {fragmento['localizador']}\n"
        )
        tokens_cabecera = contar_tokens(cabecera)
        disponible = max_tokens - tokens_usados - tokens_cabecera
        if disponible <= 20:
            omitidos.append(fragmento["chunk_id"])
            truncado = True
            continue
        texto = fragmento["texto"]
        tokens_texto = contar_tokens(texto)
        if tokens_texto > disponible:
            texto = recortar_tokens(texto, disponible)
            tokens_texto = contar_tokens(texto)
            truncado = True
        bloque = cabecera + texto
        bloques.append(bloque)
        tokens_usados += tokens_cabecera + tokens_texto
        usados.append(
            {
                "etiqueta": resultado.etiqueta,
                "chunk_id": fragmento["chunk_id"],
                "archivo": fragmento["archivo"],
                "localizador": fragmento["localizador"],
                "pagina": fragmento.get("pagina"),
                "pagina_fin": fragmento.get("pagina_fin"),
                "seccion": fragmento.get("seccion"),
                "score": round(resultado.score, 6),
                "score_denso": None
                if resultado.score_denso is None
                else round(resultado.score_denso, 6),
                "score_lexico": None
                if resultado.score_lexico is None
                else round(resultado.score_lexico, 6),
                "n_tokens": tokens_texto,
                "texto": texto,
            }
        )

    return {
        "texto": "\n\n".join(bloques),
        "fragmentos": usados,
        "tokens": tokens_usados,
        "truncado": truncado,
        "omitidos": omitidos,
    }


def formatear_fuentes(fragmentos: list[dict]) -> str:
    """Lista legible de fuentes para la respuesta final."""
    lineas = []
    for fragmento in fragmentos:
        lineas.append(
            f"[{fragmento['etiqueta']}] {fragmento['archivo']}, "
            f"{fragmento['localizador']}"
        )
    return "\n".join(lineas)
