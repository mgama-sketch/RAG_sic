"""
Carga y limpieza de documentos.

Requisitos del enunciado que cubre este módulo:
- Procesar en una misma colección al menos tres archivos distintos y dos formatos.
- Extraer texto y conservar un localizador verificable (página, sección o párrafo).
- Detectar el formato por el contenido (magic bytes) y no sólo por la extensión:
  en el corpus entregado, ``faq_estudiantil.md`` es en realidad un DOCX.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from .config import DIR_DOCUMENTOS


@dataclass
class UnidadTexto:
    """Unidad mínima con localizador verificable (página o sección/párrafos)."""

    archivo: str
    formato: str
    localizador: str
    pagina: int | None
    seccion: str | None
    texto: str
    orden: int

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass
class Documento:
    id: str
    archivo: str
    ruta: str
    formato: str
    titulo: str
    unidades: list[UnidadTexto] = field(default_factory=list)
    caracteres: int = 0

    def como_dict(self) -> dict:
        datos = asdict(self)
        datos["unidades"] = [u.como_dict() for u in self.unidades]
        return datos


# ---------------------------------------------------------------------------
# Utilidades de limpieza
# ---------------------------------------------------------------------------
_PATRON_PAGINA = re.compile(
    r"^\s*(p[áa]gina\s+\d+(\s+de\s+\d+)?|\d+\s+de\s+\d+)\s*$", re.IGNORECASE
)
_PATRON_URL_FECHA = re.compile(r"^\s*(https?://\S+|\d{1,2}/\d{1,2}/\d{2,4}.*)$")


def limpiar_texto(texto: str) -> str:
    """Normaliza espacios, saltos y caracteres de control sin perder acentos."""
    texto = unicodedata.normalize("NFKC", texto)
    texto = texto.replace("\u00ad", "")  # guiones blandos
    texto = texto.replace("\ufeff", "")
    texto = re.sub(r"-\n(?=\w)", "", texto)  # palabras partidas al final de línea
    texto = re.sub(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f]", " ", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    lineas = [linea.strip() for linea in texto.splitlines()]
    texto = "\n".join(lineas)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _lineas_repetidas(paginas: list[str], umbral: float = 0.6) -> set[str]:
    """Detecta encabezados/pies que se repiten en la mayoría de páginas."""
    if len(paginas) < 3:
        return set()
    frecuencia: dict[str, int] = {}
    for pagina in paginas:
        vistas = {
            linea.strip()
            for linea in pagina.splitlines()
            if 3 <= len(linea.strip()) <= 120
        }
        for linea in vistas:
            frecuencia[linea] = frecuencia.get(linea, 0) + 1
    return {linea for linea, n in frecuencia.items() if n / len(paginas) >= umbral}


def _limpiar_pagina(texto: str, repetidas: set[str]) -> str:
    lineas = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            lineas.append("")
            continue
        if limpia in repetidas or _PATRON_PAGINA.match(limpia):
            continue
        lineas.append(limpia)
    return limpiar_texto("\n".join(lineas))


# ---------------------------------------------------------------------------
# Detectores y cargadores por formato
# ---------------------------------------------------------------------------
def detectar_formato(ruta: Path) -> str:
    """Detecta PDF, DOCX (contenedor ZIP/OOXML) o texto por magic bytes."""
    with open(ruta, "rb") as archivo:
        cabecera = archivo.read(8)
    if cabecera.startswith(b"%PDF"):
        return "PDF"
    if cabecera.startswith(b"PK"):
        try:
            with zipfile.ZipFile(ruta) as z:
                if "word/document.xml" in z.namelist():
                    return "DOCX"
        except zipfile.BadZipFile:
            pass
    return "MD"


def _cargar_pdf(ruta: Path) -> list[UnidadTexto]:
    documento = pymupdf.open(ruta)
    textos = [pagina.get_text() for pagina in documento]
    repetidas = _lineas_repetidas(textos)
    unidades: list[UnidadTexto] = []
    for numero, bruto in enumerate(textos, start=1):
        texto = _limpiar_pagina(bruto, repetidas)
        if len(texto) < 40:  # páginas vacías o portadas sin texto útil
            continue
        unidades.append(
            UnidadTexto(
                archivo=ruta.name,
                formato="PDF",
                localizador=f"p. {numero}",
                pagina=numero,
                seccion=None,
                texto=texto,
                orden=numero,
            )
        )
    return unidades


def _cargar_docx(ruta: Path) -> list[UnidadTexto]:
    import docx

    documento = docx.Document(str(ruta))
    parrafos = [limpiar_texto(p.text) for p in documento.paragraphs]
    parrafos = [p for p in parrafos if p]

    # El FAQ tiene una estructura explícita: encabezados numerados y preguntas.
    # Se agrupa cada pregunta con su respuesta para lograr localizadores útiles.
    es_faq = sum(1 for p in parrafos if p.endswith("?")) >= 5
    unidades: list[UnidadTexto] = []
    seccion = "Inicio"
    i = 0
    orden = 0

    def agregar(texto: str, inicio: int, fin: int) -> None:
        nonlocal orden
        orden += 1
        localizador = (
            f"sección «{seccion}», párrafo {inicio + 1}"
            if inicio == fin
            else f"sección «{seccion}», párrafos {inicio + 1}-{fin + 1}"
        )
        unidades.append(
            UnidadTexto(
                archivo=ruta.name,
                formato="DOCX",
                localizador=localizador,
                pagina=None,
                seccion=seccion,
                texto=texto,
                orden=orden,
            )
        )

    if es_faq:
        while i < len(parrafos):
            actual = parrafos[i]
            if re.match(r"^\d+\.\s+\S", actual) and len(actual) < 90 and not actual.endswith("."):
                seccion = actual
                i += 1
                continue
            if actual.endswith("?"):
                inicio = i
                bloque = [actual]
                i += 1
                while i < len(parrafos):
                    siguiente = parrafos[i]
                    if siguiente.endswith("?") or (
                        re.match(r"^\d+\.\s+\S", siguiente)
                        and len(siguiente) < 90
                        and not siguiente.endswith(".")
                    ):
                        break
                    bloque.append(siguiente)
                    i += 1
                agregar("\n".join(bloque), inicio, i - 1)
            else:
                agregar(actual, i, i)
                i += 1
    else:
        bloque: list[str] = []
        inicio = 0
        for i, parrafo in enumerate(parrafos):
            if re.match(r"^\d+\.\s+\S", parrafo) and len(parrafo) < 90:
                if bloque:
                    agregar("\n".join(bloque), inicio, i - 1)
                seccion = parrafo
                bloque = []
                inicio = i + 1
            else:
                bloque.append(parrafo)
        if bloque:
            agregar("\n".join(bloque), inicio, len(parrafos) - 1)
    return unidades


def _cargar_texto(ruta: Path) -> list[UnidadTexto]:
    texto = limpiar_texto(ruta.read_text(encoding="utf-8", errors="replace"))
    secciones = re.split(r"\n(?=#{1,6}\s)", texto)
    unidades: list[UnidadTexto] = []
    for i, seccion in enumerate(secciones, start=1):
        if len(seccion.strip()) < 30:
            continue
        primera = seccion.splitlines()[0].lstrip("# ").strip() or f"Sección {i}"
        unidades.append(
            UnidadTexto(
                archivo=ruta.name,
                formato="MD",
                localizador=f"sección «{primera}»",
                pagina=None,
                seccion=primera,
                texto=seccion.strip(),
                orden=i,
            )
        )
    return unidades


def cargar_documentos(directorio: Path | None = None) -> list[Documento]:
    """Carga todos los archivos del corpus y devuelve documentos con unidades."""
    directorio = Path(directorio or DIR_DOCUMENTOS)
    rutas = sorted(p for p in directorio.iterdir() if p.is_file() and not p.name.startswith("."))
    if not rutas:
        raise FileNotFoundError(f"No se encontraron archivos en {directorio}")

    documentos: list[Documento] = []
    for ruta in rutas:
        formato = detectar_formato(ruta)
        if formato == "PDF":
            unidades = _cargar_pdf(ruta)
        elif formato == "DOCX":
            unidades = _cargar_docx(ruta)
        else:
            unidades = _cargar_texto(ruta)

        titulo = unidades[0].texto.splitlines()[0][:160] if unidades else ruta.stem
        caracteres = sum(len(u.texto) for u in unidades)
        documentos.append(
            Documento(
                id=hashlib.sha1(ruta.name.encode("utf-8")).hexdigest()[:10],
                archivo=ruta.name,
                ruta=str(ruta),
                formato=formato,
                titulo=titulo,
                unidades=unidades,
                caracteres=caracteres,
            )
        )
    return documentos


def resumen_corpus(documentos: list[Documento]) -> dict:
    """Estadísticas usadas en el informe y en las pruebas de ingesta."""
    formatos = sorted({d.formato for d in documentos})
    return {
        "archivos": len(documentos),
        "formatos": formatos,
        "paginas_pdf": sum(1 for d in documentos if d.formato == "PDF" for _ in d.unidades),
        "unidades": sum(len(d.unidades) for d in documentos),
        "caracteres": sum(d.caracteres for d in documentos),
        "detalle": [
            {
                "archivo": d.archivo,
                "formato": d.formato,
                "unidades": len(d.unidades),
                "caracteres": d.caracteres,
            }
            for d in documentos
        ],
    }


if __name__ == "__main__":  # prueba rápida de ingesta
    import json

    docs = cargar_documentos()
    print(json.dumps(resumen_corpus(docs), ensure_ascii=False, indent=2))
