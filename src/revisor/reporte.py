"""Convierte resultados en algo que se lee: una tabla o JSON.

La tabla es para personas; el JSON, para otros programas.

No consulta nada ni decide estados: recibe resultados ya hechos.
"""

import json
from collections.abc import Sequence
from urllib.parse import urlsplit, urlunsplit

from revisor.servicio import Estado, Resultado


def url_publica(url: str) -> str:
    """Devuelve la URL sin usuario, contraseña, query string ni fragmento.

    🔒 Lo que sale en un reporte termina en bitácoras ajenas, y
    ``https://usuario:clave@host`` o ``?token=...`` llevan un secreto. La ruta sí
    se conserva, porque dice qué se revisa; por eso un token tampoco va en la
    ruta.
    """
    try:
        partes = urlsplit(url)
        servidor = partes.hostname or ""
        puerto = partes.port
    except ValueError:
        return "(URL ilegible)"
    if ":" in servidor:  # IPv6 va entre corchetes
        servidor = f"[{servidor}]"
    if puerto is not None:
        servidor = f"{servidor}:{puerto}"
    return urlunsplit((partes.scheme, servidor, partes.path, "", ""))


def tiempo(tiempo_ms: int | None) -> str:
    """``142ms``, ``2.3s`` o ``—`` si no hubo respuesta."""
    if tiempo_ms is None:
        return "—"
    if tiempo_ms < 1000:
        return f"{tiempo_ms}ms"
    return f"{tiempo_ms / 1000:.1f}s"


def resumen(resultados: Sequence[Resultado]) -> str:
    """``3 servicios · 1 arriba · 1 lento · 1 caído``."""
    total = len(resultados)
    cuenta = {e: sum(1 for r in resultados if r.estado is e) for e in Estado}
    return (
        f"{total} servicio{'' if total == 1 else 's'} · "
        f"{cuenta[Estado.ARRIBA]} arriba · "
        f"{cuenta[Estado.LENTO]} lento{'' if cuenta[Estado.LENTO] == 1 else 's'} · "
        f"{cuenta[Estado.CAIDO]} caído{'' if cuenta[Estado.CAIDO] == 1 else 's'}"
    )


def tabla(resultados: Sequence[Resultado]) -> str:
    """La tabla para la terminal, con el resumen al final."""
    ancho = max([len("SERVICIO"), *(len(r.servicio.nombre) for r in resultados)])
    lineas = [f"{'SERVICIO':<{ancho}}  {'ESTADO':<6}  {'TIEMPO':>6}  DETALLE"]
    for r in resultados:
        lineas.append(
            f"{r.servicio.nombre:<{ancho}}  {r.estado:<6}  "
            f"{tiempo(r.tiempo_ms):>6}  {r.detalle}"
        )
    lineas += ["", resumen(resultados)]
    return "\n".join(lineas)


def a_json(resultados: Sequence[Resultado]) -> str:
    """El reporte para otros programas. Las URL salen limpias (``url_publica``)."""
    datos = {
        "servicios": [
            {
                "nombre": r.servicio.nombre,
                "url": url_publica(r.servicio.url),
                "estado": r.estado.value,
                "tiempo_ms": r.tiempo_ms,
                "detalle": r.detalle,
            }
            for r in resultados
        ],
        "resumen": {
            "total": len(resultados),
            "arriba": sum(1 for r in resultados if r.estado is Estado.ARRIBA),
            "lento": sum(1 for r in resultados if r.estado is Estado.LENTO),
            "caido": sum(1 for r in resultados if r.estado is Estado.CAIDO),
        },
    }
    return json.dumps(datos, ensure_ascii=False, indent=2)
