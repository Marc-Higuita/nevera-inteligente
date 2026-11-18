"""Conexión MQTT compartida entre las páginas de la app.

Un solo cliente MQTT queda escuchando en segundo plano (st.cache_resource),
guarda la última lectura del ESP32 y un historial para las gráficas.
"""
import json
import threading
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
import streamlit as st

# Deben ser IGUALES a los del sketch.ino de Wokwi
BROKER = "broker.mqttdashboard.com"   # o la IP del profe: "157.230.214.127"
PUERTO = 1883
TOPIC_DATOS = "nevera_ma_eafit/datos"
TOPIC_CMD = "nevera_ma_eafit/cmd"
TOPIC_INV = "nevera_ma_eafit/inventario"   # el escáner en vivo publica aquí "AGREGAR:Nombre"
# El navegador se conecta al mismo broker (HiveMQ público) por WebSocket seguro
BROKER_WS = "wss://broker.hivemq.com:8884/mqtt"

# Alertas al celular con ntfy (https://ntfy.sh): gratis y sin cuenta.
# Para recibirlas: instalar la app ntfy y suscribirse a este tema.
NTFY_TEMA = "nevera-eafit-ma-7k2x"

# Supuestos del cálculo de energía (ajustables)
POTENCIA_COMPRESOR_W = 120      # potencia típica de una nevera doméstica con el compresor encendido
PERDIDA_PUERTA_WH_MIN = 2.0     # consumo extra estimado por cada minuto con la puerta abierta
TARIFA_COP_KWH = 950            # tarifa residencial aproximada en pesos por kWh
ZONA = ZoneInfo("America/Bogota")
WOKWI_URL = "https://wokwi.com/projects/481057259362016257"   # simulación embebida en la app


class EstadoNevera:
    """Guarda lo que llega del ESP32. Lo comparten todas las páginas."""

    def __init__(self):
        self.ultimo = None              # último JSON recibido
        self.ultima_hora = None         # time.time() de la última lectura
        self.historial = deque(maxlen=150)
        self.pendientes = deque()       # alimentos que llegan del escáner en vivo
        self.dia = None                 # contadores del día (energía)
        self.seg_puerta = 0.0
        self.seg_compresor = 0.0
        self.alarma_previa = False
        self.ultima_alerta = 0.0
        self.alertas = deque(maxlen=10)   # historial de notificaciones enviadas
        self.conectado = False
        self.lock = threading.Lock()


@st.cache_resource
def obtener_cliente():
    estado = EstadoNevera()

    def on_connect(client, userdata, flags, reason_code, properties):
        estado.conectado = reason_code == 0
        client.subscribe(TOPIC_DATOS)
        client.subscribe(TOPIC_INV)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        estado.conectado = False

    def on_message(client, userdata, msg):
        if msg.topic == TOPIC_INV:
            texto = msg.payload.decode(errors="ignore")
            if texto.startswith("AGREGAR:") and texto[8:].strip():
                estado.pendientes.append(texto[8:].strip()[:30])
            return
        try:
            datos = json.loads(msg.payload.decode())
        except (ValueError, UnicodeDecodeError):
            return
        with estado.lock:
            ahora = time.time()
            hoy = datetime.now(ZONA).date()
            if estado.dia != hoy:                     # reinicia los contadores cada día
                estado.dia, estado.seg_puerta, estado.seg_compresor = hoy, 0.0, 0.0
            if estado.ultima_hora:
                dt = min(ahora - estado.ultima_hora, 5)   # los datos llegan cada 2 s
                if datos.get("puerta"):
                    estado.seg_puerta += dt
                if datos.get("compresor"):
                    estado.seg_compresor += dt
            # Alerta al celular cuando la alarma se activa
            if datos.get("alarma") and not estado.alarma_previa and ahora - estado.ultima_alerta > 60:
                estado.ultima_alerta = ahora
                texto = f"{datos.get('motivo', 'Alarma activa')}. Temperatura: {datos.get('temp', 0):.1f} °C"
                enviar_alerta("Alarma en la nevera", texto, estado)
            estado.alarma_previa = bool(datos.get("alarma"))
            estado.ultimo = datos
            estado.ultima_hora = ahora
            estado.historial.append({
                "hora": datetime.now(ZONA).strftime("%H:%M:%S"),
                "Temperatura interior (°C)": datos.get("temp"),
                "Objetivo (°C)": datos.get("objetivo"),
            })

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"streamlit-nevera-{int(time.time())}",
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(BROKER, PUERTO, keepalive=60)
    client.loop_start()     # hilo en segundo plano que recibe los mensajes
    for _ in range(30):     # espera hasta 3 s a que se establezca la conexión
        if estado.conectado:
            break
        time.sleep(0.1)
    return client, estado


def enviar_orden(orden: str) -> bool:
    """Publica una orden de texto para el ESP32 (ej. 'COMPRESOR_ON')."""
    client, _ = obtener_cliente()
    resultado = client.publish(TOPIC_CMD, orden)
    return resultado.rc == mqtt.MQTT_ERR_SUCCESS


def leer_estado():
    _, estado = obtener_cliente()
    return estado


def enviar_alerta(titulo: str, texto: str, estado=None, prioridad: str = "high") -> bool:
    """Envía una notificación push al celular por ntfy (en un hilo aparte para no bloquear)."""
    import urllib.request

    def tarea():
        try:
            pedido = urllib.request.Request(
                f"https://ntfy.sh/{NTFY_TEMA}", data=texto.encode("utf-8"), method="POST",
                headers={"Title": titulo.encode("utf-8").decode("latin-1", "ignore"),
                         "Priority": prioridad, "Tags": "warning,snowflake"})
            urllib.request.urlopen(pedido, timeout=10)
            ok = True
        except Exception:
            ok = False
        if estado is not None:
            estado.alertas.appendleft({"hora": datetime.now(ZONA).strftime("%H:%M:%S"),
                                       "texto": texto, "ok": ok})

    threading.Thread(target=tarea, daemon=True).start()
    return True


def energia_hoy():
    """Devuelve minutos de puerta abierta, minutos de compresor, Wh y pesos estimados del día."""
    _, estado = obtener_cliente()
    min_puerta = estado.seg_puerta / 60
    min_comp = estado.seg_compresor / 60
    wh = POTENCIA_COMPRESOR_W * min_comp / 60 + PERDIDA_PUERTA_WH_MIN * min_puerta
    pesos = wh / 1000 * TARIFA_COP_KWH
    return min_puerta, min_comp, wh, pesos
