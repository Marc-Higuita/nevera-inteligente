"""Ambiente 1: monitoreo y control de la nevera."""
import time

import pandas as pd
import streamlit as st

from estilo import (AMBAR, AZUL, AZUL_SUAVE, GRIS, ROJO, VERDE, anillo, barra_superior,
                    encabezado, estado, html, ic)
from mqtt_utils import enviar_orden, leer_estado

barra_superior(leer_estado().conectado)
encabezado("Monitoreo", "Estado de la nevera en tiempo real y control remoto del enfriamiento.", "thermostat")


def ordenar(orden: str, texto: str):
    if enviar_orden(orden):
        st.toast(texto, icon=":material/check_circle:")
    else:
        st.toast("No fue posible enviar la orden. Verifica la conexión.", icon=":material/error:")


# ---------- Datos en vivo (se actualizan cada 2 s) ----------
@st.fragment(run_every=2)
def panel_en_vivo():
    est = leer_estado()
    d = est.ultimo

    if d is None:
        html(f"""
        <div class="card" style="text-align:center;padding:2.2rem">
          {ic('sensors_off', 44, GRIS)}
          <div class="valor" style="font-size:1.2rem;margin-top:.6rem">Esperando datos de la nevera</div>
          <div class="etiqueta">Inicia la simulación en Wokwi. Los datos aparecerán aquí automáticamente.</div>
        </div>""")
        return

    if time.time() - est.ultima_hora > 10:
        st.warning(f"Último dato recibido hace {time.time() - est.ultima_hora:.0f} s.",
                   icon=":material/schedule:")

    if d.get("alarma"):
        silencio = " · Alarma silenciada" if d.get("silenciada") else ""
        html(f'<div class="alerta">{ic("warning")}<div>{d.get("motivo", "Alarma activa")}{silencio}</div></div>')

    temp_color = ROJO if d["temp"] > d["umbral"] else AZUL
    c1, c2, c3, c4 = st.columns([1.15, 1.15, 1, 1], gap="medium")
    etiqueta_temp = "Temperatura · máx. %.1f °C" % d["umbral"]
    with c1:
        html(f'<div class="card">{anillo(d["temp"], -5, 15, "°C", etiqueta_temp, temp_color)}</div>')
    with c2:
        html(f'<div class="card">{anillo(d["hum"], 0, 100, "%", "Humedad relativa", "#7C5CFF")}</div>')
    with c3:
        if d["puerta"]:
            chip = estado("Abierta", "#B4232A", "#FFF1F1")
            detalle = f'{d["seg_abierta"]} s abierta'
            icono, color, fondo = "door_open", ROJO, "#FFF1F1"
        else:
            chip = estado("Cerrada", "#11804F", "#E7F7EF")
            detalle = "Sellado correcto"
            icono, color, fondo = "door_front", VERDE, "#E7F7EF"
        html(f"""
        <div class="card">
          <span class="icono-circ" style="background:{fondo};color:{color};width:54px;height:54px">{ic(icono, 28)}</span>
          <div class="etiqueta" style="margin-top:1rem">Puerta</div>
          <div class="valor">{detalle}</div>
          <div style="margin-top:.6rem">{chip}</div>
        </div>""")
    with c4:
        if d["compresor"]:
            chip = estado("Encendido", AZUL, AZUL_SUAVE)
            icono_color, fondo = AZUL, AZUL_SUAVE
        else:
            chip = estado("Apagado", GRIS, "#F1F4FA")
            icono_color, fondo = GRIS, "#F1F4FA"
        modo = "Automático" if d["modo_auto"] else "Manual"
        html(f"""
        <div class="card">
          <span class="icono-circ" style="background:{fondo};color:{icono_color};width:54px;height:54px">{ic('ac_unit', 28)}</span>
          <div class="etiqueta" style="margin-top:1rem">Enfriamiento</div>
          <div class="valor">Modo {modo.lower()}</div>
          <div style="margin-top:.6rem">{chip}</div>
        </div>""")

    if est.historial:
        st.write("")
        with st.container(border=True):
            st.markdown("**:material/monitoring: Historial reciente**")
            df = pd.DataFrame(list(est.historial)).set_index("hora")
            st.line_chart(df, color=[AZUL, "#7C5CFF"], height=240)


panel_en_vivo()

# ---------- Controles (Streamlit -> ESP32) ----------
st.write("")
st.markdown("#### Controles")
col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    with st.container(border=True):
        st.markdown("**:material/ac_unit: Enfriamiento**")
        modo = st.segmented_control("Modo de operación", ["Automático", "Manual"], default="Automático")
        if modo == "Manual":
            b1, b2 = st.columns(2)
            if b1.button("Encender", icon=":material/power_settings_new:", type="primary",
                         use_container_width=True):
                ordenar("COMPRESOR_ON", "Enfriamiento encendido")
            if b2.button("Apagar", icon=":material/power_off:", use_container_width=True):
                ordenar("COMPRESOR_OFF", "Enfriamiento apagado")
        elif st.button("Aplicar modo automático", icon=":material/autorenew:", type="primary",
                       use_container_width=True):
            ordenar("MODO_AUTO", "Modo automático activado")

with col2:
    with st.container(border=True):
        st.markdown("**:material/device_thermostat: Temperatura máxima**")
        umbral = st.slider("Se activa la alarma por encima de", 1.0, 10.0, 5.0, 0.5, format="%.1f °C")
        if st.button("Guardar límite", icon=":material/save:", type="primary", use_container_width=True):
            ordenar(f"UMBRAL:{umbral}", f"Límite actualizado a {umbral:.1f} °C")

with col3:
    with st.container(border=True):
        st.markdown("**:material/notifications: Alarma**")
        if st.button("Silenciar alarma", icon=":material/notifications_off:", type="primary",
                     use_container_width=True):
            ordenar("SILENCIAR", "Alarma silenciada")
        if st.button("Probar alarma sonora", icon=":material/volume_up:", use_container_width=True):
            ordenar("PROBAR_ALARMA", "Prueba de alarma enviada")

with st.container(border=True):
    st.markdown("**:material/chat: Mensaje en la pantalla de la nevera**")
    with st.form("mensaje", clear_on_submit=True, border=False):
        a, b = st.columns([4, 1], vertical_alignment="bottom")
        texto = a.text_input("Texto (máximo 32 caracteres)", max_chars=32,
                             placeholder="Ejemplo: Revisar fecha de la leche")
        if b.form_submit_button("Enviar", icon=":material/send:", type="primary",
                                use_container_width=True) and texto:
            ordenar(f"MENSAJE:{texto}", "Mensaje enviado a la pantalla")
