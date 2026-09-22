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
uv sync   # instala el entorno la primera vez (o si cambian las dependencias)
```

1. **Normalización** (Fase 1):
   ```bash
   uv run pipeline/normalizar.py \
       --entrada datos/corpus_original \
       --salida datos/corpus_normalizado \
       --log datos/id_mapping_privado.csv
   ```
2. **Extracción de variables** (Fase 2, parte A):
   ```bash
   uv run pipeline/extraer_variables.py \
       --entrada datos/corpus_normalizado \
       --salida datos/variables_visuales.csv
   ```
3. **App** *(TBD — Fase 3)*: `uv run streamlit run app/canvas.py`

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
variables, sin `autor_id`/`tipo_manovich` autoasignado ni etiquetas): el
`metadata.csv` final *(TBD)* se arma uniendo esta tabla con el archivo de
etiquetas de cada autor/a.

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

**Trazabilidad `id_imagen` ↔ archivo original:** el script no escribe
ningún archivo que mapee el hash a tu nombre de archivo original — decisión
del grupo para no generar, ni por accidente, un dato que después haya que
recordar excluir del repo. Si necesitás volver del `id_imagen` al archivo
original (por ejemplo, para armar `metadata.csv` uniendo con tus
etiquetas), hay que resolverlo en el mismo paso en el que se unen ambas
tablas — ver "Variables de color e histograma" más arriba.

Convenciones fijadas (si se cambian después de medir variables en la
Fase 2, hay que volver a normalizar y volver a medir todo el corpus):
`TAMANO_FINAL = 1024`, `FORMATO_SALIDA = "JPEG"`, `CALIDAD_JPEG = 95`.

## Dataset y variables

*(TBD — Fase 2: columnas de `metadata.csv`, justificación de cada
variable de color/histograma, umbrales de sombra/altas luces.)*

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
