import streamlit as st

from estilo import AZUL, AZUL_SUAVE, VERDE, barra_superior, encabezado, html, ic
from mqtt_utils import BROKER, leer_estado

estado_mqtt = leer_estado()
barra_superior(estado_mqtt.conectado)
encabezado("Nevera Inteligente",
           "Monitoreo de temperatura, control remoto y gestión de alimentos mediante sensores, cámara y voz.",
           "kitchen")

col1, col2 = st.columns(2, gap="medium")
with col1:
    html(f"""
    <div class="card">
      <div class="titulo"><span class="icono-circ" style="background:{AZUL_SUAVE};color:{AZUL}">{ic('thermostat')}</span>Monitoreo</div>
      <div class="etiqueta">Temperatura y humedad en tiempo real, detección de puerta abierta,
      alarmas y control del enfriamiento desde la aplicación.</div>
      <div class="chips">
        <span class="chip">{ic('touch_app', 16)}Botones</span>
        <span class="chip">{ic('tune', 16)}Controles deslizantes</span>
        <span class="chip">{ic('monitoring', 16)}Gráfica en vivo</span>
        <span class="chip">{ic('notifications_active', 16)}Alertas</span>
      </div>
    </div>""")
    st.page_link("paginas/monitoreo.py", label="Abrir monitoreo", icon=":material/arrow_forward:")
with col2:
    html(f"""
    <div class="card">
      <div class="titulo"><span class="icono-circ" style="background:#E7F7EF;color:{VERDE}">{ic('shopping_basket')}</span>Despensa</div>
      <div class="etiqueta">Reconocimiento de alimentos con la cámara, comandos de voz,
      respuestas habladas y seguimiento de la vida útil de cada producto.</div>
      <div class="chips">
        <span class="chip">{ic('photo_camera', 16)}Cámara con IA</span>
        <span class="chip">{ic('mic', 16)}Voz</span>
        <span class="chip">{ic('volume_up', 16)}Respuesta hablada</span>
        <span class="chip">{ic('event_available', 16)}Vencimientos</span>
      </div>
    </div>""")
    st.page_link("paginas/despensa.py", label="Abrir despensa", icon=":material/arrow_forward:")

st.write("")
c1, c2, c3 = st.columns(3, gap="medium")
pasos = [
    (c1, "sensors", "Captura", "El ESP32 mide temperatura, humedad y el estado de la puerta."),
    (c2, "sync_alt", "Comunicación", "Los datos y las órdenes viajan en ambos sentidos por MQTT."),
    (c3, "settings_remote", "Acción", "Enfriamiento, alarma sonora y mensajes en la pantalla LCD."),
]
for col, icono, titulo, texto in pasos:
    with col:
        html(f"""
        <div class="card">
          <div class="titulo"><span class="icono-circ" style="background:#F1F4FA;color:#14161F">{ic(icono)}</span>{titulo}</div>
          <div class="etiqueta">{texto}</div>
        </div>""")

st.caption(f"Broker MQTT: {BROKER}")
