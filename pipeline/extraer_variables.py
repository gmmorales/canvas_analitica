"""
pipeline/extraer_variables.py

Fase 2 (parte A) — Variables de color e histograma, una fila por imagen.

Lee datos/corpus_normalizado/{categoria}/*.jpg y calcula, para cada
imagen, las 5 variables propuestas en la consigna. Este script SOLO
calcula variables a partir de los píxeles — no toca autor_id,
confianza_etiqueta, caso_limite ni justificacion_etiqueta (eso viene de
un archivo de etiquetas aparte, autoasignado por cada persona, y se une
en un paso posterior: construir_metadata.py).

Salida: datos/variables_visuales.csv
  id_imagen, tipo_manovich, mediana_luminancia, dispersion_luminancia,
  prop_sombras, prop_altas_luces, matiz_dominante_deg, saturacion_media,
  dominancia_cromatica

-----------------------------------------------------------------------
Qué mide cada variable, qué NO mide, y qué convención asume
(para la bitácora Voy/Vengo — esto es una propuesta, no la única opción)
-----------------------------------------------------------------------

1. mediana_luminancia (0 a 1)
   Qué mide: nivel tonal global. Convierte la imagen a escala de grises
   con skimage.color.rgb2gray (pesos ITU-R 601-2: 0.2125 R + 0.7154 G +
   0.0721 B — no es un promedio simple de los 3 canales) y toma la
   MEDIANA de esos valores, no el promedio: la mediana es menos sensible
   a que una franja de cielo muy clara o una sombra muy oscura
   desplacen el número.
   Qué NO mide: no equivale a "exposición correcta" ni a calidad
   técnica (consigna, límite explícito).

2. dispersion_luminancia (0 a ~0.5)
   Qué mide: contraste, como desvío estándar de la misma escala de
   grises — qué tan repartidos están los tonos.
   Decisión a confirmar: la consigna ofrece desvío estándar O rango
   intercuartílico (IQR) como alternativas válidas. Implementé desvío
   estándar por ser más directo de explicar; si el grupo prefiere IQR
   (más robusto a un puñado de píxeles extremos), es un cambio de una
   línea — ver CALCULAR_DISPERSION_COMO_IQR más abajo.
   Qué NO mide: el rango dinámico de la escena original — solo el de
   la imagen ya capturada (el sensor del celular y su procesado
   automático ya intervinieron antes).

3. prop_sombras / prop_altas_luces (0 a 1 cada una)
   Qué miden: proporción de píxeles por debajo/encima de un umbral de
   luminancia normalizada, sobre la misma escala de grises.
   Convención inicial (la que sugiere la consigna, a revisar contra una
   muestra del propio corpus): sombra si L < 0.10, altas luces si
   L > 0.90. Ver UMBRAL_SOMBRA / UMBRAL_ALTAS_LUCES.
   Qué NO miden: no distinguen "sombra fotográfica intencional" de
   "imagen subexpuesta" — es una convención de umbral, no un juicio
   fotográfico. Además, el procesado automático del celular (HDR,
   realce de sombras) ya intervino antes de que este script vea el
   píxel.

4. matiz_dominante_deg (0 a 360) y saturacion_media (0 a 1)
   Qué miden: familia cromática predominante e intensidad de color
   global. Convierto a HSV con skimage.color.rgb2hsv. El matiz (hue) es
   una variable CIRCULAR (0° y 360° son el mismo rojo): promediarlo
   linealmente puede dar un resultado sin sentido si hay píxeles cerca
   de los dos extremos (p. ej. rojos a 5° y a 355° promediarían a 180°,
   ¡cian!, cuando en realidad son casi el mismo color). Por eso se
   calcula la MEDIA CIRCULAR ponderada por saturación: cada píxel aporta
   un vector (cos(hue), sin(hue)) de longitud = su saturación (los
   píxeles poco saturados, casi grises, pesan menos porque su matiz es
   poco confiable), se suman los vectores, y el ángulo resultante es el
   matiz dominante. La saturación media es un promedio aritmético
   simple del canal S (ese sí es una escala lineal, no circular).
   Qué NO miden: dependen del balance de blancos, los filtros y el
   procesado de color de cada celular — no son una medición "neutra"
   del color de la escena real.

5. dominancia_cromatica (0 a 1)
   Qué mide: cuánto concentra la imagen en una familia de color.
   Cuantizo cada canal RGB a NIVELES_CUANTIZACION niveles (por defecto
   8), formo un histograma 3D de los colores cuantizados resultantes, y
   tomo la proporción de píxeles que caen en el bucket más frecuente.
   Un valor alto = la imagen está dominada por una sola familia de
   color; un valor bajo = colores repartidos.
   Qué NO mide: dos imágenes muy distintas pueden dar un valor similar
   si ambas están "concentradas" en colores diferentes — esta variable
   no dice CUÁL es el color dominante, solo CUÁNTO concentra la imagen
   en él. El resultado depende del número de niveles elegido: más
   niveles = buckets más finos = valores de dominancia más bajos en
   general (ver NIVELES_CUANTIZACION).

Escala: estas 5 variables se calculan por imagen (una fila por foto).
Los histogramas agregados y las distribuciones por tipo son una
agregación posterior, de la Fase 4, sobre el corpus completo.

Uso:
    python pipeline/extraer_variables.py \
        --entrada datos/corpus_normalizado \
        --salida datos/variables_visuales.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import rgb2gray, rgb2hsv

# --------------------------------------------------------------------------
# Convenciones del grupo — documentar en el README si se cambian.
# Si se ajustan DESPUÉS de haber medido, hay que recalcular todo el dataset.
# --------------------------------------------------------------------------
UMBRAL_SOMBRA = 0.10          # luminancia normalizada por debajo de esto = sombra
UMBRAL_ALTAS_LUCES = 0.90     # luminancia normalizada por encima de esto = altas luces
NIVELES_CUANTIZACION = 8      # niveles por canal RGB para dominancia cromática (8x8x8 = 512 buckets)
CALCULAR_DISPERSION_COMO_IQR = False  # False = desvío estándar; True = rango intercuartílico


def calcular_luminancia(img_rgb: np.ndarray) -> np.ndarray:
    """Escala de grises normalizada [0, 1] con pesos ITU-R 601-2 (skimage)."""
    return rgb2gray(img_rgb)


def mediana_y_dispersion(gris: np.ndarray) -> tuple[float, float]:
    mediana = float(np.median(gris))
    if CALCULAR_DISPERSION_COMO_IQR:
        q75, q25 = np.percentile(gris, [75, 25])
        dispersion = float(q75 - q25)
    else:
        dispersion = float(np.std(gris))
    return mediana, dispersion


def proporcion_sombras_altas_luces(gris: np.ndarray) -> tuple[float, float]:
    total = gris.size
    prop_sombras = float(np.count_nonzero(gris < UMBRAL_SOMBRA)) / total
    prop_altas_luces = float(np.count_nonzero(gris > UMBRAL_ALTAS_LUCES)) / total
    return prop_sombras, prop_altas_luces


def matiz_dominante_y_saturacion(img_rgb: np.ndarray) -> tuple[float, float]:
    """
    Matiz dominante: media circular del hue, ponderada por saturación.
    Saturación media: promedio aritmético simple del canal S.
    """
    hsv = rgb2hsv(img_rgb)
    hue = hsv[:, :, 0].ravel()          # en [0, 1) -> se pasa a radianes *2*pi
    sat = hsv[:, :, 1].ravel()          # en [0, 1]

    angulos = hue * 2 * np.pi
    x = np.sum(np.cos(angulos) * sat)
    y = np.sum(np.sin(angulos) * sat)

    if x == 0 and y == 0:
        # Caso degenerado: saturación ~0 en toda la imagen (escala de
        # grises casi pura). El matiz no es representativo; se informa
        # como 0.0 y queda documentado acá, no se oculta.
        matiz_deg = 0.0
    else:
        matiz_deg = float(np.degrees(np.arctan2(y, x)) % 360)

    saturacion_media = float(np.mean(sat))
    return matiz_deg, saturacion_media


def dominancia_cromatica(img_rgb: np.ndarray, niveles: int = NIVELES_CUANTIZACION) -> float:
    """
    Cuantiza cada canal a `niveles` valores, arma un histograma 3D de
    los colores cuantizados resultantes, y devuelve la proporción de
    píxeles en el bucket más frecuente.
    """
    ancho_bin = 256 // niveles
    cuantizada = (img_rgb // ancho_bin).astype(np.int32)
    cuantizada = np.clip(cuantizada, 0, niveles - 1)

    indices = (
        cuantizada[:, :, 0] * niveles * niveles
        + cuantizada[:, :, 1] * niveles
        + cuantizada[:, :, 2]
    ).ravel()

    conteos = np.bincount(indices, minlength=niveles ** 3)
    return float(conteos.max()) / indices.size


def calcular_variables_una_imagen(ruta: Path) -> dict:
    with Image.open(ruta) as img:
        img_rgb = np.asarray(img.convert("RGB"))

    gris = calcular_luminancia(img_rgb)
    mediana, dispersion = mediana_y_dispersion(gris)
    prop_sombras, prop_altas_luces = proporcion_sombras_altas_luces(gris)
    matiz_deg, saturacion_media = matiz_dominante_y_saturacion(img_rgb)
    dominancia = dominancia_cromatica(img_rgb)

    return {
        "id_imagen": ruta.stem,
        "tipo_manovich": ruta.parent.name,
        "mediana_luminancia": round(mediana, 4),
        "dispersion_luminancia": round(dispersion, 4),
        "prop_sombras": round(prop_sombras, 4),
        "prop_altas_luces": round(prop_altas_luces, 4),
        "matiz_dominante_deg": round(matiz_deg, 2),
        "saturacion_media": round(saturacion_media, 4),
        "dominancia_cromatica": round(dominancia, 4),
    }


def extraer_variables_corpus(dir_entrada: Path, ruta_salida: Path) -> None:
    rutas = sorted(dir_entrada.rglob("*.jpg")) + sorted(dir_entrada.rglob("*.png"))
    if not rutas:
        print(f"No se encontraron imágenes normalizadas en {dir_entrada}", file=sys.stderr)
        return

    filas = []
    for ruta in rutas:
        print(f"Calculando variables de {ruta.relative_to(dir_entrada)} ...")
        fila = calcular_variables_una_imagen(ruta)
        filas.append(fila)
        print(f"  -> {fila}")

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)

    print(f"\n{len(filas)} imágenes procesadas -> {ruta_salida}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extracción de variables visuales (Fase 2, parte A).")
    parser.add_argument("--entrada", type=Path, default=Path("datos/corpus_normalizado"))
    parser.add_argument("--salida", type=Path, default=Path("datos/variables_visuales.csv"))
    args = parser.parse_args()
    extraer_variables_corpus(args.entrada, args.salida)


if __name__ == "__main__":
    main()
