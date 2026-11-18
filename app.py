"""Nevera Inteligente — app principal (multipágina con st.navigation)."""
import streamlit as st

from estilo import aplicar_estilo

st.set_page_config(page_title="Nevera Inteligente", page_icon=":material/kitchen:", layout="wide")
aplicar_estilo()

paginas = st.navigation(
    [
        st.Page("paginas/inicio.py", title="Inicio", icon=":material/home:", default=True),
        st.Page("paginas/monitoreo.py", title="Monitoreo", icon=":material/thermostat:"),
        st.Page("paginas/despensa.py", title="Despensa", icon=":material/shopping_basket:"),
    ],
    position="top",
)
paginas.run()
