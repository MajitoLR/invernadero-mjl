
"""
Invernadero IoT - App de análisis
Proyecto Final · Computación Física e Internet de las Cosas

Carga el CSV exportado desde Grafana (uno con las dos variables, o uno por panel)
y analiza la temperatura del aire y la humedad del suelo del invernadero.
"""
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------- Definición del sistema ----------
VARIABLES = {
    "temperatura": {
        "nombre": "Temperatura del aire",
        "unidad": "°C",
        "min": 18.0,
        "max": 30.0,
        "limites": (0.0, 50.0),
        "claves": ["temp"],
        "color": "#c62828",
        "alerta_alta": "Calor excesivo: enciende el ventilador.",
        "alerta_baja": "Frío: mantén el ventilador apagado y cierra el invernadero.",
    },
    "humedad_suelo": {
        "nombre": "Humedad del suelo",
        "unidad": "%",
        "min": 40.0,
        "max": 80.0,
        "limites": (0.0, 100.0),
        "claves": ["hum", "suelo"],
        "color": "#0277bd",
        "alerta_alta": "Suelo encharcado: suspende el riego.",
        "alerta_baja": "Suelo seco: hace falta regar.",
    },
}
CSV_EJEMPLO = Path(__file__).parent / "datos_grafana.csv"

st.set_page_config(page_title="Invernadero IoT", page_icon="🌱", layout="wide")


# ---------- DISEÑO VISUAL: INVERNADERO ----------
st.markdown("""
<style>

/* Fondo verde pastel */
.stApp {
    background:
        radial-gradient(ellipse at 8% 4%, rgba(210, 232, 205, .35), transparent 28%),
        radial-gradient(ellipse at 95% 18%, rgba(224, 239, 215, .40), transparent 30%),
        linear-gradient(135deg, #EAF4E7 0%, #DDEED9 50%, #F0F6EB 100%);
    color: #294536;
    font-family: 'DM Sans', sans-serif;
}

/* Contenedor principal */
.block-container {
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

/* Títulos */
h1 {
    color: #315C43 !important;
    font-size: 2.5rem !important;
    font-weight: 800 !important;
    letter-spacing: -1px;
}

h2 {
    color: #3D684D !important;
    font-weight: 750 !important;
    margin-top: 2rem !important;
}

h3 {
    color: #52785B !important;
    font-weight: 700 !important;
}

/* Texto general */
p, label, span, div {
    color: inherit;
}

/* Descripción debajo del título */
[data-testid="stCaptionContainer"] {
    color: #68836C;
    font-size: 1rem;
}

/* Barra lateral */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #D5E9D1 0%, #E5F0DF 100%);
    border-right: 1px solid #C2DCC0;
}

[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #315C43 !important;
}

/* Tarjetas de métricas */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid #C8DEC5;
    border-radius: 18px;
    padding: 22px;
    box-shadow: 0 4px 14px rgba(65, 105, 75, 0.07);
}

[data-testid="stMetricLabel"] {
    color: #52785B !important;
    font-weight: 700;
}

[data-testid="stMetricValue"] {
    color: #315C43 !important;
    font-weight: 800;
}

/* Mensajes de estado */
[data-testid="stAlert"] {
    border-radius: 12px;
    border: 1px solid #D0E2CC;
}

/* Botones */
.stButton > button {
    background: #6E9B72;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.6rem 1.2rem;
    font-weight: 700;
}

.stButton > button:hover {
    background: #527D59;
    color: white;
    border: none;
}

/* Cargador de archivos */
[data-testid="stFileUploader"] {
    background: rgba(255, 255, 255, 0.55);
    border: 1px dashed #91B895;
    border-radius: 15px;
    padding: 12px;
}

/* Deslizadores */
.stSlider [data-baseweb="slider"] div {
    color: #527D59;
}

/* Tablas */
[data-testid="stDataFrame"] {
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid #C8DEC5;
    border-radius: 14px;
    overflow: hidden;
}

/* Expansores */
[data-testid="stExpander"] {
    background: rgba(255, 255, 255, 0.60);
    border: 1px solid #C8DEC5;
    border-radius: 14px;
}

/* Separadores */
hr {
    border-color: #C8DEC5;
}

/* Enlaces */
a {
    color: #477B50 !important;
}

/* Espaciado de elementos */
[data-testid="stVerticalBlock"] {
    gap: 1rem;
}

</style>
""", unsafe_allow_html=True)


# ---------- Lectura del CSV de Grafana ----------
def _a_numero(serie: pd.Series) -> pd.Series:
    """Convierte '25.3 °C' o '55,2%' en números (Grafana puede exportar con unidades)."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype(float)
    texto = serie.astype(str).str.replace(",", ".", regex=False)
    return pd.to_numeric(texto.str.extract(r"(-?\d+(?:\.\d+)?)")[0], errors="coerce")


def _a_tiempo(serie: pd.Series) -> pd.Series:
    """Acepta fechas en texto o marcas de tiempo en milisegundos."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_datetime(serie, unit="ms", errors="coerce")
    tiempo = pd.to_datetime(serie, errors="coerce")
    if tiempo.notna().sum() == 0:
        tiempo = pd.to_datetime(pd.to_numeric(serie, errors="coerce"), unit="ms", errors="coerce")
    if getattr(tiempo.dt, "tz", None) is not None:
        tiempo = tiempo.dt.tz_convert("America/Bogota").dt.tz_localize(None)
    return tiempo


def leer_csv(archivo) -> pd.DataFrame:
    """Devuelve un DataFrame con 'tiempo' y las variables que encuentre en el archivo."""
    crudo = pd.read_csv(archivo, sep=None, engine="python", comment="#")
    crudo.columns = [str(c).strip() for c in crudo.columns]
    crudo = crudo.loc[:, [c for c in crudo.columns if c and not c.startswith("Unnamed")]]

    if {"_field", "_value"}.issubset(crudo.columns):
        col_t = "_time" if "_time" in crudo.columns else "time"
        crudo = (crudo.pivot_table(index=col_t, columns="_field", values="_value", aggfunc="last")
                 .reset_index().rename(columns={col_t: "time"}))
        crudo.columns = [str(c) for c in crudo.columns]

    col_tiempo = next(
        (c for c in crudo.columns if re.search(r"time|tiempo|fecha", c, re.I)), crudo.columns[0]
    )
    salida = pd.DataFrame({"tiempo": _a_tiempo(crudo[col_tiempo])})

    for clave, var in VARIABLES.items():
        for col in crudo.columns:
            if col == col_tiempo:
                continue
            if any(k in col.lower() for k in var["claves"]):
                salida[clave] = _a_numero(crudo[col])
                break
    return salida.dropna(subset=["tiempo"])


def unir(tablas: list) -> pd.DataFrame:
    """Une los CSV (por ejemplo, uno por panel de Grafana) en una sola tabla por tiempo."""
    datos = None
    for tabla in tablas:
        tabla = tabla.sort_values("tiempo")
        if datos is None:
            datos = tabla
            continue
        nuevas = [c for c in tabla.columns if c != "tiempo" and c not in datos.columns]
        if nuevas:
            datos = pd.merge_asof(
                datos, tabla[["tiempo"] + nuevas], on="tiempo",
                direction="nearest", tolerance=pd.Timedelta(seconds=10),
            )
    return datos.sort_values("tiempo").reset_index(drop=True)


def episodios(datos: pd.DataFrame, clave: str) -> pd.DataFrame:
    """Agrupa las lecturas consecutivas fuera de rango en episodios de alerta."""
    var = VARIABLES[clave]
    d = datos[["tiempo", clave]].dropna()
    estado = pd.Series("ok", index=d.index)
    estado[d[clave] > var["max"]] = "alta"
    estado[d[clave] < var["min"]] = "baja"
    grupo = (estado != estado.shift()).cumsum()
    filas = []
    for _, bloque in d.groupby(grupo):
        tipo = estado.loc[bloque.index[0]]
        if tipo == "ok":
            continue
        filas.append({
            "Variable": var["nombre"],
            "Tipo": "Por encima del rango" if tipo == "alta" else "Por debajo del rango",
            "Inicio": bloque["tiempo"].iloc[0],
            "Fin": bloque["tiempo"].iloc[-1],
            "Duración (min)": round((bloque["tiempo"].iloc[-1] - bloque["tiempo"].iloc[0]).total_seconds() / 60, 1),
            "Valor extremo": f'{(bloque[clave].max() if tipo == "alta" else bloque[clave].min()):.1f} {var["unidad"]}',
            "Lecturas": len(bloque),
        })
    return pd.DataFrame(filas)


# ---------- Interfaz ----------
st.title("🌱 Invernadero IoT — análisis de operación")
st.caption(
    "Telemetría del ESP32 (temperatura del aire y humedad del suelo) guardada en InfluxDB "
    "y exportada desde Grafana."
)

with st.sidebar:
    st.header("Datos")
    archivos = st.file_uploader(
        "CSV exportado de Grafana", type="csv", accept_multiple_files=True,
        help="Puedes subir un CSV con las dos variables o uno por cada panel.",
    )
    st.header("Rangos de operación")
    for clave, var in VARIABLES.items():
        var["min"], var["max"] = st.slider(
            f'{var["nombre"]} ({var["unidad"]})',
            min_value=var["limites"][0], max_value=var["limites"][1],
            value=(var["min"], var["max"]), step=0.5,
        )
    st.caption("Los valores por defecto corresponden a un cultivo de hortalizas (tomate).")

if archivos:
    datos = unir([leer_csv(a) for a in archivos])
elif CSV_EJEMPLO.exists():
    datos = unir([leer_csv(CSV_EJEMPLO)])
    st.info("Mostrando el CSV incluido en el repositorio. Sube otro CSV de Grafana en el panel lateral para analizarlo.")
else:
    st.warning("Sube el CSV exportado desde Grafana en el panel lateral para comenzar.")
    st.stop()

presentes = [c for c in VARIABLES if c in datos.columns and datos[c].notna().any()]
if datos.empty or not presentes:
    st.error(
        "No encontré las variables en el archivo. El CSV debe tener una columna de tiempo y "
        "columnas llamadas `temperatura` y `humedad_suelo`."
    )
    st.stop()

inicio, fin = datos["tiempo"].min(), datos["tiempo"].max()
st.write(
    f"**Periodo analizado:** {inicio:%Y-%m-%d %H:%M} a {fin:%Y-%m-%d %H:%M} · "
    f"**{len(datos)} lecturas**"
)

# --- Estado actual ---
st.subheader("Última lectura")
columnas = st.columns(len(presentes))
for col, clave in zip(columnas, presentes):
    var = VARIABLES[clave]
    serie = datos[clave].dropna()
    ultimo = serie.iloc[-1]
    with col:
        st.metric(var["nombre"], f'{ultimo:.1f} {var["unidad"]}',
                  delta=f'{ultimo - serie.mean():+.1f} vs. promedio', delta_color="off")
        if ultimo > var["max"]:
            st.error(f'⚠️ {var["alerta_alta"]}')
        elif ultimo < var["min"]:
            st.error(f'⚠️ {var["alerta_baja"]}')
        else:
            st.success(f'Dentro del rango ({var["min"]:g}–{var["max"]:g} {var["unidad"]})')

# --- Series de tiempo ---
st.subheader("Comportamiento en el tiempo")
for clave in presentes:
    var = VARIABLES[clave]
    d = datos[["tiempo", clave]].dropna()
    fuera = d[(d[clave] > var["max"]) | (d[clave] < var["min"])]
    fig = go.Figure()
    fig.add_hrect(y0=var["min"], y1=var["max"], fillcolor="#2e7d32", opacity=0.10, line_width=0,
                  annotation_text="rango de operación", annotation_position="top left")
    fig.add_trace(go.Scatter(x=d["tiempo"], y=d[clave], mode="lines", name=var["nombre"],
                             line=dict(color=var["color"], width=2)))
    fig.add_trace(go.Scatter(x=fuera["tiempo"], y=fuera[clave], mode="markers", name="Fuera de rango",
                             marker=dict(color="#000000", size=6, symbol="x")))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10),
                      title=f'{var["nombre"]} ({var["unidad"]})',
                      yaxis_title=var["unidad"], legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, width="stretch")

# --- Estadísticas ---
st.subheader("Estadísticas")
filas = []
for clave in presentes:
    var = VARIABLES[clave]
    s = datos[clave].dropna()
    en_rango = ((s >= var["min"]) & (s <= var["max"])).mean() * 100
    filas.append({
        "Variable": f'{var["nombre"]} ({var["unidad"]})',
        "Mínimo": round(s.min(), 1), "Promedio": round(s.mean(), 1), "Máximo": round(s.max(), 1),
        "Desv. estándar": round(s.std(), 2),
        "Rango permitido": f'{var["min"]:g} – {var["max"]:g}',
        "% del tiempo en rango": round(en_rango, 1),
    })
st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")

# --- Alertas ---
st.subheader("Alertas por umbral")
tablas = [episodios(datos, c) for c in presentes]
alertas = pd.concat([t for t in tablas if not t.empty]) if any(not t.empty for t in tablas) else pd.DataFrame()
if alertas.empty:
    st.success("No hubo lecturas fuera de rango en el periodo.")
else:
    st.write(f"Se detectaron **{len(alertas)} episodios** fuera de rango:")
    st.dataframe(alertas.sort_values("Inicio"), hide_index=True, width="stretch")

# --- Correlación ---
if len(presentes) == 2:
    st.subheader("Relación entre temperatura y humedad del suelo")
    par = datos[presentes].dropna()
    if len(par) >= 3 and par.nunique().min() > 1:
        r = par["temperatura"].corr(par["humedad_suelo"])
        izq, der = st.columns([2, 1])
        with izq:
            fig = go.Figure(go.Scatter(
                x=par["temperatura"], y=par["humedad_suelo"], mode="markers",
                marker=dict(color="#2e7d32", size=7, opacity=0.6)))
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                              xaxis_title="Temperatura del aire (°C)",
                              yaxis_title="Humedad del suelo (%)")
            st.plotly_chart(fig, width="stretch")
        with der:
            st.metric("Correlación de Pearson", f"{r:.2f}")
            fuerza = "fuerte" if abs(r) >= 0.7 else "moderada" if abs(r) >= 0.4 else "débil"
            if abs(r) < 0.2:
                st.write("Las dos variables casi no se relacionan en este periodo.")
            elif r < 0:
                st.write(f"Relación inversa {fuerza}: cuando sube la temperatura, el suelo tiende a secarse. "
                         "Conviene programar el riego para las horas más calientes.")
            else:
                st.write(f"Relación directa {fuerza}: temperatura y humedad del suelo suben juntas en este periodo.")
    else:
        st.info("Se necesitan más lecturas (y que varíen) para calcular la correlación.")

# --- Recomendaciones ---
st.subheader("Recomendaciones para la operación")
recomendaciones = []
if "temperatura" in presentes:
    s = datos["temperatura"].dropna()
    calor = (s > VARIABLES["temperatura"]["max"]).mean() * 100
    if calor > 0:
        recomendaciones.append(f"La temperatura superó el máximo el **{calor:.0f} %** del tiempo: "
                               "el ventilador debió estar encendido en esos periodos.")
if "humedad_suelo" in presentes:
    s = datos["humedad_suelo"].dropna()
    seco = (s < VARIABLES["humedad_suelo"]["min"]).mean() * 100
    if seco > 0:
        recomendaciones.append(f"El suelo estuvo seco el **{seco:.0f} %** del tiempo: revisa la frecuencia de riego.")
if not recomendaciones:
    recomendaciones.append("El invernadero operó dentro de los rangos definidos. No se requieren acciones.")
for texto in recomendaciones:
    st.markdown(f"- {texto}")

with st.expander("Ver datos cargados"):
    st.dataframe(datos, hide_index=True, width="stretch")

