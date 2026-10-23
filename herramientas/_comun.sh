# Funciones que comparten probar-instalado.sh y probar-frontera.sh.
# No se ejecuta solo: los otros dos guiones lo cargan con «source».
#
# Están en un solo archivo a propósito: si cada guion armara su entorno y
# contara sus pruebas a su manera, el día que uno cambiara, la frontera
# probaría algo distinto de lo que corre el CI.

# El Python con que se crean los entornos: el de la variable PYTHON o python3.
# Tiene que ser 3.12 o más nuevo, como pide pyproject.toml.
PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
  # ${PY} va con llaves: sin ellas, el bash 3.2 de macOS lee el primer byte de
  # la comilla de cierre como parte del nombre de la variable.
  echo "❌ hace falta Python 3.12 o más nuevo; «${PY}» no lo es o no existe." >&2
  echo "   Indica otro con: PYTHON=/ruta/a/python3.14 bash $0" >&2
  exit 2
fi

# requisito_pytest <raíz>: la versión de pytest fijada en el grupo «dev» de
# pyproject.toml. Se lee de ahí para que haya una sola fuente.
requisito_pytest() {
  "$PY" - "$1/pyproject.toml" <<'EOF'
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    dev = tomllib.load(f)["dependency-groups"]["dev"]
print(next(r for r in dev if r.startswith("pytest")))
EOF
}

# crear_entorno <carpeta> <raíz>: un entorno virtual NUEVO, vacío, con pytest.
# Nunca el Python del sistema ni el entorno con que trabajas.
crear_entorno() {
  "$PY" -m venv "$1"
  "$1/bin/python" -m pip install -q --disable-pip-version-check "$(requisito_pytest "$2")"
}

# copiar_proyecto <origen> <destino>: copia lo que git conoce (también los
# archivos nuevos que no ignora), sin entornos, cachés ni ruedas viejas.
copiar_proyecto() {
  "$PY" - "$1" "$2" <<'EOF'
import os, shutil, subprocess, sys
from pathlib import Path
origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
try:
    salida = subprocess.run(
        ["git", "-C", str(origen), "ls-files", "-z", "-co", "--exclude-standard"],
        check=True, capture_output=True).stdout
    archivos = [Path(p) for p in salida.decode().split("\0") if p]
except (OSError, subprocess.CalledProcessError):
    fuera = {".git", ".venv", "dist", "build", "__pycache__", ".pytest_cache",
             ".mypy_cache", ".ruff_cache"}
    archivos = []
    for carpeta, subcarpetas, nombres in os.walk(origen):
        subcarpetas[:] = [d for d in subcarpetas if d not in fuera]
        archivos += [Path(carpeta, n).relative_to(origen) for n in nombres]
for relativo in archivos:
    if (origen / relativo).is_file():
        (destino / relativo).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen / relativo, destino / relativo)
EOF
}

# correr_pruebas <entorno> <proyecto> <informe.xml> [VAR=valor ...]
# Corre pytest del entorno en la carpeta del proyecto y deja el informe JUnit.
# La salida completa queda en <informe.xml>.log. Devuelve el código de pytest.
# --continue-on-collection-errors: si un archivo de pruebas no se puede ni
# importar, falla ESE archivo y las demás pruebas corren igual; así el informe
# dice cuántas pasaron en vez de interrumpirse.
correr_pruebas() {
  local entorno="$1" proyecto="$2" informe="$3"
  shift 3
  (cd "$proyecto" && env "$@" "$entorno/bin/pytest" -p no:cacheprovider \
    --continue-on-collection-errors --junitxml="$informe" >"$informe.log" 2>&1)
}

# contar <informe.xml>: los números se leen del INFORME, nunca del código de
# salida. Imprime «total pasaron fallaron errores saltadas» y, debajo, una
# línea por cada prueba que no pasó: «nombre: primera línea del mensaje».
contar() {
  "$PY" - "$1" <<'EOF'
import sys, xml.etree.ElementTree as ET
try:
    raiz = ET.parse(sys.argv[1]).getroot()
except (OSError, ET.ParseError):
    print("0 0 0 0 0"); sys.exit()
suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
if suite is None:  # un XML que no es de pytest: cero, y eso es rojo
    print("0 0 0 0 0"); sys.exit()
n = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
pasaron = n["tests"] - n["failures"] - n["errors"] - n["skipped"]
print(n["tests"], pasaron, n["failures"], n["errors"], n["skipped"])
for caso in suite.iter("testcase"):
    for malo in list(caso.findall("failure")) + list(caso.findall("error")):
        # El renglón «E ...» del rastro dice la causa; el atributo message a
        # veces solo dice «collection failure».
        causas = [r[1:].strip() for r in (malo.text or "").splitlines()
                  if r.startswith("E ")]
        mensaje = (malo.get("message") or "").strip().splitlines() or [""]
        print(f'{caso.get("name")}: {causas[-1] if causas else mensaje[0]}')
EOF
}

# origen_bajo_prueba <informe.xml>: la línea del guardia de tests/conftest.py.
origen_bajo_prueba() {
  grep -m1 '^revisor bajo prueba:' "$1.log" || echo "revisor bajo prueba: (no se supo)"
}
