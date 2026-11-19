"""
Fragmentación (chunking) y conteo de tokens.

Decisiones de diseño:
- La unidad de corte es la oración, no el carácter. Se acumulan oraciones hasta
  alcanzar el límite y el solapamiento se construye repitiendo las últimas
  oraciones, evitando fragmentos que empiecen o terminen a mitad de palabra.
- En PDF se permite que un fragmento abarque páginas consecutivas para acercarse
  al tamaño nominal (400 o 200 tokens). El localizador se expresa como rango
  verificable: ``p. 6`` o ``p. 6-7``.
- En DOCX/MD se fragmenta dentro de cada sección o par pregunta-respuesta para no
  mezclar temas y conservar un localizador de sección y párrafos.

El conteo usa el tokenizador o200k_base como aproximación común a todas las
configuraciones; se documenta que el proveedor puede tokenizar de forma distinta.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import asdict, dataclass

from .carga_documentos import Documento

try:
    import tiktoken

    _CODIFICADOR = tiktoken.get_encoding("o200k_base")
except Exception:  # pragma: no cover - sólo si falta la dependencia
    _CODIFICADOR = None


def contar_tokens(texto: str) -> int:
    """Cuenta tokens con o200k_base; si no está disponible, aproxima por palabras."""
    if _CODIFICADOR is not None:
        return len(_CODIFICADOR.encode(texto))
    return max(1, len(re.findall(r"\w+|[^\w\s]", texto)))


@dataclass
class Fragmento:
    chunk_id: str
    documento_id: str
    archivo: str
    formato: str
    localizador: str
    pagina: int | None
    pagina_fin: int | None
    seccion: str | None
    texto: str
    n_tokens: int
    orden: int

    def como_dict(self) -> dict:
        return asdict(self)


_PATRON_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡«\"(])|\n{2,}")


def _partir_oracion(oracion: str, max_tokens: int) -> list[str]:
    """Divide una oración gigantesca (tablas, listas) en trozos por palabras."""
    if contar_tokens(oracion) <= max_tokens:
        return [oracion]
    palabras = oracion.split()
    trozos: list[str] = []
    actual: list[str] = []
    for palabra in palabras:
        candidato = " ".join(actual + [palabra])
        if actual and contar_tokens(candidato) > max_tokens:
            trozos.append(" ".join(actual))
            actual = [palabra]
        else:
            actual.append(palabra)
    if actual:
        trozos.append(" ".join(actual))
    return trozos


def _oraciones(texto: str, max_tokens: int) -> list[str]:
    partes = [p.strip() for p in _PATRON_ORACION.split(texto) if p and p.strip()]
    resultado: list[str] = []
    for parte in partes:
        resultado.extend(_partir_oracion(parte, max_tokens))
    return resultado


def _ventanas(items: list[dict], max_tokens: int, overlap: int) -> list[list[dict]]:
    """Ventanas deslizantes de elementos (oración + metadatos de origen)."""
    ventanas: list[list[dict]] = []
    i = 0
    while i < len(items):
        actual: list[dict] = []
        tokens_actual = 0
        j = i
        while j < len(items):
            t = items[j]["tokens"]
            if actual and tokens_actual + t > max_tokens:
                break
            actual.append(items[j])
            tokens_actual += t
            j += 1
        if not actual:
            actual = [items[i]]
            j = i + 1
        ventanas.append(actual)

        if j >= len(items):
            break

        # Retroceder oraciones completas hasta agotar el presupuesto de solape.
        k = j - 1
        tokens_solape = 0
        while k > i:
            t = items[k]["tokens"]
            if tokens_solape + t > overlap:
                break
            tokens_solape += t
            k -= 1
        i = max(k + 1, i + 1)
    return ventanas


def _crear_fragmento(
    documento: Documento,
    ventana: list[dict],
    contador: int,
    orden: int,
) -> Fragmento | None:
    texto = " ".join(item["texto"] for item in ventana).strip()
    if len(texto) < 30:
        return None
    paginas = [item["pagina"] for item in ventana if item["pagina"] is not None]
    secciones = [item["seccion"] for item in ventana if item["seccion"]]
    if paginas:
        inicio, fin = min(paginas), max(paginas)
        localizador = f"p. {inicio}" if inicio == fin else f"p. {inicio}-{fin}"
    else:
        inicio = fin = None
        localizador = ventana[0]["localizador"]
    return Fragmento(
        chunk_id=f"{documento.id}-{contador:04d}",
        documento_id=documento.id,
        archivo=documento.archivo,
        formato=documento.formato,
        localizador=localizador,
        pagina=inicio,
        pagina_fin=fin,
        seccion=secciones[0] if secciones and len(set(secciones)) == 1 else None,
        texto=texto,
        n_tokens=contar_tokens(texto),
        orden=orden,
    )


def fragmentar_documentos(
    documentos: list[Documento],
    max_tokens: int = 400,
    overlap: int = 60,
) -> list[Fragmento]:
    """Convierte documentos en fragmentos con metadatos de trazabilidad."""
    if max_tokens <= 0:
        raise ValueError("max_tokens debe ser positivo")
    if overlap < 0 or overlap >= max_tokens:
        raise ValueError("overlap debe estar en [0, max_tokens)")

    fragmentos: list[Fragmento] = []
    for documento in documentos:
        contador = 0

        if documento.formato == "PDF":
            # Flujo continuo de oraciones con la página de origen de cada una.
            items: list[dict] = []
            for unidad in documento.unidades:
                for oracion in _oraciones(unidad.texto, max_tokens):
                    items.append(
                        {
                            "texto": oracion,
                            "tokens": contar_tokens(oracion),
                            "pagina": unidad.pagina,
                            "seccion": None,
                            "localizador": unidad.localizador,
                        }
                    )
            for ventana in _ventanas(items, max_tokens, overlap):
                fragmento = _crear_fragmento(documento, ventana, contador + 1, len(fragmentos))
                if fragmento:
                    contador += 1
                    fragmentos.append(fragmento)
        else:
            # En DOCX/MD se respeta cada sección o par pregunta-respuesta.
            for unidad in documento.unidades:
                items = [
                    {
                        "texto": oracion,
                        "tokens": contar_tokens(oracion),
                        "pagina": None,
                        "seccion": unidad.seccion,
                        "localizador": unidad.localizador,
                    }
                    for oracion in _oraciones(unidad.texto, max_tokens)
                ]
                for ventana in _ventanas(items, max_tokens, overlap):
                    fragmento = _crear_fragmento(documento, ventana, contador + 1, len(fragmentos))
                    if fragmento:
                        contador += 1
                        fragmentos.append(fragmento)
    return fragmentos


def estadisticas_fragmentos(fragmentos: list[Fragmento]) -> dict:
    """Resumen verificable de la fragmentación efectiva (no sólo la nominal)."""
    if not fragmentos:
        return {"fragmentos": 0}
    tamanos = [f.n_tokens for f in fragmentos]
    return {
        "fragmentos": len(fragmentos),
        "tokens_min": min(tamanos),
        "tokens_mediana": int(statistics.median(tamanos)),
        "tokens_media": round(statistics.mean(tamanos), 1),
        "tokens_max": max(tamanos),
        "tokens_total": sum(tamanos),
        "por_archivo": {
            archivo: sum(1 for f in fragmentos if f.archivo == archivo)
            for archivo in sorted({f.archivo for f in fragmentos})
        },
        "localizadores_unicos": len({(f.archivo, f.localizador) for f in fragmentos}),
    }


def huella_configuracion(max_tokens: int, overlap: int, modelo_embeddings: str) -> str:
    """Identificador estable de una combinación de fragmentación + embeddings."""
    cadena = f"{max_tokens}|{overlap}|{modelo_embeddings}"
    return hashlib.sha1(cadena.encode("utf-8")).hexdigest()[:12]
