"""
Ejecución de las 36 corridas del protocolo y cálculo de métricas.

El enunciado define cuatro indicadores:
- Cobertura de evidencia (recuperada y conservada en el contexto).
- Corrección de las 6 preguntas respondibles.
- Respaldo de las citas en respuestas sustantivas.
- Abstención apropiada en las 3 preguntas sin respuesta.

La cobertura, la abstención detectada, las citas y los tiempos se calculan
automáticamente. La corrección y el respaldo de citas se registran en
``resultados/evaluacion_manual.csv`` tras leer cada respuesta; así el informe no
afirma resultados que no hayan sido verificados.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import (
    CONFIGURACIONES,
    CONFIGURACIONES_PRINCIPALES,
    DIR_RESULTADOS,
    FRASE_SIN_INFORMACION,
)
from .generacion_respuestas import ClienteOpenRouter, responder
from .recuperacion import Recuperador

RUTA_PREGUNTAS = Path(__file__).resolve().parents[1] / "data" / "preguntas_evaluacion.json"
RUTA_CORRIDAS = DIR_RESULTADOS / "corridas.jsonl"
RUTA_CSV = DIR_RESULTADOS / "corridas.csv"
RUTA_MANUAL = DIR_RESULTADOS / "evaluacion_manual.csv"
RUTA_METRICAS = DIR_RESULTADOS / "metricas_evaluacion.md"
RUTA_TABLA = DIR_RESULTADOS / "tabla_resultados.csv"
RUTA_RESUMEN = DIR_RESULTADOS / "resumen_configuraciones.csv"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^\w%.,]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def cargar_preguntas(ruta: Path | None = None) -> list[dict]:
    datos = json.loads(Path(ruta or RUTA_PREGUNTAS).read_text(encoding="utf-8"))
    preguntas = datos["preguntas"]
    conteo = {
        tipo: sum(1 for p in preguntas if p["tipo"] == tipo)
        for tipo in ("directa", "multidocumento", "sin_respuesta")
    }
    if len(preguntas) != 9 or conteo != {"directa": 3, "multidocumento": 3, "sin_respuesta": 3}:
        raise ValueError(f"El protocolo exige 3+3+3 preguntas; se encontró {conteo}")
    return preguntas


def _coincide(evidencia: dict, fragmento: dict) -> bool:
    """Comprueba archivo, página/sección y todos los términos de un pasaje."""
    if evidencia["archivo"] != fragmento.get("archivo"):
        return False
    pagina = evidencia.get("pagina")
    if pagina is not None:
        inicio = fragmento.get("pagina")
        fin = fragmento.get("pagina_fin") or inicio
        if inicio is None or not (inicio <= pagina <= fin):
            return False
    seccion = evidencia.get("seccion")
    if seccion:
        objetivo = _norm(seccion)
        propia = _norm(fragmento.get("seccion") or "")
        if objetivo not in propia and objetivo not in _norm(fragmento.get("texto", "")):
            return False
    texto = _norm(fragmento.get("texto", ""))
    return all(_norm(termino) in texto for termino in evidencia.get("terminos", []))


def cobertura(run: dict) -> dict:
    """Cobertura de evidencia recuperada y conservada en el contexto enviado."""
    evidencias = run.get("evidencia") or []
    if not evidencias:
        return {"aplica": False, "recuperada": None, "en_contexto": None, "detalle": []}
    recuperados = run.get("fragmentos_recuperados", [])
    contexto = (run.get("contexto") or {}).get("fragmentos", [])
    detalle = []
    for ev in evidencias:
        en_recuperado = any(_coincide(ev, f) for f in recuperados)
        en_contexto = any(_coincide(ev, f) for f in contexto)
        detalle.append(
            {
                "localizador": ev.get("localizador"),
                "archivo": ev.get("archivo"),
                "obligatoria": ev.get("obligatoria", True),
                "recuperada": en_recuperado,
                "en_contexto": en_contexto,
            }
        )
    obligatorias = [d for d in detalle if d["obligatoria"]]
    return {
        "aplica": True,
        "recuperada": all(d["recuperada"] for d in obligatorias) if obligatorias else None,
        "en_contexto": all(d["en_contexto"] for d in obligatorias) if obligatorias else None,
        "detalle": detalle,
    }


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
def _ids_existentes(ruta: Path) -> set[str]:
    if not ruta.exists():
        return set()
    ids = set()
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            try:
                ids.add(json.loads(linea)["id_corrida"])
            except Exception:
                continue
    return ids


def ejecutar_evaluacion(
    configuraciones: list[str] | None = None,
    reanudar: bool = True,
    forzar_indice: bool = False,
    ruta_salida: Path | None = None,
) -> list[dict]:
    """Ejecuta las 9 preguntas en cada configuración y guarda un JSONL incremental."""
    configuraciones = configuraciones or CONFIGURACIONES_PRINCIPALES
    preguntas = cargar_preguntas()
    ruta = Path(ruta_salida or RUTA_CORRIDAS)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    existentes = _ids_existentes(ruta) if reanudar else set()
    cliente = ClienteOpenRouter()
    ejecutadas: list[dict] = []

    for config_id in configuraciones:
        config = CONFIGURACIONES[config_id]
        recuperador = None
        if config.usar_recuperacion:
            print(f"\n[{config_id}] Construyendo/cargando índice…")
            recuperador = Recuperador(config, forzar_indice=forzar_indice)
            print(f"[{config_id}] Índice listo: {recuperador.indice.meta.get('fragmentos')} fragmentos.")

        for pregunta in preguntas:
            id_corrida = f"{config_id}-{pregunta['id']}"
            if id_corrida in existentes:
                print(f"  = {id_corrida} (ya existe, se omite)")
                continue
            print(f"  → {id_corrida}: {pregunta['pregunta'][:70]}…")
            try:
                corrida = responder(
                    pregunta=pregunta["pregunta"],
                    config=config,
                    cliente=cliente,
                    recuperador=recuperador,
                    metadatos_pregunta=pregunta,
                )
            except Exception as error:  # noqa: BLE001 - se registra para no perder la corrida
                corrida = {
                    "id_pregunta": pregunta["id"],
                    "tipo_pregunta": pregunta["tipo"],
                    "pregunta": pregunta["pregunta"],
                    "respuesta_esperada": pregunta.get("respuesta_esperada", ""),
                    "evidencia": pregunta.get("evidencia", []),
                    "configuracion": config_id,
                    "respuesta": "",
                    "respuesta_con_fuentes": "",
                    "citas": [],
                    "fragmentos_recuperados": [],
                    "contexto": {},
                    "error": f"{type(error).__name__}: {error}",
                    "tiempo_total_s": None,
                }
            corrida["id_corrida"] = id_corrida
            corrida["fecha_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            corrida["indice"] = recuperador.indice.meta if recuperador else {}
            with open(ruta, "a", encoding="utf-8") as archivo:
                archivo.write(json.dumps(corrida, ensure_ascii=False, default=str) + "\n")
            existentes.add(id_corrida)
            ejecutadas.append(corrida)
    return ejecutadas


def cargar_corridas(ruta: Path | None = None) -> list[dict]:
    ruta = Path(ruta or RUTA_CORRIDAS)
    if not ruta.exists():
        return []
    cargas: dict[str, dict] = {}
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            run = json.loads(linea)
            cargas[run.get("id_corrida", "")] = run
    return list(cargas.values())


def generar_plantilla_manual(ruta: Path | None = None) -> pd.DataFrame:
    """Crea la plantilla que el evaluador completa tras leer las respuestas."""
    corridas = cargar_corridas()
    filas = []
    for run in sorted(corridas, key=lambda r: (r["configuracion"], r["id_pregunta"])):
        filas.append(
            {
                "id_corrida": run.get("id_corrida"),
                "configuracion": run.get("configuracion"),
                "id_pregunta": run.get("id_pregunta"),
                "tipo_pregunta": run.get("tipo_pregunta"),
                "correccion_0_1": "",
                "respaldo_citas_0_1_NA": "",
                "abstencion_apropiada_0_1": "",
                "notas": "",
            }
        )
    tabla = pd.DataFrame(filas)
    tabla.to_csv(Path(ruta or RUTA_MANUAL), index=False, encoding="utf-8-sig")
    return tabla


def cargar_manual(ruta: Path | None = None) -> dict[str, dict]:
    ruta = Path(ruta or RUTA_MANUAL)
    if not ruta.exists():
        return {}
    tabla = pd.read_csv(ruta, encoding="utf-8-sig")
    resultado = {}
    for _, fila in tabla.iterrows():
        resultado[str(fila["id_corrida"])] = fila.to_dict()
    return resultado


def _entero(valor) -> int | None:
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto in {"", "NA", "N/A", "nan"}:
        return None
    try:
        return int(float(texto))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def calcular_metricas() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    corridas = cargar_corridas()
    preguntas = {p["id"]: p for p in cargar_preguntas()}
    manual = cargar_manual()
    if not corridas:
        raise RuntimeError("No hay corridas. Ejecute primero la evaluación.")

    filas = []
    for run in sorted(corridas, key=lambda r: (r["configuracion"], r["id_pregunta"])):
        cobertura_run = cobertura(run)
        decision = manual.get(run.get("id_corrida"), {})
        correccion = _entero(decision.get("correccion_0_1"))
        respaldo = _entero(decision.get("respaldo_citas_0_1_NA"))
        abstencion = _entero(decision.get("abstencion_apropiada_0_1"))
        es_sin_respuesta = run.get("tipo_pregunta") == "sin_respuesta"
        respuesta = (run.get("respuesta") or "").strip()
        filas.append(
            {
                "id_corrida": run.get("id_corrida"),
                "configuracion": run.get("configuracion"),
                "id_pregunta": run.get("id_pregunta"),
                "tipo": run.get("tipo_pregunta"),
                "pregunta": run.get("pregunta"),
                "respuesta": respuesta,
                "respuesta_esperada": preguntas.get(run.get("id_pregunta"), {}).get(
                    "respuesta_esperada", run.get("respuesta_esperada", "")
                ),
                "citas": ", ".join(
                    f"[{c['etiqueta']}] {c['archivo']}, {c['localizador']}"
                    for c in run.get("citas", [])
                ),
                "n_citas": len(run.get("citas", [])),
                "citas_invalidas": ", ".join(map(str, run.get("citas_invalidas", []))),
                "sin_citas": bool(run.get("sin_citas")),
                "abstencion_detectada": bool(run.get("abstencion_detectada")),
                "cobertura_recuperada": cobertura_run["recuperada"],
                "cobertura_contexto": cobertura_run["en_contexto"],
                "evidencia_detalle": json.dumps(cobertura_run["detalle"], ensure_ascii=False),
                "correccion": correccion,
                "respaldo_citas": respaldo,
                "abstencion_apropiada": abstencion,
                "tiempo_total_s": run.get("tiempo_total_s"),
                "tiempo_recuperacion_s": run.get("tiempo_recuperacion_s"),
                "tiempo_generacion_s": run.get("tiempo_generacion_s"),
                "tokens_prompt": (run.get("usage") or {}).get("prompt_tokens"),
                "tokens_salida": (run.get("usage") or {}).get("completion_tokens"),
                "costo_usd": (run.get("usage") or {}).get("cost"),
                "error": run.get("error"),
                "es_sin_respuesta": es_sin_respuesta,
                "es_sustantiva": bool(respuesta) and not run.get("abstencion_detectada"),
            }
        )
    tabla = pd.DataFrame(filas)

    resumen = []
    for config_id in list(dict.fromkeys(tabla["configuracion"])):
        sub = tabla[tabla["configuracion"] == config_id]
        respondibles = sub[~sub["es_sin_respuesta"]]
        sin_respuesta = sub[sub["es_sin_respuesta"]]
        rag = CONFIGURACIONES[config_id].usar_recuperacion

        def suma(columna, marco):
            valores = [v for v in marco[columna].tolist() if v is not None and not pd.isna(v)]
            return int(sum(valores)) if valores else None

        denominador_citas = len(
            [v for v in sub["respaldo_citas"].tolist() if v is not None and not pd.isna(v)]
        ) if rag else 0
        resumen.append(
            {
                "configuracion": config_id,
                "n": len(sub),
                "evidencia_recuperada_6": (
                    int(respondibles["cobertura_recuperada"].fillna(False).sum())
                    if rag else None
                ),
                "evidencia_contexto_6": (
                    int(respondibles["cobertura_contexto"].fillna(False).sum())
                    if rag else None
                ),
                "correccion_6": suma("correccion", respondibles),
                "correccion_pct": (
                    round(100 * suma("correccion", respondibles) / 6, 1)
                    if suma("correccion", respondibles) is not None else None
                ),
                "respaldo_citas": (
                    f"{suma('respaldo_citas', sub)}/{denominador_citas}"
                    if rag and denominador_citas else ("no aplica" if rag else "no aplica")
                ),
                "respaldo_citas_pct": (
                    round(100 * suma("respaldo_citas", sub) / denominador_citas, 1)
                    if rag and denominador_citas and suma("respaldo_citas", sub) is not None
                    else None
                ),
                "abstencion_3": suma("abstencion_apropiada", sin_respuesta),
                "abstencion_detectada_3": int(sin_respuesta["abstencion_detectada"].sum()),
                "falsas_abstenciones_6": int(respondibles["abstencion_detectada"].sum()),
                "tiempo_medio_s": round(sub["tiempo_total_s"].dropna().mean(), 3)
                if sub["tiempo_total_s"].notna().any() else None,
                "tiempo_mediana_s": round(sub["tiempo_total_s"].dropna().median(), 3)
                if sub["tiempo_total_s"].notna().any() else None,
                "tiempo_p95_s": round(sub["tiempo_total_s"].dropna().quantile(0.95), 3)
                if sub["tiempo_total_s"].notna().any() else None,
                "tokens_prompt_medio": round(sub["tokens_prompt"].dropna().mean(), 1)
                if sub["tokens_prompt"].notna().any() else None,
                "costo_total_usd": round(sub["costo_usd"].fillna(0).sum(), 6)
                if "costo_usd" in sub else None,
                "errores": int(sub["error"].notna().sum()),
            }
        )
    resumen_df = pd.DataFrame(resumen)
    return tabla, resumen_df, {
        "corridas": len(tabla),
        "configuraciones": list(resumen_df["configuracion"]),
        "manual_disponible": bool(manual),
        "frase_sin_informacion": FRASE_SIN_INFORMACION,
    }


def guardar_resultados() -> tuple[pd.DataFrame, pd.DataFrame]:
    tabla, resumen, info = calcular_metricas()
    tabla.to_csv(RUTA_TABLA, index=False, encoding="utf-8-sig")
    resumen.to_csv(RUTA_RESUMEN, index=False, encoding="utf-8-sig")

    columnas_csv = [
        "id_corrida", "configuracion", "id_pregunta", "tipo", "pregunta",
        "respuesta", "citas", "n_citas", "citas_invalidas", "sin_citas",
        "abstencion_detectada", "cobertura_recuperada", "cobertura_contexto",
        "correccion", "respaldo_citas", "abstencion_apropiada",
        "tiempo_total_s", "tiempo_recuperacion_s", "tiempo_generacion_s",
        "tokens_prompt", "tokens_salida", "costo_usd", "error",
    ]
    tabla[columnas_csv].to_csv(RUTA_CSV, index=False, encoding="utf-8-sig")

    lineas = [
        "# Métricas de evaluación",
        "",
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Corridas registradas: **{info['corridas']}**. "
        f"Evaluación manual disponible: **{'sí' if info['manual_disponible'] else 'no'}**.",
        "",
        "## Resumen por configuración",
        "",
        resumen.to_markdown(index=False),
        "",
        "## Definiciones",
        "",
        "- **Cobertura de evidencia (recuperada / contexto):** preguntas respondibles "
        "cuyos pasajes necesarios aparecen en los fragmentos recuperados y, además, "
        "quedan dentro del contexto enviado al LLM. Se reporta sobre 6.",
        "- **Corrección:** respuestas correctas y completas frente a la referencia, "
        "sobre 6. Una respuesta parcial o una abstención cuenta como incorrecta.",
        "- **Respaldo de citas:** proporción de respuestas sustantivas RAG cuyas "
        "afirmaciones centrales están respaldadas por los pasajes citados.",
        "- **Abstención apropiada:** preguntas sin respuesta documental en las que el "
        "sistema reconoce que no puede responder y no añade una respuesta sin respaldo, "
        "sobre 3.",
        "",
        "## Nota metodológica",
        "",
        "La cobertura, la abstención detectada, las citas y los tiempos son cálculos "
        "automáticos. La corrección y el respaldo de citas se diligenciaron tras leer "
        "cada respuesta y contrastarla con la referencia y los fragmentos citados; "
        "por eso el informe puede auditar cada fila de `tabla_resultados.csv`.",
    ]
    RUTA_METRICAS.write_text("\n".join(lineas), encoding="utf-8")
    return tabla, resumen
