"""
app/canvas.py — Canvas Analítico (Fase 3/4, TPI Manovich)

App de Streamlit inspirada en *ImagePlot* (Manovich): ubica cada foto del
corpus en un plano de dos variables visuales y permite explorar cómo se
distribuyen según el tipo asignado por cada autor/a.

Dos pestañas:
  1) Plano (ImagePlot): scatter X/Y o ranking en línea, puntos coloreados
     por tipo O por matiz (variable circular), con la miniatura y la
     justificación al hacer click.
  2) Distribuciones: histogramas agregados del corpus por tipo, boxplots y
     una rosa polar del matiz. NO es el histograma de una foto: es la
     distribución de la variable en todo el corpus (Fase 4).

Umbrales ajustables: los umbrales de "sombras" y "altas luces" se pueden
mover en vivo. La app mide la luminancia de cada imagen UNA vez (pesos
ITU-R 601-2, igual que el pipeline) y guarda su histograma; recalcular con
otro umbral es instantáneo y no vuelve a leer las fotos.

Detección automática: la app clasifica sola las columnas (numéricas,
categóricas, texto libre, identificadoras) y resuelve roles por nombre
conocido o por contenido. No hay listas de variables de color escritas a
mano.

Uso:
    uv run streamlit run app/canvas.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# --------------------------------------------------------------------------
# Rutas y convenciones
# --------------------------------------------------------------------------
RUTAS_DATOS_CANDIDATAS = [
    Path("datos/dataset.csv"),
    Path("datos/referencias.csv"),
    Path("datos/metadata.csv"),
    Path("datos/metadata_normalizado.csv"),
]
RUTA_IMAGENES_POR_DEFECTO = Path("datos/corpus_normalizado")

# Nombres "conocidos" SOLO de columnas de identificación/etiqueta.
COL_ID = "id_imagen"
COL_TIPO = "tipo_manovich"
COL_CONFIANZA = "confianza_etiqueta"
COL_CASO = "caso_limite"
COL_JUSTIFICACION = "justificacion_etiqueta"

UMBRAL_TEXTO_LARGO = 120
MAX_CATEGORIAS = 12
FRACCION_NUMERICA = 0.95

# Umbrales iniciales sugeridos por la consigna (se pueden mover en la app).
UMBRAL_SOMBRA_INICIAL = 0.10
UMBRAL_ALTAS_INICIAL = 0.90

# Pistas para los roles que necesitan tratamiento especial (matiz circular,
# columnas de umbral). Se busca por subcadena, no es una lista fija.
PALABRAS_MATIZ = ("matiz", "hue")
PALABRAS_SATURACION = ("saturacion",)
PALABRAS_SOMBRAS = ("sombra",)
PALABRAS_ALTAS = ("alta",)

PALETA = [
    "#4C78A8", "#F58518", "#54A24B", "#E45752",
    "#72B7B2", "#B279A2", "#FF9DA6", "#9D755D",
    "#BAB0AC", "#EECA3B",
]


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def leer_tabla(ruta: str) -> pd.DataFrame:
    df = pd.read_csv(ruta, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    return df


@st.cache_data(show_spinner="Leyendo las fotos: histogramas y miniaturas (solo la primera vez)...")
def analizar_imagenes(raiz: str, lado_miniatura: int = 64) -> dict:
    """
    Recorre las imágenes normalizadas UNA sola vez y devuelve:
      - "hist":  id_imagen -> histograma de 256 bins de luminancia [0,1]
                 (pesos ITU-R 601-2, iguales a los del pipeline).
      - "thumb": id_imagen -> data URI JPEG de la miniatura (para el plano
                 estilo ImagePlot).
    """
    import base64
    import io

    from PIL import Image

    base = Path(raiz)
    hist: dict[str, list[int]] = {}
    thumb: dict[str, str] = {}
    if not base.exists():
        return {"hist": hist, "thumb": thumb}
    for patron in ("*.jpg", "*.jpeg", "*.png"):
        for ruta in base.rglob(patron):
            if ruta.stem in hist:
                continue
            try:
                with Image.open(ruta) as img:
                    rgb_img = img.convert("RGB")
                    rgb = np.asarray(rgb_img, dtype=np.float32) / 255.0
                    miniatura = rgb_img.copy()
                    miniatura.thumbnail((lado_miniatura, lado_miniatura))
                gris = 0.2125 * rgb[..., 0] + 0.7154 * rgb[..., 1] + 0.0721 * rgb[..., 2]
                h, _ = np.histogram(gris, bins=256, range=(0.0, 1.0))
                hist[ruta.stem] = h.astype(np.int64).tolist()
                buffer = io.BytesIO()
                miniatura.save(buffer, format="JPEG", quality=70)
                thumb[ruta.stem] = (
                    "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
                )
            except Exception:
                continue
    return {"hist": hist, "thumb": thumb}


@st.cache_data(show_spinner=False)
def indexar_imagenes(raiz: str) -> dict[str, str]:
    base = Path(raiz)
    indice: dict[str, str] = {}
    if not base.exists():
        return indice
    for patron in ("*.jpg", "*.jpeg", "*.png"):
        for ruta in base.rglob(patron):
            indice.setdefault(ruta.stem, str(ruta))
    return indice


def primera_ruta_datos(ruta_preferida: str | None) -> Path | None:
    if ruta_preferida:
        p = Path(ruta_preferida)
        return p if p.exists() else None
    for p in RUTAS_DATOS_CANDIDATAS:
        if p.exists():
            return p
    return None


# --------------------------------------------------------------------------
# Detección automática de columnas y roles
# --------------------------------------------------------------------------
def es_texto_libre(serie: pd.Series) -> bool:
    if not (serie.dtype == object or pd.api.types.is_string_dtype(serie)):
        return False
    largos = serie.dropna().astype(str).str.len()
    return len(largos) > 0 and largos.mean() >= UMBRAL_TEXTO_LARGO


def detectar_columnas(df: pd.DataFrame) -> dict:
    numericas, texto_libre, categoricas, identificadoras = [], [], [], []
    for col in df.columns:
        serie = df[col]
        if es_texto_libre(serie):
            texto_libre.append(col)
            continue
        como_num = pd.to_numeric(serie, errors="coerce")
        parseable = serie.notna().any() and como_num.notna().mean() >= FRACCION_NUMERICA
        if parseable and como_num.nunique(dropna=True) > 2:
            numericas.append(col)
            continue
        if serie.dtype == object or pd.api.types.is_string_dtype(serie):
            distintos = serie.nunique(dropna=True)
            (categoricas if 1 < distintos <= MAX_CATEGORIAS else identificadoras).append(col)
    return {
        "numericas": numericas,
        "texto_libre": texto_libre,
        "categoricas": categoricas,
        "identificadoras": identificadoras,
    }


def _contiene(col: str, palabras: tuple[str, ...]) -> bool:
    c = col.lower()
    return any(p in c for p in palabras)


def _primera(lista, palabras=None):
    if palabras is not None:
        return next((c for c in lista if _contiene(c, palabras)), None)
    return lista[0] if lista else None


def detectar_roles(df: pd.DataFrame, columnas: dict) -> dict:
    cols = set(df.columns)

    id_col = COL_ID if COL_ID in cols else _primera(columnas["identificadoras"])
    tipo_col = COL_TIPO if COL_TIPO in cols else _primera(columnas["categoricas"])
    confianza_col = (
        COL_CONFIANZA if COL_CONFIANZA in cols
        else _primera(columnas["categoricas"], ("conf",))
    )
    caso_col = (
        COL_CASO if COL_CASO in cols
        else _primera(columnas["identificadoras"] + columnas["categoricas"], ("caso",))
    )
    justificacion_col = (
        COL_JUSTIFICACION if COL_JUSTIFICACION in cols
        else _primera(columnas["texto_libre"])
    )
    return {
        "id": id_col,
        "tipo": tipo_col,
        "confianza": confianza_col,
        "caso_limite": caso_col,
        "justificacion": justificacion_col,
        "matiz": _primera(columnas["numericas"], PALABRAS_MATIZ),
        "saturacion": _primera(columnas["numericas"], PALABRAS_SATURACION),
        "sombras": _primera(columnas["numericas"], PALABRAS_SOMBRAS),
        "altas": _primera(columnas["numericas"], PALABRAS_ALTAS),
    }


# --------------------------------------------------------------------------
# Umbrales recalculables (sombras / altas luces)
# --------------------------------------------------------------------------
def proporciones_desde_hist(hist: list[int], u_bajo: float, u_alto: float) -> tuple[float, float]:
    total = int(sum(hist))
    if total == 0:
        return 0.0, 0.0
    i_bajo = min(256, max(0, int(round(u_bajo * 256))))
    i_alto = min(256, max(0, int(round(u_alto * 256))))
    prop_bajo = sum(hist[:i_bajo]) / total
    prop_alto = sum(hist[i_alto:]) / total
    return prop_bajo, prop_alto


def aplicar_umbrales(
    df: pd.DataFrame,
    hist: dict[str, list[int]],
    roles: dict,
    u_bajo: float,
    u_alto: float,
) -> tuple[pd.DataFrame, str, str]:
    d = df.copy()
    bajos, altos = [], []
    for idv in d[roles["id"]].astype(str):
        h = hist.get(idv)
        if h is None:
            bajos.append(np.nan)
            altos.append(np.nan)
        else:
            b, a = proporciones_desde_hist(h, u_bajo, u_alto)
            bajos.append(b)
            altos.append(a)
    col_bajo = roles["sombras"] or "prop_bajo_umbral"
    col_alto = roles["altas"] or "prop_sobre_umbral"
    d[col_bajo] = bajos
    d[col_alto] = altos
    return d, col_bajo, col_alto


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def a_booleano(serie: pd.Series) -> pd.Series:
    def conv(valor) -> object:
        t = str(valor).strip().lower()
        if t in {"true", "1", "1.0", "si", "sí", "yes", "y"}:
            return True
        if t in {"false", "0", "0.0", "no", "n"}:
            return False
        return "sin dato"
    return serie.map(conv)


def a_texto(serie: pd.Series) -> pd.Series:
    """Convierte vacíos/NaN a 'sin dato' para que los filtros no los oculten."""
    return serie.map(lambda v: "sin dato" if pd.isna(v) or str(v).strip() == "" else str(v))


def mapa_colores(valores) -> dict:
    limpios = sorted({str(v) for v in valores if pd.notna(v)})
    return {v: PALETA[i % len(PALETA)] for i, v in enumerate(limpios)}


def color_de(mapa: dict, valor) -> str:
    return mapa.get(str(valor), PALETA[0])


def separar_puntos_superpuestos(df: pd.DataFrame, radio: float = 0.012) -> pd.DataFrame:
    """Desplaza mínimamente las filas con idénticas coordenadas de dibujo."""
    d = df.copy()
    rango_x = d["_x_disp"].max() - d["_x_disp"].min()
    rango_y = d["_y_disp"].max() - d["_y_disp"].min()
    rango_x = float(rango_x) if pd.notna(rango_x) and rango_x else 1.0
    rango_y = float(rango_y) if pd.notna(rango_y) and rango_y else 1.0
    for (x, y), indices in d.groupby(["_x_disp", "_y_disp"], dropna=False).groups.items():
        indices = list(indices)
        if len(indices) <= 1:
            continue
        for k, i in enumerate(indices):
            angulo = 2 * np.pi * k / len(indices)
            d.at[i, "_x_disp"] = x + radio * rango_x * np.cos(angulo)
            d.at[i, "_y_disp"] = y + radio * rango_y * np.sin(angulo)
    return d


def agregar_miniaturas(fig, df, id_col, thumbs, tamano_px,
                       ancho_px: float = 1000.0, alto_px: float = 540.0) -> None:
    """
    Coloca cada foto como imagen en su coordenada (modo ImagePlot). El
    tamaño se pasa en píxeles de pantalla y se convierte a unidades de
    datos, para que la miniatura quede aproximadamente cuadrada.
    """
    x = pd.to_numeric(df["_x_disp"], errors="coerce")
    y = pd.to_numeric(df["_y_disp"], errors="coerce")
    rango_x = float(x.max() - x.min()) or 1.0
    rango_y = float(y.max() - y.min()) or 1.0
    sizex = tamano_px * rango_x / ancho_px
    sizey = tamano_px * rango_y / alto_px
    for idv, xv, yv in zip(df[id_col].astype(str), x, y):
        if pd.isna(xv) or pd.isna(yv):
            continue
        uri = thumbs.get(idv)
        if not uri:
            continue
        fig.add_layout_image(dict(
            source=uri, xref="x", yref="y",
            x=float(xv) - sizex / 2, y=float(yv) + sizey / 2,
            sizex=sizex, sizey=sizey, xanchor="left", yanchor="top",
            layer="below", opacity=1,
        ))


# --------------------------------------------------------------------------
# Figuras — pestaña Plano
# --------------------------------------------------------------------------
def construir_scatter_por_tipo(df, x_col, y_col, tipo_col, id_col, colores,
                               tamano_punto: float = 12, transparente: bool = False) -> go.Figure:
    fig = go.Figure()
    for tipo, grupo in df.groupby(tipo_col, dropna=False, sort=True):
        color = "rgba(0,0,0,0)" if transparente else color_de(colores, tipo)
        linea = dict(width=0) if transparente else dict(width=1, color="white")
        fig.add_trace(
            go.Scatter(
                x=grupo["_x_disp"], y=grupo["_y_disp"], mode="markers",
                name=str(tipo),
                customdata=grupo[[id_col, x_col, y_col, "_clave"]].to_numpy(),
                marker=dict(size=tamano_punto, color=color, line=linea),
                hovertemplate=(
                    f"<b>%{{customdata[0]}}</b><br>{x_col}: %{{customdata[1]}}"
                    f"<br>{y_col}: %{{customdata[2]}}<br>{tipo_col}: {tipo}<extra></extra>"
                ),
            )
        )
    fig.update_layout(xaxis_title=x_col, yaxis_title=y_col, legend_title=tipo_col,
                      margin=dict(l=10, r=10, t=30, b=10), height=620)
    return fig


def construir_scatter_por_valor(df, x_col, y_col, id_col, valor_col, escala, cmin, cmax,
                                titulo, tamano_punto: float = 12,
                                transparente: bool = False) -> go.Figure:
    marcador: dict = dict(size=tamano_punto)
    if transparente:
        # Área clickeable invisible del tamaño de la miniatura.
        marcador["color"] = "rgba(0,0,0,0)"
        marcador["line"] = dict(width=0)
    else:
        marcador.update(
            color=pd.to_numeric(df[valor_col], errors="coerce"),
            colorscale=escala, cmin=cmin, cmax=cmax,
            colorbar=dict(title=titulo), line=dict(width=1, color="white"),
        )
    fig = go.Figure(
        go.Scatter(
            x=df["_x_disp"], y=df["_y_disp"], mode="markers",
            customdata=df[[id_col, x_col, y_col, valor_col, "_clave"]].to_numpy(),
            marker=marcador,
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b><br>{x_col}: %{{customdata[1]}}"
                f"<br>{y_col}: %{{customdata[2]}}<br>{titulo}: %{{customdata[3]}}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(xaxis_title=x_col, yaxis_title=y_col,
                      margin=dict(l=10, r=10, t=30, b=10), height=620)
    return fig


def construir_ranking(df, col, tipo_col, id_col, colores) -> go.Figure:
    ordenado = df.sort_values(col, ascending=True).reset_index(drop=True)
    ordenado["_rank"] = np.arange(1, len(ordenado) + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ordenado["_rank"], y=np.zeros(len(ordenado)), mode="lines",
        line=dict(color="rgba(150,150,150,0.35)", width=1),
        hoverinfo="skip", showlegend=False,
    ))
    for tipo, grupo in ordenado.groupby(tipo_col, dropna=False, sort=True):
        fig.add_trace(go.Scatter(
            x=grupo["_rank"], y=np.zeros(len(grupo)), mode="markers",
            name=str(tipo),
            customdata=grupo[[id_col, col, "_clave"]].to_numpy(),
            marker=dict(size=13, color=color_de(colores, tipo),
                        line=dict(width=1, color="white")),
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b><br>puesto %{{x}} de {len(ordenado)}"
                f"<br>{col}: %{{customdata[1]}}<extra></extra>"
            ),
        ))
    fig.update_layout(
        xaxis_title=f"ranking por {col} (menor -> mayor)",
        yaxis=dict(showticklabels=False, range=[-1, 1], title=""),
        legend_title=tipo_col, margin=dict(l=10, r=10, t=30, b=10), height=420,
    )
    return fig


def puntos_seleccionados(evento) -> list:
    try:
        return list(evento.selection.points)
    except Exception:
        try:
            return list(evento["selection"]["points"])
        except Exception:
            return []


def claves_desde_puntos(puntos: list, df_plot: pd.DataFrame) -> list[int]:
    claves: list[int] = []
    for punto in puntos:
        cd = punto.get("customdata")
        if cd and isinstance(cd, (list, tuple)):
            claves.append(int(cd[-1]))
            continue
        idx = punto.get("point_index", punto.get("point_number"))
        if idx is not None and 0 <= int(idx) < len(df_plot):
            claves.append(int(df_plot.iloc[int(idx)]["_clave"]))
    vistas: list[int] = []
    for c in claves:
        if c not in vistas:
            vistas.append(c)
    return vistas


def mostrar_panel(fila, roles, numericas, indice_imagenes, nota=None) -> None:
    id_imagen = fila[roles["id"]] if roles["id"] else "—"
    izquierda, derecha = st.columns([1, 2])
    with izquierda:
        ruta = indice_imagenes.get(str(id_imagen))
        if ruta:
            st.image(ruta, caption=str(id_imagen), width="stretch")
        else:
            st.info(f"No se encontró la imagen de {id_imagen} en el corpus.")
    with derecha:
        st.markdown(f"### `{id_imagen}`")
        if nota:
            st.caption(nota)
        etiquetas = []
        for etiqueta, col in [("tipo", roles["tipo"]), ("confianza", roles["confianza"]),
                              ("caso límite", roles["caso_limite"])]:
            if col and col in fila.index:
                etiquetas.append(f"**{etiqueta}:** {fila[col]}")
        if etiquetas:
            st.markdown("  \n".join(etiquetas))
        if numericas:
            st.markdown("**Variables numéricas**")
            st.dataframe(pd.DataFrame({"variable": numericas,
                                       "valor": [fila.get(c, "") for c in numericas]}),
                         hide_index=True, width="stretch")
        col_just = roles["justificacion"]
        if col_just and col_just in fila.index and pd.notna(fila[col_just]):
            st.markdown("**Justificación de la etiqueta**")
            st.info(str(fila[col_just]))


# --------------------------------------------------------------------------
# Figuras — pestaña Distribuciones
# --------------------------------------------------------------------------
def figura_histogramas_resumen(df, cols, tipo_col, colores, ncols=3) -> go.Figure:
    n = len(cols)
    nrows = int(np.ceil(n / ncols))
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=cols,
                        horizontal_spacing=0.08, vertical_spacing=0.14)
    for i, col in enumerate(cols):
        r, c = i // ncols + 1, i % ncols + 1
        for tipo, g in df.groupby(tipo_col, dropna=False, sort=True):
            fig.add_trace(
                go.Histogram(x=pd.to_numeric(g[col], errors="coerce"), nbinsx=25,
                             name=str(tipo), marker_color=color_de(colores, tipo),
                             opacity=0.55, showlegend=(i == 0)),
                row=r, col=c,
            )
    fig.update_layout(barmode="overlay", height=250 * nrows, legend_title=tipo_col,
                      margin=dict(l=10, r=10, t=50, b=10), title=None)
    return fig


def figura_detalle_variable(df, col, tipo_col, colores) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, row_heights=[0.68, 0.32], shared_xaxes=True,
                        vertical_spacing=0.06, subplot_titles=[f"Histograma de {col}",
                                                               "Distribución por tipo"])
    for tipo, g in df.groupby(tipo_col, dropna=False, sort=True):
        valores = pd.to_numeric(g[col], errors="coerce")
        fig.add_trace(go.Histogram(x=valores, nbinsx=25, name=str(tipo),
                                   marker_color=color_de(colores, tipo), opacity=0.55,
                                   showlegend=True), row=1, col=1)
        fig.add_trace(go.Box(x=valores, name=str(tipo), marker_color=color_de(colores, tipo),
                             showlegend=False), row=2, col=1)
    fig.update_layout(barmode="overlay", height=560, legend_title=tipo_col,
                      margin=dict(l=10, r=10, t=50, b=10))
    return fig


def figura_rosa_matiz(df, matiz_col, tipo_col, colores, n_bins=24) -> go.Figure:
    ancho = 360.0 / n_bins
    fig = go.Figure()
    for tipo, g in df.groupby(tipo_col, dropna=False, sort=True):
        valores = pd.to_numeric(g[matiz_col], errors="coerce").dropna()
        if valores.empty:
            continue
        conteos, bordes = np.histogram(valores, bins=n_bins, range=(0.0, 360.0))
        centros = (bordes[:-1] + bordes[1:]) / 2
        fig.add_trace(go.Barpolar(
            r=conteos, theta=centros, width=ancho, name=str(tipo),
            marker_color=color_de(colores, tipo), opacity=0.7,
            thetaunit="degrees",
        ))
    fig.update_layout(
        polar=dict(angularaxis=dict(direction="clockwise", rotation=90,
                                    tickmode="array",
                                    tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                                    ticktext=["0° rojo", "45°", "90°", "135°", "180° cian",
                                              "225°", "270°", "315°"])),
        legend_title=tipo_col, height=560, margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


@st.cache_data(show_spinner=False)
def imagen_grande_base64(ruta: str, lado: int = 380, borde: int = 8) -> str | None:
    """Imagen ampliada (con marco blanco) como data URI, para el zoom flotante."""
    import base64
    import io

    from PIL import Image

    try:
        with Image.open(ruta) as img:
            im = img.convert("RGB")
            im.thumbnail((lado, lado))
        lienzo = Image.new("RGB", (im.width + 2 * borde, im.height + 2 * borde), "white")
        lienzo.paste(im, (borde, borde))
        buffer = io.BytesIO()
        lienzo.save(buffer, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None


def agregar_overlay(fig, x, y, uri, sizex, sizey) -> None:
    """Pega una imagen ampliada flotando sobre el gráfico, centrada en (x, y)."""
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=x - sizex / 2, y=y + sizey / 2, sizex=sizex, sizey=sizey,
        xanchor="left", yanchor="top", layer="above",
    ))


def seleccion_de_sesion(key: str) -> list:
    """Puntos seleccionados guardados por Streamlit para un plotly_chart."""
    estado = st.session_state.get(key)
    if isinstance(estado, dict):
        seleccion = estado.get("selection", estado)
        if isinstance(seleccion, dict):
            return list(seleccion.get("points", []) or [])
    return []


def _traza_seleccion(xs, ys, cd, cell_px) -> go.Scatter:
    """Marcadores invisibles que hacen clickeable cada miniatura."""
    return go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=cell_px, color="rgba(0,0,0,0)"),
        customdata=cd,
        hovertemplate="<b>%{customdata[0]}</b><br>tipo: %{customdata[2]}<extra></extra>",
    )


def figura_montage(df, var, ncols, thumbs, id_col, tipo_col, cell_px) -> tuple[go.Figure, dict]:
    """Grilla ordenada por una variable (ImageMontage)."""
    orden = df.assign(_v=pd.to_numeric(df[var], errors="coerce")).sort_values("_v").reset_index(drop=True)
    n = len(orden)
    nrows = max(1, int(np.ceil(n / ncols))) if n else 1
    fig = go.Figure()
    pos: dict[int, tuple[float, float]] = {}
    xs, ys, cd = [], [], []
    for i, fila in orden.iterrows():
        col, row = i % ncols, i // ncols
        x, y = col + 0.5, -(row + 0.5)
        clave = int(fila["_clave"])
        pos[clave] = (x, y)
        uri = thumbs.get(str(fila[id_col]))
        if uri:
            fig.add_layout_image(dict(source=uri, xref="x", yref="y",
                                      x=x - 0.46, y=y + 0.46, sizex=0.92, sizey=0.92,
                                      xanchor="left", yanchor="top", layer="below"))
        xs.append(x); ys.append(y)
        cd.append([fila[id_col], clave, fila.get(tipo_col, "")])
    fig.add_trace(_traza_seleccion(xs, ys, cd, cell_px))
    fig.update_layout(
        height=int(min(2600, max(280, nrows * (cell_px + 8)))),
        margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
        title=f"Montage ordenado por {var} (menor → mayor)",
        xaxis=dict(visible=False, range=[0, ncols]),
        yaxis=dict(visible=False, range=[-nrows, 0], scaleanchor="x", scaleratio=1),
    )
    return fig, pos


def figura_matriz(df, vx, vy, bins, por_fila, thumbs, id_col, tipo_col, cell_px) -> tuple[go.Figure, dict]:
    """Matriz de cuantiles: filas = rangos de vy, columnas = rangos de vx."""
    d = df.assign(_vx=pd.to_numeric(df[vx], errors="coerce"),
                  _vy=pd.to_numeric(df[vy], errors="coerce")).dropna(subset=["_vx", "_vy"])
    if d.empty:
        return go.Figure(), {}
    qx = max(2, min(int(bins), int(d["_vx"].nunique())))
    qy = max(2, min(int(bins), int(d["_vy"].nunique())))
    d["_bx"] = pd.qcut(d["_vx"], q=qx, labels=False, duplicates="drop")
    d["_by"] = pd.qcut(d["_vy"], q=qy, labels=False, duplicates="drop")
    nb_x = int(d["_bx"].max()) + 1
    nb_y = int(d["_by"].max()) + 1
    grupos = {(int(bx), int(by)): g.sort_values("_vx")
              for (bx, by), g in d.groupby(["_bx", "_by"])}
    max_filas = max(int(np.ceil(len(g) / por_fila)) for g in grupos.values())
    block_w = por_fila + 1
    block_h = max_filas + 1
    fig = go.Figure()
    pos: dict[int, tuple[float, float]] = {}
    xs, ys, cd = [], [], []
    for (bx, by), g in grupos.items():
        ox = bx * block_w
        oy = -((nb_y - 1 - by) * block_h)
        for k, (_, fila) in enumerate(g.iterrows()):
            x = ox + (k % por_fila) + 0.5
            y = oy - (k // por_fila) - 0.5
            clave = int(fila["_clave"])
            pos[clave] = (x, y)
            uri = thumbs.get(str(fila[id_col]))
            if uri:
                fig.add_layout_image(dict(source=uri, xref="x", yref="y",
                                          x=x - 0.46, y=y + 0.46, sizex=0.92, sizey=0.92,
                                          xanchor="left", yanchor="top", layer="below"))
            xs.append(x); ys.append(y)
            cd.append([fila[id_col], clave, fila.get(tipo_col, "")])
    fig.add_trace(_traza_seleccion(xs, ys, cd, cell_px))
    fig.update_layout(
        height=int(min(2600, max(320, nb_y * block_h * (cell_px + 6)))),
        margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
        title=f"Matriz {vy} (filas) × {vx} (columnas)",
        xaxis=dict(title=f"{vx} (cuantiles, bajo → alto)", range=[0, nb_x * block_w]),
        yaxis=dict(title=f"{vy} (alto → bajo)", range=[-nb_y * block_h, 0],
                   scaleanchor="x", scaleratio=1),
    )
    return fig, pos


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Canvas Analítico — TPI Manovich", layout="wide")
    st.title("Canvas Analítico")
    st.caption("Inspirado en ImagePlot de Manovich: cada punto es una fotografía del corpus.")

    # ---------------- Datos ----------------
    with st.sidebar:
        st.header("Datos")
        ruta_detectada = primera_ruta_datos(None)
        ruta_txt = st.text_input("Tabla (CSV)",
                                 value=str(ruta_detectada) if ruta_detectada else "datos/dataset.csv")
        raiz_txt = st.text_input("Carpeta de imágenes", value=str(RUTA_IMAGENES_POR_DEFECTO))
        if st.button("Recargar datos"):
            st.cache_data.clear()

    ruta_datos = primera_ruta_datos(ruta_txt)
    if ruta_datos is None:
        st.error("No se encontró la tabla. Corré el pipeline o indicá una ruta válida.")
        st.stop()

    df = leer_tabla(str(ruta_datos))
    columnas = detectar_columnas(df)
    roles = detectar_roles(df, columnas)
    indice_imagenes = indexar_imagenes(raiz_txt)

    if roles["id"] is None:
        nombre_fila = "_fila"
        while nombre_fila in df.columns:
            nombre_fila += "_"
        df[nombre_fila] = [f"foto_{i + 1}" for i in range(len(df))]
        roles["id"] = nombre_fila

    tipo_col = roles["tipo"]
    if tipo_col is None:
        tipo_col = "_tipo_unico"
        df[tipo_col] = "todas"

    # ---------------- Parámetros recalculables ----------------
    imagenes = analizar_imagenes(raiz_txt) if roles["id"] else {"hist": {}, "thumb": {}}
    hist = imagenes["hist"]
    thumbs = imagenes["thumb"]
    with st.sidebar:
        st.header("Parámetros recalculables")
        u_bajo = st.slider("Umbral de sombras (L <)", 0.00, 0.50, UMBRAL_SOMBRA_INICIAL, 0.01,
                           help="Se recalcula la proporción de píxeles oscuros de cada foto.")
        u_alto = st.slider("Umbral de altas luces (L >)", 0.50, 1.00, UMBRAL_ALTAS_INICIAL, 0.01,
                           help="Se recalcula la proporción de píxeles claros de cada foto.")
        if not hist:
            st.warning("No se pudieron leer las imágenes; los umbrales no se recalculan.")

    col_bajo, col_alto = roles["sombras"], roles["altas"]
    if hist:
        df, col_bajo, col_alto = aplicar_umbrales(df, hist, roles, u_bajo, u_alto)
    columnas = detectar_columnas(df)

    if not columnas["numericas"]:
        st.error("La tabla no tiene columnas numéricas para usar como ejes.")
        st.stop()

    # ---------------- Filtros y ejes ----------------
    with st.sidebar:
        st.header("Filtros")
        df_f = df.copy()
        if roles["tipo"]:
            txt = a_texto(df[roles["tipo"]])
            vals = sorted(txt.unique())
            sel = st.multiselect("Tipo", vals, default=vals)
            df_f = df_f[a_texto(df_f[roles["tipo"]]).isin(sel)]
        if roles["confianza"]:
            txt = a_texto(df[roles["confianza"]])
            vals = sorted(txt.unique())
            sel = st.multiselect("Confianza", vals, default=vals)
            df_f = df_f[a_texto(df_f[roles["confianza"]]).isin(sel)]
        if roles["caso_limite"]:
            caso = a_booleano(df[roles["caso_limite"]])
            vals = sorted({str(v) for v in caso.dropna().unique()})
            sel = st.multiselect("Caso límite", vals, default=vals)
            df_f = df_f[caso.reindex(df_f.index).astype(str).isin(sel)]

        st.header("Ejes")
        opciones = ["(ninguna)"] + columnas["numericas"]
        dx = columnas["numericas"][0]
        dy = columnas["numericas"][1] if len(columnas["numericas"]) > 1 else "(ninguna)"
        x_col = st.selectbox("Eje X", opciones, index=opciones.index(dx))
        y_col = st.selectbox("Eje Y", opciones, index=opciones.index(dy))

        opciones_color: list[tuple[str, str]] = []
        if roles["tipo"]:
            opciones_color.append(("Tipo asignado", roles["tipo"]))
        if roles["matiz"]:
            opciones_color.append(("Matiz (circular)", roles["matiz"]))
        if not opciones_color:
            opciones_color = [("Único", tipo_col)]
        etiquetas_color = [e for e, _ in opciones_color]
        color_sel = st.selectbox("Color de los puntos", etiquetas_color)
        color_col = dict(opciones_color)[color_sel]

    with st.expander("Columnas y roles detectados automáticamente", expanded=False):
        st.markdown(
            f"- **Numéricas (ejes):** {', '.join(columnas['numericas']) or '—'}\n"
            f"- **Categóricas:** {', '.join(columnas['categoricas']) or '—'}\n"
            f"- **Texto libre:** {', '.join(columnas['texto_libre']) or '—'}\n"
            f"- **Identificadoras:** {', '.join(columnas['identificadoras']) or '—'}\n"
            f"- **Roles:** id `{roles['id']}`, tipo `{roles['tipo']}`, "
            f"matiz `{roles['matiz']}`, saturación `{roles['saturacion']}`, "
            f"sombras `{col_bajo}`, altas luces `{col_alto}`"
        )

    colores = mapa_colores(df[tipo_col]) if tipo_col else {}
    df_plot = df_f.reset_index(drop=True)
    if df_plot.empty:
        st.warning("No hay fotografías que cumplan los filtros.")
        st.stop()
    df_plot = df_plot.assign(_clave=range(len(df_plot)))

    tab_plano, tab_dist, tab_grilla = st.tabs(
        ["Plano (ImagePlot)", "Distribuciones", "Grilla (montage)"]
    )

    # ================= Pestaña 1: Plano =================
    with tab_plano:
        st.caption(
            f"{len(df_plot)} fotografías. Umbrales aplicados: sombras L < {u_bajo:.2f}, "
            f"altas luces L > {u_alto:.2f} (recalculado desde las imágenes)."
        )
        x_activo, y_activo = x_col != "(ninguna)", y_col != "(ninguna)"
        if not x_activo and not y_activo:
            st.info("Elegí al menos una variable numérica para un eje (barra lateral).")
        else:
            if roles["matiz"] and (x_col == roles["matiz"] or y_col == roles["matiz"]):
                st.warning(
                    "El matiz es circular: un eje lineal corta el círculo en 0°/360°. "
                    "Mejor usalo como color de los puntos, o mirá la rosa polar en "
                    "la pestaña Distribuciones."
                )
            if x_activo and y_activo:
                c_thumb, c_tam = st.columns([2, 1])
                with c_thumb:
                    usar_miniaturas = st.checkbox(
                        "Modo ImagePlot: cada foto como miniatura en el plano",
                        value=True,
                        help="Dibuja la miniatura de cada foto en su coordenada. "
                             "El área de la miniatura queda clickeable para seleccionarla.",
                    )
                with c_tam:
                    tamano_px = st.slider("Tamaño de miniatura (px)", 24, 110, 56, 4,
                                          disabled=not usar_miniaturas)
                separar = st.checkbox("Separar filas superpuestas (misma foto repetida)",
                                      value=True)
                df_disp = df_plot.copy()
                df_disp["_x_disp"] = pd.to_numeric(df_disp[x_col], errors="coerce")
                df_disp["_y_disp"] = pd.to_numeric(df_disp[y_col], errors="coerce")
                if separar:
                    df_disp = separar_puntos_superpuestos(df_disp)
                miniaturas_ok = usar_miniaturas and bool(thumbs)
                if miniaturas_ok:
                    # área clickeable invisible del tamaño de la miniatura
                    tamano_punto, transparente = tamano_px, True
                else:
                    tamano_punto, transparente = 12, False
                if color_col == roles["matiz"]:
                    fig = construir_scatter_por_valor(
                        df_disp, x_col, y_col, roles["id"], color_col, "hsv", 0, 360,
                        "matiz (°)", tamano_punto, transparente,
                    )
                else:
                    fig = construir_scatter_por_tipo(
                        df_disp, x_col, y_col, tipo_col, roles["id"], colores,
                        tamano_punto, transparente,
                    )
                if miniaturas_ok:
                    agregar_miniaturas(fig, df_disp, roles["id"], thumbs, tamano_px)
                    fig.update_layout(height=760)
                elif usar_miniaturas:
                    st.warning("No se pudieron preparar las miniaturas; se muestran puntos.")
            else:
                columna_activa = x_col if x_activo else y_col
                fig = construir_ranking(df_plot, columna_activa, tipo_col, roles["id"], colores)

            # Zoom flotante: si venía seleccionada una miniatura, se agranda
            # sobre el plano (se lee de la selección persistida del gráfico).
            if x_activo and y_activo and miniaturas_ok:
                clave_prev = (claves_desde_puntos(seleccion_de_sesion("grafico"), df_plot) or [None])[-1]
                if clave_prev is not None:
                    fila_prev = df_plot.iloc[int(clave_prev)]
                    uri_prev = imagen_grande_base64(
                        indice_imagenes.get(str(fila_prev[roles["id"]]), "")
                    )
                    fd = df_disp[df_disp["_clave"] == clave_prev]
                    if uri_prev and not fd.empty:
                        xp = float(fd["_x_disp"].iloc[0])
                        yp = float(fd["_y_disp"].iloc[0])
                        xr = float(df_disp["_x_disp"].max() - df_disp["_x_disp"].min()) or 1.0
                        yr = float(df_disp["_y_disp"].max() - df_disp["_y_disp"].min()) or 1.0
                        agregar_overlay(fig, xp, yp, uri_prev,
                                        3.2 * tamano_px * xr / 1000.0,
                                        3.2 * tamano_px * yr / 540.0)

            evento = st.plotly_chart(fig, width="stretch", on_select="rerun",
                                     selection_mode="points", key="grafico")
            claves_sel = claves_desde_puntos(puntos_seleccionados(evento), df_plot)
            if claves_sel:
                st.divider()
                if len(claves_sel) == 1:
                    clave = claves_sel[0]
                else:
                    etq = {k: f"{df_plot.iloc[k][roles['id']]} · fila {k + 1}" for k in claves_sel}
                    clave = st.selectbox("Fila seleccionada", claves_sel,
                                         format_func=lambda k: etq[k])
                fila = df_plot.iloc[int(clave)]
                id_fila = fila[roles["id"]] if roles["id"] else None
                repetidas = (int((df_plot[roles["id"]].astype(str) == str(id_fila)).sum())
                             if id_fila is not None else 1)
                nota = (f"Esta foto tiene {repetidas} filas en el dataset; estás viendo "
                        f"la fila {int(clave) + 1}." if repetidas > 1 else None)
                mostrar_panel(fila, roles, columnas["numericas"], indice_imagenes, nota)
            else:
                st.caption("Hacé click en un punto para ver la miniatura, sus variables y la justificación.")

        with st.expander("Ver tabla filtrada"):
            st.dataframe(df_f, width="stretch")
            st.download_button("Descargar CSV filtrado",
                               data=df_f.to_csv(index=False).encode("utf-8"),
                               file_name="corpus_filtrado.csv", mime="text/csv")

    # ================= Pestaña 2: Distribuciones =================
    with tab_dist:
        st.caption(
            "Agregado de todo el corpus (una distribución por variable), no el "
            "histograma de una foto. Las líneas se solapan por tipo asignado."
        )
        numeric = columnas["numericas"]
        if st.checkbox("Mostrar resumen de todas las variables", value=True):
            st.plotly_chart(figura_histogramas_resumen(df_plot, numeric, tipo_col, colores),
                            width="stretch")

        variable = st.selectbox("Variable en detalle", numeric,
                                index=numeric.index("mediana_luminancia")
                                if "mediana_luminancia" in numeric else 0)
        st.plotly_chart(figura_detalle_variable(df_plot, variable, tipo_col, colores),
                        width="stretch")

        if roles["matiz"]:
            st.subheader("Matiz dominante (variable circular)")
            n_bins = st.slider("Cantidad de sectores", 8, 48, 24, 4)
            st.plotly_chart(
                figura_rosa_matiz(df_plot, roles["matiz"], tipo_col, colores, n_bins),
                width="stretch",
            )
        else:
            st.info("No se detectó una columna de matiz para el gráfico polar.")

    # ================= Pestaña 3: Grilla (montage) =================
    with tab_grilla:
        st.caption(
            "Vista tipo ImageMontage: las fotos ordenadas o agrupadas en una "
            "cuadrícula según sus variables. Hacé click en una miniatura para "
            "agrandarla flotando sobre la grilla."
        )
        if not thumbs:
            st.warning("No se pudieron preparar las miniaturas. Revisá la 'Carpeta de imágenes'.")
        else:
            modo = st.radio(
                "Modo",
                ["Una variable (montage ordenado)", "Dos variables (matriz)"],
                horizontal=True,
            )
            if modo.startswith("Una"):
                c1, c2 = st.columns(2)
                with c1:
                    var = st.selectbox("Ordenar por", columnas["numericas"], key="g_var")
                with c2:
                    ncols = st.slider("Columnas", 4, 30, 14, 1, key="g_cols")
                cell_px = st.slider("Tamaño de miniatura (px)", 36, 120, 64, 4, key="g_px")
                fig, pos = figura_montage(df_plot, var, ncols, thumbs,
                                          roles["id"], tipo_col, cell_px)
                lado_overlay = 4.5
            else:
                c1, c2, c3 = st.columns(3)
                with c1:
                    vx = st.selectbox("Variable de columnas (X)", columnas["numericas"], key="g_vx")
                with c2:
                    idx_y = 1 if len(columnas["numericas"]) > 1 else 0
                    vy = st.selectbox("Variable de filas (Y)", columnas["numericas"],
                                      index=idx_y, key="g_vy")
                with c3:
                    bins = st.slider("Bins por variable (cuantiles)", 2, 8, 4, 1, key="g_bins")
                c4, c5 = st.columns(2)
                with c4:
                    por_fila = st.slider("Miniaturas por fila en cada celda", 2, 10, 6, 1, key="g_pf")
                with c5:
                    cell_px = st.slider("Tamaño de miniatura (px)", 28, 90, 48, 4, key="g_px2")
                fig, pos = figura_matriz(df_plot, vx, vy, bins, por_fila, thumbs,
                                         roles["id"], tipo_col, cell_px)
                lado_overlay = 6.5

            clave_zoom = (claves_desde_puntos(seleccion_de_sesion("grilla"), df_plot) or [None])[-1]
            if clave_zoom is not None and clave_zoom in pos:
                fila_zoom = df_plot.iloc[int(clave_zoom)]
                uri_zoom = imagen_grande_base64(
                    indice_imagenes.get(str(fila_zoom[roles["id"]]), "")
                )
                if uri_zoom:
                    xz, yz = pos[clave_zoom]
                    agregar_overlay(fig, xz, yz, uri_zoom, lado_overlay, lado_overlay)
                st.caption(f"Ampliando `{fila_zoom[roles['id']]}`")
            else:
                st.caption("Hacé click en una miniatura para verla ampliada y flotando.")

            st.plotly_chart(fig, width="stretch", on_select="rerun",
                            selection_mode="points", key="grilla")

            if clave_zoom is not None:
                st.divider()
                mostrar_panel(df_plot.iloc[int(clave_zoom)], roles,
                              columnas["numericas"], indice_imagenes)


if __name__ == "__main__":
    main()
