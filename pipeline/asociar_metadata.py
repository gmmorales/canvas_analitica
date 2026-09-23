"""
pipeline/asociar_metadata.py

Fase 2 (parte B) — Reemplaza los nombres viejos de las fotos (los de
datos/corpus_original) que hoy están en la columna id_imagen de
datos/metadata.csv por los id_imagen NUEVOS que asigna
pipeline/normalizar.py (el hash del contenido, que a la vez es el nombre
del archivo en datos/corpus_normalizado/{categoria}/).

De dónde sale la asociación:
  normalizar.py deja un mapa de trazabilidad privado, una fila por imagen:

      archivo_original,nombre_original,id_imagen,categoria,archivo_normalizado
      casual/casual_01_CB.jpg,casual_01_CB,<hash>,casual,casual/<hash>.jpg

  Este script no adivina ni recalcula hashes: usa ese mapa. Si el mapa no
  existe, hay que volver a correr normalizar.py (ver README > Normalización).

Por qué no alcanza con un match literal de texto:
  los nombres viejos en metadata.csv traen typos, tildes, espacios y a
  veces les falta el autor. Ejemplos reales de este corpus:
    - "profesiona_02_CB"   -> el archivo es profesional_02_CB.jpeg
    - "profesioal_01_SL"   -> profesional_01_SL.jpg
    - "diseño_01_DD.jpg"   -> disenio_01_DD.jpg (además, sin tilde y con .jpg)
    - "Diseño_01_RNM"      -> disenio_01_RNM_.jpg
    - "disenio_01_MBD"     -> diseno_01_MBD.jpg
    - "casual_3_DM"        -> casual_03_DM.jpg
    - "disenio_03_CC"      -> disenio_03_CE.jpg (autor CC vs CE)
    - "casual_01" (MC)     -> casual_01_MC.jpg (sin autor en el nombre)
  Por eso se hacen dos pasadas, de la más a la menos estricta:

  1. Nombre normalizado exacto: minúsculas, sin tildes y sin ningún
     carácter que no sea [a-z0-9]. Eso solo ya cubre extensiones, "_",
     espacios y puntos sueltos.
  2. Clave canónica (categoria, numero, autor): se normaliza la categoría
     (diseño/disenio/diseno -> diseno), el número se lleva a 2 dígitos
     (3 -> 03) y se prueban como autor tanto el token que trae el nombre
     como el autor_id de metadata. Resuelve los typos, las filas sin
     autor y CC vs CE. La categoría se toma del NOMBRE y tipo_manovich
     queda solo como respaldo, porque hay filas con tipo_manovich mal
     cargado (p. ej. casual_0X_DM figura como "diseño").

Nunca se asigna a ciegas: las filas que no matchean se avisan por stderr
y se listan en el resumen; los ids nuevos repetidos (varias filas de
metadata apuntando a la misma foto) también se avisan. Con --estricto, si
queda alguna fila sin match no se escribe la salida y se sale con error.

Salida: por defecto datos/metadata_normalizado.csv, con el id_imagen ya
reemplazado y SIN la columna autor_apellido_nombre. Columnas finales:

    id_imagen, autor_id, tipo_manovich, confianza_etiqueta, caso_limite,
    justificacion_etiqueta

(autor_apellido_nombre se elimina para no arrastrar el nombre de la
persona autora al dataset analítico.)

Para dejar datos/metadata.csv con los ids nuevos:
    uv run pipeline/asociar_metadata.py --salida datos/metadata.csv

Uso:
    uv run pipeline/asociar_metadata.py \
        --metadata datos/metadata.csv \
        --mapa datos/trazabilidad_original_normalizado_privado.csv \
        --salida datos/metadata_normalizado.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

RUTA_METADATA_POR_DEFECTO = Path("datos/metadata.csv")
RUTA_MAPA_POR_DEFECTO = Path("datos/trazabilidad_original_normalizado_privado.csv")
RUTA_SALIDA_POR_DEFECTO = Path("datos/metadata_normalizado.csv")

# Columnas que NO van al dataset final (identifican a la persona, no a la foto).
COLUMNAS_A_ELIMINAR = ["autor_apellido_nombre"]

CAMPOS_MAPA = [
    "archivo_original",
    "nombre_original",
    "id_imagen",
    "categoria",
    "archivo_normalizado",
]


# --------------------------------------------------------------------------
# Normalización de texto para poder cruzar nombres "sucios"
# --------------------------------------------------------------------------
def sin_acentos(texto: str) -> str:
    """'Diseño' -> 'Diseno' (descompone y saca los diacríticos)."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def solo_alnum(texto: str) -> str:
    """minúsculas, sin tildes y sin nada que no sea [a-z0-9]. Quita .jpg, '_', ' '."""
    return re.sub(r"[^a-z0-9]", "", sin_acentos(texto).lower())


def normalizar_categoria(texto: str) -> str:
    """diseño / disenio / diseno -> 'diseno'; profesional/profesiona/profesioal -> 'profesional'."""
    t = solo_alnum(texto)
    if t.startswith("disen"):
        return "diseno"
    if t.startswith("profesi"):
        return "profesional"
    if t.startswith("casual"):
        return "casual"
    return t


CATEGORIAS_VALIDAS = {"casual", "profesional", "diseno"}


def categoria_desde_nombre(texto: str) -> str:
    """
    Categoría que trae el nombre del archivo (primer token), si la trae.
    Ej.: 'casual_3_DM' -> 'casual'; 'diseño_01_DD.jpg' -> 'diseno'; 'foo' -> ''.
    """
    base = re.sub(r"\.(jpe?g|png|webp|heic)$", "", texto, flags=re.IGNORECASE)
    partes = [p for p in re.split(r"[_\s]+", base) if p]
    if not partes:
        return ""
    categoria = normalizar_categoria(partes[0])
    return categoria if categoria in CATEGORIAS_VALIDAS else ""


def numero_desde(texto: str) -> str:
    """Primer grupo de dígitos, a 2 posiciones: 'casual_3_DM' -> '03'."""
    encontrado = re.search(r"\d+", texto)
    return encontrado.group(0).zfill(2) if encontrado else ""


def token_autor(texto: str, categoria: str) -> str:
    """
    Autor que trae el nombre del archivo, si trae alguno: se descarta el
    primer token (la categoría) y los que son solo dígitos.
    Ej.: 'diseño_01_DD.jpg' -> 'dd'; 'casual_01' -> ''.
    """
    base = re.sub(r"\.(jpe?g|png|webp|heic)$", "", texto, flags=re.IGNORECASE)
    partes = [p for p in re.split(r"[_\s]+", base) if p]
    sobrantes: list[str] = []
    for indice, parte in enumerate(partes):
        if indice == 0 and normalizar_categoria(parte) in CATEGORIAS_VALIDAS:
            continue
        if re.fullmatch(r"\d+", parte):
            continue
        sobrantes.append(parte)
    return solo_alnum("".join(sobrantes))


# --------------------------------------------------------------------------
# Mapa de trazabilidad
# --------------------------------------------------------------------------
def leer_mapa(ruta_mapa: Path) -> tuple[dict, dict]:
    """
    Devuelve dos índices sobre el mapa de normalizar.py:
      - por nombre normalizado: solo_alnum(nombre_original) -> [filas]
      - por clave canónica: (categoria, numero, autor) -> [filas]
    """
    if not ruta_mapa.exists():
        print(
            f"No existe el mapa de trazabilidad {ruta_mapa}.\n"
            "Corré primero pipeline/normalizar.py (deja ese archivo privado) "
            "o pasá --mapa con la ruta correcta.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    with ruta_mapa.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        faltantes = [c for c in CAMPOS_MAPA if c not in (lector.fieldnames or [])]
        if faltantes:
            print(
                f"El mapa {ruta_mapa} no tiene las columnas {faltantes}; "
                f"se esperaban {CAMPOS_MAPA}.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        filas = list(lector)

    por_nombre: dict[str, list[dict]] = {}
    por_clave: dict[tuple[str, str, str], list[dict]] = {}
    for fila in filas:
        por_nombre.setdefault(solo_alnum(fila["nombre_original"]), []).append(fila)
        categoria = normalizar_categoria(fila["categoria"])
        numero = numero_desde(fila["nombre_original"])
        autor = token_autor(fila["nombre_original"], categoria)
        por_clave.setdefault((categoria, numero, autor), []).append(fila)
    return por_nombre, por_clave


def resolver_id(
    nombre_viejo: str,
    categoria_metadata: str,
    autor_id: str,
    por_nombre: dict,
    por_clave: dict,
) -> tuple[str | None, str]:
    """
    Devuelve (id_imagen_nuevo, metodo). metodo es 'nombre', 'clave' o
    'ambiguo'/'sin_match' con id None.
    """
    # Pasada 1: nombre normalizado exacto.
    candidatos = por_nombre.get(solo_alnum(nombre_viejo), [])
    ids = {f["id_imagen"] for f in candidatos}
    if len(ids) == 1:
        return ids.pop(), "nombre"
    if len(ids) > 1:
        return None, "ambiguo"

    # Pasada 2: clave canónica (categoria, numero, autor).
    # La categoría del NOMBRE manda; tipo_manovich es solo respaldo (puede
    # venir mal cargado: p. ej. las filas casual_0X_DM tienen tipo "diseño").
    categoria = categoria_desde_nombre(nombre_viejo) or normalizar_categoria(
        categoria_metadata
    )
    numero = numero_desde(nombre_viejo)
    autores: list[str] = []
    autor_del_nombre = token_autor(nombre_viejo, categoria)
    if autor_del_nombre:
        autores.append(autor_del_nombre)
    autor_de_metadata = solo_alnum(autor_id)
    if autor_de_metadata and autor_de_metadata not in autores:
        autores.append(autor_de_metadata)

    encontrados: dict[str, dict] = {}
    for autor in autores:
        for fila in por_clave.get((categoria, numero, autor), []):
            encontrados[fila["id_imagen"]] = fila
    if len(encontrados) == 1:
        return next(iter(encontrados)), "clave"
    if len(encontrados) > 1:
        return None, "ambiguo"

    # Pasada 2b: tolerancia a autor truncado (p. ej. RN vs RNM).
    for autor in autores:
        for (cat, num, aut), filas in por_clave.items():
            if cat == categoria and num == numero and (
                aut.startswith(autor) or autor.startswith(aut)
            ):
                for fila in filas:
                    encontrados[fila["id_imagen"]] = fila
    if len(encontrados) == 1:
        return next(iter(encontrados)), "clave"
    if len(encontrados) > 1:
        return None, "ambiguo"

    return None, "sin_match"


# --------------------------------------------------------------------------
# Lectura/escritura de metadata conservando formato y columnas
# --------------------------------------------------------------------------
def leer_metadata(ruta: Path) -> tuple[list[dict], list[str], str]:
    # Detecta BOM para no cambiarlo al escribir.
    crudo = ruta.read_bytes()
    encoding = "utf-8-sig" if crudo[:3] == b"\xef\xbb\xbf" else "utf-8"
    with ruta.open(encoding=encoding, newline="") as f:
        lector = csv.DictReader(f)
        campos = list(lector.fieldnames or [])
        filas = list(lector)
    return filas, campos, encoding


def escribir_metadata(
    ruta: Path, filas: list[dict], campos: list[str], encoding: str
) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding=encoding) as f:
        # extrasaction="ignore": descarta columnas que no estén en `campos`
        # (p. ej. autor_apellido_nombre) sin tener que mutar las filas.
        escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def asociar(
    ruta_metadata: Path,
    ruta_mapa: Path,
    ruta_salida: Path,
    estricto: bool,
) -> None:
    por_nombre, por_clave = leer_mapa(ruta_mapa)
    filas, campos, encoding = leer_metadata(ruta_metadata)

    if "id_imagen" not in campos:
        print(f"{ruta_metadata} no tiene la columna id_imagen.", file=sys.stderr)
        raise SystemExit(2)

    campos_salida = [c for c in campos if c not in COLUMNAS_A_ELIMINAR]
    eliminadas = [c for c in campos if c in COLUMNAS_A_ELIMINAR]

    sin_match: list[tuple[int, dict]] = []
    ambiguos: list[tuple[int, dict]] = []
    usos: dict[str, list[int]] = {}
    metodos: dict[str, int] = {}

    for numero_fila, fila in enumerate(filas, start=2):
        viejo = fila["id_imagen"]
        nuevo, metodo = resolver_id(
            viejo,
            fila.get("tipo_manovich", ""),
            fila.get("autor_id", ""),
            por_nombre,
            por_clave,
        )
        metodos[metodo] = metodos.get(metodo, 0) + 1
        if nuevo is None:
            destino = ambiguos if metodo == "ambiguo" else sin_match
            destino.append((numero_fila, fila))
            continue
        fila["id_imagen"] = nuevo
        usos.setdefault(nuevo, []).append(numero_fila)

    repetidos = {k: v for k, v in usos.items() if len(v) > 1}

    print(f"\n{len(filas)} filas de {ruta_metadata}")
    print("  métodos de match: " + ", ".join(f"{k}={v}" for k, v in sorted(metodos.items())))
    print(f"  ids nuevos repetidos (varias filas a la misma foto): {len(repetidos)}")

    for numero_fila, fila in sin_match:
        print(
            f"  [SIN MATCH] fila {numero_fila}: {fila['id_imagen']!r} "
            f"(autor_id={fila.get('autor_id', '')!r}, tipo={fila.get('tipo_manovich', '')!r})",
            file=sys.stderr,
        )
    for numero_fila, fila in ambiguos:
        print(
            f"  [AMBIGUO] fila {numero_fila}: {fila['id_imagen']!r} "
            "matchea más de una foto; se deja sin reemplazar.",
            file=sys.stderr,
        )
    for id_nuevo, numeros in sorted(repetidos.items()):
        print(
            f"  [AVISO] id {id_nuevo} usado por las filas {numeros} "
            "(revisar duplicados de metadata)",
            file=sys.stderr,
        )

    if (sin_match or ambiguos) and estricto:
        print(
            "\n--estricto: hay filas sin asociar, NO se escribió la salida.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    escribir_metadata(ruta_salida, filas, campos_salida, encoding)
    if eliminadas:
        print(f"  columnas eliminadas: {', '.join(eliminadas)}")
    print(f"  columnas de salida: {', '.join(campos_salida)}")
    print(f"\n-> {ruta_salida}")
    if ruta_salida.resolve() != ruta_metadata.resolve():
        print(
            "   (para dejar metadata.csv con los ids nuevos y sin "
            "autor_apellido_nombre: --salida datos/metadata.csv)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reemplaza id_imagen viejos de metadata por los de normalizar.py (Fase 2)."
    )
    parser.add_argument("--metadata", type=Path, default=RUTA_METADATA_POR_DEFECTO)
    parser.add_argument("--mapa", type=Path, default=RUTA_MAPA_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=RUTA_SALIDA_POR_DEFECTO)
    parser.add_argument(
        "--estricto",
        action="store_true",
        help="No escribir la salida si alguna fila queda sin asociar.",
    )
    args = parser.parse_args()
    asociar(args.metadata, args.mapa, args.salida, args.estricto)


if __name__ == "__main__":
    main()
