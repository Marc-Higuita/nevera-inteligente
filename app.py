"""Nevera Inteligente — app principal (multipágina con st.navigation)."""
import streamlit as st

from estilo import aplicar_estilo
from mqtt_utils import WOKWI_URL

st.set_page_config(page_title="Nevera Inteligente", page_icon=":material/kitchen:", layout="wide",
                   initial_sidebar_state="expanded")
aplicar_estilo()

# La simulación de Wokwi vive en el panel lateral: queda visible en todas las páginas,
# así nunca se pausa (Wokwi se detiene cuando su pestaña no está a la vista).
with st.sidebar:
    st.markdown("#### :material/memory: Nevera física (Wokwi)")
    st.caption("1. Pulsa ▶ y espera a que la pantalla muestre la temperatura.  \n"
               "2. Usa la app: los cambios se ven aquí en la pantalla LCD y en los LED.  \n"
               "3. Clic en el sensor DHT22 para cambiar la temperatura de la cocina; "
               "el interruptor es la puerta.")
    st.components.v1.iframe(WOKWI_URL, height=640, scrolling=False)
    st.caption("Usa solo esta simulación: si Wokwi está abierto en otra pestaña, ciérralo.")

paginas = st.navigation(
    [
        st.Page("paginas/inicio.py", title="Inicio", icon=":material/home:", default=True),
        st.Page("paginas/monitoreo.py", title="Monitoreo", icon=":material/thermostat:"),
        st.Page("paginas/despensa.py", title="Despensa", icon=":material/shopping_basket:"),
    ],
    position="top",
)
paginas.run()
