"""Nevera Inteligente — app principal (multipágina con st.navigation)."""
import streamlit as st

from estilo import aplicar_estilo

st.set_page_config(page_title="Nevera Inteligente", page_icon="🧊", layout="wide")
aplicar_estilo()

paginas = st.navigation([
    st.Page("paginas/inicio.py", title="Inicio", icon="🏠", default=True),
    st.Page("paginas/monitoreo.py", title="Monitoreo de la nevera", icon="🌡️"),
    st.Page("paginas/despensa.py", title="Despensa inteligente", icon="🥕"),
])
paginas.run()
