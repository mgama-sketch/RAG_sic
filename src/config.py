"""
Configuración central del proyecto RAG.

Este módulo concentra rutas, credenciales (leídas desde .env o desde los
secretos de Colab) y las cuatro configuraciones experimentales exigidas por
el enunciado: R0 (base), R1 (fragmentación), R2 (recuperación) y C0 (control
sin recuperación), además de los dos experimentos adicionales E1 (otro modelo
de embeddings) y E2 (otro LLM).

No contiene claves API: éstas se leen de variables de entorno.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[1]
DIR_DATOS = RAIZ / "data"
DIR_DOCUMENTOS = DIR_DATOS / "documentos_fuente"
DIR_RESULTADOS = RAIZ / "resultados"
DIR_INDICES = DIR_RESULTADOS / "indices"
DIR_FIGURAS = DIR_RESULTADOS / "figuras"
DIR_INFORME = RAIZ / "informe"

for _directorio in (DIR_DATOS, DIR_DOCUMENTOS, DIR_RESULTADOS, DIR_INDICES, DIR_FIGURAS, DIR_INFORME):
    _directorio.mkdir(parents=True, exist_ok=True)

# Carga .env si existe. En Colab se pueden usar los secretos del entorno.
load_dotenv(RAIZ / ".env")


def _secreto(nombre: str, defecto: str = "") -> str:
    """Lee un secreto del entorno o de los secretos de Colab, sin imprimirlo."""
    valor = os.getenv(nombre, "").strip()
    if valor:
        return valor
    try:  # pragma: no cover - sólo aplica en Google Colab
        from google.colab import userdata  # type: ignore

        return str(userdata.get(nombre)).strip()
    except Exception:
        return defecto


# ---------------------------------------------------------------------------
# Modelos y credenciales
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = _secreto("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

MODELO_LLM = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
MODELO_LLM_ALTERNO = os.getenv("OPENROUTER_MODEL_ALTERNO", "google/gemini-2.5-flash")

MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_EMBEDDINGS_ALTERNO = "sentence-transformers/all-MiniLM-L6-v2"

TEMPERATURA = float(os.getenv("TEMPERATURA", "0.0"))
MAX_TOKENS_SALIDA = int(os.getenv("MAX_TOKENS_SALIDA", "500"))

# Límite de contexto compartido por R0, R1 y R2. Se expresa en tokens del
# tokenizador o200k_base (el mismo usado por los modelos GPT-4o/4.1).
MAX_TOKENS_CONTEXTO = 3500

# Frase exacta que el sistema debe devolver cuando la evidencia no alcanza.
FRASE_SIN_INFORMACION = (
    "No tengo información suficiente en los documentos proporcionados para "
    "responder esta pregunta."
)

# Encabezados que OpenRouter recomienda para identificar la aplicación.
CABECERAS_OPENROUTER = {
    "HTTP-Referer": "https://localhost/proyecto-rag-unal",
    "X-Title": "Proyecto RAG - Sistemas Inteligentes Computacionales",
}


@dataclass(frozen=True)
class ConfiguracionRAG:
    """Parámetros efectivos de una configuración experimental."""

    id: str
    nombre: str
    hipotesis: str
    usar_recuperacion: bool = True
    tipo_recuperacion: str = "densa"  # "densa" | "hibrida"
    chunk_tokens: int = 400
    chunk_overlap: int = 60
    k: int = 6
    modelo_embeddings: str = MODELO_EMBEDDINGS
    modelo_llm: str = MODELO_LLM
    temperatura: float = TEMPERATURA
    max_tokens_salida: int = MAX_TOKENS_SALIDA
    max_tokens_contexto: int = MAX_TOKENS_CONTEXTO
    usar_citas: bool = True

    def como_dict(self) -> dict:
        return asdict(self)

    @property
    def etiqueta_corta(self) -> str:
        if not self.usar_recuperacion:
            return "C0 · sin recuperación"
        return (
            f"{self.id} · chunk={self.chunk_tokens}/{self.chunk_overlap} · "
            f"k={self.k} · {self.modelo_embeddings.split('/')[-1]}"
        )


# ---------------------------------------------------------------------------
# Configuraciones del protocolo
# ---------------------------------------------------------------------------
CONFIGURACIONES: dict[str, ConfiguracionRAG] = {
    "R0": ConfiguracionRAG(
        id="R0",
        nombre="Base: fragmentos de 400 tokens, solapamiento 60, k=6",
        hipotesis=(
            "Referencia estable. Con 400 tokens se conserva contexto suficiente "
            "para artículos y tablas, aunque puede introducir texto irrelevante."
        ),
        chunk_tokens=400,
        chunk_overlap=60,
        k=6,
    ),
    "R1": ConfiguracionRAG(
        id="R1",
        nombre="Fragmentación: 200 tokens, solapamiento 30 (misma proporción 15 %)",
        hipotesis=(
            "Al reducir el tamaño se espera mayor precisión en preguntas factuales "
            "directas, pero mayor riesgo de cortar artículos y de perder evidencia "
            "en preguntas que combinan documentos."
        ),
        chunk_tokens=200,
        chunk_overlap=30,
        k=6,
    ),
    "R2": ConfiguracionRAG(
        id="R2",
        nombre="Recuperación híbrida (densa + léxica TF-IDF, fusión RRF, k=6)",
        hipotesis=(
            "Combinar la similitud semántica con coincidencias léxicas debería "
            "recuperar mejor códigos, fechas y frases exactas (por ejemplo 4100552 "
            "o «diciembre 11»), mejorando la cobertura en preguntas que combinan "
            "documentos. El costo esperado es algo más de latencia y algún ruido "
            "léxico en consultas puramente conceptuales."
        ),
        tipo_recuperacion="hibrida",
        chunk_tokens=400,
        chunk_overlap=60,
        k=6,
    ),
    "C0": ConfiguracionRAG(
        id="C0",
        nombre="Control sin recuperación (sin RAG)",
        hipotesis=(
            "El LLM responderá con fluidez usando conocimiento paramétrico, pero "
            "fallará en datos institucionales específicos y no podrá abstenerse con "
            "la misma precisión porque no recibe evidencia documental."
        ),
        usar_recuperacion=False,
        usar_citas=False,
    ),
    "E1": ConfiguracionRAG(
        id="E1",
        nombre="Experimento: otro modelo de embeddings (all-MiniLM-L6-v2)",
        hipotesis=(
            "Un modelo entrenado principalmente en inglés representará peor las "
            "consultas en español y reducirá la cobertura de evidencia frente al "
            "modelo multilingüe de R0."
        ),
        modelo_embeddings=MODELO_EMBEDDINGS_ALTERNO,
        chunk_tokens=400,
        chunk_overlap=60,
        k=6,
    ),
    "E2": ConfiguracionRAG(
        id="E2",
        nombre="Experimento: otro LLM (Google Gemini 2.5 Flash) sobre R0",
        hipotesis=(
            "Un modelo distinto puede redactar mejor y citar con más precisión, pero "
            "también puede ser más propenso a completar con conocimiento externo; "
            "se evalúa con el mismo prompt y la misma recuperación de R0."
        ),
        modelo_llm=MODELO_LLM_ALTERNO,
        chunk_tokens=400,
        chunk_overlap=60,
        k=6,
    ),
}

CONFIGURACIONES_PRINCIPALES = ["R0", "R1", "R2", "C0"]
CONFIGURACIONES_EXPERIMENTOS = ["E1", "E2"]


def validar_configuracion() -> None:
    """Comprueba que existan los insumos mínimos antes de gastar llamadas API."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "Falta OPENROUTER_API_KEY. Copie .env.example a .env y escriba su clave, "
            "o configúrela como secreto de Colab."
        )
    if not DIR_DOCUMENTOS.exists() or not any(DIR_DOCUMENTOS.iterdir()):
        raise RuntimeError(f"No hay documentos en {DIR_DOCUMENTOS}")

