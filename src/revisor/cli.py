"""La línea de comandos: lee las opciones, arma las piezas y decide el código de salida.

Es delgada a propósito. No sabe qué es un servicio sano ni cómo se consulta: eso
vive en ``servicio`` y ``revisar``. ``main`` DEVUELVE el código en vez de llamar a
``sys.exit``, así que las pruebas la llaman como a cualquier función.

Códigos de salida:

- ``0``: todos los servicios están ARRIBA.
- ``1``: el revisor funcionó, pero alguno está LENTO o CAIDO.
- ``2``: no se pudo revisar: uso inválido (lo decide argparse) o configuración
  que no sirve.
"""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from revisor.config import ErrorDeConfiguracion, leer_servicios
from revisor.reporte import a_json, tabla
from revisor.revisar import ConsultorHTTP, revisar_todos
from revisor.servicio import Estado


def _al_menos_uno(texto: str) -> int:
    try:
        numero = int(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} no es un número entero") from None
    if numero < 1:
        raise argparse.ArgumentTypeError("tiene que ser al menos 1")
    return numero


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="revisor",
        description="Revisa si una lista de servicios responde por HTTP.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("servicios.toml"),
        help="archivo TOML con los servicios (por omisión: servicios.toml)",
    )
    parser.add_argument(
        "--formato",
        choices=["tabla", "json"],
        default="tabla",
        help="forma del reporte (por omisión: tabla)",
    )
    parser.add_argument(
        "--paralelo",
        type=_al_menos_uno,
        default=5,
        help="cuántos servicios se consultan a la vez (por omisión: 5)",
    )
    # La versión sale de los metadatos del paquete INSTALADO: vive en un solo
    # lugar, pyproject.toml. Sin instalar, esto falla, y está bien que falle.
    parser.add_argument(
        "--version", action="version", version=f"revisor {version('revisor')}"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    opciones = construir_parser().parse_args(argv)

    try:
        servicios = leer_servicios(opciones.config)
    except ErrorDeConfiguracion as error:
        print(f"error de configuración: {error}", file=sys.stderr)
        return 2

    resultados = revisar_todos(servicios, ConsultorHTTP(), paralelo=opciones.paralelo)
    print(a_json(resultados) if opciones.formato == "json" else tabla(resultados))

    return 0 if all(r.estado is Estado.ARRIBA for r in resultados) else 1
