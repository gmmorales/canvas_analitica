"""
app/canvas.py — Canvas Analítico (Fase 3, TPI Manovich)

App de Streamlit que lee el dataset del corpus (metadata + variables de
color/histograma) y permite explorarlo como un plano:

  - Ejes X/Y: dos columnas NUMÉRICAS elegidas de un menú desplegable.
  - Puntos coloreados según la columna de tipo (tipo_manovich).
  - Con una sola columna activa: ranking en línea (ordenada por ese valor).
  - Filtros por tipo, confianza y caso límite.
  - Al hacer click en un punto: panel con la miniatura, todas las variables
    numéricas y la justificación de la etiqueta.

La app detecta sola los roles de las columnas:
  - numéricas  -> candidatas a los ejes (no hay nombres de variables a mano);
  - texto libre -> justificación;
  - categóricas -> tipo / confianza / caso límite;
  - identificadoras -> id_imagen / autor_id.

Uso:
    uv run streamlit run app/canvas.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------
# Rutas y convenciones
# --------------------------------------------------------------------------
RUTAS_DATOS_CANDIDATAS = [
    Path("datos/dataset.csv"),
    Path("datos/referencias.csv"),
    Path("datos/metadata_normalizado.csv"),
]
RUTA_IMAGENES_POR_DEFECTO = Path("datos/corpus_normalizado")

# Nombres "conocidos" SOLO de columnas de identificación/etiqueta (el
# enunciado las nombra). Las variables de color NO se nombran acá: se
# detectan solas por tipo de dato.
COL_ID = "id_imagen"
COL_TIPO = "tipo_manovich"
COL_CONFIANZA = "confianza_etiqueta"
COL_CASO = "caso_limite"
COL_JUSTIFICACION = "justificacion_etiqueta"

UMBRAL_TEXTO_LARGO = 120      # largo promedio (caracteres) para "texto libre"
MAX_CATEGORIAS = 12           # más valores distintos que esto = identificadora
FRACCION_NUMERICA = 0.95      # % de valores parseables para tratar como numérica

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


@st.cache_data(show_spinner=False)
def indexar_imagenes(raiz: str) -> dict[str, str]:
    """id_imagen (stem) -> ruta de la imagen normalizada."""
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
# Detección automática de columnas
# --------------------------------------------------------------------------
def es_texto_libre(serie: pd.Series) -> bool:
    if not (serie.dtype == object or pd.api.types.is_string_dtype(serie)):
        return False
    largos = serie.dropna().astype(str).str.len()
    return len(largos) > 0 and largos.mean() >= UMBRAL_TEXTO_LARGO


def detectar_columnas(df: pd.DataFrame) -> dict:
    """
    Devuelve {'numericas', 'texto_libre', 'categoricas', 'identificadoras'}.
    No usa nombres de variables: clasifica por contenido/dtype.
    """
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
            if 1 < distintos <= MAX_CATEGORIAS:
                categoricas.append(col)
            else:
                identificadoras.append(col)
    return {
        "numericas": numericas,
        "texto_libre": texto_libre,
        "categoricas": categoricas,
        "identificadoras": identificadoras,
    }


def detectar_roles(df: pd.DataFrame, columnas: dict) -> dict:
    """
    Mapea los roles que necesita la app a columnas concretas. Prefiere los
    nombres conocidos de las columnas de identificación/etiqueta y, si no
    están, cae al representante detectado por contenido.
    """
    cols = set(df.columns)

    def primero(lista):
        return lista[0] if lista else None

    id_col = COL_ID if COL_ID in cols else primero(columnas["identificadoras"])
    tipo_col = COL_TIPO if COL_TIPO in cols else primero(columnas["categoricas"])
    confianza_col = (
        COL_CONFIANZA if COL_CONFIANZA in cols
        else next((c for c in columnas["categoricas"] if "conf" in c.lower()), None)
    )
    caso_col = (
        COL_CASO if COL_CASO in cols
        else next((c for c in columnas["identificadoras"] + columnas["categoricas"]
                   if "caso" in c.lower()), None)
    )
    justificacion_col = (
        COL_JUSTIFICACION if COL_JUSTIFICACION in cols
        else primero(columnas["texto_libre"])
    )
    return {
        "id": id_col,
        "tipo": tipo_col,
        "confianza": confianza_col,
        "caso_limite": caso_col,
        "justificacion": justificacion_col,
    }


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


def mapa_colores(valores) -> dict:
    limpios = sorted({str(v) for v in valores if pd.notna(v)})
    return {v: PALETA[i % len(PALETA)] for i, v in enumerate(limpios)}


def color_de(mapa: dict, valor) -> str:
    return mapa.get(str(valor), PALETA[0])


def construir_scatter(df, x_col, y_col, tipo_col, id_col, colores) -> go.Figure:
    """df debe traer las columnas de dibujo `_x_disp` y `_y_disp`."""
    fig = go.Figure()
    for tipo, grupo in df.groupby(tipo_col, dropna=False, sort=True):
        fig.add_trace(
            go.Scatter(
                x=grupo["_x_disp"],
                y=grupo["_y_disp"],
                mode="markers",
                name=str(tipo),
                customdata=grupo[[id_col, x_col, y_col, "_clave"]].to_numpy(),
                marker=dict(
                    size=12,
                    color=color_de(colores, tipo),
                    line=dict(width=1, color="white"),
                ),
                hovertemplate=(
                    f"<b>%{{customdata[0]}}</b><br>{x_col}: %{{customdata[1]}}"
                    f"<br>{y_col}: %{{customdata[2]}}<br>{tipo_col}: {tipo}"
                    "<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=y_col,
        legend_title=tipo_col,
        margin=dict(l=10, r=10, t=30, b=10),
        height=620,
    )
    return fig


def separar_puntos_superpuestos(df, radio: float = 0.012) -> pd.DataFrame:
    """
    Da un desplazamiento mínimo (en círculo) a las filas que comparten
    exactamente las mismas coordenadas, para que las filas repetidas de una
    misma foto no queden una encima de la otra. Solo mueve la POSICIÓN de
    dibujo (`_x_disp`/`_y_disp`); los valores reales que muestra el hover
    salen de las columnas originales.
    """
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


def construir_ranking(df, col, tipo_col, id_col, colores) -> go.Figure:
    """Una sola variable activa: ordena los puntos en una línea (ranking)."""
    ordenado = df.sort_values(col, ascending=True).reset_index(drop=True)
    ordenado["_rank"] = np.arange(1, len(ordenado) + 1)

    fig = go.Figure()
    # Línea guía que marca el orden.
    fig.add_trace(
        go.Scatter(
            x=ordenado["_rank"],
            y=np.zeros(len(ordenado)),
            mode="lines",
            line=dict(color="rgba(150,150,150,0.35)", width=1),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    for tipo, grupo in ordenado.groupby(tipo_col, dropna=False, sort=True):
        fig.add_trace(
            go.Scatter(
                x=grupo["_rank"],
                y=np.zeros(len(grupo)),
                mode="markers",
                name=str(tipo),
                customdata=grupo[[id_col, col, "_clave"]].to_numpy(),
                marker=dict(
                    size=13,
                    color=color_de(colores, tipo),
                    line=dict(width=1, color="white"),
                ),
                hovertemplate=(
                    f"<b>%{{customdata[0]}}</b><br>puesto %{{x}} de "
                    f"{len(ordenado)}<br>{col}: %{{customdata[1]}}<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        xaxis_title=f"ranking por {col} (menor -> mayor)",
        yaxis=dict(showticklabels=False, range=[-1, 1], title=""),
        legend_title=tipo_col,
        margin=dict(l=10, r=10, t=30, b=10),
        height=420,
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


def claves_desde_puntos(puntos: list, df_plot: pd.DataFrame) -> list:
    """
    Devuelve la clave interna (`_clave`) de cada fila seleccionada. Se usa
    la clave y no el id_imagen para que dos filas de la MISMA foto (ids
    repetidos) se puedan mostrar por separado.
    """
    claves: list[int] = []
    for punto in puntos:
        customdata = punto.get("customdata")
        if customdata and isinstance(customdata, (list, tuple)):
            claves.append(int(customdata[-1]))
            continue
        idx = punto.get("point_index", punto.get("point_number"))
        if idx is not None and 0 <= int(idx) < len(df_plot):
            claves.append(int(df_plot.iloc[int(idx)]["_clave"]))
    vistas: list[int] = []
    for clave in claves:
        if clave not in vistas:
            vistas.append(clave)
    return vistas


def mostrar_panel(
    fila: pd.Series,
    roles: dict,
    numericas: list,
    indice_imagenes: dict,
    nota: str | None = None,
) -> None:
    id_imagen = fila[roles["id"]] if roles["id"] else "—"
    izquierda, derecha = st.columns([1, 2])

    with izquierda:
        ruta = indice_imagenes.get(str(id_imagen))
        if ruta:
            st.image(ruta, caption=str(id_imagen), use_container_width=True)
        else:
            st.info(f"No se encontró la imagen de {id_imagen} en el corpus.")

    with derecha:
        st.markdown(f"### `{id_imagen}`")
        if nota:
            st.caption(nota)
        etiquetas = []
        for etiqueta, col in [
            ("tipo", roles["tipo"]),
            ("confianza", roles["confianza"]),
            ("caso límite", roles["caso_limite"]),
        ]:
            if col and col in fila.index:
                etiquetas.append(f"**{etiqueta}:** {fila[col]}")
        if etiquetas:
            st.markdown("  \n".join(etiquetas))

        if numericas:
            st.markdown("**Variables numéricas**")
            tabla = pd.DataFrame(
                {"variable": numericas, "valor": [fila.get(c, "") for c in numericas]}
            )
            st.dataframe(tabla, hide_index=True, use_container_width=True)

        col_just = roles["justificacion"]
        if col_just and col_just in fila.index and pd.notna(fila[col_just]):
            st.markdown("**Justificación de la etiqueta**")
            st.info(str(fila[col_just]))


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Canvas Analítico — TPI Manovich", layout="wide")
    st.title("Canvas Analítico")
    st.caption(
        "Cada punto es una fotografía del corpus. Ejes = variables numéricas; "
        "color = tipo asignado (tipo_manovich)."
    )

    # ---------------- Sidebar: datos ----------------
    with st.sidebar:
        st.header("Datos")
        ruta_detectada = primera_ruta_datos(None)
        ruta_txt = st.text_input(
            "Tabla (CSV)",
            value=str(ruta_detectada) if ruta_detectada else "datos/dataset.csv",
        )
        raiz_txt = st.text_input("Carpeta de imágenes", value=str(RUTA_IMAGENES_POR_DEFECTO))
        if st.button("Recargar datos"):
            st.cache_data.clear()

    ruta_datos = primera_ruta_datos(ruta_txt)
    if ruta_datos is None:
        st.error(
            "No se encontró la tabla. Corré el pipeline "
            "(`pipeline/construir_dataset.py`) o indicá una ruta válida en la barra lateral."
        )
        st.stop()

    df = leer_tabla(str(ruta_datos))
    columnas = detectar_columnas(df)
    roles = detectar_roles(df, columnas)
    indice_imagenes = indexar_imagenes(raiz_txt)

    # Si no hay columna de id, generamos una por fila para poder seleccionar.
    if roles["id"] is None:
        nombre_fila = "_fila"
        while nombre_fila in df.columns:
            nombre_fila += "_"
        df[nombre_fila] = [f"foto_{i + 1}" for i in range(len(df))]
        roles["id"] = nombre_fila

    # Si no hay columna de tipo, usamos una constante para poder graficar.
    tipo_col = roles["tipo"]
    if tipo_col is None:
        tipo_col = "_tipo_unico"
        df[tipo_col] = "todas"

    if not columnas["numericas"]:
        st.error("La tabla no tiene columnas numéricas para usar como ejes.")
        st.stop()

    with st.expander("Columnas detectadas automáticamente", expanded=False):
        st.markdown(
            f"- **Numéricas (ejes):** {', '.join(columnas['numericas']) or '—'}\n"
            f"- **Categóricas:** {', '.join(columnas['categoricas']) or '—'}\n"
            f"- **Texto libre:** {', '.join(columnas['texto_libre']) or '—'}\n"
            f"- **Identificadoras:** {', '.join(columnas['identificadoras']) or '—'}\n"
            f"- **Rol id:** `{roles['id']}` · **tipo:** `{roles['tipo']}` · "
            f"**confianza:** `{roles['confianza']}` · **caso límite:** `{roles['caso_limite']}`"
        )

    # ---------------- Sidebar: filtros y ejes ----------------
    with st.sidebar:
        st.header("Ejes")
        opciones_eje = ["(ninguna)"] + columnas["numericas"]
        default_x = columnas["numericas"][0]
        default_y = columnas["numericas"][1] if len(columnas["numericas"]) > 1 else "(ninguna)"
        x_col = st.selectbox("Eje X", opciones_eje, index=opciones_eje.index(default_x))
        y_col = st.selectbox("Eje Y", opciones_eje, index=opciones_eje.index(default_y))

        st.header("Filtros")
        df_filtrado = df.copy()
        if roles["tipo"]:
            valores_tipo = [v for v in df[roles["tipo"]].dropna().unique()]
            sel_tipo = st.multiselect("Tipo", sorted(map(str, valores_tipo)), default=sorted(map(str, valores_tipo)))
            df_filtrado = df_filtrado[df_filtrado[roles["tipo"]].astype(str).isin(sel_tipo)]

        if roles["confianza"]:
            valores_conf = sorted({str(v) for v in df[roles["confianza"]].dropna().unique()})
            sel_conf = st.multiselect("Confianza", valores_conf, default=valores_conf)
            df_filtrado = df_filtrado[df_filtrado[roles["confianza"]].astype(str).isin(sel_conf)]

        if roles["caso_limite"]:
            caso_bool = a_booleano(df[roles["caso_limite"]])
            valores_caso = sorted({str(v) for v in caso_bool.dropna().unique()})
            sel_caso = st.multiselect("Caso límite", valores_caso, default=valores_caso)
            df_filtrado = df_filtrado[caso_bool.reindex(df_filtrado.index).astype(str).isin(sel_caso)]

    st.caption(f"{len(df_filtrado)} de {len(df)} fotografías tras los filtros.")

    df_plot = df_filtrado.reset_index(drop=True)
    if df_plot.empty:
        st.warning("No hay fotografías que cumplan los filtros.")
        st.stop()
    # Clave interna única por fila: permite distinguir dos filas de la MISMA
    # foto (id_imagen repetido) al seleccionar.
    df_plot = df_plot.assign(_clave=range(len(df_plot)))

    colores = mapa_colores(df[tipo_col]) if tipo_col else {}

    # ---------------- Gráfico ----------------
    x_activo = x_col != "(ninguna)"
    y_activo = y_col != "(ninguna)"
    if not x_activo and not y_activo:
        st.info("Elegí al menos una variable numérica para un eje.")
        st.stop()

    if x_activo and y_activo:
        separar = st.checkbox(
            "Separar filas superpuestas (misma foto repetida)",
            value=True,
            help=(
                "Desplaza mínimamente las filas que comparten coordenadas para "
                "que no queden una encima de otra. No cambia los valores que "
                "se muestran al pasar el mouse."
            ),
        )
        df_disp = df_plot.copy()
        df_disp["_x_disp"] = pd.to_numeric(df_disp[x_col], errors="coerce")
        df_disp["_y_disp"] = pd.to_numeric(df_disp[y_col], errors="coerce")
        if separar:
            df_disp = separar_puntos_superpuestos(df_disp)
        fig = construir_scatter(df_disp, x_col, y_col, tipo_col, roles["id"], colores)
    else:
        columna_activa = x_col if x_activo else y_col
        fig = construir_ranking(df_plot, columna_activa, tipo_col, roles["id"], colores)

    evento = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="grafico",
    )

    # ---------------- Panel del punto seleccionado ----------------
    puntos = puntos_seleccionados(evento)
    claves_sel = claves_desde_puntos(puntos, df_plot)
    if claves_sel:
        st.divider()
        if len(claves_sel) == 1:
            clave = claves_sel[0]
        else:
            etiquetas = {
                k: f"{df_plot.iloc[k][roles['id']]} · fila {k + 1}" for k in claves_sel
            }
            clave = st.selectbox(
                "Fila seleccionada", claves_sel, format_func=lambda k: etiquetas[k]
            )
        fila = df_plot.iloc[int(clave)]
        id_fila = fila[roles["id"]] if roles["id"] else None
        repetidas = (
            int((df_plot[roles["id"]].astype(str) == str(id_fila)).sum())
            if id_fila is not None
            else 1
        )
        nota = (
            f"Esta foto tiene {repetidas} filas en el dataset; estás viendo la "
            f"fila {int(clave) + 1}."
            if repetidas > 1
            else None
        )
        mostrar_panel(fila, roles, columnas["numericas"], indice_imagenes, nota)
    else:
        st.caption("Hacé click en un punto para ver la miniatura, sus variables y la justificación.")

    # ---------------- Tabla y descarga ----------------
    with st.expander("Ver tabla filtrada"):
        st.dataframe(df_filtrado, use_container_width=True)
        st.download_button(
            "Descargar CSV filtrado",
            data=df_filtrado.to_csv(index=False).encode("utf-8"),
            file_name="corpus_filtrado.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
