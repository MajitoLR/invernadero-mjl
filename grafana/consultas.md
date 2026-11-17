# Consultas de los paneles de Grafana

Fuente de datos: **InfluxDB Invernadero** (InfluxDB Cloud, lenguaje SQL) · bucket `invernadero` · measurement `invernadero`.
Dashboard: **Invernadero IoT** (actualización cada 5 s, últimos 30 min).

Panel **Temperatura del aire (°C)** — umbrales 18 y 30 °C
```sql
SELECT time, temperatura
FROM "invernadero"
WHERE $__timeFilter(time)
ORDER BY time
```

Panel **Humedad del suelo (%)** — umbrales 40 y 80 %
```sql
SELECT time, humedad_suelo
FROM "invernadero"
WHERE $__timeFilter(time)
ORDER BY time
```

Panel **Datos para exportar** (tabla con las dos variables; de aquí sale el CSV de la app)
```sql
SELECT time, temperatura, humedad_suelo, ventilador
FROM "invernadero"
WHERE $__timeFilter(time)
ORDER BY time DESC
```

Exportar: menú ⋮ del panel → **Inspect → Data** → **Download CSV**.
