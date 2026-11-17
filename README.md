# 🌱 Invernadero IoT — Proyecto Final

**Computación Física e Internet de las Cosas (IoT)** · Sofía Betancur · Universidad EAFIT

Sistema IoT de telemetría y telecontrol para un invernadero, con un ESP32 simulado en Wokwi.

| | |
|---|---|
| **Variables medidas** | Temperatura del aire (°C, DHT22) · Humedad del suelo (%, sensor analógico) |
| **Actuador** | Relé que enciende el ventilador |
| **Rangos de operación** | Temperatura 18–30 °C · Humedad del suelo 40–80 % |
| **Intervalo de lectura** | 5 segundos |

## Arquitectura

```
                 ┌──MQTT (telemetría)──► ThingsBoard (dashboard + interruptor)
ESP32 (Wokwi) ───┤◄─MQTT (comandos RPC)──┘
                 └──HTTPS──► InfluxDB Cloud ──► Grafana ──CSV──► Streamlit Cloud
```

- **Tópico de datos (MQTT):** `v1/devices/me/telemetry` → `{"temperatura":25.3,"humedad_suelo":55.0,"ventilador":0}`
- **Tópico de control (MQTT):** `v1/devices/me/rpc/request/+` → `{"method":"setVentilador","params":true}` / `false`
- **InfluxDB:** bucket `invernadero`, measurement `invernadero`, campos `temperatura`, `humedad_suelo`, `ventilador`

## Enlaces

- Simulación en Wokwi: https://wokwi.com/projects/480955229561677825
- App en Streamlit Cloud: https://invernadero-iot-sofi.streamlit.app
- Dashboard de Grafana: ver capturas en [`grafana/`](grafana/) y el CSV exportado en [`streamlit/datos_grafana.csv`](streamlit/datos_grafana.csv)
- Video: _PEGA AQUÍ EL ENLACE_

## Contenido del repositorio

| Carpeta | Contenido |
|---|---|
| `esp32/` | `sketch.ino`, `diagram.json`, `libraries.txt` y `secrets.example.h` del proyecto de Wokwi |
| `streamlit/` | `app.py`, `requirements.txt` y el CSV exportado de Grafana que usa la app |
| `grafana/` | Consultas de los paneles y capturas del dashboard |

## Seguridad

El código no contiene contraseñas ni tokens. El token de InfluxDB y el access token de ThingsBoard
van en `esp32/secrets.h`, que está en `.gitignore`; en el repositorio solo está la plantilla
`secrets.example.h`.
