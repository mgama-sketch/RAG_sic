"""
Punto de entrada del proyecto RAG.

Ejemplos:
    python -m src.main ingesta
    python -m src.main indexar --configs R0,R1,R2
    python -m src.main consultar --config R2 --pregunta "¿Cuándo inician las clases?"
    python -m src.main evaluar --configs R0,R1,R2,C0
    python -m src.main plantilla
    python -m src.main metricas
    python -m src.main todo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .carga_documentos import cargar_documentos, resumen_corpus
from .config import CONFIGURACIONES, CONFIGURACIONES_PRINCIPALES, DIR_RESULTADOS, validar_configuracion
from .evaluacion import (
    cargar_corridas,
    ejecutar_evaluacion,
    generar_plantilla_manual,
    guardar_resultados,
)
from .generacion_respuestas import ClienteOpenRouter, responder
from .recuperacion import Recuperador, formatear_fuentes


def _configs(texto: str | None) -> list[str]:
    ids = [c.strip().upper() for c in (texto or "").split(",") if c.strip()]
    if not ids:
        return list(CONFIGURACIONES_PRINCIPALES)
    desconocidas = [c for c in ids if c not in CONFIGURACIONES]
    if desconocidas:
        raise SystemExit(f"Configuraciones desconocidas: {desconocidas}")
    return ids


def comando_ingesta(_args) -> None:
    documentos = cargar_documentos()
    resumen = resumen_corpus(documentos)
    ruta = DIR_RESULTADOS / "ingesta.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    if resumen["archivos"] < 3 or len(resumen["formatos"]) < 2:
        raise SystemExit("El corpus no cumple el mínimo de 3 archivos y 2 formatos.")
    print(f"\nResumen guardado en {ruta}")


def comando_indexar(args) -> None:
    for config_id in _configs(args.configs):
        config = CONFIGURACIONES[config_id]
        if not config.usar_recuperacion:
            print(f"[{config_id}] Sin recuperación: no requiere índice.")
            continue
        recuperador = Recuperador(config, forzar_indice=args.forzar)
        meta = recuperador.indice.meta
        print(
            f"[{config_id}] {meta['fragmentos']} fragmentos · "
            f"{meta['dimension']} dimensiones · {meta['modelo_embeddings']}"
        )


def comando_consultar(args) -> None:
    validar_configuracion()
    config = CONFIGURACIONES[args.config.upper()]
    cliente = ClienteOpenRouter()
    recuperador = Recuperador(config) if config.usar_recuperacion else None
    corrida = responder(args.pregunta, config, cliente, recuperador)
    print(f"\nPregunta: {args.pregunta}\n")
    print(corrida["respuesta"] or corrida.get("error", ""))
    if corrida.get("fragmentos_recuperados"):
        print("\nFragmentos recuperados (orden):")
        for fragmento in corrida["fragmentos_recuperados"]:
            print(
                f"  [{fragmento['etiqueta']}] score={fragmento['score']:.3f} · "
                f"{fragmento['archivo']}, {fragmento['localizador']}"
            )
    if corrida.get("citas"):
        print("\nFuentes citadas:")
        print(formatear_fuentes(corrida["citas"]))
    print(f"\nTiempo total: {corrida['tiempo_total_s']} s")


def comando_evaluar(args) -> None:
    validar_configuracion()
    ejecutar_evaluacion(
        configuraciones=_configs(args.configs),
        reanudar=not args.sin_reanudar,
        forzar_indice=args.forzar,
    )
    tabla, resumen = guardar_resultados()
    print("\nResumen:")
    print(resumen.to_string(index=False))
    if not args.sin_plantilla:
        generar_plantilla_manual()
        print("\nPlantilla manual: resultados/evaluacion_manual.csv")


def comando_experimentos(args) -> None:
    from .experimentos import ejecutar_experimentos

    validar_configuracion()
    ejecutar_experimentos(reanudar=not args.sin_reanudar, forzar_indice=args.forzar)
    guardar_resultados()
    print("Experimentos terminados. Revise resultados/tabla_resultados.csv")


def comando_plantilla(_args) -> None:
    tabla = generar_plantilla_manual()
    print(f"Plantilla creada con {len(tabla)} filas: resultados/evaluacion_manual.csv")


def comando_metricas(_args) -> None:
    tabla, resumen = guardar_resultados()
    print(resumen.to_string(index=False))
    print(f"\nDetalle: resultados/tabla_resultados.csv ({len(tabla)} corridas)")


def comando_todo(args) -> None:
    comando_ingesta(args)
    comando_indexar(args)
    comando_evaluar(args)
    if not args.sin_experimentos:
        comando_experimentos(args)
    print("\nListo. Complete resultados/evaluacion_manual.csv y ejecute:")
    print("  python -m src.main metricas")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Proyecto RAG · Sistema Inteligente Computacional")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("ingesta", help="Carga el corpus y muestra el resumen")
    p.set_defaults(func=comando_ingesta)

    p = sub.add_parser("indexar", help="Construye los índices vectoriales")
    p.add_argument("--configs", default=None)
    p.add_argument("--forzar", action="store_true")
    p.set_defaults(func=comando_indexar)

    p = sub.add_parser("consultar", help="Hace una pregunta al sistema")
    p.add_argument("--config", default="R0")
    p.add_argument("--pregunta", required=True)
    p.set_defaults(func=comando_consultar)

    p = sub.add_parser("evaluar", help="Ejecuta las 9 preguntas en las configuraciones")
    p.add_argument("--configs", default=None)
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--sin-reanudar", action="store_true")
    p.add_argument("--sin-plantilla", action="store_true")
    p.set_defaults(func=comando_evaluar)

    p = sub.add_parser("experimentos", help="Ejecuta E1 y E2")
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--sin-reanudar", action="store_true")
    p.set_defaults(func=comando_experimentos)

    p = sub.add_parser("plantilla", help="Genera la plantilla de evaluación manual")
    p.set_defaults(func=comando_plantilla)

    p = sub.add_parser("metricas", help="Recalcula métricas y tablas")
    p.set_defaults(func=comando_metricas)

    p = sub.add_parser("todo", help="Ingesta + índices + evaluación + experimentos")
    p.add_argument("--configs", default=None)
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--sin-reanudar", action="store_true")
    p.add_argument("--sin-plantilla", action="store_true")
    p.add_argument("--sin-experimentos", action="store_true")
    p.set_defaults(func=comando_todo)
    return parser


def main() -> None:
    args = construir_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
