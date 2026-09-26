# Canvas Analítico

**Analítica cultural aplicada a fotografías de Instagram, basada en el marco de Lev Manovich**

---

## Contexto del proyecto

Lev Manovich propone leer las imágenes de Instagram no solo por su
contenido, sino por sus propiedades visuales: luminosidad, contraste,
color, composición.

Canvas Analítico toma esa propuesta y la vuelve un pipeline reproducible:
un corpus de fotografías reales, autoetiquetadas por su tipo, procesado
para extraer descriptores visuales objetivos — y comparar si lo que cada
autor/a *dice* que es su foto coincide con lo que la imagen *mide*.

---

## ¿Cómo funciona?

```
Foto original (celular)
        │
        ▼
  1. normalizar.py
     orientación EXIF · sRGB · 1024×1024 · id anónimo por hash
        │
        ├─────────────────────────────┐
        ▼                             ▼
  2. extraer_variables.py    mapa privado de trazabilidad
     5 variables de color      (archivo original ↔ id_imagen,
        │                       no se sube al repo)
        │                             ▼
        │                    3. asociar_metadata.py
        │                       referencias.csv (nombres) + mapa
        │                       → metadata_normalizado.csv
        │                             │
        └──────────────┬──────────────┘
                        ▼
              4. construir_dataset.py
                 une variables + etiquetas → dataset.csv
                        │
                        ▼
              Canvas interactivo (Streamlit)
```

1. **`normalizar.py`** — corrige la orientación EXIF, convierte a sRGB
   y redimensiona cada foto a 1024×1024. A cada imagen le asigna un
   `id_imagen` anónimo (hash de su contenido, no del nombre de archivo
   original) y organiza la salida en
   `datos/corpus_normalizado/{casual,profesional,diseno}/`. De paso
   escribe un mapa privado que conecta cada `id_imagen` con el archivo
   original — necesario para el paso 3, pero que nunca se sube al repo.

2. **`extraer_variables.py`** — sobre cada foto ya normalizada, mide
   las 5 variables de color e histograma (ver tabla más abajo) y las
   vuelca en `datos/variables_visuales.csv`, una fila por imagen.

3. **`asociar_metadata.py`** — el archivo de etiquetas que completa
   cada autor/a (`datos/referencias.csv`) nombra las fotos por su
   nombre original y trae el nombre y apellido de la persona autora.
   Este script usa el mapa privado del paso 1 para reemplazar esos
   nombres originales por los `id_imagen` anónimos, y descarta la
   columna con nombre y apellido. Resultado: `datos/metadata_normalizado.csv`.

4. **`construir_dataset.py`** — une `metadata_normalizado.csv` (las
   etiquetas) con `variables_visuales.csv` (lo medido) por `id_imagen`,
   y arma la tabla final: `datos/dataset.csv`.

5. **Canvas interactivo** (`app/canvas.py`, Streamlit) — lee
   `dataset.csv` y arma la visualización explorable del corpus (detalle
   en "Instalación y uso local").

---

## Corpus de trabajo

207 fotografías (formato 1:1), tomadas con celular y autoetiquetadas
según la tipología de Manovich: `casual`, `profesional`, `diseno`. Cada
foto viene acompañada de:

- `confianza_etiqueta` — qué tan segura estuvo la persona autora de su
  clasificación (`alta`/`media`/`baja`).
- `caso_limite` — si dudó entre dos tipos.
- `justificacion_etiqueta` — un texto de 80 a 120 palabras explicando el
  criterio de clasificación.

---

## Variables medidas

| Variable | Qué mide |
|---|---|
| `mediana_luminancia` | Nivel tonal global de la imagen |
| `dispersion_luminancia` | Contraste (qué tan repartidos están los tonos) |
| `prop_sombras` / `prop_altas_luces` | Proporción de píxeles muy oscuros / muy claros |
| `matiz_dominante_deg` / `saturacion_media` | Familia cromática predominante e intensidad de color |
| `dominancia_cromatica` | Cuánto concentra la imagen en una sola familia de color |

Son 5 variables medidas en 7 columnas numéricas (las dos últimas filas
de la tabla se registran como par). Cada una está documentada en
detalle —qué mide, qué convención asume y qué no captura— directamente
en el docstring de `pipeline/extraer_variables.py`.

---

## Estructura del proyecto

```
canvas_analitica/
├── README.md
├── pipeline/
│   ├── normalizar.py           # 1 — normalización técnica
│   ├── extraer_variables.py    # 2 — variables de color/histograma
│   ├── asociar_metadata.py     # 3 — id_imagen en las etiquetas
│   └── construir_dataset.py    # 4 — dataset final
├── app/
│   └── canvas.py                # Canvas interactivo (Streamlit)
├── paper/                       # bitácora, decisiones, licencia, nómina
├── datos/
│   ├── corpus_normalizado/
│   │   ├── casual/
│   │   ├── profesional/
│   │   └── diseno/
│   ├── variables_visuales.csv   # salida de extraer_variables.py
│   ├── metadata_normalizado.csv # salida de asociar_metadata.py
│   └── dataset.csv              # dataset final, salida de construir_dataset.py
├── pyproject.toml
├── uv.lock
└── .python-version
```

Tres archivos son **locales, no se suben al repositorio** (ver
`.gitignore`):

- `datos/corpus_original/` — las fotos crudas, sin normalizar; puede
  tener EXIF con datos del dispositivo o geolocalización.
- `datos/referencias.csv` — el archivo de entradas del corpus (una fila
  por foto, con nombre y apellido de la persona autora); se comparte
  con el grupo por otro canal, no por git.
- `datos/trazabilidad_original_normalizado_privado.csv` — el mapa
  privado del paso 1; conecta cada `id_imagen` con el nombre de archivo
  original.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Procesamiento de imagen | Pillow, scikit-image |
| Cómputo numérico | NumPy |
| Datos tabulares | CSV nativo (sin pandas en el pipeline) |
| Interfaz | Streamlit |
| Gestión de dependencias | [uv](https://docs.astral.sh/uv/) |

---

## Demo

La aplicación está disponible públicamente en Streamlit Community Cloud:

[https://canvas-manovich.streamlit.app/](https://canvas-manovich.streamlit.app/)

---

## Instalación y uso local

```bash
git clone https://github.com/gmmorales/canvas_analitica.git
cd canvas_analitica

uv sync --all-extras
```

Con las fotos originales en `datos/corpus_original/` y el archivo de
referencias en `datos/referencias.csv`, correr el pipeline en orden:

```bash
# 1. Normalización — deja el mapa de trazabilidad privado
uv run pipeline/normalizar.py \
    --entrada datos/corpus_original \
    --salida datos/corpus_normalizado

# 2. Extracción de variables
uv run pipeline/extraer_variables.py \
    --entrada datos/corpus_normalizado \
    --salida datos/variables_visuales.csv

# 3. Reemplazo de nombres por id_imagen en las referencias
uv run pipeline/asociar_metadata.py \
    --metadata datos/referencias.csv \
    --mapa datos/trazabilidad_original_normalizado_privado.csv \
    --salida datos/metadata_normalizado.csv

# 4. Dataset final
uv run pipeline/construir_dataset.py \
    --metadata datos/metadata_normalizado.csv \
    --variables datos/variables_visuales.csv \
    --salida datos/dataset.csv

# 5. Canvas interactivo
uv run streamlit run app/canvas.py
```

Cada script admite rutas de entrada/salida por parámetro — ver
`--help` en cada uno. Para agregar una dependencia nueva: `uv add
<paquete>` (actualiza `pyproject.toml` y `uv.lock` solo).

**Sobre `asociar_metadata.py`**: el cruce entre `referencias.csv` y el
mapa de trazabilidad tolera typos, tildes y espacios en los nombres
cargados a mano, y avisa las filas que no puede asociar en vez de
asignarlas a ciegas. No se puede correr dos veces por accidente: si los
`id_imagen` de la entrada ya son hashes, se detiene (usar `--forzar`
para rehacerlo).

**Sobre el Canvas interactivo**: detecta solo qué columnas de
`dataset.csv` son numéricas (candidatas a los ejes), cuáles categóricas
(tipo/confianza/caso límite), cuál es texto libre (justificación) y
cuáles identificadoras. Tiene tres vistas:

- **Plano (ImagePlot)** — scatter X/Y, o ranking en línea con una sola
  variable. Con "Modo ImagePlot" cada foto se dibuja como miniatura en
  su coordenada (tamaño ajustable), como en el software original de
  Manovich; un click la agranda flotando sobre el plano, con un panel
  con sus variables y justificación. Los puntos se colorean por tipo
  asignado o por matiz (variable circular, con escala cíclica), con
  filtros por tipo, confianza y caso límite.
- **Distribuciones** — histogramas agregados del corpus (no de una
  foto), uno por variable y solapados por tipo; boxplot por tipo; y una
  rosa polar del matiz (24 sectores ajustables) para tratarlo como
  variable circular.
- **Grilla (montage)** — estilo ImageMontage. Con una variable, las
  fotos quedan ordenadas en una cuadrícula de menor a mayor; con dos
  variables, una matriz de cuantiles (filas × columnas). Un click en
  una miniatura la agranda flotando sobre la grilla.

Los umbrales de sombras y altas luces son ajustables en vivo desde la
barra lateral: la app mide la luminancia de cada foto una sola vez (con
los mismos pesos que el pipeline) y recalcula las proporciones al
instante.

---

## Protocolo de normalización y trazabilidad

Implementado en `pipeline/normalizar.py`, se aplica igual a las 207
imágenes.

**Qué normaliza:**
1. Corrección de orientación EXIF, *antes* de leer dimensiones o medir
   nada.
2. Conversión a sRGB (si la imagen trae perfil ICC embebido, se
   convierte desde ese perfil; si no trae perfil —el caso más común en
   fotos de celular— se asume sRGB por convención).
3. Redimensionado a **1024×1024 px**. El pipeline *no recorta*: asume
   que cada imagen ya llegó 1:1 (recorte hecho por la persona autora al
   fotografiar).
4. Formato de salida único: **JPEG, calidad 95**, organizado en
   `datos/corpus_normalizado/{casual,profesional,diseno}/` según
   `tipo_manovich`. La categoría se detecta por el prefijo del nombre
   de archivo (`casual_01_CB.jpg` → `casual`) o, si no matchea, por la
   carpeta contenedora. Lo que no se puede categorizar cae en
   `sin_categoria/` con un aviso — nunca se asigna a ciegas.
5. `id_imagen`: hash sha256 (16 hex) del contenido del archivo — no
   reutiliza el nombre original, que puede traer información personal
   (iniciales, fecha).

**Qué NO normaliza:** ecualización de contraste, brillo o saturación
(normalización *tonal*) queda fuera de este paso — eso borraría
justamente la variación que las variables de la Fase 2 miden.

**Trazabilidad `id_imagen` ↔ archivo original:** `normalizar.py`
escribe, por defecto en
`datos/trazabilidad_original_normalizado_privado.csv`, un mapa con
`archivo_original`, `nombre_original`, `id_imagen`, `categoria` y
`archivo_normalizado` por cada foto. Ese archivo está en `.gitignore`
—contiene los nombres originales— y es lo que después usa
`asociar_metadata.py` para traducir `referencias.csv` a `id_imagen`. Se
puede cambiar de ruta con `--mapa`, o no generarlo con `--sin-mapa`.

**Convenciones fijadas** (si se cambian después de medir variables, hay
que volver a normalizar y volver a medir todo el corpus):
`TAMANO_FINAL = 1024`, `FORMATO_SALIDA = "JPEG"`, `CALIDAD_JPEG = 95`.

---

## Dataset y variables

`datos/dataset.csv` es la tabla final, una fila por fotografía, armada
por `construir_dataset.py`. Columnas, en orden:

1. `id_imagen` — hash sha256 (16 hex) del contenido; estable, no
   depende del nombre de archivo original.
2. `autor_id` — código/seudónimo de quien fotografió.
3. `tipo_manovich` — `casual`, `profesional` o `diseno` (el tipo
   autoasignado).
4. `confianza_etiqueta` — `alta`, `media` o `baja`.
5. `caso_limite` — booleano (`True`/`False`): ¿la persona autora dudó
   entre dos tipos?
6. `justificacion_etiqueta` — texto de 80 a 120 palabras; queda como
   evidencia cualitativa, no se cuantifica.
7. Las 5 variables de color/histograma (7 columnas — ver tabla más
   arriba).

`construir_dataset.py` no recalcula nada: solo une por `id_imagen`,
normaliza las columnas categóricas (`diseño` → `diseno`, `Media` →
`media`, `SI`/`NO` → `True`/`False`) y **avisa por stderr, sin corregir
a ciegas**: campos vacíos, valores no reconocidos, justificaciones
fuera de 80–120 palabras, `id_imagen` duplicados, y fotos con variables
pero sin etiqueta. Con `--estricto` no escribe la salida si hay
faltantes o duplicados.

`variables_visuales.csv` y `metadata_normalizado.csv` son resultados
intermedios — la tabla que se entrega es `dataset.csv`.

---

## Consentimiento y ética

Solo se incluyen en `datos/corpus_normalizado/` (y por lo tanto en el
repositorio público) fotografías con consentimiento explícito de
publicación por parte de su autor/a. El identificador de cada imagen es
un hash de su contenido, no su nombre de archivo original, y el nombre
y apellido de cada persona autora nunca se sube al repo — vive solo en
`datos/referencias.csv`, local y fuera de git.

---

## Estado del proyecto

- [x] Normalización técnica del corpus
- [x] Extracción de variables de color e histograma
- [x] Asociación de etiquetas con id_imagen
- [x] Construcción del dataset final
- [x] Canvas interactivo (Streamlit)
- [ ] Paper final

---

## Autores

Trabajo grupal — ver `paper/` para la nómina completa de integrantes.

---

## Contexto académico

Trabajo práctico integrador para la materia de Procesamiento de
Imágenes de la Tecnicatura en Ciencia de Datos e Inteligencia
Artificial, IFTS N°24, basado en la propuesta de analítica cultural de
Lev Manovich en *Instagram y la imagen contemporánea*.
