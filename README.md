# 🧊 Nevera Inteligente

Proyecto final, **Creación de Interfaces Multimodales**, Universidad EAFIT.

Esta app conecta una nevera simulada en **Wokwi (ESP32)** con una aplicación en **Streamlit**
por **MQTT**, en las dos direcciones. Así se puede vigilar la temperatura y la puerta,
controlar el enfriamiento y llevar el inventario de alimentos con la **cámara** y la **voz**.

## Enlaces

- **App en Streamlit Cloud:** https://nevera-inteligente-eafit.streamlit.app
- **Simulación en Wokwi:** https://wokwi.com/projects/481057259362016257

## Arquitectura

```
 Wokwi (ESP32)                         Broker MQTT                      Streamlit Cloud
 DHT22, interruptor puerta  ──►  nevera_ma_eafit/datos  ──►  Página Monitoreo (gráficas, alertas)
 LED compresor, LED alarma,  ◄──  nevera_ma_eafit/cmd   ◄──  Botones, slider, texto, voz, cámara
 buzzer, LCD 16x2                broker.mqttdashboard.com:1883
```

## Modalidades de interacción

| Ambiente | Entrada | Salida |
|---|---|---|
| Monitoreo de la nevera | Botones, radio, slider, texto | Métricas, gráfica en vivo, alertas, LEDs, buzzer, LCD |
| Despensa inteligente | Cámara, foto o enlace (modelo CLIP), voz (SpeechRecognition), texto | Tabla de inventario, voz sintetizada (gTTS), LCD |

## Funciones destacadas

- **Escáner en vivo:** detección de alimentos en tiempo real en el navegador (TensorFlow.js, COCO-SSD) con interfaz tipo HUD; registra el alimento por MQTT.
- **Reconocimiento por foto:** modelo CLIP que identifica 34 alimentos (incluidos leche, huevos y queso) desde la cámara, un archivo o un enlace.
- **Control por gestos:** MediaPipe reconoce gestos de la mano y envía órdenes al ESP32 (mano abierta = silenciar, pulgar arriba/abajo = enfriamiento, V = automático, índice = probar alarma).
- **Alertas al celular:** notificaciones push con ntfy cuando se activa la alarma.
- **Recetas anti-desperdicio:** sugiere recetas que usan primero los alimentos por vencer; también por voz ("qué puedo cocinar").
- **Energía:** minutos de puerta abierta y de enfriamiento, Wh y costo estimado del día.

## Estructura

```
app.py                  # navegación entre páginas
mqtt_utils.py           # cliente MQTT compartido, alertas ntfy y energía
estilo.py               # sistema visual (íconos Material Symbols, tarjetas)
componentes/escaner.html  # escáner en vivo (TensorFlow.js)
componentes/gestos.html   # control por gestos (MediaPipe)
paginas/inicio.py
paginas/monitoreo.py    # ambiente 1
paginas/despensa.py     # ambiente 2
modelo/                 # keras_model.h5 + labels.txt de Teachable Machine
wokwi/sketch.ino        # firmware del ESP32
wokwi/diagram.json      # circuito
wokwi/libraries.txt     # bibliotecas de Wokwi
```

## Cómo correrlo

### 1. Wokwi
1. Entra a https://wokwi.com, crea un proyecto **ESP32** y borra el código de ejemplo.
2. Pega `wokwi/sketch.ino` en `sketch.ino` y `wokwi/diagram.json` en `diagram.json`.
3. Crea el archivo `libraries.txt` (botón ▼ → *New file*) y pega el contenido de `wokwi/libraries.txt`.
4. Dale ▶. En el monitor serial debe salir `WiFi conectada` y luego `conectado`.
5. Para probar: haz clic en el DHT22 y sube la temperatura, o mueve el interruptor (la puerta).

### 2. Streamlit (local)
```bash
pip install -r requirements.txt
streamlit run app.py
```

### 3. Streamlit Cloud
1. Sube este repositorio a GitHub.
2. En https://share.streamlit.io elige **Create app** → el repositorio → archivo principal `app.py`.
3. En *Advanced settings* elige **Python 3.11** o 3.12.

## Órdenes MQTT (tema `nevera_ma_eafit/cmd`)

| Orden | Efecto en el ESP32 |
|---|---|
| `COMPRESOR_ON` / `COMPRESOR_OFF` | Prende o apaga el enfriamiento (pasa a modo manual) |
| `MODO_AUTO` / `MODO_MANUAL` | En automático, enfría solo si la temperatura supera el umbral |
| `UMBRAL:6.5` | Cambia la temperatura máxima permitida |
| `SILENCIAR` | Silencia la alarma actual |
| `PROBAR_ALARMA` | Hace sonar el buzzer 1 segundo |
| `MENSAJE:texto` | Muestra el texto en la LCD durante 5 segundos |

Si cambias el broker o los temas, cámbialos **en los dos lados**: `wokwi/sketch.ino` y `mqtt_utils.py`.
