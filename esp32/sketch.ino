/*
  Proyecto Final IoT - Invernadero inteligente
  Telemetría y telecontrol con ESP32 + MQTT (ThingsBoard) + InfluxDB

  Sensores (lectura cada 5 s):
    - DHT22 (GPIO 15)            -> temperatura del aire (°C)
    - Sensor de humedad de suelo  -> humedad del suelo (%)
      (salida analógica en GPIO 34; en Wokwi se simula con un potenciómetro)
  Actuador:
    - Relé (GPIO 26) que enciende el ventilador del invernadero

  Telemetría:
    - MQTT -> ThingsBoard, tópico v1/devices/me/telemetry
      {"temperatura":25.3,"humedad_suelo":55.0,"ventilador":0}
    - InfluxDB Cloud, bucket "invernadero", measurement "invernadero"
  Telecontrol:
    - Suscrito a v1/devices/me/rpc/request/+ (comandos desde ThingsBoard)
      {"method":"setVentilador","params":true|false}  /  {"method":"getVentilador"}
*/

#if defined(ESP32)
#include <WiFiMulti.h>
WiFiMulti wifiMulti;
#define DEVICE "ESP32"
#elif defined(ESP8266)
#include <ESP8266WiFiMulti.h>
ESP8266WiFiMulti wifiMulti;
#define DEVICE "ESP8266"
#endif

#include <InfluxDbClient.h>
#include <InfluxDbCloud.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "DHTesp.h"
#include "secrets.h"   // INFLUXDB_TOKEN y TB_TOKEN

// WiFi del simulador
#define WIFI_SSID "Wokwi-GUEST"
#define WIFI_PASSWORD ""

// InfluxDB Cloud
#define INFLUXDB_URL "https://us-east-1-1.aws.cloud2.influxdata.com"
#define INFLUXDB_ORG "eafit"
#define INFLUXDB_BUCKET "invernadero"

// Zona horaria de Colombia (UTC-5)
#define TZ_INFO "<-05>5"

// ThingsBoard (MQTT)
#define MQTT_BROKER "mqtt.thingsboard.cloud"
#define MQTT_PORT 1883
const char* TOPIC_DATOS     = "v1/devices/me/telemetry";       // tópico de datos
const char* TOPIC_CONTROL   = "v1/devices/me/rpc/request/+";   // tópico de control
const char* TOPIC_RESPUESTA = "v1/devices/me/rpc/response/";

// Pines
const int PIN_DHT   = 15;
const int PIN_SUELO = 34;
const int PIN_RELE  = 26;

const unsigned long INTERVALO_MS = 5000;   // intervalo fijo de lectura: 5 s

// Cliente de InfluxDB con el certificado de InfluxCloud
InfluxDBClient client(INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET, INFLUXDB_TOKEN, InfluxDbCloud2CACert);
Point sensor("invernadero");

WiFiClient espClient;
PubSubClient mqtt(espClient);
DHTesp dht;

unsigned long ultimoEnvio = 0;
bool ventiladorEncendido = false;
float temperatura = NAN;
float humedadSuelo = NAN;

// ---------- Actuador ----------
void setVentilador(bool encender) {
  ventiladorEncendido = encender;
  digitalWrite(PIN_RELE, encender ? HIGH : LOW);
  Serial.print("Ventilador: ");
  Serial.println(encender ? "ENCENDIDO" : "APAGADO");
}

// ---------- Sensores ----------
bool leerSensores() {
  temperatura = dht.getTemperature();
  int lectura = analogRead(PIN_SUELO);              // ADC de 12 bits (0-4095)
  humedadSuelo = lectura * 100.0 / 4095.0;          // convertido a %
  if (isnan(temperatura)) {
    Serial.println("Error leyendo el DHT22");
    return false;
  }
  temperatura = round(temperatura * 10) / 10.0;
  humedadSuelo = round(humedadSuelo * 10) / 10.0;
  return true;
}

// ---------- Telemetría por MQTT (ThingsBoard) ----------
void publicarMQTT() {
  StaticJsonDocument<128> doc;
  doc["temperatura"]   = temperatura;
  doc["humedad_suelo"] = humedadSuelo;
  doc["ventilador"]    = ventiladorEncendido ? 1 : 0;
  char buffer[128];
  serializeJson(doc, buffer);
  mqtt.publish(TOPIC_DATOS, buffer);
  Serial.print("MQTT publicado: ");
  Serial.println(buffer);
}

// ---------- Almacenamiento en InfluxDB ----------
void guardarInflux() {
  sensor.clearFields();
  sensor.addField("temperatura", temperatura);
  sensor.addField("humedad_suelo", humedadSuelo);
  sensor.addField("ventilador", ventiladorEncendido ? 1.0 : 0.0);   // decimal: así está definida la columna

  if (client.writePoint(sensor)) {
    Serial.println("Guardado en InfluxDB");
  } else {
    Serial.print("InfluxDB write failed: ");
    Serial.println(client.getLastErrorMessage());
  }
}

// ---------- Telecontrol (comandos RPC de ThingsBoard) ----------
void alRecibirMensaje(char* topic, byte* payload, unsigned int length) {
  Serial.print("Comando recibido: ");
  Serial.write(payload, length);
  Serial.println();

  StaticJsonDocument<200> doc;
  if (deserializeJson(doc, payload, length)) {
    Serial.println("JSON invalido, comando ignorado");
    return;
  }
  const char* metodo = doc["method"];
  if (metodo == nullptr) return;

  bool esSet = strcmp(metodo, "setVentilador") == 0;
  if (esSet) setVentilador(doc["params"].as<bool>());

  // Respuesta a ThingsBoard con el estado actual del ventilador
  String t = String(topic);
  String respuesta = String(TOPIC_RESPUESTA) + t.substring(t.lastIndexOf('/') + 1);
  mqtt.publish(respuesta.c_str(), ventiladorEncendido ? "true" : "false");

  if (esSet && leerSensores()) publicarMQTT();   // confirma el nuevo estado
}

void conectarMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Conectando a ThingsBoard (MQTT)...");
    String clientId = "invernadero-esp32-" + String(random(0xffff), HEX);
    if (mqtt.connect(clientId.c_str(), TB_TOKEN, NULL)) {   // el token va como usuario
      Serial.println(" conectado");
      mqtt.subscribe(TOPIC_CONTROL);
    } else {
      Serial.print(" fallo (rc=");
      Serial.print(mqtt.state());
      Serial.println("), reintento en 2 s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELE, OUTPUT);
  setVentilador(false);
  dht.setup(PIN_DHT, DHTesp::DHT22);

  // WiFi
  WiFi.mode(WIFI_STA);
  wifiMulti.addAP(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to wifi");
  while (wifiMulti.run() != WL_CONNECTED) {
    Serial.print(".");
    delay(100);
  }
  Serial.println();

  // Hora exacta: necesaria para el certificado de InfluxDB y las marcas de tiempo
  timeSync(TZ_INFO, "pool.ntp.org", "time.nis.gov");

  if (client.validateConnection()) {
    Serial.print("Connected to InfluxDB: ");
    Serial.println(client.getServerUrl());
  } else {
    Serial.print("InfluxDB connection failed: ");
    Serial.println(client.getLastErrorMessage());
  }

  sensor.addTag("dispositivo", DEVICE);

  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(alRecibirMensaje);
}

void loop() {
  if ((WiFi.RSSI() == 0) && (wifiMulti.run() != WL_CONNECTED)) {
    Serial.println("Wifi connection lost");
  }
  if (!mqtt.connected()) conectarMQTT();
  mqtt.loop();

  if (millis() - ultimoEnvio >= INTERVALO_MS) {
    ultimoEnvio = millis();
    if (leerSensores()) {
      publicarMQTT();
      guardarInflux();
      Serial.println("");
    }
  }
}
