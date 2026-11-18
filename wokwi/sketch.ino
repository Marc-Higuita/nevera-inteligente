/*
  NEVERA INTELIGENTE - Proyecto final Interfaces Multimodales
  ESP32 simulado en Wokwi

  Sensores:   DHT22 (temperatura y humedad de la cocina, alrededor de la nevera)
              Interruptor deslizante (puerta abierta / cerrada)
  Actuadores: LED azul  -> compresor (enfriamiento)
              LED rojo  -> alarma
              Buzzer    -> alarma sonora
              LCD 16x2  -> mensajes que llegan desde Streamlit

  Modelo termico (gemelo digital): la temperatura INTERIOR se calcula cada 2 s.
    - Con el compresor encendido baja 0.3 °C.
    - El calor de la cocina (DHT22) entra poco a poco; con la puerta abierta entra mucho mas rapido.
    Asi se ve como la nevera enfria hasta el objetivo del termostato y como se calienta.

  Comunicacion bidireccional por MQTT:
    ESP32  -> Streamlit : publica los datos en TOPIC_DATOS cada 2 s (JSON)
    Streamlit -> ESP32  : envia ordenes en TOPIC_CMD (texto)

  Ordenes que entiende (TOPIC_CMD):
    OBJETIVO_MAS / OBJETIVO_MENOS  sube o baja 1 grado la temperatura objetivo (termostato)
    OBJETIVO:3.5                   fija la temperatura objetivo
    COMPRESOR_ON / COMPRESOR_OFF   enciende o apaga el enfriamiento (modo manual)
    MODO_AUTO / MODO_MANUAL        en automatico el compresor enfria hasta llegar al objetivo
    UMBRAL:6.5                     cambia la temperatura maxima permitida
    SILENCIAR                      apaga el sonido de la alarma actual
    PROBAR_ALARMA                  suena el buzzer 1 segundo
    MENSAJE:texto                  muestra el texto en la pantalla LCD
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "DHTesp.h"
#include <LiquidCrystal_I2C.h>

// ---------- Red y broker ----------
const char* ssid        = "Wokwi-GUEST";
const char* password    = "";
const char* mqtt_server = "broker.mqttdashboard.com";   // o la IP del profe: "157.230.214.127"
const int   mqtt_port   = 1883;

// Temas MQTT: deben ser IGUALES a los de mqtt_utils.py en Streamlit
const char* TOPIC_DATOS = "nevera_ma_eafit/datos";
const char* TOPIC_CMD   = "nevera_ma_eafit/cmd";

// ---------- Pines ----------
const int DHT_PIN     = 15;
const int PUERTA_PIN  = 4;    // interruptor deslizante
const int LED_ALARMA  = 2;    // LED rojo
const int LED_COMP    = 5;    // LED azul (compresor)
const int BUZZER_PIN  = 18;

// ---------- Objetos ----------
WiFiClient espClient;
PubSubClient client(espClient);
DHTesp dhtSensor;
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ---------- Estado ----------
float umbral = 5.0;                  // temperatura maxima permitida, activa la alarma (°C)
float objetivo = 4.0;                // temperatura objetivo del termostato (°C)
const unsigned long PUERTA_MAX_MS = 10000;   // 10 s con la puerta abierta = alarma
bool compresor = false;
bool modoAuto = true;
bool silenciada = false;
bool alarma = false;
String motivoAlarma = "";
unsigned long puertaAbiertaDesde = 0;
unsigned long ultimoEnvio = 0;
unsigned long mensajeHasta = 0;      // hasta cuando se muestra un mensaje en el LCD
float temp = 4.0, hum = 0;          // temp = temperatura interior (modelo termico)
float ambiente = 24.0;               // temperatura de la cocina medida por el DHT22
bool puertaAbierta = false;

void mostrarObjetivo() {
  // Muestra el nuevo objetivo en la LCD durante 3 segundos y aplica el termostato de inmediato
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Termostato");
  lcd.setCursor(0, 1);
  lcd.print("Objetivo: " + String(objetivo, 0) + " C");
  mensajeHasta = millis() + 3000;
  ultimoEnvio = 0;   // fuerza una actualizacion y publicacion inmediata
}

// ---------- Recepcion de ordenes desde Streamlit ----------
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  Serial.print("Orden recibida: ");
  Serial.println(msg);

  if (msg == "OBJETIVO_MAS")        { objetivo = min(objetivo + 1.0f, 8.0f); modoAuto = true; mostrarObjetivo(); }
  else if (msg == "OBJETIVO_MENOS") { objetivo = max(objetivo - 1.0f, -2.0f); modoAuto = true; mostrarObjetivo(); }
  else if (msg.startsWith("OBJETIVO:")) { objetivo = msg.substring(9).toFloat(); modoAuto = true; mostrarObjetivo(); }
  else if (msg == "COMPRESOR_ON")  { modoAuto = false; compresor = true; }
  else if (msg == "COMPRESOR_OFF") { modoAuto = false; compresor = false; }
  else if (msg == "MODO_AUTO")     { modoAuto = true; }
  else if (msg == "MODO_MANUAL")   { modoAuto = false; }
  else if (msg == "SILENCIAR")     { silenciada = true; noTone(BUZZER_PIN); }
  else if (msg == "PROBAR_ALARMA") { tone(BUZZER_PIN, 1200, 1000); }
  else if (msg.startsWith("UMBRAL:")) {
    umbral = msg.substring(7).toFloat();
  }
  else if (msg.startsWith("MENSAJE:")) {
    String texto = msg.substring(8);
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(texto.substring(0, 16));
    lcd.setCursor(0, 1);
    lcd.print(texto.substring(16, 32));
    mensajeHasta = millis() + 5000;   // el mensaje se ve 5 segundos
  }
}

void setup_wifi() {
  Serial.print("Conectando a ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectada. IP: " + WiFi.localIP().toString());
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Conectando a MQTT...");
    String clientId = "ESP32-Nevera-" + String(random(0xffff), HEX);  // ID unico
    if (client.connect(clientId.c_str())) {
      Serial.println("conectado");
      client.subscribe(TOPIC_CMD);           // <- aqui empieza a escuchar a Streamlit
    } else {
      Serial.print("falla, rc=");
      Serial.print(client.state());
      Serial.println(" reintento en 5 s");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PUERTA_PIN, INPUT);
  pinMode(LED_ALARMA, OUTPUT);
  pinMode(LED_COMP, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  dhtSensor.setup(DHT_PIN, DHTesp::DHT22);

  lcd.init();
  lcd.backlight();
  lcd.print("Nevera IA");
  lcd.setCursor(0, 1);
  lcd.print("Conectando...");

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void actualizarLogica() {
  // Lectura de sensores
  TempAndHumidity data = dhtSensor.getTempAndHumidity();
  if (!isnan(data.temperature)) ambiente = data.temperature;
  if (!isnan(data.humidity)) hum = data.humidity;
  puertaAbierta = digitalRead(PUERTA_PIN) == HIGH;

  // Modelo termico de la nevera (cada 2 s)
  if (compresor) temp -= 0.30;                          // el compresor saca calor
  float fuga = puertaAbierta ? 0.035 : 0.006;           // fraccion del calor de la cocina que entra
  temp += (ambiente - temp) * fuga;
  temp = constrain(temp, -5.0, ambiente);

  // Tiempo con la puerta abierta
  if (puertaAbierta) {
    if (puertaAbiertaDesde == 0) puertaAbiertaDesde = millis();
  } else {
    puertaAbiertaDesde = 0;
  }
  bool puertaMucho = puertaAbierta && (millis() - puertaAbiertaDesde > PUERTA_MAX_MS);
  // La alarma salta por encima del limite (o 1.5 °C sobre el objetivo, si el objetivo es mayor)
  bool muyCaliente = temp > max(umbral, objetivo + 1.5f);

  // Modo automatico (termostato con histeresis de 0.5 °C):
  // enfria si la temperatura esta por encima del objetivo y se apaga al alcanzarlo
  if (modoAuto) {
    if (temp > objetivo + 0.3) compresor = true;
    else if (temp < objetivo - 0.3) compresor = false;
  }

  // Alarma
  bool alarmaAntes = alarma;
  alarma = puertaMucho || muyCaliente;
  if (puertaMucho && muyCaliente) motivoAlarma = "Puerta abierta y temperatura alta";
  else if (puertaMucho)           motivoAlarma = "Puerta abierta mucho tiempo";
  else if (muyCaliente)           motivoAlarma = "Temperatura alta";
  else                            motivoAlarma = "";
  if (!alarma) silenciada = false;          // cuando se resuelve, la alarma se rearma
  if (alarma && !alarmaAntes) silenciada = false;
}

void actualizarSalidas() {
  digitalWrite(LED_COMP, compresor ? HIGH : LOW);

  // LED rojo parpadea con la alarma
  bool parpadeo = (millis() / 300) % 2;
  digitalWrite(LED_ALARMA, alarma && parpadeo ? HIGH : LOW);

  if (alarma && !silenciada) {
    if (parpadeo) tone(BUZZER_PIN, 900); else noTone(BUZZER_PIN);
  }
}

void mostrarLCD() {
  if (millis() < mensajeHasta) return;      // hay un mensaje de Streamlit en pantalla
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("T:" + String(temp, 1) + "C Obj:" + String(objetivo, 0) + "C");
  lcd.setCursor(0, 1);
  if (alarma)             lcd.print("ALARMA!");
  else if (puertaAbierta) lcd.print("Puerta ABIERTA");
  else if (compresor)     lcd.print("Enfriando...");
  else                    lcd.print("Puerta cerrada");
}

void publicarDatos() {
  StaticJsonDocument<256> doc;
  doc["temp"] = temp;
  doc["hum"] = hum;
  doc["ambiente"] = ambiente;
  doc["puerta"] = puertaAbierta;
  doc["seg_abierta"] = puertaAbierta ? (millis() - puertaAbiertaDesde) / 1000 : 0;
  doc["compresor"] = compresor;
  doc["modo_auto"] = modoAuto;
  doc["umbral"] = umbral;
  doc["objetivo"] = objetivo;
  doc["alarma"] = alarma;
  doc["motivo"] = motivoAlarma;
  doc["silenciada"] = silenciada;
  char buffer[256];
  serializeJson(doc, buffer);
  client.publish(TOPIC_DATOS, buffer);
  Serial.println(buffer);
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  actualizarSalidas();

  if (millis() - ultimoEnvio > 2000) {
    ultimoEnvio = millis();
    actualizarLogica();
    mostrarLCD();
    publicarDatos();
  }
}
