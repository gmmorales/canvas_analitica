"""
pipeline/normalizar.py

Fase 1 — Normalización técnica del corpus (Canvas Analítico, TPI Manovich).

Qué hace (y qué NO hace) este script:

  SÍ aplica, sí o sí, a las 180 imágenes:
    1. Corrección de orientación EXIF (antes de leer dimensiones o medir nada).
    2. Conversión a sRGB.
    3. Redimensionado a una dimensión final única y documentada (ver TAMANO_FINAL).
       El pipeline NO recorta: las fotos ya llegan encuadradas 1:1 por cada autor/a;
       acá solo se lleva ese cuadrado a un tamaño estándar.
    4. Guardado en un formato de archivo único y documentado (ver FORMATO_SALIDA),
       organizado por categoría (tipo_manovich) en subcarpetas:
       datos/corpus_normalizado/{casual,profesional,diseno}/
    5. Un id_imagen estable que NO reutiliza el nombre de archivo original
       (hash del contenido de la imagen), porque el nombre puede traer
       información personal (iniciales, fecha, etc. — como en este mismo
       corpus de prueba: "casual_01_CB.jpg").

  NO aplica (y no debe aplicarse acá):
    - Ecualización de contraste, brillo o saturación (normalización TONAL).
      Eso borraría la variación que en la Fase 2 vamos a medir. Si en algún
      momento se necesita para la interfaz, es sobre una copia aparte,
      nunca sobre el corpus que se usa para extraer variables.

Cómo se detecta la categoría (tipo_manovich) de cada imagen:
  1. Se busca el prefijo del nombre de archivo antes del primer "_"
     (ej.: "casual_01_CB.jpg" -> "casual").
  2. Si eso no matchea ninguna categoría válida, se prueba con el nombre
     de la carpeta contenedora (por si organizás datos/corpus_original/
     en subcarpetas casual/, profesional/, diseno/ en vez de nombrar los
     archivos con prefijo).
  3. Si ninguna de las dos funciona, la imagen se guarda en
     datos/corpus_normalizado/sin_categoria/ y se avisa por stderr —
     nunca se descarta ni se asigna una categoría a ciegas.

  El script acepta cualquiera de las dos convenciones de entrada (archivos
  planos con prefijo, o subcarpetas por categoría) porque escanea
  datos/corpus_original/ de forma recursiva.

Trazabilidad (nombre original -> id_imagen) — la pide la Fase 2:
  Este script TAMBIÉN escribe un mapa con una fila por imagen normalizada,

      archivo_original, nombre_original, id_imagen, categoria, archivo_normalizado

  El archivo por defecto es datos/trazabilidad_original_normalizado_privado.csv.
  Es PRIVADO (termina en "_privado.csv"): contiene los nombres originales
  de las fotos, que pueden traer iniciales, fechas, etc. El .gitignore ya
  lo excluye, no lo subas al repo ni lo compartas. Sirve para que
  pipeline/asociar_metadata.py reemplace los nombres viejos de
  datos/metadata.csv por los id_imagen nuevos. Se puede cambiar de ruta
  con --mapa. Si preferís no generarlo, pasá --sin-mapa.

Uso:
    python pipeline/normalizar.py \
        --entrada datos/corpus_original \
        --salida datos/corpus_normalizado \
        --mapa datos/trazabilidad_original_normalizado_privado.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

from PIL import Image, ImageCms

# --------------------------------------------------------------------------
# Convenciones del grupo — documentar acá y en el README si se cambian.
# Si se modifican DESPUÉS de haber medido variables (Fase 2), hay que
# volver a normalizar y volver a medir todo el corpus.
# --------------------------------------------------------------------------
TAMANO_FINAL = 1024          # px, imagen final cuadrada TAMANO_FINAL x TAMANO_FINAL
FORMATO_SALIDA = "JPEG"      # único formato de salida para las 180 imágenes
CALIDAD_JPEG = 95            # solo aplica si FORMATO_SALIDA == "JPEG"
EXTENSIONES_ENTRADA = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
CATEGORIAS_VALIDAS = {"casual", "profesional", "diseno"}
CATEGORIA_DESCONOCIDA = "sin_categoria"

PERFIL_SRGB = ImageCms.createProfile("sRGB")

# Mapa de trazabilidad nombre_original -> id_imagen. Es privado (contiene
# los nombres originales): termina en "_privado.csv" y el .gitignore lo
# excluye. Lo consume pipeline/asociar_metadata.py.
RUTA_MAPA_POR_DEFECTO = Path("datos/trazabilidad_original_normalizado_privado.csv")


def calcular_id_imagen(datos_bytes: bytes) -> str:
    """
    id_imagen estable y anónimo: hash sha256 del contenido de la imagen
    (no del nombre de archivo, que puede tener iniciales, fecha, etc.).
    Se trunca a 16 hex para que sea manejable; la probabilidad de
    colisión en un corpus de 180 imágenes es despreciable.
    """
    return hashlib.sha256(datos_bytes).hexdigest()[:16]


def detectar_categoria(ruta: Path) -> str:
    """
    Determina tipo_manovich (casual/profesional/diseno) a partir de:
      1. El prefijo del nombre de archivo antes del primer "_".
      2. Si no matchea, el nombre de la carpeta contenedora.
    Si ninguna de las dos coincide con CATEGORIAS_VALIDAS, devuelve
    CATEGORIA_DESCONOCIDA (nunca falla en silencio: se avisa aparte).
    """
    prefijo = ruta.stem.split("_")[0].lower()
    if prefijo in CATEGORIAS_VALIDAS:
        return prefijo

    nombre_carpeta = ruta.parent.name.lower()
    if nombre_carpeta in CATEGORIAS_VALIDAS:
        return nombre_carpeta

    return CATEGORIA_DESCONOCIDA


def leer_orientacion_exif(img: Image.Image) -> int | None:
    exif = img.getexif()
    return exif.get(0x0112)  # tag EXIF "Orientation"


def corregir_orientacion_exif(img: Image.Image) -> Image.Image:
    """
    Aplica físicamente la rotación/espejado que indica el tag EXIF
    Orientation, y devuelve una imagen SIN ese tag (ya no hace falta:
    los píxeles ya están en la orientación correcta).
    """
    from PIL import ImageOps
    img_corregida = ImageOps.exif_transpose(img)
    return img_corregida if img_corregida is not None else img


def convertir_a_srgb(img: Image.Image) -> Image.Image:
    """
    Si la imagen trae un perfil ICC embebido distinto de sRGB, convierte.
    Si NO trae perfil (caso más común en fotos de celular, incluidas las
    de este corpus de prueba), se asume sRGB por convención — la mayoría
    de las cámaras de celular graban en sRGB por defecto — y solo se
    asegura el modo de color RGB.
    """
    perfil_icc = img.info.get("icc_profile")
    if perfil_icc:
        try:
            perfil_entrada = ImageCms.ImageCmsProfile(
                __import__("io").BytesIO(perfil_icc)
            )
            img = ImageCms.profileToProfile(
                img, perfil_entrada, PERFIL_SRGB, outputMode="RGB"
            )
        except (ImageCms.PyCMSError, OSError):
            # Perfil embebido corrupto o no soportado: fallback documentado.
            img = img.convert("RGB")
    else:
        img = img.convert("RGB")
    return img


def redimensionar(img: Image.Image, tamano: int) -> Image.Image:
    """
    Redimensiona a tamano x tamano. NO recorta: asume que la imagen ya
    llega 1:1 (recorte hecho por cada autor/a al fotografiar). Si por
    algún motivo no llega exactamente cuadrada, avisa en stderr en vez
    de recortar en silencio — el recorte es una decisión fotográfica,
    no una decisión del pipeline.
    """
    ancho, alto = img.size
    if ancho != alto:
        print(
            f"  [aviso] imagen no cuadrada ({ancho}x{alto}); "
            "se redimensiona igual pero revisar el encuadre original.",
            file=sys.stderr,
        )
    return img.resize((tamano, tamano), Image.LANCZOS)


def normalizar_una_imagen(
    ruta_origen: Path, dir_salida: Path
) -> tuple[str, str, Path]:
    """
    Normaliza una imagen y devuelve (id_imagen, categoria, ruta_salida)
    para el resumen por consola y para el mapa de trazabilidad.
    """
    datos_originales = ruta_origen.read_bytes()
    id_imagen = calcular_id_imagen(datos_originales)
    categoria = detectar_categoria(ruta_origen)
    if categoria == CATEGORIA_DESCONOCIDA:
        print(
            f"  [aviso] no se pudo determinar la categoría de "
            f"{ruta_origen.name} (ni por prefijo ni por carpeta); "
            f"va a {CATEGORIA_DESCONOCIDA}/ para revisión manual.",
            file=sys.stderr,
        )

    with Image.open(ruta_origen) as img:
        orientacion_original = leer_orientacion_exif(img)

        img = corregir_orientacion_exif(img)
        img = convertir_a_srgb(img)
        img = redimensionar(img, TAMANO_FINAL)

        extension = ".jpg" if FORMATO_SALIDA == "JPEG" else ".png"
        dir_categoria = dir_salida / categoria
        dir_categoria.mkdir(parents=True, exist_ok=True)
        ruta_salida = dir_categoria / f"{id_imagen}{extension}"

        if FORMATO_SALIDA == "JPEG":
            img.save(ruta_salida, format="JPEG", quality=CALIDAD_JPEG)
        else:
            img.save(ruta_salida, format="PNG")

    print(f"  -> id_imagen={id_imagen}  categoria={categoria}  "
          f"(orientación EXIF original={orientacion_original})")
    return id_imagen, categoria, ruta_salida


def escribir_mapa_trazabilidad(filas: list[dict], ruta_mapa: Path) -> None:
    """
    Escribe el mapa nombre_original -> id_imagen que devuelve normalizar.py.
    PRIVADO: contiene los nombres originales de las fotos. No subir al repo.
    """
    ruta_mapa.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "archivo_original",
        "nombre_original",
        "id_imagen",
        "categoria",
        "archivo_normalizado",
    ]
    with ruta_mapa.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)


def normalizar_corpus(
    dir_entrada: Path, dir_salida: Path, ruta_mapa: Path | None
) -> None:
    dir_salida.mkdir(parents=True, exist_ok=True)

    # rglob (recursivo): funciona tanto si corpus_original/ tiene los
    # archivos planos con prefijo (casual_01_CB.jpg) como si están
    # organizados en subcarpetas casual/, profesional/, diseno/.
    rutas = sorted(
        p
        for p in dir_entrada.rglob("*")
        if p.is_file() and p.suffix.lower() in EXTENSIONES_ENTRADA
    )
    if not rutas:
        print(f"No se encontraron imágenes en {dir_entrada}", file=sys.stderr)
        return

    conteo_por_categoria: dict[str, int] = {}
    filas_mapa: list[dict] = []
    for ruta in rutas:
        print(f"Normalizando {ruta.relative_to(dir_entrada)} ...")
        id_imagen, categoria, ruta_salida = normalizar_una_imagen(ruta, dir_salida)
        conteo_por_categoria[categoria] = conteo_por_categoria.get(categoria, 0) + 1
        filas_mapa.append(
            {
                "archivo_original": ruta.relative_to(dir_entrada).as_posix(),
                "nombre_original": ruta.stem,
                "id_imagen": id_imagen,
                "categoria": categoria,
                "archivo_normalizado": ruta_salida.relative_to(dir_salida).as_posix(),
            }
        )

    print(f"\n{len(rutas)} imágenes normalizadas -> {dir_salida}")
    for categoria, cantidad in sorted(conteo_por_categoria.items()):
        print(f"  {categoria}: {cantidad}")

    if ruta_mapa is not None:
        escribir_mapa_trazabilidad(filas_mapa, ruta_mapa)
        print(
            f"\nMapa de trazabilidad (nombre original -> id_imagen) -> {ruta_mapa}\n"
            "  [aviso] ese archivo contiene los nombres originales de las fotos "
            "y está ignorado por git; no lo subas ni lo compartas."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalización técnica del corpus (Fase 1).")
    parser.add_argument("--entrada", type=Path, default=Path("datos/corpus_original"))
    parser.add_argument("--salida", type=Path, default=Path("datos/corpus_normalizado"))
    parser.add_argument(
        "--mapa",
        type=Path,
        default=RUTA_MAPA_POR_DEFECTO,
        help=(
            "CSV de trazabilidad nombre original -> id_imagen (privado, "
            "ignorado por git)."
        ),
    )
    parser.add_argument(
        "--sin-mapa",
        action="store_true",
        help="No escribir el CSV de trazabilidad.",
    )
    args = parser.parse_args()
    ruta_mapa = None if args.sin_mapa else args.mapa
    normalizar_corpus(args.entrada, args.salida, ruta_mapa)


if __name__ == "__main__":
    main()

