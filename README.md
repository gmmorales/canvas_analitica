# Canvas Analítico — TPI Procesamiento de Imágenes

Proyecto grupal (comisión completa, 20 integrantes) que aplica analítica
cultural (Lev Manovich, *Instagram y la imagen contemporánea*) a un corpus
de 180 fotografías (20 personas × 9 fotos, formato 1:1), explorando qué
relación hay entre el tipo asignado por cada autor/a (`casual`,
`profesional`, `diseno`) y descriptores visuales calculados por un
pipeline propio.

> Este README se completa fase a fase. Las secciones marcadas `(TBD)`
> se llenan a medida que avanzamos.

## Estructura del repositorio

```
canvas-analitica/
├── README.md
├── datos/
│   ├── corpus_normalizado/
│   │   ├── casual/
│   │   ├── profesional/
│   │   └── diseno/
│   └── metadata.csv          # (TBD, Fase 2)
├── pipeline/                 # normalización + extracción de variables (Fase 1 y 2)
├── app/                      # Canvas Analítico en Streamlit (Fase 3)
├── paper/                    # decisiones, matriz-hallazgos.md, bitácora Voy/Vengo (Fase 4)
├── pyproject.toml            # dependencias (gestionadas con uv)
├── uv.lock
└── .python-version
```

`datos/corpus_original/` existe solo en copias locales de trabajo (no se
sube al repo — ver `.gitignore`): ahí van las fotos tal cual salen del
celular, antes de normalizar. Podés organizarlas como prefiero nombrarlas
(`casual_01_CB.jpg`) o en subcarpetas `casual/`, `profesional/`,
`diseno/` — `pipeline/normalizar.py` detecta la categoría de cualquiera
de las dos formas.

## Cómo correr el proyecto

Dependencias gestionadas con [uv](https://docs.astral.sh/uv/). No hace
falta crear ni activar un venv a mano: `uv run` lo resuelve solo a
partir de `pyproject.toml` / `uv.lock`.

```bash
uv sync --all-extras   # instala el entorno la primera vez (o si cambian las dependencias)
```

1. **Normalización** (Fase 1) — normaliza el corpus y deja el mapa de
   trazabilidad privado:
   ```bash
   uv run pipeline/normalizar.py \
       --entrada datos/corpus_original \
       --salida datos/corpus_normalizado
   ```
2. **Extracción de variables** (Fase 2, parte A):
   ```bash
   uv run pipeline/extraer_variables.py \
       --entrada datos/corpus_normalizado \
       --salida datos/variables_visuales.csv
   ```
3. **Asociación de ids en metadata** (Fase 2, parte B): reemplaza los
   nombres viejos de las fotos por los `id_imagen` nuevos que asignó
   `normalizar.py` y quita la columna `autor_apellido_nombre`:
   ```bash
   uv run pipeline/asociar_metadata.py \
       --metadata datos/metadata.csv \
       --mapa datos/trazabilidad_original_normalizado_privado.csv \
       --salida datos/metadata_normalizado.csv
   ```
   `metadata_normalizado.csv` queda con las columnas `id_imagen`,
   `autor_id`, `tipo_manovich`, `confianza_etiqueta`, `caso_limite`,
   `justificacion_etiqueta`. Para dejar el nombre `metadata.csv`, usar
   `--salida datos/metadata.csv`; en ese caso el paso 4 lo detecta solo.
   Este script no se puede correr dos veces por accidente: si los
   `id_imagen` ya son hashes, se detiene (usar `--forzar` para rehacerlo).
4. **Construir el dataset final** (Fase 2, parte C): une las etiquetas
   con las variables, normaliza las columnas categóricas (`diseño` ->
   `diseno`, `SI/NO` -> booleano) y avisa faltantes, duplicados y
   justificaciones fuera de 80-120 palabras:
   ```bash
   uv run pipeline/construir_dataset.py \
       --metadata datos/metadata_normalizado.csv \
       --variables datos/variables_visuales.csv \
       --salida datos/dataset.csv
   ```
5. **App** *(TBD — Fase 3)*: `uv run streamlit run app/canvas.py`

## Variables de color e histograma (Fase 2)

Implementadas en `pipeline/extraer_variables.py`, una fila por imagen en
`datos/variables_visuales.csv`. Cada una se explica en detalle (qué mide,
qué no mide) en el docstring del script — resumen:

| Variable | Qué mide | Convención/umbral |
|---|---|---|
| `mediana_luminancia` | nivel tonal global (mediana de gris) | — |
| `dispersion_luminancia` | contraste (desvío estándar de gris) | ver `CALCULAR_DISPERSION_COMO_IQR` |
| `prop_sombras` / `prop_altas_luces` | proporción de píxeles muy oscuros/claros | sombra si L < 0.10, altas luces si L > 0.90 |
| `matiz_dominante_deg` / `saturacion_media` | familia cromática y intensidad de color | media circular del hue ponderada por saturación (no promedio lineal) |
| `dominancia_cromatica` | cuánto concentra la imagen en una familia de color | cuantización a 8 niveles por canal RGB |

Los umbrales de sombra/altas luces y el nivel de cuantización son
convenciones documentadas en el script (`UMBRAL_SOMBRA`,
`UMBRAL_ALTAS_LUCES`, `NIVELES_CUANTIZACION`) — si se cambian después de
haber medido el corpus completo, hay que volver a correr el script sobre
las 180 imágenes.

`datos/variables_visuales.csv` es un resultado intermedio (solo las 5
variables, sin `autor_id`, etiquetas ni `justificacion_etiqueta`): el
dataset final se arma uniendo esta tabla con el archivo de etiquetas de
cada autor/a — ver `pipeline/construir_dataset.py` y "Dataset y
variables" más abajo.

Para agregar una dependencia nueva: `uv add <paquete>` (actualiza
`pyproject.toml` y `uv.lock` automáticamente, no se edita a mano).

## Protocolo de normalización

Implementado en `pipeline/normalizar.py`. Se aplica igual a las 180 imágenes.

**Normalización técnica (sí se aplica):**
1. Corrección de orientación EXIF, *antes* de leer dimensiones o medir nada.
2. Conversión a sRGB (si la imagen trae perfil ICC embebido se convierte
   desde ese perfil; si no trae perfil —el caso más común en fotos de
   celular— se asume sRGB por convención).
3. Redimensionado a **1024×1024 px** (dimensión final única). El pipeline
   *no recorta*: asume que cada imagen ya llegó 1:1 (recorte hecho por
   la persona autora al fotografiar).
4. Formato de salida único: **JPEG, calidad 95**, organizado en
   `datos/corpus_normalizado/{casual,profesional,diseno}/` según
   `tipo_manovich`. La categoría se detecta por el prefijo del nombre de
   archivo (`casual_01_CB.jpg` → `casual`) o, si no matchea, por el
   nombre de la carpeta contenedora. Lo que no se puede categorizar cae
   en `sin_categoria/` con un aviso — nunca se asigna a ciegas.
5. `id_imagen`: hash sha256 (16 hex) del contenido del archivo — no
   reutiliza el nombre original, que puede traer información personal
   (iniciales, fecha, etc.).

**Normalización tonal (NO se aplica acá):** ecualización de contraste,
brillo o saturación queda fuera del pipeline de normalización — se
mediría antes de calcular las variables de la Fase 2 y borraría
justamente la variación que se quiere describir.

**Trazabilidad `id_imagen` ↔ archivo original:** `normalizar.py` escribe
un mapa privado, una fila por imagen, con
`archivo_original`, `nombre_original`, `id_imagen`, `categoria` y
`archivo_normalizado`. Por defecto va a
`datos/trazabilidad_original_normalizado_privado.csv`: el `.gitignore` lo
excluye porque contiene los nombres originales (pueden traer iniciales,
fechas, etc.), así que no se sube al repo ni se comparte. Se puede
cambiar de ruta con `--mapa`, o no generarlo con `--sin-mapa`.
`pipeline/asociar_metadata.py` consume ese mapa para reemplazar los
nombres viejos de `metadata.csv` por los ids nuevos (y de paso quita la
columna `autor_apellido_nombre`); el cruce tolera typos, tildes y espacios
de los nombres cargados a mano, y avisa las filas que no puede asociar en
vez de asignarlas a ciegas.

Convenciones fijadas (si se cambian después de medir variables en la
Fase 2, hay que volver a normalizar y volver a medir todo el corpus):
`TAMANO_FINAL = 1024`, `FORMATO_SALIDA = "JPEG"`, `CALIDAD_JPEG = 95`.

## Dataset y variables

El dataset final es **una fila por fotografía** y se arma con
`pipeline/construir_dataset.py` (paso 4 de "Cómo correr el proyecto"),
uniendo las etiquetas autoasignadas con las variables ya medidas:
`datos/dataset.csv`.

Columnas, en orden:

1. `id_imagen` — hash sha256 (16 hex) del contenido; estable y no
   dependiente del nombre de archivo original.
2. `autor_id` — código/seudónimo de quien fotografió.
3. `tipo_manovich` — `casual`, `profesional` o `diseno` (el tipo
   autoasignado, no una categoría declarada).
4. `confianza_etiqueta` — `alta`, `media` o `baja`.
5. `caso_limite` — booleano (`True`/`False`): ¿la persona autora dudó
   entre dos tipos?
6. `justificacion_etiqueta` — texto de 80 a 120 palabras: por qué se
   asignó el tipo y qué ambigüedad reconoce. Queda como evidencia
   cualitativa, no se cuantifica.
7. Las 5 variables de color/histograma (7 columnas; ver la tabla de
   arriba): `mediana_luminancia`, `dispersion_luminancia`,
   `prop_sombras`, `prop_altas_luces`, `matiz_dominante_deg`,
   `saturacion_media`, `dominancia_cromatica`.

`construir_dataset.py` no recalcula nada: solo une por `id_imagen`,
normaliza las categóricas (`diseño` -> `diseno`, `Media` -> `media`,
`SI/NO` -> `True`/`False`) y **avisa por stderr** (sin corregir a ciegas)
los campos vacíos, los valores no reconocidos, las justificaciones fuera
de 80-120 palabras, los `id_imagen` duplicados y las fotos con variables
pero sin etiqueta. Con `--estricto` no escribe la salida si hay faltantes
o duplicados.

`datos/variables_visuales.csv` y `datos/metadata_normalizado.csv` son
resultados intermedios: la tabla que se entrega es `datos/dataset.csv`.

## Consentimiento y alcance ético

*(TBD: criterio de consentimiento/anonimización del grupo antes de
publicar el repo — qué fotos entran a `corpus_normalizado/`, cómo se
tratan los rostros de terceros, qué metadatos sensibles se remueven.)*

## Licencia

*(TBD: código y fotografías pueden — y probablemente deban — licenciarse
por separado. Definir antes de la entrega.)*

## Bitácora Voy/Vengo

Documentada en `paper/bitacora.md`.

## Integrantes

*(TBD — nombres/códigos de la comisión.)*
