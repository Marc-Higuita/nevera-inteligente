"""Ambiente 1: monitoreo y control de la nevera (botones, slider, texto)."""
import time

import pandas as pd
import streamlit as st

from estilo import encabezado
from mqtt_utils import enviar_orden, leer_estado

encabezado("🌡️ Monitoreo de la nevera", "Datos en vivo del ESP32 y control remoto del enfriamiento")


def avisar(orden, texto):
    if enviar_orden(orden):
        st.toast(f"✅ {texto}")
    else:
        st.toast("⚠️ No se pudo enviar. ¿Está conectado el broker?")


# ---------- Datos en vivo (se refrescan solos cada 2 s) ----------
@st.fragment(run_every=2)
def panel_en_vivo():
    estado = leer_estado()
    d = estado.ultimo

    if d is None:
        st.info(
            "Esperando datos de la nevera… Inicia la simulación en Wokwi "
            "(botón ▶) y espera a que diga *conectado*."
        )
        return

    segundos = time.time() - estado.ultima_hora
    if segundos > 10:
        st.warning(f"Último dato hace {segundos:.0f} s. ¿Sigue corriendo Wokwi?")

    if d.get("alarma"):
        st.error(f"🚨 ALARMA: {d.get('motivo', '')}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperatura", f"{d['temp']:.1f} °C",
              delta=f"máx. {d['umbral']:.1f} °C", delta_color="off")
    c2.metric("Humedad", f"{d['hum']:.0f} %")
    c3.metric("Puerta", "ABIERTA 🔓" if d["puerta"] else "Cerrada 🔒",
              delta=f"{d['seg_abierta']} s abierta" if d["puerta"] else None,
              delta_color="inverse")
    c4.metric("Enfriamiento", "Encendido ❄️" if d["compresor"] else "Apagado",
              delta="automático" if d["modo_auto"] else "manual", delta_color="off")

    if estado.historial:
        df = pd.DataFrame(list(estado.historial)).set_index("hora")
        st.line_chart(df)


panel_en_vivo()

st.divider()

# ---------- Controles (Streamlit -> ESP32) ----------
st.subheader("🎛️ Controles")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Enfriamiento**")
    modo = st.radio("Modo", ["Automático", "Manual"], horizontal=True)
    if modo == "Automático":
        if st.button("Activar modo automático", use_container_width=True):
            avisar("MODO_AUTO", "Modo automático activado")
    else:
        b1, b2 = st.columns(2)
        if b1.button("❄️ Encender", use_container_width=True):
            avisar("COMPRESOR_ON", "Enfriamiento encendido")
        if b2.button("⏹️ Apagar", use_container_width=True):
            avisar("COMPRESOR_OFF", "Enfriamiento apagado")

with col2:
    st.markdown("**Temperatura máxima**")
    umbral = st.slider("Alarma si supera (°C)", 1.0, 10.0, 5.0, 0.5)
    if st.button("Enviar temperatura máxima", use_container_width=True):
        avisar(f"UMBRAL:{umbral}", f"Temperatura máxima: {umbral} °C")

with col3:
    st.markdown("**Alarma**")
    if st.button("🔕 Silenciar alarma", use_container_width=True):
        avisar("SILENCIAR", "Alarma silenciada")
    if st.button("🔔 Probar buzzer", use_container_width=True):
        avisar("PROBAR_ALARMA", "Probando buzzer")

st.subheader("💬 Mensaje para la pantalla de la nevera")
with st.form("mensaje", clear_on_submit=True):
    texto = st.text_input("Escribe un mensaje (máx. 32 letras)", max_chars=32,
                          placeholder="Ej: Hay pastel, no tocar!")
    if st.form_submit_button("Enviar a la LCD") and texto:
        avisar(f"MENSAJE:{texto}", "Mensaje enviado a la LCD")
