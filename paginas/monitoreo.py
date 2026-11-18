"""Ambiente 1: monitoreo y control de la nevera."""
import time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from estilo import (AMBAR, AZUL, AZUL_SUAVE, GRIS, ROJO, VERDE, anillo, barra_superior, encabezado, estado,
                    html, ic, lcd_virtual, sonido)
from mqtt_utils import (BROKER_WS, NTFY_TEMA, PERDIDA_PUERTA_WH_MIN, POTENCIA_COMPRESOR_W, TARIFA_COP_KWH,
                        TOPIC_CMD, TOPIC_DATOS, energia_hoy, enviar_alerta, enviar_orden, leer_estado)

barra_superior(leer_estado().conectado)
encabezado("Monitoreo", "Estado de la nevera en tiempo real y control remoto.", "thermostat")


def ordenar(orden: str, texto: str, con_sonido: bool = True):
    if enviar_orden(orden):
        st.toast(texto, icon=":material/check_circle:")
        if con_sonido:
            sonido("confirmar")
    else:
        st.toast("No fue posible enviar la orden. Verifica la conexión.", icon=":material/error:")
        if con_sonido:
            sonido("error")


def datos():
    return leer_estado().ultimo or {}


# =====================================================================
# 1. ESTADO EN VIVO (se actualiza cada 2 s)
# =====================================================================
@st.fragment(run_every=2)
def panel_en_vivo():
    est = leer_estado()
    d = est.ultimo

    if d is None:
        html(f"""
        <div class="card" style="text-align:center;padding:2.2rem">
          {ic('sensors_off', 44, GRIS)}
          <div class="valor" style="font-size:1.2rem;margin-top:.6rem">Esperando datos de la nevera</div>
          <div class="etiqueta">Pulsa ▶ en la simulación de Wokwi (panel izquierdo). Los datos aparecerán aquí.</div>
        </div>""")
        return

    if time.time() - est.ultima_hora > 10:
        st.warning(f"Último dato recibido hace {time.time() - est.ultima_hora:.0f} s. "
                   "Revisa que la simulación de Wokwi esté corriendo.", icon=":material/schedule:")

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
        texto = f"Puerta abierta: está entrando calor de la cocina ({d['temp']:.1f} °C)"
    elif d["compresor"]:
        icono, color, fondo = "ac_unit", AZUL, AZUL_SUAVE
        texto = f"Enfriando: {d['temp']:.1f} °C → objetivo {obj:.0f} °C"
    elif d["temp"] < obj - 0.3:
        icono, color, fondo = "pause_circle", "#11804F", "#E7F7EF"
        texto = f"Por debajo del objetivo: el compresor descansa ({d['temp']:.1f} °C)"
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
      <span class="pill">{ic('countertops', 18)} Cocina {d.get('ambiente', 0):.1f} °C · {d.get('hum', 0):.0f} %</span>
    </div>""")

    c1, c2, c3, c4 = st.columns([1.05, 1.5, .95, .95], gap="medium")
    with c1:
        etiqueta = "Objetivo %.0f °C · máx. %.1f °C" % (obj, d["umbral"])
        html(f'<div class="card">{anillo(d["temp"], -2, 12, "°C interior", etiqueta, ROJO if d.get("alarma") else AZUL)}</div>')
    with c2:
        html(f"""
        <div class="card">
          <div class="titulo">{ic('developer_board', 20)}Pantalla de la nevera</div>
          {lcd_virtual(d.get('lcd1', ''), d.get('lcd2', ''))}
          <div class="etiqueta" style="margin-top:.6rem">Réplica en vivo de la LCD 16x2 del ESP32.</div>
        </div>""")
    with c3:
        if d["puerta"]:
            chip, detalle = estado("Abierta", "#B4232A", "#FFF1F1"), f'{d["seg_abierta"]} s'
            icono, color, fondo = "door_open", ROJO, "#FFF1F1"
        else:
            chip, detalle = estado("Cerrada", "#11804F", "#E7F7EF"), "Sellada"
            icono, color, fondo = "door_front", VERDE, "#E7F7EF"
        html(f"""
        <div class="card">
          <span class="icono-circ" style="background:{fondo};color:{color};width:50px;height:50px">{ic(icono, 26)}</span>
          <div class="etiqueta" style="margin-top:.9rem">Puerta</div>
          <div class="valor">{detalle}</div>
          <div style="margin-top:.5rem">{chip}</div>
        </div>""")
    with c4:
        if d["compresor"]:
            chip, icono_color, fondo = estado("Encendido", AZUL, AZUL_SUAVE), AZUL, AZUL_SUAVE
        else:
            chip, icono_color, fondo = estado("Apagado", GRIS, "#F1F4FA"), GRIS, "#F1F4FA"
        modo_txt = "Automático" if d["modo_auto"] else "Manual"
        html(f"""
        <div class="card">
          <span class="icono-circ" style="background:{fondo};color:{icono_color};width:50px;height:50px">{ic('ac_unit', 26)}</span>
          <div class="etiqueta" style="margin-top:.9rem">Compresor</div>
          <div class="valor">{modo_txt}</div>
          <div style="margin-top:.5rem">{chip}</div>
        </div>""")


panel_en_vivo()

# =====================================================================
# 2. CONTROLES
# =====================================================================
st.write("")
t1, t2 = st.columns([3, 1], vertical_alignment="bottom")
t1.markdown("#### Controles")
with t2.popover("Cómo funciona", icon=":material/help:", use_container_width=True):
    st.markdown(
        "1. **Fija el objetivo** con el termostato, con gestos o por voz.\n"
        "2. **El ESP32 decide:** si la nevera está más caliente que el objetivo, enciende el compresor.\n"
        "3. **La temperatura cambia** poco a poco: baja al enfriar y sube si la puerta queda abierta.\n\n"
        "El sensor DHT22 de Wokwi mide la cocina; la temperatura interior la calcula el ESP32 con un "
        "modelo térmico."
    )


@st.fragment(run_every=2)
def tarjeta_termostato():
    d = datos()
    st.markdown("**:material/thermostat: Termostato**")
    st.markdown(f"<div style='font-size:2.3rem;font-weight:800;text-align:center;margin:.1rem 0'>"
                f"{d.get('objetivo', 4.0):.0f} °C</div><div class='etiqueta' style='text-align:center;"
                f"margin-bottom:.6rem'>Objetivo · ahora {d.get('temp', 0):.1f} °C</div>", unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    if b1.button("", icon=":material/remove:", key="obj_menos", use_container_width=True, help="Bajar 1 °C"):
        ordenar("OBJETIVO_MENOS", "Objetivo: 1 °C menos")
    if b2.button("", icon=":material/add:", key="obj_mas", use_container_width=True, help="Subir 1 °C"):
        ordenar("OBJETIVO_MAS", "Objetivo: 1 °C más")


@st.fragment(run_every=2)
def tarjeta_puerta():
    d = datos()
    st.markdown("**:material/door_front: Puerta**")
    abierta = d.get("puerta", False)
    if abierta:
        st.markdown(f"<div class='valor' style='color:{ROJO};text-align:center;margin:.35rem 0'>Abierta</div>"
                    f"<div class='etiqueta' style='text-align:center;margin-bottom:.6rem'>"
                    f"{d.get('seg_abierta', 0)} s · entra calor</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='valor' style='color:#11804F;text-align:center;margin:.35rem 0'>Cerrada</div>"
                    f"<div class='etiqueta' style='text-align:center;margin-bottom:.6rem'>Sellado correcto</div>",
                    unsafe_allow_html=True)
    if d.get("puerta_remota") or not abierta:
        if abierta:
            if st.button("Cerrar puerta", icon=":material/door_front:", type="primary", use_container_width=True):
                ordenar("PUERTA_CERRAR", "Puerta cerrada")
        elif st.button("Abrir puerta", icon=":material/door_open:", use_container_width=True):
            ordenar("PUERTA_ABRIR", "Puerta abierta (simulación)")
    else:
        st.caption("Se abrió con el interruptor de Wokwi: ciérrala desde allí.")


def cambiar_modo():
    if st.session_state.get("modo") == "Automático":
        ordenar("MODO_AUTO", "Modo automático activado", con_sonido=False)
    elif st.session_state.get("modo") == "Manual":
        ordenar("MODO_MANUAL", "Modo manual activado", con_sonido=False)


if "umbral" not in st.session_state:
    st.session_state["umbral"] = float(datos().get("umbral", 5.0))

col0, col1, col2, col3 = st.columns(4, gap="small")
with col0:
    with st.container(border=True):
        tarjeta_termostato()
with col1:
    with st.container(border=True):
        st.markdown("**:material/ac_unit: Compresor**")
        modo = st.segmented_control("Modo", ["Automático", "Manual"], default="Automático", key="modo",
                                    on_change=cambiar_modo, label_visibility="collapsed")
        if modo == "Manual":
            if st.button("Encender", icon=":material/power_settings_new:", type="primary", use_container_width=True):
                ordenar("COMPRESOR_ON", "Compresor encendido")
            if st.button("Apagar", icon=":material/power_off:", use_container_width=True):
                ordenar("COMPRESOR_OFF", "Compresor apagado")
        else:
            st.caption("En automático el ESP32 enfría hasta llegar al objetivo del termostato.")
with col2:
    with st.container(border=True):
        tarjeta_puerta()
with col3:
    with st.container(border=True):
        st.markdown("**:material/notifications: Alarma**")
        umbral = st.slider("Temperatura máxima", 1.0, 10.0, step=0.5, format="%.1f °C", key="umbral")
        if st.button("Guardar límite", icon=":material/save:", use_container_width=True):
            ordenar(f"UMBRAL:{umbral}", f"Límite: {umbral:.1f} °C")
        if st.button("Silenciar", icon=":material/notifications_off:", type="primary", use_container_width=True):
            ordenar("SILENCIAR", "Alarma silenciada")

# Mensaje para la pantalla, con vista previa
with st.container(border=True):
    st.markdown("**:material/chat: Mensaje en la pantalla de la nevera**")
    m1, m2 = st.columns([1.4, 1], gap="large", vertical_alignment="center")
    with m1:
        texto = st.text_input("Texto (máximo 32 caracteres)", max_chars=32,
                              placeholder="Ejemplo: Revisar fecha de la leche", key="texto_lcd")
        e1, e2 = st.columns(2)
        if e1.button("Enviar a la nevera", icon=":material/send:", type="primary", use_container_width=True,
                     disabled=not texto):
            ordenar(f"MENSAJE:{texto}", "Mensaje enviado a la pantalla")
        if e2.button("Probar alarma sonora", icon=":material/volume_up:", use_container_width=True):
            ordenar("PROBAR_ALARMA", "Prueba de alarma enviada")
    with m2:
        vista = texto or "Escribe un texto"
        html(f'<div class="etiqueta" style="margin-bottom:.4rem">Vista previa</div>'
             f'{lcd_virtual(vista[:16], vista[16:32], apagada=not texto)}')

# =====================================================================
# 3. CONTROL POR GESTOS
# =====================================================================
st.write("")
st.markdown("#### Control por gestos")
st.caption("Usa la mano como termostato: pulgar arriba o abajo cambia el objetivo. Sostén cada gesto un segundo.")


def html_gestos():
    ruta = Path(__file__).resolve().parent.parent / "componentes" / "gestos.html"
    return (ruta.read_text(encoding="utf-8").replace("__TOPIC_CMD__", TOPIC_CMD)
            .replace("__TOPIC_DATOS__", TOPIC_DATOS).replace("__BROKER_WS__", BROKER_WS))


components.html(html_gestos(), height=620, scrolling=False)

# =====================================================================
# 4. ENERGÍA E HISTORIAL
# =====================================================================
st.markdown("#### Energía e historial")


@st.fragment(run_every=4)
def panel_historial():
    est = leer_estado()
    min_puerta, min_comp, wh, pesos = energia_hoy()
    e1, e2, e3 = st.columns(3, gap="medium")
    tarjetas = [
        (e1, "door_open", "#FFF1F1", ROJO, "Puerta abierta hoy", f"{min_puerta:.1f} min"),
        (e2, "ac_unit", AZUL_SUAVE, AZUL, "Compresor encendido hoy", f"{min_comp:.1f} min"),
        (e3, "bolt", "#FFF4E0", AMBAR, "Energía estimada hoy", f"{wh:.1f} Wh · ${pesos:,.0f} COP".replace(",", ".")),
    ]
    for col, icono, fondo, color, etiqueta, valor in tarjetas:
        with col:
            html(f"""
            <div class="card" style="display:flex;gap:.9rem;align-items:center;padding:1rem 1.2rem">
              <span class="icono-circ" style="background:{fondo};color:{color};width:48px;height:48px">{ic(icono, 24)}</span>
              <div><div class="etiqueta">{etiqueta}</div><div class="valor" style="font-size:1.25rem">{valor}</div></div>
            </div>""")
    st.write("")
    with st.container(border=True):
        st.markdown("**:material/monitoring: Temperatura interior frente al objetivo**")
        if est.historial:
            df = pd.DataFrame(list(est.historial)).set_index("hora")
            st.line_chart(df, color=[AZUL, AMBAR], height=240)
        else:
            st.caption("La gráfica aparece cuando llegan los primeros datos.")


panel_historial()
with st.popover("Cómo se calcula la energía", icon=":material/info:"):
    st.markdown(
        f"- Compresor: **{POTENCIA_COMPRESOR_W} W** mientras está encendido.\n"
        f"- Puerta abierta: **{PERDIDA_PUERTA_WH_MIN} Wh** extra por cada minuto, por la entrada de aire caliente.\n"
        f"- Tarifa: **${TARIFA_COP_KWH} COP por kWh** (valor residencial aproximado).\n\n"
        "Son estimaciones para mostrar el impacto de dejar la puerta abierta; los contadores se reinician cada día."
    )

# =====================================================================
# 5. ALERTAS AL CELULAR
# =====================================================================
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
