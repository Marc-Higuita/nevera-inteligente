"""Ambiente 1: monitoreo y control de la nevera."""
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

from estilo import (AMBAR, AZUL, AZUL_SUAVE, GRIS, ROJO, VERDE, anillo, barra_superior,
                    encabezado, estado, html, ic, sonido)
from mqtt_utils import (BROKER_WS, NTFY_TEMA, PERDIDA_PUERTA_WH_MIN, POTENCIA_COMPRESOR_W, TARIFA_COP_KWH,
                        TOPIC_CMD, TOPIC_DATOS, energia_hoy, enviar_alerta, enviar_orden, leer_estado)

barra_superior(leer_estado().conectado)
encabezado("Monitoreo", "Estado de la nevera en tiempo real y control remoto del enfriamiento.", "thermostat")

pasos = [("tune", "1. Fija el objetivo", "Con gestos, con los botones del termostato o por voz."),
         ("memory", "2. El ESP32 decide", "Si la nevera está más caliente que el objetivo, enciende el compresor."),
         ("trending_down", "3. La temperatura cambia", "Baja poco a poco al enfriar; sube si la puerta queda abierta.")]
html('<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:1rem">' + "".join(
    f'<div class="card" style="padding:.9rem 1rem;display:flex;gap:.7rem;align-items:center">'
    f'<span class="icono-circ" style="background:#E8EFFF;color:{AZUL};width:40px;height:40px">{ic(i, 20)}</span>'
    f'<div><div style="font-weight:700;font-size:.92rem">{t}</div><div class="etiqueta">{x}</div></div></div>'
    for i, t, x in pasos) + "</div>")


def ordenar(orden: str, texto: str):
    if enviar_orden(orden):
        st.toast(texto, icon=":material/check_circle:")
        sonido("confirmar")
    else:
        sonido("error")
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

    # Sirena en la página cuando la alarma se activa (una vez por evento)
    if d.get("alarma") and not d.get("silenciada"):
        if not st.session_state.get("sirena_sonada"):
            st.session_state["sirena_sonada"] = True
            sonido("alarma")
    else:
        st.session_state["sirena_sonada"] = False

    if d.get("alarma"):
        silencio = " · Alarma silenciada" if d.get("silenciada") else ""
        html(f'<div class="alerta">{ic("warning")}<div>{d.get("motivo", "Alarma activa")}{silencio}</div></div>')

    # Estado explicado en palabras
    obj = d.get("objetivo", 4.0)
    previo = est.historial[-2]["Temperatura interior (°C)"] if len(est.historial) > 1 else d["temp"]
    tendencia = "bajando" if d["temp"] < previo - 0.01 else ("subiendo" if d["temp"] > previo + 0.01 else "estable")
    if d["puerta"]:
        icono, color, fondo = "door_open", "#B4232A", "#FFF1F1"
        texto = f"Puerta abierta: está entrando calor de la cocina ({d['temp']:.1f} °C, {tendencia})"
    elif d["compresor"]:
        icono, color, fondo = "ac_unit", AZUL, AZUL_SUAVE
        texto = f"Enfriando: {d['temp']:.1f} °C → objetivo {obj:.0f} °C"
    elif d["temp"] < obj - 0.3:
        icono, color, fondo = "pause_circle", "#11804F", "#E7F7EF"
        texto = f"Por debajo del objetivo: el compresor descansa y la temperatura sube despacio ({d['temp']:.1f} °C)"
    else:
        icono, color, fondo = "check_circle", "#11804F", "#E7F7EF"
        texto = f"Estable en el objetivo de {obj:.0f} °C"
    flecha = {"bajando": "trending_down", "subiendo": "trending_up", "estable": "trending_flat"}[tendencia]
    html(f"""
    <div class="card" style="display:flex;align-items:center;gap:.9rem;padding:.9rem 1.2rem;margin-bottom:1rem;
         background:{fondo};border-color:{fondo}">
      <span class="icono-circ" style="background:white;color:{color};width:44px;height:44px">{ic(icono, 24)}</span>
      <div style="flex:1;font-weight:700;color:{color}">{texto}</div>
      <span class="pill">{ic(flecha, 18, color)} Temperatura {tendencia}</span>
      <span class="pill">{ic('countertops', 18)} Cocina {d.get('ambiente', 0):.1f} °C</span>
    </div>""")

    temp_color = ROJO if d.get("alarma") else AZUL
    c1, c2, c3, c4 = st.columns([1.15, 1.15, 1, 1], gap="medium")
    etiqueta_temp = "Objetivo %.0f °C · máx. %.1f °C" % (d.get("objetivo", 4), d["umbral"])
    with c1:
        html(f'<div class="card">{anillo(d["temp"], -2, 12, "°C interior", etiqueta_temp, temp_color)}</div>')
    with c2:
        html(f'<div class="card">{anillo(d["hum"], 0, 100, "%", "Humedad de la cocina", "#7C5CFF")}</div>')
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

    # Energía del día
    min_puerta, min_comp, wh, pesos = energia_hoy()
    st.write("")
    e1, e2, e3 = st.columns(3, gap="medium")
    tarjetas = [
        (e1, "door_open", "#FFF1F1", ROJO, "Puerta abierta hoy", f"{min_puerta:.1f} min"),
        (e2, "ac_unit", AZUL_SUAVE, AZUL, "Enfriamiento encendido hoy", f"{min_comp:.1f} min"),
        (e3, "bolt", "#FFF4E0", AMBAR, "Energía estimada hoy", f"{wh:.1f} Wh · ${pesos:,.0f} COP".replace(",", ".")),
    ]
    for col, icono, fondo, color, etiqueta, valor in tarjetas:
        with col:
            html(f"""
            <div class="card" style="display:flex;gap:.9rem;align-items:center;padding:1rem 1.2rem">
              <span class="icono-circ" style="background:{fondo};color:{color};width:48px;height:48px">{ic(icono, 24)}</span>
              <div><div class="etiqueta">{etiqueta}</div><div class="valor" style="font-size:1.25rem">{valor}</div></div>
            </div>""")

    if est.historial:
        st.write("")
        with st.container(border=True):
            st.markdown("**:material/monitoring: Historial reciente**")
            df = pd.DataFrame(list(est.historial)).set_index("hora")
            st.line_chart(df, color=[AZUL, "#E9A23B"], height=240)


panel_en_vivo()

# ---------- Controles (Streamlit -> ESP32) ----------
st.write("")
st.markdown("#### Controles")
col0, col1, col2, col3 = st.columns(4, gap="small")

with col0:
    with st.container(border=True):
        st.markdown("**:material/thermostat: Termostato**")
        actual = (leer_estado().ultimo or {}).get("objetivo", 4.0)
        st.markdown(f"<div style='font-size:2.2rem;font-weight:800;text-align:center;margin:.2rem 0'>"
                    f"{actual:.0f} °C</div><div class='etiqueta' style='text-align:center;margin-bottom:.6rem'>"
                    f"Temperatura objetivo</div>", unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("", icon=":material/remove:", key="obj_menos", use_container_width=True,
                     help="Bajar 1 °C"):
            ordenar("OBJETIVO_MENOS", "Objetivo: 1 °C menos")
        if b2.button("", icon=":material/add:", key="obj_mas", use_container_width=True, help="Subir 1 °C"):
            ordenar("OBJETIVO_MAS", "Objetivo: 1 °C más")

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


with st.popover("Cómo se calcula la energía", icon=":material/info:"):
    st.markdown(
        f"- Enfriamiento: **{POTENCIA_COMPRESOR_W} W** mientras el compresor está encendido.\n"
        f"- Puerta abierta: **{PERDIDA_PUERTA_WH_MIN} Wh** extra por cada minuto, por la entrada de aire caliente.\n"
        f"- Tarifa: **${TARIFA_COP_KWH} COP por kWh** (valor residencial aproximado).\n\n"
        "Son estimaciones para mostrar el impacto de dejar la puerta abierta; los contadores se reinician cada día."
    )

# ---------- Control por gestos ----------
st.write("")
st.markdown("#### Control por gestos")
st.caption("Usa la mano como termostato: pulgar arriba o abajo cambia la temperatura objetivo. Sostén cada gesto un segundo.")


def html_gestos():
    ruta = Path(__file__).resolve().parent.parent / "componentes" / "gestos.html"
    return (ruta.read_text(encoding="utf-8").replace("__TOPIC_CMD__", TOPIC_CMD)
            .replace("__TOPIC_DATOS__", TOPIC_DATOS).replace("__BROKER_WS__", BROKER_WS))


components.html(html_gestos(), height=620, scrolling=False)

# ---------- Alertas al celular ----------
st.write("")
st.markdown("#### Alertas al celular")
with st.container(border=True):
    a1, a2 = st.columns([1, 1.6], gap="large", vertical_alignment="center")
    url_tema = f"https://ntfy.sh/{NTFY_TEMA}"
    with a1:
        st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=8&data={url_tema}", width=200)
    with a2:
        st.markdown(
            "Cuando la puerta queda abierta o la temperatura supera el límite, la nevera envía una "
            "**notificación push** a tu celular.\n\n"
            "1. Instala la app **ntfy** (Android o iPhone), o abre el enlace del código QR.\n"
            f"2. Suscríbete al tema **`{NTFY_TEMA}`**.\n"
            "3. Listo: las alertas llegan aunque la app no esté abierta."
        )
        if st.button("Enviar notificación de prueba", icon=":material/notifications_active:", type="primary"):
            enviar_alerta("Nevera Inteligente", "Notificación de prueba: las alertas están configuradas.",
                          leer_estado(), prioridad="default")
            st.toast("Notificación enviada", icon=":material/check_circle:")
    alertas = list(leer_estado().alertas)
    if alertas:
        st.caption("Últimas notificaciones: " + " · ".join(
            f"{a['hora']} {'enviada' if a['ok'] else 'falló'}" for a in alertas[:4]))
