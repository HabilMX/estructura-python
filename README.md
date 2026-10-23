> El código es MIT; el texto y las explicaciones son CC BY-SA 4.0.

# estructura-python

**Una plantilla de Python que se clona, corre a la primera y prueba lo que de verdad se instala**:
el paquete en `src/`, las pruebas en `tests/`, todo descrito en un solo `pyproject.toml`, y nada más
hasta que haga falta.

Es una **semilla**, no un molde completo: trae una funcionalidad real de punta a punta (una línea de
comandos que revisa si otros servicios responden por HTTP), sus pruebas y un CI que comprueba la
frontera que Python vigila por ti al instalar. Lo demás crece cuando duela, y la sección
[«Cómo crece»](#cómo-crece-cuándo-agregar-cada-cosa) dice cuándo.

Es parte de la serie «La estructura de un proyecto», de Hábil. El ejemplo es el `revisor` del
[curso de Python](https://www.habil.mx/es/cursos/python/).

---

## Córrelo

Necesitas Python 3.12 o más nuevo (`python3 --version`), Git y `bash`. Todo va dentro de un entorno
virtual, nunca en el Python del sistema.

- **Linux Mint 22** trae 3.12. Si `python3 -m venv .venv` contesta que falta `ensurepip`, corre
  `sudo apt install python3.12-venv` y vuelve a crear el entorno con la misma orden. La
  [lección 1 del curso de Python](https://www.habil.mx/es/cursos/python/01-instalacion/) lo explica.
- **macOS** trae en `/usr/bin/python3` un Python más viejo, el de las herramientas de Apple (en la
  Mac donde se probó, 3.9.6). Instala uno reciente con el instalador de
  [python.org](https://www.python.org/downloads/macos/).
- **Windows**: usa WSL.

**1. Prepara el entorno** (una sola vez):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip        # --group pide pip 25.1 o más nuevo
python -m pip install --group dev -e .     # las herramientas y el paquete, en modo editable
```

El `--upgrade pip` no sobra: un entorno nuevo de Linux Mint 22 trae pip 24.0, que contesta
`no such option: --group`.

**2. Corre las pruebas**, primero contra tu carpeta y después contra lo instalado:

```bash
pytest                                  # rápido: lee tu carpeta src/
bash herramientas/probar-instalado.sh   # lo que ve quien instala tu paquete
```

Las últimas tres líneas del guion:

```
revisor bajo prueba: …/site-packages/revisor (el paquete INSTALADO)
pruebas: 62 · pasaron 62 · fallaron 0 · con error 0 · saltadas 0
✅ lo instalado pasa sus pruebas
```

**3. Úsalo.** Lee `servicios.toml` de la carpeta actual:

```bash
revisor
```

Lo que contestó el 22-oct-2026 (los tiempos cambian, y los dos de `python.org` salen `ARRIBA` solo si
tienes internet):

```
SERVICIO         ESTADO  TIEMPO  DETALLE
python.org       ARRIBA    66ms  200
docs.python.org  ARRIBA   279ms  200
no-existe        CAIDO        —  no se encontró el servidor

3 servicios · 2 arriba · 0 lentos · 1 caído
```

Sale con código `1` porque uno está caído (`echo $?`). Los códigos son tres: `0` todo arriba, `1`
alguno lento o caído, `2` no se pudo revisar (uso inválido o configuración rota). También:
`revisor --formato json`, `revisor --config otra.toml`, `revisor --paralelo 10`, `revisor --version` y
`python -m revisor`, que es lo mismo que `revisor`.

---

## Qué es cada carpeta y por qué existe

```
estructura-python/
├── pyproject.toml               el proyecto: cómo se construye, qué es, qué comando crea, qué lo revisa
├── servicios.toml               el ejemplo que usa «Córrelo»
├── src/
│   └── revisor/                 EL PAQUETE: lo único que viaja al instalar
│       ├── __init__.py          lo vuelve paquete
│       ├── __main__.py          lo que corre con python -m revisor
│       ├── cli.py               la línea de comandos: opciones y código de salida
│       ├── servicio.py          el vocabulario: Servicio, Estado, Resultado. Sin red ni archivos
│       ├── config.py            lee y valida servicios.toml
│       ├── revisar.py           consulta muchos servicios a la vez; declara el protocolo que USA
│       ├── reporte.py           tabla para personas, JSON para programas
│       └── py.typed             avisa que el paquete trae tipos
├── tests/                       las pruebas: no viajan con el paquete
│   ├── conftest.py              el guardia de lo instalado y un servidor HTTP local
│   └── test_*.py                una por módulo
├── herramientas/
│   ├── _comun.sh                lo que comparten los dos guiones: entorno, pruebas y conteo
│   ├── probar-instalado.sh      las pruebas contra la rueda instalada en un entorno nuevo
│   └── probar-frontera.sh       demuestra que lo que no está en el paquete no llega
└── .github/workflows/verificar.yml
```

**`src/`.** La guía de empaquetado de Python (PyPA) explica la diferencia: con el diseño `src/` hay
que instalar el proyecto para correr su código, y con el diseño plano no. Esa incomodidad es el punto:
con el paquete en la raíz, Python encuentra tu carpeta antes que lo instalado, y un archivo que nunca
entró al paquete pasa tus pruebas igual. La misma guía dice que lo típico es usar la instalación
editable para desarrollar y la normal para probar. Esta plantilla hace las dos.

**`src/revisor/`.** El paquete. Una línea de `pyproject.toml` decide qué viaja en la rueda (el
archivo `.whl` que se instala):

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/revisor"]
```

Todo lo que esté dentro de `src/revisor/` viaja; lo que esté fuera, no. Ojo con un detalle medido: la
instalación editable de hatchling agrega la carpeta `src/` **completa** a la ruta de búsqueda de
Python, así que un `src/suelto.py` se importa en tu máquina y falta en la rueda. Por eso las pruebas
también corren contra lo instalado.

hatchling tiene una opción que lo evita, `dev-mode-exact = true`: con ella, la editable expone solo el
paquete (medido: `import suelto` da `ModuleNotFoundError`). La plantilla no la usa, por tres razones:
su documentación avisa que los analizadores de código y los editores no la entienden, así que el
autocompletado deja de funcionar; tampoco ve lo que la rueda excluye *dentro* del paquete (medido); y
quien usa tu paquete recibe la rueda, así que es la rueda lo que se prueba.

**`servicio.py`.** El dominio. No importa a ningún otro módulo del proyecto, y todos los demás lo
importan a él: se prueba sin red ni disco y no puede formar parte de un ciclo de importaciones.

**`revisar.py`.** La consulta concurrente. El protocolo `Consultor` vive aquí porque aquí se usa;
`ConsultorHTTP` lo cumple sin heredar de él, y el doble de las pruebas también. Cada consulta tiene su
tiempo límite (en la conexión, en cada lectura y en el cuerpo completo), lee como mucho 64 KiB del
cuerpo, y **ningún detalle de error repite la URL**: urllib a veces mete la URL entera, con su query
string, en sus mensajes (`unknown url type: 'sin-esquema/?token=...'`), así que esos textos se cambian
por frases fijas. Cada una de esas protecciones tiene su prueba.

**`reporte.py`.** La URL de cada servicio sale **sin usuario, contraseña ni query string**
(`url_publica`): lo que sale en un reporte termina en bitácoras ajenas. La ruta sí sale, porque dice
qué se revisa; por eso un token tampoco va en la ruta.

**`config.py`.** Rechaza un campo desconocido (`tiemout`), un nombre repetido, un esquema que no sea
`http` o `https`, y una URL con credenciales (`https://usuario:clave@...`), sin repetir la URL en el
error.

**`cli.py`.** Delgada: arma las piezas y decide el código de salida. `main` **devuelve** el código en
vez de llamar a `sys.exit`, así que las pruebas la llaman como a cualquier función. La versión de
`--version` se lee de los metadatos del paquete instalado: vive en un solo lugar, `pyproject.toml`.

**`tests/`.** Fuera del paquete, para que no viajen. pytest corre en modo `importlib`, que la
documentación de pytest recomienda para proyectos nuevos: no mete carpetas del proyecto en la ruta de
búsqueda, así que se prueba lo que está instalado en el entorno. Las pruebas de red usan un servidor de
verdad en `127.0.0.1`, en un puerto libre: no salen a internet.

**`tests/conftest.py`.** Al arrancar, pytest imprime de dónde viene el `revisor` que prueba:

```
revisor bajo prueba: src/revisor (la CARPETA del proyecto)
```

Con `REVISOR_EXIGIR_INSTALADO=1`, se niega a correr si viene de la carpeta. Así el guion de lo
instalado no puede probar tu `src/revisor` creyendo que probó la rueda. El guardia solo mira de dónde
viene `revisor`: que otro módulo de tu carpeta se cuele en esas pruebas lo ataja la frontera, abajo.

---

## La frontera que sabe fallar

`herramientas/probar-frontera.sh` trabaja en una copia temporal del proyecto (tu carpeta no se toca).
Siembra `src/suelto.py`, un módulo que vive en `src/` pero fuera del paquete, y una prueba que lo
importa. Corre la suite completa dos veces, en dos entornos nuevos con el mismo Python, la misma copia y la misma versión de pytest.
Entre las dos solo cambia una bandera de pip, `-e`:

1. **Control**, con `pip install -e`: Python lee la carpeta, así que todas las pruebas tienen que
   pasar, la sembrada incluida. Si no pasan, el experimento está mal montado y el guion para en rojo.
2. **Violación**, con `pip install`: se instala la rueda. Tiene que fallar **una sola** prueba, la
   sembrada, y por la razón exacta.

Ésta es la salida real:

```
1/2 control: pip install -e (la carpeta) · src/suelto.py está fuera del paquete
   revisor bajo prueba: src/revisor (la CARPETA del proyecto)
   ✅ 63 de 63 pasaron: desde la carpeta, suelto.py se ve
2/2 violación: pip install (la rueda) · el mismo archivo, la misma prueba
   revisor bajo prueba: …/site-packages/revisor (el paquete INSTALADO)
     ✗ test_suelto_viaja_con_el_paquete: ModuleNotFoundError: No module named 'suelto'
   ✅ 62 de 63 pasaron; falló solo la que usa suelto.py, por la razón exacta
✅ frontera: se sostiene
```

Si en el paso 2 todo pasa (por ejemplo, si alguien cambia `packages` para que la rueda meta todo
`src/`), sale `❌ PASÓ: lo instalado vio src/suelto.py, que no está en el paquete. La frontera no
existe.` Si falla otra cosa, o más de una prueba, también sale en rojo. Los números se leen del
informe de pytest, no de su código de salida.

**Rómpelo tú.** Crea un módulo fuera del paquete y una prueba que lo use:

```bash
cat > src/exportar.py <<'EOF'
def a_csv(filas: list[tuple[str, str]]) -> str:
    return "\n".join(",".join(fila) for fila in filas)
EOF
cat > tests/test_exportar.py <<'EOF'
from exportar import a_csv


def test_a_csv() -> None:
    assert a_csv([("pagos", "ARRIBA")]) == "pagos,ARRIBA"
EOF
pytest -q                               # 63 passed: tu carpeta dice que todo está bien
bash herramientas/probar-instalado.sh   # lo instalado dice otra cosa
```

```
pruebas: 63 · pasaron 62 · fallaron 0 · con error 1 · saltadas 0
   ✗ tests.test_exportar: ModuleNotFoundError: No module named 'exportar'
```

Para arreglarlo, mételo al paquete: `mv src/exportar.py src/revisor/exportar.py` y cambia el import a
`from revisor.exportar import a_csv`. Para regresar todo: `git checkout -- . && git clean -fd`. Ojo:
`git clean -fd` también borra cualquier archivo nuevo que hayas creado en el repositorio, como tus
notas.

---

## Qué NO trae y por qué

| No trae | Por qué |
|---|---|
| `setup.py` | La guía oficial pide, para proyectos nuevos, la tabla `[project]` de `pyproject.toml`, y conservar `setup.py` solo si hace falta configuración programática, como compilar extensiones en C |
| `requirements.txt` | pip lee solo las dependencias declaradas en los metadatos del proyecto al instalarlo; un `requirements.txt` solo se usa si alguien corre `pip install -r`. Las herramientas de desarrollo van en `[dependency-groups]` (PEP 735), que no viajan con el paquete |
| `utils.py`, `helpers.py`, `common.py` | Un nombre que no dice qué hay adentro se vuelve el cajón donde cae todo. Cada módulo se llama por lo que hace |
| Dependencias | Solo la biblioteca estándar: `urllib`, `concurrent.futures`, `tomllib`, `argparse` |
| `tests/__init__.py` | Con el modo `importlib`, las pruebas no necesitan ser paquete y pueden repetir nombre de archivo |
| Base de datos, Docker, logging configurable | Fuera del ejemplo. Ver «Cómo crece» |

---

## Cómo crece: cuándo agregar cada cosa

| Cuando… | Agrega… | Y deja… |
|---|---|---|
| Un módulo crece y mezcla dos temas | dos módulos con nombre de lo que hacen (`src/revisor/notificar.py`) | sin `utils.py` |
| Un tema ya tiene varios módulos | un subpaquete: `src/revisor/notificar/` con su `__init__.py` | el resto plano |
| Necesitas una dependencia de terceros | la línea en `dependencies`, con su versión mínima | las herramientas de desarrollo en `[dependency-groups]` |
| Quieres instalaciones idénticas en cada máquina | un archivo de bloqueo, `pylock.toml` (PEP 751), generado por tu herramienta | `pyproject.toml` como la fuente |
| Guardas estado en una base de datos | un módulo que hable con la base; si el dominio necesita un protocolo para eso, se declara del lado que lo usa | `servicio.py` sin SQL |
| Otro proyecto necesita importar algo de aquí | publícalo como paquete; lo interno, con nombre que empiece con `_` | `src/revisor/` como única puerta |
| Se necesita un contenedor | un `Dockerfile` en la raíz que instale la rueda | — |

Regla para decidir: **una carpeta nueva tiene que resolver un problema que ya tienes**. Si no puedes
decir cuál, todavía no la necesitas.

---

## Cómo quitar el ejemplo

El `revisor` está para demostrar la estructura. Para empezar tu propio proyecto:

1. En `pyproject.toml`, cambia `name`, `description`, el comando de `[project.scripts]` y la ruta de
   `packages` (`src/<tu_paquete>`).
2. Renombra `src/revisor/` a `src/<tu_paquete>/` y cambia los imports
   (`grep -rl 'revisor' src tests` te dice dónde).
3. Borra `servicio.py`, `config.py`, `revisar.py`, `reporte.py`, `servicios.toml` y sus pruebas.
   `__init__.py`, `__main__.py`, `py.typed` y la forma de `cli.py` suelen sobrevivir.
4. En `tests/conftest.py`, cambia `import revisor` por tu paquete y quita el servidor si no lo usas;
   conserva el guardia de lo instalado.
5. En `herramientas/probar-frontera.sh` no hay nada que cambiar: siembra su propio módulo.
6. Corre `ruff check . && mypy && pytest && bash herramientas/probar-instalado.sh && bash herramientas/probar-frontera.sh`.
7. Reescribe este README. El código y `LICENSE` son MIT; si conservas el texto de los `.md`, mira
   `LICENSE-CONTENIDO.md`.

---

## Versiones

Medidas el 22 de octubre de 2026.

| Pieza | Versión |
|---|---|
| Python | `requires-python = ">=3.12"`. Probado con 3.14.8 y 3.12.12 en macOS, y con 3.14.9, 3.12.15 y 3.12.3 (el de Ubuntu 24.04, la base de Linux Mint 22) en Linux. La 3.14.9 es la más reciente de la 3.14 en python.org ese día |
| Construcción | hatchling 1.27 o más nuevo (se probó con 1.32.4) |
| Desarrollo | pytest 9.1.1, ruff 0.17.1, mypy 2.4.0, fijadas en `[dependency-groups]` |
| Dependencias | Ninguna: solo la biblioteca estándar |
| CI | GitHub Actions: `actions/checkout@v4`, `actions/setup-python@v5`, con Python 3.12 y 3.14; corre en cada cambio, a mano y cada lunes. GitHub apaga la corrida de los lunes si el repositorio público pasa 60 días sin actividad |

---

## Licencia

El código es [MIT](LICENSE). El texto y las explicaciones son
[CC BY-SA 4.0](LICENSE-CONTENIDO.md).
