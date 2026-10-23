"""El vocabulario se prueba sin red y sin archivos: es lógica pura."""

import pytest

from revisor.servicio import TIMEOUT_POR_OMISION_S, Estado, Servicio, clasificar


@pytest.mark.parametrize(
    ("codigo", "tiempo_ms", "esperado"),
    [
        (200, 120, Estado.ARRIBA),
        (204, 999, Estado.ARRIBA),
        (200, 1000, Estado.LENTO),  # el umbral ya cuenta como lento
        (301, 50, Estado.ARRIBA),
        (404, 50, Estado.CAIDO),
        (503, 50, Estado.CAIDO),
        (None, None, Estado.CAIDO),
        (200, None, Estado.ARRIBA),
    ],
)
def test_clasificar(
    codigo: int | None, tiempo_ms: int | None, esperado: Estado
) -> None:
    assert clasificar(codigo, tiempo_ms) is esperado


def test_el_umbral_se_puede_cambiar() -> None:
    assert clasificar(200, 300, umbral_ms=250) is Estado.LENTO


def test_un_servicio_sin_timeout_usa_el_de_omision() -> None:
    assert Servicio("a", "https://a.example").timeout_s == TIMEOUT_POR_OMISION_S
