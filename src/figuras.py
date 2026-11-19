"""Genera las figuras del informe a partir de los resultados reales."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

from .config import DIR_FIGURAS, DIR_RESULTADOS

COLORES = {
    "R0": "#1f4e79",
    "R1": "#c55a11",
    "R2": "#2e75b6",
    "C0": "#7f7f7f",
    "E1": "#548235",
    "E2": "#7030a0",
}


def _resumen() -> pd.DataFrame:
    ruta = DIR_RESULTADOS / "resumen_configuraciones.csv"
    if not ruta.exists():
        raise FileNotFoundError(
            "Falta resultados/resumen_configuraciones.csv. Ejecute primero la evaluación."
        )
    return pd.read_csv(ruta, encoding="utf-8-sig")


def figura_cobertura(resumen: pd.DataFrame) -> Path:
    datos = resumen[resumen["configuracion"].isin(["R0", "R1", "R2"])]
    x = range(len(datos))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ancho = 0.36
    ax.bar(
        [i - ancho / 2 for i in x],
        datos["evidencia_recuperada_6"],
        ancho,
        label="Recuperada",
        color="#2e75b6",
    )
    ax.bar(
        [i + ancho / 2 for i in x],
        datos["evidencia_contexto_6"],
        ancho,
        label="Conservada en el contexto",
        color="#9dc3e6",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(datos["configuracion"])
    ax.set_ylim(0, 6.5)
    ax.set_ylabel("Preguntas con evidencia (de 6)")
    ax.set_title("Cobertura de evidencia por configuración")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=0.25)
    for i, fila in enumerate(datos.itertuples()):
        ax.text(i - ancho / 2, fila.evidencia_recuperada_6 + 0.1, str(fila.evidencia_recuperada_6), ha="center", fontsize=9)
        ax.text(i + ancho / 2, fila.evidencia_contexto_6 + 0.1, str(fila.evidencia_contexto_6), ha="center", fontsize=9)
    fig.tight_layout()
    ruta = DIR_FIGURAS / "fig_cobertura.png"
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return ruta


def figura_calidad(resumen: pd.DataFrame) -> Path:
    datos = resumen[resumen["configuracion"].isin(["R0", "R1", "R2", "C0"])]
    fig, ejes = plt.subplots(1, 2, figsize=(9.2, 4.1))
    colores = [COLORES.get(c, "#999999") for c in datos["configuracion"]]

    ejes[0].bar(datos["configuracion"], datos["correccion_6"], color=colores)
    ejes[0].set_ylim(0, 6.5)
    ejes[0].set_title("Corrección en preguntas respondibles")
    ejes[0].set_ylabel("Respuestas correctas (de 6)")
    ejes[0].grid(axis="y", alpha=0.25)
    for i, valor in enumerate(datos["correccion_6"]):
        if pd.notna(valor):
            ejes[0].text(i, valor + 0.1, str(int(valor)), ha="center", fontsize=9)

    ejes[1].bar(datos["configuracion"], datos["abstencion_3"], color=colores)
    ejes[1].set_ylim(0, 3.5)
    ejes[1].set_title("Abstención apropiada")
    ejes[1].set_ylabel("Preguntas sin respuesta (de 3)")
    ejes[1].grid(axis="y", alpha=0.25)
    for i, valor in enumerate(datos["abstencion_3"]):
        if pd.notna(valor):
            ejes[1].text(i, valor + 0.05, str(int(valor)), ha="center", fontsize=9)

    fig.suptitle("Calidad de las respuestas", fontsize=12)
    fig.tight_layout()
    ruta = DIR_FIGURAS / "fig_calidad.png"
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return ruta


def figura_latencia(resumen: pd.DataFrame) -> Path:
    datos = resumen[resumen["configuracion"].isin(["R0", "R1", "R2", "C0"])]
    x = range(len(datos))
    ancho = 0.36
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.bar(
        [i - ancho / 2 for i in x],
        datos["tiempo_medio_s"],
        ancho,
        label="Media",
        color="#548235",
    )
    ax.bar(
        [i + ancho / 2 for i in x],
        datos["tiempo_p95_s"],
        ancho,
        label="Percentil 95",
        color="#a9d18e",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(datos["configuracion"])
    ax.set_ylabel("Segundos por corrida")
    ax.set_title("Latencia de extremo a extremo")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    ruta = DIR_FIGURAS / "fig_latencia.png"
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return ruta


def figura_tokens(resumen: pd.DataFrame) -> Path:
    datos = resumen[resumen["configuracion"].isin(["R0", "R1", "R2", "C0"])]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.bar(
        datos["configuracion"],
        datos["tokens_prompt_medio"],
        color=[COLORES.get(c, "#999999") for c in datos["configuracion"]],
    )
    ax.set_ylabel("Tokens de entrada (promedio)")
    ax.set_title("Costo de contexto por configuración")
    ax.grid(axis="y", alpha=0.25)
    for i, valor in enumerate(datos["tokens_prompt_medio"]):
        if pd.notna(valor):
            ax.text(i, valor + 15, f"{valor:.0f}", ha="center", fontsize=9)
    fig.tight_layout()
    ruta = DIR_FIGURAS / "fig_tokens.png"
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return ruta


def figura_flujo() -> Path:
    """Diagrama de arquitectura y flujo de una consulta."""
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    cajas = [
        (0.15, 2.95, 1.55, 0.9, "Documentos\n(PDF + DOCX)", "#dbe5f1"),
        (2.0, 2.95, 1.55, 0.9, "Carga y\nlimpieza", "#dbe5f1"),
        (3.85, 2.95, 1.55, 0.9, "Fragmentación\n400/60 · 200/30", "#dbe5f1"),
        (5.7, 2.95, 1.55, 0.9, "Embeddings\n+ índice", "#dbe5f1"),
        (7.55, 2.95, 1.55, 0.9, "Recuperación\ndensa / híbrida", "#fce4d6"),
        (7.55, 1.25, 1.55, 0.9, "Contexto\n[F1]…[Fk]", "#fce4d6"),
        (5.55, 1.25, 1.55, 0.9, "LLM\n(OpenRouter)", "#e2efda"),
        (3.55, 1.25, 1.55, 0.9, "Respuesta\n+ citas", "#e2efda"),
        (1.55, 1.25, 1.55, 0.9, "Evaluación\n9 preguntas", "#fff2cc"),
    ]
    for x, y, w, h, texto, color in cajas:
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08",
                linewidth=1.1, edgecolor="#44546a", facecolor=color,
            )
        )
        ax.text(x + w / 2, y + h / 2, texto, ha="center", va="center", fontsize=9)

    flechas = [
        ((1.7, 3.4), (2.0, 3.4)),
        ((3.55, 3.4), (3.85, 3.4)),
        ((5.4, 3.4), (5.7, 3.4)),
        ((7.25, 3.4), (7.55, 3.4)),
        ((8.325, 2.95), (8.325, 2.15)),
        ((7.55, 1.7), (7.1, 1.7)),
        ((5.55, 1.7), (5.1, 1.7)),
        ((3.55, 1.7), (3.1, 1.7)),
    ]
    for inicio, fin in flechas:
        ax.annotate(
            "", xy=fin, xytext=inicio,
            arrowprops=dict(arrowstyle="->", color="#44546a", lw=1.3),
        )

    ax.text(5.25, 4.22, "Flujo del sistema RAG", ha="center", fontsize=14, weight="bold")
    ax.text(
        5.25, 0.55,
        "La misma consulta se ejecuta en R0, R1, R2 y C0; E1 cambia el modelo de embeddings y E2 el LLM.\n"
        "Cada corrida registra fragmentos, contexto, respuesta, citas, tiempos, tokens y costo.",
        ha="center", fontsize=8.5, color="#404040",
    )
    fig.tight_layout()
    ruta = DIR_FIGURAS / "fig_flujo.png"
    fig.savefig(ruta, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return ruta


def figura_corpus() -> Path:
    ruta_ingesta = DIR_RESULTADOS / "ingesta.json"
    if not ruta_ingesta.exists():
        raise FileNotFoundError("Falta resultados/ingesta.json")
    datos = json.loads(ruta_ingesta.read_text(encoding="utf-8"))
    detalle = datos["detalle"]
    nombres = [d["archivo"].replace(".pdf", "").replace("..", ".") for d in detalle]
    caracteres = [d["caracteres"] for d in detalle]
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    ax.barh(nombres, caracteres, color="#2e75b6")
    ax.set_xlabel("Caracteres extraídos")
    ax.set_title("Composición del corpus (6 archivos, 2 formatos)")
    ax.grid(axis="x", alpha=0.25)
    for i, valor in enumerate(caracteres):
        ax.text(valor + 400, i, f"{valor:,}", va="center", fontsize=8)
    fig.tight_layout()
    ruta = DIR_FIGURAS / "fig_corpus.png"
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return ruta


def generar_todas() -> list[Path]:
    DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    resumen = _resumen()
    rutas = [
        figura_flujo(),
        figura_corpus(),
        figura_cobertura(resumen),
        figura_calidad(resumen),
        figura_latencia(resumen),
        figura_tokens(resumen),
    ]
    return rutas


if __name__ == "__main__":
    for ruta in generar_todas():
        print(ruta)
