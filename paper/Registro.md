# Paso a paso técnico – Canvas Analítico


## 1. Creación y organización del proyecto

El proyecto se encuentra centralizado en el repositorio de GitHub
`canvas_analitica`.

El repositorio está organizado en distintas carpetas según su función:

- `pipeline/`: contiene los scripts de Python utilizados para procesar las imágenes.
- `datos/`: contiene los datos de entrada y los resultados generados durante el procesamiento.
- `app/`: destinada a la futura aplicación o Canvas Analítico.
- `paper/`: destinada a la documentación del proyecto.


**Resultado:** quedó definida una estructura común para organizar y desarrollar
el trabajo.

---

## 2. Preparación del entorno de programación

El proyecto está desarrollado en Python.

Para administrar el entorno y las librerías necesarias se utiliza `uv`.

Las dependencias del proyecto se encuentran definidas principalmente en
`pyproject.toml` y `uv.lock`.

Para preparar el entorno se ejecutó:

    uv sync --all-extras

Al ejecutar este comando, `uv` creó el entorno virtual `.venv` e instaló las
dependencias necesarias para ejecutar el proyecto.

**Resultado:** quedó preparado el entorno de Python con las dependencias
necesarias para ejecutar el código.

---

## 3. Preparación del corpus original

Las fotografías originales se incorporaron en:

    datos/corpus_original/

El corpus se encuentra organizado en tres categorías:

    corpus_original/
    ├── Casual/
    ├── diseno/
    └── Profesional/

Estas fotografías constituyen los datos de entrada del procesamiento.

Los archivos originales se mantienen sin modificaciones. El programa los lee
y genera nuevas imágenes procesadas en otra carpeta, permitiendo conservar
siempre la fuente original.

El corpus original se utiliza de manera local y no se almacena dentro del
repositorio de GitHub.

**Resultado:** quedó disponible el corpus original, organizado por categoría.


---

## 4. Normalización de las imágenes

Para realizar la normalización se utiliza el script:

    pipeline/normalizar.py

El objetivo de este proceso es generar una versión técnicamente estandarizada
de cada fotografía sin modificar los archivos originales.

Entre las operaciones realizadas por el script se encuentran:

- lectura de las fotografías originales;
- identificación de la categoría de cada imagen;
- corrección de la orientación mediante información EXIF;
- conversión al espacio de color sRGB;
- homogeneización técnica de las imágenes;
- generación de un identificador para cada imagen;
- almacenamiento de la nueva imagen dentro del corpus normalizado.

La normalización realizada es técnica y no busca igualar características
visuales como brillo, contraste o saturación.

---

## 5. Control de imágenes durante la normalización

Durante la ejecución, el programa realiza controles sobre las imágenes.

Por ejemplo, si encuentra una fotografía que no es completamente cuadrada,
genera un aviso indicando sus dimensiones y señala que debe revisarse el
encuadre original.

Ejemplo de aviso:

    [aviso] imagen no cuadrada (...); se redimensiona igual pero revisar el encuadre original.

Este mensaje funciona como advertencia y no detiene el procesamiento.

También se informa durante el proceso:

- el identificador de la imagen (`id_imagen`);
- la categoría;
- la orientación EXIF original, cuando está disponible.

**Resultado:** las imágenes pueden ser procesadas y, al mismo tiempo, quedan
señalados los casos que requieren una revisión posterior.

---

## 6. Ejecución del proceso de normalización

Una vez preparado el entorno y disponible el corpus original, se ejecutó:

    uv run pipeline/normalizar.py --entrada datos/corpus_original --salida datos/corpus_normalizado

El comando indica:

- `--entrada datos/corpus_original`: carpeta desde la cual se leen las fotografías originales.
- `--salida datos/corpus_normalizado`: carpeta donde se generan las fotografías normalizadas.

El proceso sigue el siguiente flujo:

    corpus_original
          ↓
    normalizar.py
          ↓
    corpus_normalizado

Las fotografías originales permanecen sin modificaciones.

---

## 7. Resultado de la normalización

La ejecución finalizó correctamente con un total de **196 imágenes
normalizadas**.

La distribución obtenida fue:

- Casual: 66 imágenes
- Diseño: 66 imágenes
- Profesional: 64 imágenes

El resultado quedó almacenado en:

    datos/corpus_normalizado/

con la siguiente estructura:

    corpus_normalizado/
    ├── casual/
    ├── diseno/
    └── profesional/

Por lo tanto, al finalizar esta etapa existen dos conjuntos diferenciados:

    datos/
    ├── corpus_original/       # fotografías originales
    └── corpus_normalizado/    # fotografías generadas por el pipeline

Esto permite conservar las imágenes fuente y trabajar en las etapas
posteriores sobre las versiones técnicamente normalizadas.

---

## Estado del proyecto al finalizar esta etapa

Hasta el momento se completó el siguiente flujo:

    Fotografías originales
            ↓
    datos/corpus_original
            ↓
    pipeline/normalizar.py
            ↓
    Normalización técnica
            ↓
    datos/corpus_normalizado
            ↓
    196 imágenes normalizadas

La normalización del corpus quedó ejecutada correctamente.

---

## Próxima etapa

La siguiente etapa prevista es la extracción de variables visuales a partir
de las imágenes normalizadas.

