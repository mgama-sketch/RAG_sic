"""Genera una revisión legible de todas las corridas para la evaluación manual."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluacion import cargar_corridas

ORDEN = ["R0", "R1", "R2", "C0", "E1", "E2"]


def main() -> None:
    runs = cargar_corridas()
    runs.sort(key=lambda r: (ORDEN.index(r["configuracion"]) if r["configuracion"] in ORDEN else 99, r["id_pregunta"]))
    lineas = ["# Revisión de respuestas", "", f"Corridas: {len(runs)}", ""]
    for run in runs:
        lineas.append(f"## {run['configuracion']}-{run['id_pregunta']} · {run.get('tipo_pregunta')}")
        lineas.append(f"**Pregunta:** {run['pregunta']}")
        lineas.append(f"**Esperada:** {run.get('respuesta_esperada', '')}")
        lineas.append(f"**Respuesta:** {(run.get('respuesta') or '').strip()}")
        lineas.append(
            f"**Abstención detectada:** {run.get('abstencion_detectada')} · "
            f"**Citas:** {run.get('citas_numeros')} · "
            f"**Inválidas:** {run.get('citas_invalidas')} · "
            f"**Error:** {run.get('error')}"
        )
        fuentes = [
            f"[{f['etiqueta']}] {f['archivo']}, {f['localizador']}"
            for f in (run.get("contexto") or {}).get("fragmentos", [])
        ]
        lineas.append("**Contexto:** " + " | ".join(fuentes))
        lineas.append("")
    ruta = Path("resultados/revision_respuestas.md")
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Escrito {ruta} con {len(runs)} corridas")


if __name__ == "__main__":
    main()
