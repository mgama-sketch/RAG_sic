"""Construye el notebook entregable sin depender de nbformat."""

from __future__ import annotations

import json
from pathlib import Path


def md(texto: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": texto.splitlines(keepends=True)}


def codigo(texto: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": texto.splitlines(keepends=True),
    }


CELDAS = [
    md(
        """# Proyecto RAG · Administración de Sistemas Informáticos (UNAL Manizales)

**Curso:** Sistemas Inteligentes Computacionales  
**Profesor:** Néstor Darío Duque Méndez  
**Autores:** Manuela Gama Peña · Franklin Libreros  
**Universidad Nacional de Colombia — Sede Manizales**

Este notebook ejecuta el sistema RAG construido para el parcial práctico: carga seis documentos (PDF y DOCX), construye índices, recupera fragmentos con localizador verificable, genera respuestas con citas y abstención explícita, y reproduce la evaluación de R0, R1, R2 y C0.

> **Seguridad:** la clave de OpenRouter se solicita en tiempo de ejecución. No está escrita en el notebook, en el código ni en el informe.
"""
    ),
    md(
        """## 1. Instalación

En Google Colab ejecute esta celda. En un entorno local, si ya instaló `requirements.txt`, puede omitirla.
"""
    ),
    codigo(
        """# En Colab: instala las dependencias del proyecto.
# En local puede comentar esta línea si ya ejecutó: pip install -r requirements.txt
!pip install -q -r requirements.txt
"""
    ),
    md(
        """## 2. Ubicación del proyecto y clave API

Suba la carpeta `proyecto_rag` a Colab o móntela en Drive. Ajuste `RAIZ` si es necesario. La clave se lee de `OPENROUTER_API_KEY` o se solicita con `getpass`; nunca se imprime.
"""
    ),
    codigo(
        """import os
import sys
from getpass import getpass
from pathlib import Path

RAIZ = Path.cwd()
if not (RAIZ / "src").exists():
    # Ajuste esta ruta si el proyecto está en otro directorio.
    RAIZ = Path("/content/proyecto_rag")

os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ))

if not os.getenv("OPENROUTER_API_KEY"):
    try:
        from google.colab import userdata

        os.environ["OPENROUTER_API_KEY"] = userdata.get("OPENROUTER_API_KEY")
    except Exception:
        os.environ["OPENROUTER_API_KEY"] = getpass("OpenRouter API key: ")

print("Directorio de trabajo:", RAIZ)
print("Clave configurada:", bool(os.getenv("OPENROUTER_API_KEY")))
"""
    ),
    md(
        """## 3. Configuraciones del protocolo

| ID | Cambio | Fragmentación | Recuperación | LLM |
|---|---|---|---|---|
| R0 | Base | 400 / 60 | densa, k=6 | GPT-4o-mini |
| R1 | Fragmentación | 200 / 30 | densa, k=6 | GPT-4o-mini |
| R2 | Recuperación | 400 / 60 | híbrida densa + TF-IDF (RRF), k=6 | GPT-4o-mini |
| C0 | Control sin RAG | — | — | GPT-4o-mini |
| E1 | Otro embedding | 400 / 60 | densa, k=6, all-MiniLM-L6-v2 | GPT-4o-mini |
| E2 | Otro LLM | 400 / 60 | densa, k=6 | Gemini 2.5 Flash |

Todas las configuraciones comparten corpus, preguntas, temperatura (0.0), límite de salida (500 tokens) y límite de contexto (3500 tokens).
"""
    ),
    codigo(
        """import pandas as pd
from IPython.display import Markdown, display

from src.config import CONFIGURACIONES

filas = []
for cid, cfg in CONFIGURACIONES.items():
    filas.append({
        "ID": cid,
        "Configuración": cfg.nombre,
        "Chunk": cfg.chunk_tokens if cfg.usar_recuperacion else "—",
        "Solape": cfg.chunk_overlap if cfg.usar_recuperacion else "—",
        "k": cfg.k if cfg.usar_recuperacion else 0,
        "Embeddings": cfg.modelo_embeddings.split("/")[-1] if cfg.usar_recuperacion else "—",
        "LLM": cfg.modelo_llm,
    })
display(pd.DataFrame(filas))
"""
    ),
    md(
        """## 4. Ingesta y verificación del corpus

Se detecta el formato por *magic bytes*: `faq_estudiantil.md` es en realidad un DOCX. Cada documento conserva página o sección/párrafo como localizador verificable.
"""
    ),
    codigo(
        """from src.carga_documentos import cargar_documentos, resumen_corpus

documentos = cargar_documentos()
resumen = resumen_corpus(documentos)
print("Archivos:", resumen["archivos"])
print("Formatos:", resumen["formatos"])
print("Páginas PDF:", resumen["paginas_pdf"])
print("Caracteres:", f"{resumen['caracteres']:,}")
display(pd.DataFrame(resumen["detalle"]))
"""
    ),
    md(
        """## 5. Fragmentación efectiva

El corte se hace por oraciones y se conserva el rango de páginas. R0 y R1 comparten la misma proporción de solapamiento (15 %).
"""
    ),
    codigo(
        """from src.procesamiento_texto import estadisticas_fragmentos, fragmentar_documentos

for max_tokens, overlap in [(400, 60), (200, 30)]:
    fragmentos = fragmentar_documentos(documentos, max_tokens, overlap)
    stats = estadisticas_fragmentos(fragmentos)
    print(f"Chunk={max_tokens}/{overlap}: {stats['fragmentos']} fragmentos · "
          f"mediana={stats['tokens_mediana']} tokens · máximo={stats['tokens_max']}")
"""
    ),
    md(
        """## 6. Índices vectoriales

Se usa `IndexFlatIP` de FAISS con vectores normalizados (similitud coseno exacta) y respaldo en NumPy. El índice se cachea y se invalida si cambia el corpus o la configuración.
"""
    ),
    codigo(
        """from src.base_vectorial import cargar_indice

for cid in ["R0", "R1"]:
    indice = cargar_indice(CONFIGURACIONES[cid])
    meta = indice.meta
    print(f"[{cid}] {meta['fragmentos']} fragmentos · {meta['dimension']} dimensiones · "
          f"{meta['modelo_embeddings']}")
"""
    ),
    md(
        """## 7. Demostración de recuperación

La consulta se codifica con el mismo modelo del índice. En R2 se fusionan la lista densa y una lista léxica TF-IDF mediante *Reciprocal Rank Fusion*.
"""
    ),
    codigo(
        """from src.recuperacion import Recuperador, construir_contexto

pregunta = "¿Qué título otorga el programa de Administración de Sistemas Informáticos y cuántos semestres dura?"

for cid in ["R0", "R1", "R2"]:
    recuperador = Recuperador(CONFIGURACIONES[cid])
    resultados = recuperador.buscar(pregunta)
    print(f"\\n=== {cid} ===")
    for r in resultados:
        print(f"[{r.etiqueta}] score={r.score:.4f} · {r.fragmento['archivo']}, {r.fragmento['localizador']}")
"""
    ),
    md(
        """## 8. Generación de una respuesta con citas

El prompt obliga a usar sólo los fragmentos, citar con `[F#]` y abstenerse con una frase exacta cuando la evidencia no alcanza. Esta celda consume una llamada real a OpenRouter.
"""
    ),
    codigo(
        """from src.generacion_respuestas import ClienteOpenRouter, responder

cliente = ClienteOpenRouter()
corrida = responder(
    pregunta=pregunta,
    config=CONFIGURACIONES["R0"],
    cliente=cliente,
    recuperador=Recuperador(CONFIGURACIONES["R0"]),
)
display(Markdown(corrida["respuesta_con_fuentes"]))
print("Tiempo total:", corrida["tiempo_total_s"], "s")
"""
    ),
    md(
        """## 9. Evaluación completa (opcional)

El protocolo ejecuta 9 preguntas × 4 configuraciones = 36 corridas. Cambie `EJECUTAR_EVALUACION` a `True` para volver a generarlas; cada corrida se guarda de forma incremental en `resultados/corridas.jsonl`. La evaluación manual se diligencia en `resultados/evaluacion_manual.csv`.
"""
    ),
    codigo(
        """EJECUTAR_EVALUACION = False

if EJECUTAR_EVALUACION:
    from src.evaluacion import ejecutar_evaluacion, generar_plantilla_manual, guardar_resultados

    ejecutar_evaluacion(configuraciones=["R0", "R1", "R2", "C0"], reanudar=True)
    guardar_resultados()
    generar_plantilla_manual()
    print("Corridas terminadas. Complete resultados/evaluacion_manual.csv y recalcule.")
else:
    print("Celda omitida para no consumir llamadas. Los resultados incluidos ya están calculados.")
"""
    ),
    md(
        """## 10. Métricas del protocolo

- **Cobertura de evidencia:** preguntas respondibles cuya evidencia aparece en los fragmentos recuperados y en el contexto, sobre 6.
- **Corrección:** respuestas correctas y completas, sobre 6; una respuesta parcial cuenta como incorrecta.
- **Respaldo de citas:** proporción de respuestas sustantivas RAG cuyas afirmaciones centrales están respaldadas por los fragmentos citados.
- **Abstención apropiada:** preguntas sin respuesta documental en las que el sistema reconoce que no puede responder y no inventa, sobre 3.
"""
    ),
    codigo(
        """from src.evaluacion import guardar_resultados

tabla, resumen = guardar_resultados()
display(resumen)
"""
    ),
    md("""## 11. Figuras del informe"""),
    codigo(
        """from src.figuras import generar_todas

for ruta in generar_todas():
    print(ruta)
"""
    ),
    codigo(
        """from IPython.display import Image

for nombre in ["fig_flujo.png", "fig_cobertura.png", "fig_calidad.png", "fig_latencia.png"]:
    display(Image(filename=f"resultados/figuras/{nombre}"))
"""
    ),
    md(
        """## 12. Lectura de resultados y reproducibilidad

Los resultados incluidos corresponden a corridas reales registradas en `resultados/corridas.jsonl`. La hoja `resultados/evaluacion_manual.csv` contiene la decisión de corrección, respaldo de citas y abstención para cada corrida, con una nota que explica los casos parciales.

**Uso de IA:** el equipo utilizó un asistente de IA para apoyar la implementación, la redacción y la revisión metodológica. Las decisiones de evaluación y la verificación de cada respuesta fueron revisadas contra los documentos y quedaron registradas fila a fila; el informe declara este uso.

**Seguridad:** no guarde la clave en el notebook ni en el repositorio. Rote cualquier clave que haya sido compartida en un chat o en un archivo público.
"""
    ),
]


def main() -> None:
    notebook = {
        "cells": CELDAS,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    ruta = Path(__file__).resolve().parents[1] / "Proyecto_RAG.ipynb"
    ruta.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Notebook escrito en {ruta}")


if __name__ == "__main__":
    main()
