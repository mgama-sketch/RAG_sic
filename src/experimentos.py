"""Ejecución de los experimentos adicionales E1 (embeddings) y E2 (LLM)."""

from __future__ import annotations

from .evaluacion import cargar_corridas, ejecutar_evaluacion


def ejecutar_experimentos(reanudar: bool = True, forzar_indice: bool = False) -> list[dict]:
    """Corre las 9 preguntas con E1 y E2 sobre el mismo protocolo."""
    print("Experimento E1: otro modelo de embeddings (se reconstruye el índice).")
    print("Experimento E2: otro LLM sobre la recuperación de R0.")
    corridas = ejecutar_evaluacion(
        configuraciones=["E1", "E2"],
        reanudar=reanudar,
        forzar_indice=forzar_indice,
    )
    print(f"Corridas nuevas: {len(corridas)}")
    return corridas


if __name__ == "__main__":
    ejecutar_experimentos()
