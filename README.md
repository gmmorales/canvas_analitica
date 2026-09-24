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

# Instalar dependencias (con uv)
uv sync --all-extras
```

Con las fotos originales en `datos/corpus_original/`, correr el
pipeline en orden:

```bash
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