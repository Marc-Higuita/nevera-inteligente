import streamlit as st

from estilo import encabezado
from mqtt_utils import BROKER, leer_estado

encabezado("🧊 Nevera Inteligente",
           "Cuida tus alimentos con sensores, cámara y voz — ESP32 en Wokwi + Streamlit por MQTT")

st.markdown(
    "En muchas casas se pierde comida porque la nevera queda abierta, la temperatura sube "
    "sin que nadie lo note o se nos olvida qué hay adentro hasta que se vence. "
    "Esta app conecta una **nevera simulada** con dos ambientes de interacción:"
)

col1, col2 = st.columns(2, gap="large")
with col1:
    st.markdown(
        """<div class="tarjeta">
<h3>🌡️ Monitoreo de la nevera</h3>
<p>Temperatura y humedad en vivo, aviso de puerta abierta y control del enfriamiento.</p>
<span class="chip">Botones</span><span class="chip">Slider</span>
<span class="chip">Texto a la LCD</span><span class="chip">Gráfica en vivo</span>
</div>""",
        unsafe_allow_html=True,
    )
    st.page_link("paginas/monitoreo.py", label="Abrir monitoreo →", icon="🌡️")
with col2:
    st.markdown(
        """<div class="tarjeta">
<h3>🥕 Despensa inteligente</h3>
<p>La cámara reconoce el alimento, la voz lo agrega y la app te avisa qué consumir primero.</p>
<span class="chip">Cámara + IA</span><span class="chip">Voz</span>
<span class="chip">Respuesta hablada</span><span class="chip">Vencimientos</span>
</div>""",
        unsafe_allow_html=True,
    )
    st.page_link("paginas/despensa.py", label="Abrir despensa →", icon="🥕")

st.write("")
st.markdown("#### ¿Cómo funciona?")
c1, c2, c3 = st.columns(3)
c1.markdown("**1. Sensa** \nEl ESP32 mide temperatura, humedad y el estado de la puerta.")
c2.markdown("**2. Comunica** \nLos datos viajan por MQTT a esta app, y las órdenes vuelven a la nevera.")
c3.markdown("**3. Actúa** \nEnfriamiento, alarma, buzzer y mensajes en la pantalla LCD.")

st.divider()
estado = leer_estado()
if estado.conectado:
    st.success(f"🟢 Conectado al broker MQTT `{BROKER}`")
else:
    st.warning(f"🟡 Conectando al broker MQTT `{BROKER}`… recarga en unos segundos.")
