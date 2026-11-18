"""Sistema visual de la app: tipografía, íconos (Material Symbols) y componentes."""
import math

import streamlit as st

AZUL = "#2F6BFF"
AZUL_SUAVE = "#E8EFFF"
VERDE = "#1FA971"
AMBAR = "#E9A23B"
ROJO = "#E5484D"
TINTA = "#14161F"
GRIS = "#6B7185"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..600,0..1,0&display=block');

html, body, .stApp, .stMarkdown, button, input, textarea { font-family: 'Plus Jakarta Sans', sans-serif !important; }
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #DCE6FF 0%, transparent 60%),
                     radial-gradient(900px 500px at 110% 10%, #EDE7FF 0%, transparent 55%), #F3F5FA; }
.block-container { padding-top: 4.2rem; max-width: 1180px; }
[data-testid="stToolbarActions"], footer { display: none !important; }
h1, h2, h3, h4 { color: #14161F; letter-spacing: -0.02em; }

.ic { font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal;
      line-height: 1; display: inline-block; vertical-align: middle;
      font-variation-settings: 'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24; }

/* Barra superior */
.topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:1.2rem; }
.topbar .marca { display:flex; align-items:center; gap:.7rem; }
.topbar .logo { width:44px; height:44px; border-radius:14px; background:#14161F; color:white;
                display:flex; align-items:center; justify-content:center; font-size:24px; }
.topbar .t1 { font-weight:800; font-size:1.05rem; color:#14161F; }
.topbar .t2 { font-size:.82rem; color:#6B7185; }
.pill { display:inline-flex; align-items:center; gap:.4rem; padding:.42rem .85rem; border-radius:999px;
        font-size:.8rem; font-weight:600; background:white; border:1px solid #E3E7F0; color:#14161F; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }

/* Encabezado de página */
.hero { background: linear-gradient(135deg, #2F6BFF 0%, #5B8CFF 100%); color:white; border-radius:28px;
        padding:1.8rem 2rem; margin-bottom:1.4rem; box-shadow:0 18px 40px rgba(47,107,255,.25);
        display:flex; justify-content:space-between; align-items:center; gap:1rem; }
.hero h1 { color:white !important; font-weight:800; font-size:2rem; margin:0; padding:0; }
.hero p { color:#E7EEFF; margin:.35rem 0 0; font-size:1rem; }
.hero .ic { font-size:64px; opacity:.9; }

/* Tarjetas */
.card { background:white; border-radius:26px; padding:1.3rem 1.4rem; border:1px solid #EAEDF4;
        box-shadow:0 10px 30px rgba(20,22,31,.06); height:100%; }
.card .titulo { display:flex; align-items:center; gap:.55rem; font-weight:700; color:#14161F; margin-bottom:.6rem; }
.icono-circ { width:42px; height:42px; border-radius:50%; display:inline-flex; align-items:center;
              justify-content:center; font-size:22px; }
.etiqueta { color:#6B7185; font-size:.82rem; font-weight:500; }
.valor { color:#14161F; font-size:1.55rem; font-weight:800; letter-spacing:-.02em; }
.estado { display:inline-flex; align-items:center; gap:.35rem; padding:.28rem .7rem; border-radius:999px;
          font-size:.76rem; font-weight:700; }
.anillo { display:flex; flex-direction:column; align-items:center; }
.anillo .num { font-size:2.1rem; font-weight:800; fill:#14161F; }
.anillo .uni { font-size:.8rem; fill:#6B7185; font-weight:600; }

.alerta { display:flex; gap:.8rem; align-items:center; background:#FFF1F1; border:1px solid #FFD5D6;
          color:#B4232A; border-radius:20px; padding:.9rem 1.1rem; margin-bottom:1rem; font-weight:600; }
.alerta .ic { font-size:26px; }

.chips { margin-top:.7rem; }
.chip { display:inline-flex; align-items:center; gap:.3rem; background:#F1F4FA; color:#3A4058;
        border-radius:999px; padding:.3rem .7rem; margin:.15rem .2rem .15rem 0; font-size:.78rem; font-weight:600; }
.chip .ic { font-size:16px; }

/* Inventario tipo cuadrícula */
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:14px; }
.tile { background:white; border-radius:24px; padding:1rem; border:1px solid #EAEDF4; text-align:center;
        box-shadow:0 8px 22px rgba(20,22,31,.05); }
.tile .ic { font-size:40px; }
.tile .nom { font-weight:700; margin-top:.4rem; color:#14161F; }
.tile .sub { font-size:.75rem; color:#6B7185; margin:.15rem 0 .5rem; }

/* Widgets de Streamlit */
.stButton button, .stFormSubmitButton button { border-radius:999px; font-weight:600; padding:.5rem 1.1rem;
        border:1px solid #E3E7F0; }
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] { background:#14161F; border-color:#14161F; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:26px !important; background:white;
        border-color:#EAEDF4 !important; box-shadow:0 10px 30px rgba(20,22,31,.06); }
.stTabs [data-baseweb="tab-list"] { gap:.4rem; }
.stTabs [data-baseweb="tab"] { background:white; border-radius:999px; padding:.45rem 1rem; font-weight:600;
        border:1px solid #E3E7F0; }
.stTabs [aria-selected="true"] { background:#14161F; color:white; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }
[data-testid="stCameraInput"], [data-testid="stAudioInput"] { border-radius:22px; overflow:hidden; }
</style>
"""


def html(contenido: str):
    """Muestra HTML sin sangrías (Markdown convierte las sangrías en bloques de código)."""
    limpio = " ".join(linea.strip() for linea in contenido.splitlines() if linea.strip())
    st.markdown(limpio, unsafe_allow_html=True)


def ic(nombre: str, tam: int = 22, color: str = "inherit") -> str:
    return f'<span class="ic" style="font-size:{tam}px;color:{color}">{nombre}</span>'


def aplicar_estilo():
    st.markdown(CSS, unsafe_allow_html=True)


def barra_superior(conectado: bool):
    color = VERDE if conectado else "#A0A6B8"
    texto = "Nevera en línea" if conectado else "Sin conexión"
    html(f"""
    <div class="topbar">
      <div class="marca">
        <div class="logo">{ic('kitchen', 24, 'white')}</div>
        <div><div class="t1">Nevera Inteligente</div><div class="t2">Sistema IoT de monitoreo y despensa</div></div>
      </div>
      <span class="pill"><span class="dot" style="background:{color}"></span>{texto}</span>
    </div>""")


def encabezado(titulo: str, subtitulo: str, icono: str):
    html(f"""
    <div class="hero">
      <div><h1>{titulo}</h1><p>{subtitulo}</p></div>
      {ic(icono, 64, 'white')}
    </div>""")


def anillo(valor, minimo, maximo, unidad, etiqueta, color=AZUL):
    """Indicador circular estilo termostato."""
    r = 62
    circ = 2 * math.pi * r
    frac = 0.0 if valor is None else max(0.0, min(1.0, (valor - minimo) / (maximo - minimo)))
    arco = circ * 0.75                     # el anillo ocupa 3/4 de vuelta
    lleno = arco * frac
    texto = "—" if valor is None else f"{valor:.1f}"
    return f"""
    <div class="anillo">
      <svg width="170" height="160" viewBox="0 0 170 160">
        <g transform="rotate(135 85 85)">
          <circle cx="85" cy="85" r="{r}" fill="none" stroke="#EEF1F7" stroke-width="14"
            stroke-linecap="round" stroke-dasharray="{arco:.1f} {circ:.1f}"/>
          <circle cx="85" cy="85" r="{r}" fill="none" stroke="{color}" stroke-width="14"
            stroke-linecap="round" stroke-dasharray="{lleno:.1f} {circ:.1f}"/>
        </g>
        <text x="85" y="88" text-anchor="middle" class="num">{texto}</text>
        <text x="85" y="112" text-anchor="middle" class="uni">{unidad}</text>
      </svg>
      <div class="etiqueta" style="margin-top:-12px">{etiqueta}</div>
    </div>"""


def estado(texto: str, color: str, fondo: str) -> str:
    return f'<span class="estado" style="color:{color};background:{fondo}">{texto}</span>'
