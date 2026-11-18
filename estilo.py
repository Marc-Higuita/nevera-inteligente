"""Estilo visual compartido: tipografía, tarjetas y encabezados."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button { font-family: 'Inter', sans-serif; }

.block-container { padding-top: 2rem; max-width: 1200px; }

.hero {
  background: linear-gradient(135deg, #0E7C86 0%, #12A4B0 55%, #7FD6DC 100%);
  color: white; border-radius: 22px; padding: 2rem 2.2rem; margin-bottom: 1.4rem;
  box-shadow: 0 10px 30px rgba(14,124,134,.25);
}
.hero h1 { color: white; font-weight: 800; margin: 0; font-size: 2.3rem; }
.hero p  { color: #E9FBFC; margin: .4rem 0 0; font-size: 1.05rem; }

.tarjeta {
  background: white; border-radius: 18px; padding: 1.3rem 1.4rem;
  border: 1px solid #DCEBED; box-shadow: 0 4px 14px rgba(22,50,58,.06); height: 100%;
}
.tarjeta h3 { margin-top: 0; }
.chip {
  display: inline-block; background: #E6F2F3; color: #0E7C86; border-radius: 999px;
  padding: .2rem .7rem; margin: .15rem; font-size: .82rem; font-weight: 600;
}

div[data-testid="stMetric"] {
  background: white; border: 1px solid #DCEBED; border-radius: 16px;
  padding: 1rem 1.1rem; box-shadow: 0 4px 14px rgba(22,50,58,.06);
}
.stButton button { border-radius: 12px; font-weight: 600; }
.stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 1rem; }
</style>
"""


def aplicar_estilo():
    st.markdown(CSS, unsafe_allow_html=True)


def encabezado(titulo: str, subtitulo: str):
    st.markdown(f'<div class="hero"><h1>{titulo}</h1><p>{subtitulo}</p></div>',
                unsafe_allow_html=True)
