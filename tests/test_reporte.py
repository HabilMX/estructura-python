"""El reporte se prueba con resultados hechos a mano: no consulta nada."""

import json

import pytest

from revisor.reporte import a_json, resumen, tabla, tiempo, url_publica
from revisor.servicio import Estado, Resultado, Servicio

RESULTADOS = [
    Resultado(
        Servicio("catalogo", "https://catalogo.example"), Estado.ARRIBA, 142, "200"
    ),
    Resultado(Servicio("inventario", "https://inv.example"), Estado.LENTO, 2300, "200"),
    Resultado(
        Servicio("reportes", "https://rep.example"),
        Estado.CAIDO,
        None,
        "conexión rechazada",
    ),
]


@pytest.mark.parametrize(
    ("url", "esperada"),
    [
        ("https://a.example/salud", "https://a.example/salud"),
        ("https://yo:clave@a.example/salud", "https://a.example/salud"),
        ("https://a.example/salud?token=SECRETO#x", "https://a.example/salud"),
        ("http://a.example:8080/x?k=v", "http://a.example:8080/x"),
        ("http://[::1]:8080/x", "http://[::1]:8080/x"),
        ("http://a.example:puerto/x", "(URL ilegible)"),
    ],
)
def test_url_publica(url: str, esperada: str) -> None:
    assert url_publica(url) == esperada


def test_el_json_no_lleva_secretos() -> None:
    con_secreto = Servicio("s", "https://yo:CLAVE@s.example/salud?token=SECRETO")
    texto = a_json([Resultado(con_secreto, Estado.ARRIBA, 10, "200")])
    assert "CLAVE" not in texto and "SECRETO" not in texto
    assert json.loads(texto)["servicios"][0]["url"] == "https://s.example/salud"


def test_el_json_trae_el_resumen() -> None:
    datos = json.loads(a_json(RESULTADOS))
    assert datos["resumen"] == {"total": 3, "arriba": 1, "lento": 1, "caido": 1}
    assert datos["servicios"][2]["tiempo_ms"] is None


def test_la_tabla() -> None:
    assert tabla(RESULTADOS).splitlines() == [
        "SERVICIO    ESTADO  TIEMPO  DETALLE",
        "catalogo    ARRIBA   142ms  200",
        "inventario  LENTO     2.3s  200",
        "reportes    CAIDO        —  conexión rechazada",
        "",
        "3 servicios · 1 arriba · 1 lento · 1 caído",
    ]


@pytest.mark.parametrize(
    ("ms", "texto"),
    [(None, "—"), (0, "0ms"), (999, "999ms"), (1000, "1.0s"), (2345, "2.3s")],
)
def test_tiempo(ms: int | None, texto: str) -> None:
    assert tiempo(ms) == texto


def test_resumen_en_singular() -> None:
    assert resumen(RESULTADOS[:1]) == "1 servicio · 1 arriba · 0 lentos · 0 caídos"
