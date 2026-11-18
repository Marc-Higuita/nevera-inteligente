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
ZONA = ZoneInfo("America/Bogota")


class EstadoNevera:
    """Guarda lo que llega del ESP32. Lo comparten todas las páginas."""

    def __init__(self):
        self.ultimo = None              # último JSON recibido
        self.ultima_hora = None         # time.time() de la última lectura
        self.historial = deque(maxlen=150)
        self.conectado = False
        self.lock = threading.Lock()


@st.cache_resource
def obtener_cliente():
    estado = EstadoNevera()

    def on_connect(client, userdata, flags, reason_code, properties):
        estado.conectado = reason_code == 0
        client.subscribe(TOPIC_DATOS)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        estado.conectado = False

    def on_message(client, userdata, msg):
        try:
            datos = json.loads(msg.payload.decode())
        except (ValueError, UnicodeDecodeError):
            return
        with estado.lock:
            estado.ultimo = datos
            estado.ultima_hora = time.time()
            estado.historial.append({
                "hora": datetime.now(ZONA).strftime("%H:%M:%S"),
                "Temperatura (°C)": datos.get("temp"),
                "Humedad (%)": datos.get("hum"),
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
