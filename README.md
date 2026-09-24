# Canvas Analítico

**Analítica cultural aplicada a fotografías de Instagram, basada en el marco de Lev Manovich**

---

## Contexto del proyecto

Cuando miramos un feed de Instagram intuimos diferencias entre una foto
"casual", una "profesional" y una pensada como pieza de "diseño" — pero
esa intuición rara vez se pone a prueba con datos. Lev Manovich propone
leer estas imágenes no solo por su contenido, sino por sus propiedades
visuales: luminosidad, contraste, color, composición.

Canvas Analítico toma esa propuesta y la vuelve un pipeline reproducible:
un corpus de fotografías reales, autoetiquetadas por su tipo, procesado
para extraer descriptores visuales objetivos — y comparar si lo que cada
autor/a *dice* que es su foto coincide con lo que la imagen *mide*.

Proyecto grupal (comisión completa, 20 integrantes) para la materia de
Procesamiento de Imágenes de la Tecnicatura en Ciencia de Datos e
Inteligencia Artificial, IFTS N°24.

---

## ¿Cómo funciona?

El proyecto implementa un pipeline de cuatro etapas, cada una con su
propio script y su propia salida verificable:

```
Foto original (celular)
        ↓
  Normalización técnica
  (orientación, sRGB, 1024×1024, id anónimo por hash)
        ↓
  Extracción de variables
  (luminancia, contraste, sombras/luces, matiz, dominancia cromática)
        ↓
  Unión con etiquetas autoasignadas
  (tipo_manovich, confianza, justificación de cada autor/a)
        ↓
     metadata.csv
        ↓
  Canvas interactivo (Streamlit)
```

1. **Normalización** (`pipeline/normalizar.py`) corrige orientación
   EXIF, convierte a sRGB, redimensiona a un tamaño único y asigna a
   cada imagen un identificador anónimo (hash de su contenido, no de su
   nombre de archivo original).
2. **Extracción de variables** (`pipeline/extraer_variables.py`) mide,
   sobre cada imagen ya normalizada, cinco descriptores visuales — ver
   tabla más abajo.
3. **Unión con etiquetas** cruza esas variables con el archivo de
   etiquetas que completó cada autor/a (tipo asignado, nivel de
   confianza, justificación), validando y señalando inconsistencias en
   vez de asumirlas.
4. **Canvas interactivo** *(en desarrollo)*: visualización en Streamlit
   del corpus completo, explorable por tipo y por variable.

---

## Variables medidas

| Variable | Qué mide |
|---|---|
| `mediana_luminancia` | Nivel tonal global de la imagen |
| `dispersion_luminancia` | Contraste (qué tan repartidos están los tonos) |
| `prop_sombras` / `prop_altas_luces` | Proporción de píxeles muy oscuros / muy claros |
| `matiz_dominante_deg` / `saturacion_media` | Familia cromática predominante e intensidad de color |
| `dominancia_cromatica` | Cuánto concentra la imagen en una sola familia de color |

Cada variable está documentada en detalle —qué mide, qué convención
asume y qué no captura— directamente en el docstring de
`pipeline/extraer_variables.py`.

---

## Corpus de trabajo

207 fotografías (formato 1:1), tomadas con
celular y autoetiquetadas según la tipología de Manovich: `casual`,
`profesional`, `diseno`. Cada foto viene acompañada de una justificación
escrita por su autor/a explicando el criterio de clasificación y el
nivel de confianza en esa etiqueta.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Procesamiento de imagen | Pillow, scikit-image |
| Cómputo numérico | NumPy |
| Datos tabulares | CSV nativo (sin pandas en el pipeline) |
| Interfaz | Streamlit *(en desarrollo)* |
| Gestión de dependencias | [uv](https://docs.astral.sh/uv/) |

---

## Estructura del proyecto

```
canvas_analitica/
├── README.md
├── pipeline/
│   ├── normalizar.py           # Etapa 1 — normalización técnica
│   └── extraer_variables.py    # Etapa 2 — variables de color/histograma
├── app/                         # Canvas interactivo (Streamlit)
├── paper/                       # Bitácora, decisiones, hallazgos
├── datos/
│   ├── corpus_normalizado/
│   │   ├── casual/
│   │   ├── profesional/
│   │   └── diseno/
│   └── referencias.csv       # LOCAL, NO se sube: trae nombres de autores/as
├── pipeline/                 # normalización + extracción de variables (Fase 1 y 2)
├── app/                      # Canvas Analítico en Streamlit (Fase 3)
├── paper/                    # decisiones, matriz-hallazgos.md, bitácora Voy/Vengo (Fase 4)
├── pyproject.toml            # dependencias (gestionadas con uv)
│   ├── etiquetas_autores.csv    # etiquetas autoasignadas por autor/a
│   ├── variables_visuales.csv   # salida de extraer_variables.py
│   └── metadata.csv             # dataset final
├── pyproject.toml
├── uv.lock
└── .python-version
```

`datos/corpus_original/` (las fotos crudas, sin normalizar) vive solo en
copias locales de trabajo — nunca se sube al repositorio (ver
`.gitignore`): puede tener EXIF con datos del dispositivo o, en algunos
casos, geolocalización.

---

## Instalación y uso local

```bash
git clone https://github.com/gmmorales/canvas_analitica.git
cd canvas_analitica

`datos/referencias.csv` (antes `metadata.csv`) es el archivo de entradas
del corpus: una fila por foto con el `id_imagen` original, el nombre y
apellido de la persona autora (`autor_apellido_nombre`), el `autor_id`,
el tipo autoasignado y su justificación. **No se sube al repositorio**
porque contiene nombres y apellidos (dato personal) — está en
`.gitignore`. Igual que `corpus_original/`, es un insumo local: se
comparte por otro canal con el grupo, no por git. El paso 3 del pipeline
lo procesa y genera `metadata_normalizado.csv`, que es el mismo contenido
pero con los `id_imagen` ya hasheados y **sin** la columna con el nombre,
así que ese sí puede versionarse.

## Cómo correr el proyecto
# Instalar dependencias (con uv)
uv sync --all-extras
```

Con las fotos originales en `datos/corpus_original/`, correr el
pipeline en orden:

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
3. **Asociación de ids en las referencias** (Fase 2, parte B): toma
   `datos/referencias.csv` (local, no versionado), reemplaza los nombres
   viejos de las fotos por los `id_imagen` nuevos que asignó
   `normalizar.py` y quita la columna `autor_apellido_nombre`:
   ```bash
   uv run pipeline/asociar_metadata.py \
       --metadata datos/referencias.csv \
       --mapa datos/trazabilidad_original_normalizado_privado.csv \
       --salida datos/metadata_normalizado.csv
   ```
   `metadata_normalizado.csv` queda con las columnas `id_imagen`,
   `autor_id`, `tipo_manovich`, `confianza_etiqueta`, `caso_limite`,
   `justificacion_etiqueta`. Para dejar el nombre `referencias.csv`, usar
   `--salida datos/referencias.csv`; en ese caso el paso 4 lo detecta solo.
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
5. **App** (Fase 3):
   ```bash
   uv run streamlit run app/canvas.py
   ```
   Lee el dataset (por defecto `datos/dataset.csv`) y **detecta sola** qué
   columnas son numéricas (candidatas a los ejes), cuáles son categóricas
   (tipo/confianza/caso límite), cuál es texto libre (justificación) y
   cuáles son identificadoras. Permite elegir dos variables numéricas para
   los ejes X/Y (puntos coloreados por `tipo_manovich`), o una sola para
   ver un ranking en línea; filtra por tipo, confianza y caso límite; y al
   hacer click en un punto muestra la miniatura, todas las variables y la
   justificación de esa foto. Si una misma foto tiene varias filas (ids
   repetidos), se separan mínimamente en el plano y el panel permite ver
   cada fila por separado.

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
nombres viejos de `referencias.csv` por los ids nuevos (y de paso quita la
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
uv run pipeline/normalizar.py
uv run pipeline/extraer_variables.py
```

Cada script puede correrse de forma independiente y admite rutas de
entrada/salida por parámetro — ver `--help` en cada uno.

---

## Consentimiento y ética

Solo se incluyen en `datos/corpus_normalizado/` (y por lo tanto en el
repositorio público) fotografías con consentimiento explícito de
publicación por parte de su autor/a. El identificador de cada imagen es
un hash de su contenido, no su nombre de archivo original, para evitar
exponer información personal (iniciales, fechas) en un repositorio
público.

---

## Estado del proyecto

- [x] Normalización técnica del corpus
- [x] Extracción de variables de color e histograma
- [x] Unión de etiquetas y variables en un dataset único
- [ ] Canvas interactivo (Streamlit)
- [ ] Análisis agregado y paper final

---

## Autores

Trabajo grupal — ver `paper/` para la nómina completa de integrantes.

---

## Contexto académico

Trabajo práctico integrador para la materia de Procesamiento de
Imágenes de la Tecnicatura en Ciencia de Datos e Inteligencia
Artificial, IFTS N°24, basado en la propuesta de analítica cultural de
Lev Manovich en *Instagram y la imagen contemporánea*.

---

*Canvas Analítico. Porque una foto casual y una pensada como pieza de
diseño no se diferencian a ojo — se miden.*
