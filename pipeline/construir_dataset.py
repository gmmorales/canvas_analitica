"""
pipeline/construir_dataset.py

Fase 2 (parte C) — Arma el dataset final del TPI: una fila por fotografía,
con las etiquetas autoasignadas + las 5 variables de color/histograma.

Entradas:
  --metadata   salida de asociar_metadata.py (id_imagen ya reemplazado por
               el hash). Por defecto datos/metadata_normalizado.csv.
  --variables  salida de extraer_variables.py. Por defecto
               datos/variables_visuales.csv.

Salida (una sola tabla, columnas en este orden):
  id_imagen, autor_id, tipo_manovich, confianza_etiqueta, caso_limite,
  justificacion_etiqueta,
  mediana_luminancia, dispersion_luminancia, prop_sombras,
  prop_altas_luces, matiz_dominante_deg, saturacion_media,
  dominancia_cromatica

Qué hace además de unir:
  1. Une metadata + variables por id_imagen.
  2. Normaliza las columnas categóricas al formato de la consigna:
       - tipo_manovich: casual / profesional / diseno  (diseño -> diseno)
       - confianza_etiqueta: alta / media / baja       (Media -> media)
       - caso_limite: booleano True / False            (SI/NO -> True/False)
  3. Valida y avisa por stderr (nunca corrige ni borra a ciegas):
       - campos vacíos en las columnas obligatorias;
       - valores categóricos no reconocidos;
       - justificacion_etiqueta fuera del rango de 80-120 palabras;
       - id_imagen duplicado (varias filas para la misma foto);
       - fotos con variables pero sin etiqueta, y viceversa;
       - desacuerdo entre el tipo_manovich de la etiqueta y el de la carpeta.

  Con --estricto, si hay algún problema bloqueante (faltantes, duplicados o
  fotos sin variable) no escribe la salida y sale con error.

Los umbrales y parámetros de las variables NO se recalculan acá: vienen ya
medidos por extraer_variables.py. Este script solo los une.

Uso:
    uv run pipeline/construir_dataset.py \
        --metadata datos/metadata_normalizado.csv \
        --variables datos/variables_visuales.csv \
        --salida datos/dataset.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

RUTA_METADATA_POR_DEFECTO = Path("datos/metadata_normalizado.csv")
RUTA_VARIABLES_POR_DEFECTO = Path("datos/variables_visuales.csv")
RUTA_SALIDA_POR_DEFECTO = Path("datos/dataset.csv")

COLUMNAS_ETIQUETA = [
    "id_imagen",
    "autor_id",
    "tipo_manovich",
    "confianza_etiqueta",
    "caso_limite",
    "justificacion_etiqueta",
]
COLUMNAS_VARIABLES = [
    "mediana_luminancia",
    "dispersion_luminancia",
    "prop_sombras",
    "prop_altas_luces",
    "matiz_dominante_deg",
    "saturacion_media",
    "dominancia_cromatica",
]
COLUMNAS_SALIDA = COLUMNAS_ETIQUETA + COLUMNAS_VARIABLES

PALABRAS_MIN = 80
PALABRAS_MAX = 120

CATEGORIAS_VALIDAS = {"casual", "profesional", "diseno"}
CONFIANZAS_VALIDAS = {"alta", "media", "baja"}
VERDADEROS = {"si", "s", "true", "verdadero", "1", "yes", "y", "x"}
FALSOS = {"no", "n", "false", "falso", "0"}


# --------------------------------------------------------------------------
# Normalización de texto / valores
# --------------------------------------------------------------------------
def sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar_categoria(texto: str) -> str:
    """diseño / disenio / diseno -> 'diseno'; profesional; casual."""
    t = re.sub(r"[^a-z0-9]", "", sin_acentos(texto).lower())
    if t.startswith("disen"):
        return "diseno"
    if t.startswith("profesi"):
        return "profesional"
    if t.startswith("casual"):
        return "casual"
    return t


def normalizar_confianza(texto: str) -> str:
    """'Media ' / 'ALTA' -> 'media' / 'alta'."""
    return re.sub(r"[^a-z]", "", sin_acentos(texto).lower())


def normalizar_caso_limite(texto: str) -> str:
    """Devuelve 'True', 'False' o '' si no se puede interpretar."""
    t = re.sub(r"[^a-z0-9]", "", sin_acentos(texto).lower())
    if t in VERDADEROS:
        return "True"
    if t in FALSOS:
        return "False"
    return ""


# --------------------------------------------------------------------------
# L/E
# --------------------------------------------------------------------------
def leer_csv(ruta: Path) -> tuple[list[dict], list[str], str]:
    if not ruta.exists():
        print(f"No existe {ruta}.", file=sys.stderr)
        raise SystemExit(2)
    crudo = ruta.read_bytes()
    encoding = "utf-8-sig" if crudo[:3] == b"\xef\xbb\xbf" else "utf-8"
    with ruta.open(encoding=encoding, newline="") as f:
        lector = csv.DictReader(f)
        campos = list(lector.fieldnames or [])
        filas = list(lector)
    return filas, campos, encoding


def escribir_csv(ruta: Path, filas: list[dict], campos: list[str], encoding: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding=encoding) as f:
        escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


# --------------------------------------------------------------------------
# Construcción
# --------------------------------------------------------------------------
def construir(
    ruta_metadata: Path,
    ruta_variables: Path,
    ruta_salida: Path,
    estricto: bool,
) -> None:
    filas_meta, campos_meta, _ = leer_csv(ruta_metadata)
    filas_vars, campos_vars, encoding = leer_csv(ruta_variables)

    faltan_meta = [c for c in COLUMNAS_ETIQUETA if c not in campos_meta]
    if faltan_meta:
        print(
            f"{ruta_metadata} no tiene las columnas {faltan_meta}. "
            "¿Corriste antes pipeline/asociar_metadata.py?",
            file=sys.stderr,
        )
        raise SystemExit(2)
    faltan_vars = [c for c in COLUMNAS_VARIABLES if c not in campos_vars]
    if faltan_vars:
        print(
            f"{ruta_variables} no tiene las columnas {faltan_vars}. "
            "¿Corriste antes pipeline/extraer_variables.py?",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # Índice de variables por id_imagen (avisa duplicados).
    variables_por_id: dict[str, dict] = {}
    dup_vars: list[str] = []
    for fila in filas_vars:
        idv = fila["id_imagen"]
        if idv in variables_por_id:
            dup_vars.append(idv)
        variables_por_id[idv] = fila

    avisos: list[str] = []
    bloqueantes: list[str] = []
    salida: list[dict] = []
    vistos: dict[str, list[int]] = {}
    ids_sin_variable: list[tuple[int, str]] = []

    for numero_fila, fila in enumerate(filas_meta, start=2):
        id_imagen = fila["id_imagen"]

        # Normalización de categóricas.
        tipo = normalizar_categoria(fila["tipo_manovich"])
        if tipo not in CATEGORIAS_VALIDAS:
            avisos.append(
                f"fila {numero_fila}: tipo_manovich {fila['tipo_manovich']!r} no reconocido"
            )
        confianza = normalizar_confianza(fila["confianza_etiqueta"])
        if confianza and confianza not in CONFIANZAS_VALIDAS:
            avisos.append(
                f"fila {numero_fila}: confianza_etiqueta {fila['confianza_etiqueta']!r} no reconocida"
            )
        caso = normalizar_caso_limite(fila["caso_limite"])
        if fila["caso_limite"].strip() and caso == "":
            avisos.append(
                f"fila {numero_fila}: caso_limite {fila['caso_limite']!r} no es booleano"
            )

        # Campos obligatorios vacíos.
        for columna, valor in [
            ("autor_id", fila["autor_id"]),
            ("tipo_manovich", fila["tipo_manovich"]),
            ("confianza_etiqueta", fila["confianza_etiqueta"]),
            ("caso_limite", fila["caso_limite"]),
            ("justificacion_etiqueta", fila["justificacion_etiqueta"]),
        ]:
            if not valor.strip():
                avisos.append(f"fila {numero_fila}: {columna} vacío")

        # Justificación: 80-120 palabras.
        palabras = len(fila["justificacion_etiqueta"].split())
        if palabras and not (PALABRAS_MIN <= palabras <= PALABRAS_MAX):
            avisos.append(
                f"fila {numero_fila}: justificacion_etiqueta tiene {palabras} palabras "
                f"(se piden {PALABRAS_MIN}-{PALABRAS_MAX})"
            )

        # Duplicados de id_imagen.
        vistos.setdefault(id_imagen, []).append(numero_fila)

        # Unión con variables.
        variable = variables_por_id.get(id_imagen)
        if variable is None:
            ids_sin_variable.append((numero_fila, id_imagen))
            bloqueantes.append(f"fila {numero_fila}: {id_imagen} no tiene variables medidas")
        elif normalizar_categoria(variable.get("tipo_manovich", "")) != tipo and tipo in CATEGORIAS_VALIDAS:
            avisos.append(
                f"fila {numero_fila}: tipo_manovich de la etiqueta ({tipo}) no coincide "
                f"con la carpeta del archivo normalizado "
                f"({normalizar_categoria(variable.get('tipo_manovich', ''))})"
            )

        registro = {
            "id_imagen": id_imagen,
            "autor_id": fila["autor_id"].strip(),
            "tipo_manovich": tipo,
            "confianza_etiqueta": confianza,
            "caso_limite": caso,
            "justificacion_etiqueta": fila["justificacion_etiqueta"].strip(),
        }
        for columna_variable in COLUMNAS_VARIABLES:
            registro[columna_variable] = (
                variable.get(columna_variable, "") if variable else ""
            )
        salida.append(registro)

    # Reporte.
    duplicados = {k: v for k, v in vistos.items() if len(v) > 1}
    for id_imagen, numeros in sorted(duplicados.items()):
        avisos.append(f"id_imagen {id_imagen} repetido en las filas {numeros}")
    for id_imagen in sorted(set(dup_vars)):
        avisos.append(f"variables_visuales tiene id_imagen {id_imagen} repetido")
    ids_meta = set(vistos)
    ids_vars = set(variables_por_id)
    medidas_sin_etiqueta = sorted(ids_vars - ids_meta)

    print(f"\n{len(salida)} filas -> dataset")
    print(f"  ids únicos: {len(vistos)}  (fotos con más de una fila: {len(duplicados)})")
    print(f"  filas sin variables: {len(ids_sin_variable)}")
    print(f"  fotos medidas sin etiqueta en metadata: {len(medidas_sin_etiqueta)}")

    for aviso in avisos:
        print(f"  [AVISO] {aviso}", file=sys.stderr)
    for bloqueante in bloqueantes:
        print(f"  [FALTA] {bloqueante}", file=sys.stderr)

    problemas = bool(bloqueantes or duplicados)
    if problemas and estricto:
        print(
            "\n--estricto: hay problemas bloqueantes (faltantes o duplicados); "
            "NO se escribió la salida.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    escribir_csv(ruta_salida, salida, COLUMNAS_SALIDA, encoding)
    print(f"\n-> {ruta_salida}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arma el dataset final: etiquetas + variables (Fase 2, parte C)."
    )
    parser.add_argument("--metadata", type=Path, default=RUTA_METADATA_POR_DEFECTO)
    parser.add_argument("--variables", type=Path, default=RUTA_VARIABLES_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_SALIDA_POR_DEFECTO)
    parser.add_argument(
        "--estricto",
        action="store_true",
        help="No escribir la salida si hay faltantes o id_imagen duplicados.",
    )
    args = parser.parse_args()
    ruta_metadata = args.metadata
    # Si se usó el default y no existe metadata_normalizado.csv (porque la
    # asociación se hizo en el lugar, sobre metadata.csv), usar metadata.csv.
    if (
        ruta_metadata == RUTA_METADATA_POR_DEFECTO
        and not ruta_metadata.exists()
        and Path("datos/metadata.csv").exists()
    ):
        print(
            f"No existe {ruta_metadata}; uso datos/metadata.csv "
            "(asociación hecha en el lugar).",
            file=sys.stderr,
        )
        ruta_metadata = Path("datos/metadata.csv")
    construir(ruta_metadata, args.variables, args.salida, args.estricto)


if __name__ == "__main__":
    main()
