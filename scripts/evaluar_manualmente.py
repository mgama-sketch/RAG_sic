"""Diligencia la evaluación manual a partir de la lectura de las 36 respuestas.

Cada decisión se tomó contrastando la respuesta con la referencia y con los
fragmentos efectivamente citados. Los comentarios de la columna ``notas``
explican los casos parciales. Esta hoja es la fuente de verdad de las métricas
de corrección, respaldo de citas y abstención apropiada.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluacion import RUTA_MANUAL, cargar_corridas

# (correccion, respaldo_citas, abstencion, nota)
DECISIONES: dict[str, tuple[str, str, str, str]] = {
    # R0 -----------------------------------------------------------------
    "R0-D1": ("1", "1", "", "Título y duración correctos; citas F1 y F2 pertinentes."),
    "R0-D2": ("1", "1", "", "3.0 y tres evaluaciones correctos; citas F1 y F2 pertinentes."),
    "R0-D3": ("1", "1", "", "24 de agosto y 4 de septiembre correctos; citas F2 y F4 pertinentes."),
    "R0-M1": (
        "0", "1", "",
        "Responde sólo los documentos del instructivo; no recuperó el Artículo 13 y se abstuvo de la segunda parte. Parcial.",
    ),
    "R0-M2": (
        "0", "0", "",
        "Omite la autorización del Consejo de Facultad y la solicitud justificada; además cita la fecha en F2 (Estatuto) cuando está en F1 (calendario).",
    ),
    "R0-M3": (
        "0", "NA", "",
        "Se abstiene: el contexto no incluyó el Artículo 52 ni la ficha del programa. Falso negativo.",
    ),
    "R0-U1": ("", "NA", "1", "Abstención exacta, sin inventar correo."),
    "R0-U2": ("", "NA", "1", "Abstención exacta, sin inventar montos."),
    "R0-U3": ("", "NA", "1", "Abstención exacta, sin inventar horario."),
    # R1 -----------------------------------------------------------------
    "R1-D1": ("1", "1", "", "Título y duración correctos; citas pertinentes."),
    "R1-D2": ("1", "1", "", "3.0 y tres evaluaciones correctos; citas pertinentes."),
    "R1-D3": ("1", "1", "", "Fechas correctas; F5 contiene ambos datos."),
    "R1-M1": (
        "0", "1", "",
        "Sólo responde los documentos del instructivo; el Artículo 13 quedó fuera del contexto. Parcial.",
    ),
    "R1-M2": (
        "0", "1", "",
        "Recupera la autorización del Consejo, pero no la fecha límite aunque el calendario estaba en el contexto. Parcial.",
    ),
    "R1-M3": (
        "0", "NA", "",
        "Se abstiene: no recuperó el Artículo 52 ni la duración. Falso negativo.",
    ),
    "R1-U1": ("", "NA", "1", "Abstención exacta."),
    "R1-U2": ("", "NA", "1", "Abstención exacta."),
    "R1-U3": ("", "NA", "1", "Abstención exacta."),
    # R2 -----------------------------------------------------------------
    "R2-D1": ("1", "1", "", "Título y duración correctos; citas pertinentes."),
    "R2-D2": ("1", "1", "", "3.0 y tres evaluaciones correctos; citas pertinentes."),
    "R2-D3": ("1", "1", "", "Fechas correctas; citas F2 y F4 pertinentes."),
    "R2-M1": (
        "0", "1", "",
        "Sólo responde los documentos del instructivo; el Artículo 13 no fue recuperado. Parcial.",
    ),
    "R2-M2": (
        "0", "1", "",
        "Autorización y fecha correctas, pero omite el requisito de mantener el mínimo de créditos. Parcial.",
    ),
    "R2-M3": (
        "1", "1", "",
        "Responde ambos requisitos del Artículo 52 y la duración; citas F2 y F3 pertinentes.",
    ),
    "R2-U1": ("", "NA", "1", "Abstención exacta."),
    "R2-U2": ("", "NA", "1", "Abstención exacta."),
    "R2-U3": ("", "NA", "1", "Abstención exacta."),
    # C0 -----------------------------------------------------------------
    "C0-D1": (
        "1", "NA", "",
        "Acierta título y duración con conocimiento paramétrico; añade una advertencia de verificación.",
    ),
    "C0-D2": (
        "1", "NA", "",
        "Acierta 3.0 y tres evaluaciones con conocimiento general, aunque no puede citar la norma.",
    ),
    "C0-D3": (
        "0", "NA", "",
        "No responde las fechas específicas de 2026-2; reconoce no tener acceso al calendario.",
    ),
    "C0-M1": (
        "0", "NA", "",
        "Da documentos y acciones genéricos, no los del instructivo y el Artículo 13. Parcial/incorrecto.",
    ),
    "C0-M2": (
        "0", "NA", "",
        "Condiciones genéricas, sin fecha ni requisito de créditos. Incorrecto.",
    ),
    "C0-M3": (
        "0", "NA", "",
        "Requisitos genéricos y duración aproximada (8-10 semestres); no responde el Artículo 52. Incorrecto.",
    ),
    "C0-U1": (
        "", "NA", "1",
        "Reconoce no tener acceso y no inventa un correo; el detector automático no lo marca porque usa otra fórmula.",
    ),
    "C0-U2": (
        "", "NA", "1",
        "Reconoce no tener acceso y no inventa montos ni descuentos.",
    ),
    "C0-U3": (
        "", "NA", "1",
        "Reconoce no tener acceso y no inventa horarios.",
    ),
    # E1: otro modelo de embeddings --------------------------------------
    "E1-D1": ("1", "1", "", "Título y duración correctos; citas F2 y F3 pertinentes."),
    "E1-D2": ("1", "1", "", "3.0 y tres evaluaciones correctos; citas F1 y F2 pertinentes."),
    "E1-D3": (
        "0", "1", "",
        "Confunde la cancelación justificada con el período de adición/cancelación y no da el 4 de septiembre. Parcial/incorrecto.",
    ),
    "E1-M1": (
        "0", "1", "",
        "Sólo responde los documentos del instructivo; no recuperó el Artículo 13. Parcial.",
    ),
    "E1-M2": (
        "0", "NA", "",
        "Se abstiene aunque el contexto contenía el calendario y el Estatuto. Falso negativo.",
    ),
    "E1-M3": (
        "0", "NA", "",
        "Se abstiene; no recuperó el Artículo 52. Falso negativo.",
    ),
    "E1-U1": ("", "NA", "1", "Abstención exacta."),
    "E1-U2": ("", "NA", "1", "Abstención exacta."),
    "E1-U3": ("", "NA", "1", "Abstención exacta."),
    # E2: otro LLM --------------------------------------------------------
    "E2-D1": ("1", "1", "", "Título y duración correctos; citas F1 y F2 pertinentes."),
    "E2-D2": ("1", "1", "", "3.0 y tres evaluaciones correctos; citas pertinentes."),
    "E2-D3": ("1", "1", "", "24 de agosto y 4 de septiembre correctos; citas F2 y F4."),
    "E2-M1": (
        "0", "1", "",
        "Sólo responde los documentos del instructivo; no recuperó el Artículo 13. Parcial.",
    ),
    "E2-M2": (
        "0", "0", "",
        "Confunde el umbral del 50 % con la 'segunda semana', omite el mínimo de créditos y cita F2 para una condición que no está formulada así.",
    ),
    "E2-M3": (
        "0", "NA", "",
        "Se abstiene; no recuperó el Artículo 52. Falso negativo.",
    ),
    "E2-U1": ("", "NA", "1", "Abstención exacta."),
    "E2-U2": ("", "NA", "1", "Abstención exacta."),
    "E2-U3": ("", "NA", "1", "Abstención exacta."),
}


def main() -> None:
    corridas = cargar_corridas()
    filas = []
    for run in sorted(corridas, key=lambda r: (r["configuracion"], r["id_pregunta"])):
        clave = run["id_corrida"]
        if clave not in DECISIONES:
            raise KeyError(f"Falta decisión manual para {clave}")
        correccion, respaldo, abstencion, nota = DECISIONES[clave]
        filas.append(
            {
                "id_corrida": clave,
                "configuracion": run["configuracion"],
                "id_pregunta": run["id_pregunta"],
                "tipo_pregunta": run["tipo_pregunta"],
                "correccion_0_1": correccion,
                "respaldo_citas_0_1_NA": respaldo,
                "abstencion_apropiada_0_1": abstencion,
                "notas": nota,
            }
        )
    tabla = pd.DataFrame(filas)
    tabla.to_csv(RUTA_MANUAL, index=False, encoding="utf-8-sig")
    print(f"Escritas {len(tabla)} filas en {RUTA_MANUAL}")


if __name__ == "__main__":
    main()
