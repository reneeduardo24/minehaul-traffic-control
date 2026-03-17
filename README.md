# MVTS Distributed MVP

MVP ejecutable para un sistema distribuido mínimo de monitoreo de tráfico en mina.

## Qué incluye

Arquitectura distribuida mínima con **5 servicios/procesos**:

- **Gateway** (`app.main`)  
  expone la API pública, mantiene estado agregado y publica eventos WebSocket.
- **Ingest service** (`app.services_ingest`)  
  recibe posiciones y entregas.
- **Traffic-light service** (`app.services_traffic_light`)  
  administra semáforos y auditoría de cambios.
- **Congestion service** (`app.services_congestion`)  
  evalúa congestión por zona.
- **Report service** (`app.services_report`)  
  genera reportes desde SQLite.

Además:
- **Persistencia SQLite** lista desde el arranque (`data/mvts.db`).
- **Simulador mínimo de vehículos** que publica posiciones y genera entregas.
- **Monitor por consola** para observar eventos, cambiar semáforos y consultar resumen.
- **Script simple de arranque distribuido** para demo rápida.

## Estructura

```text
minehaul-control/
├── app/
│   ├── main.py                    # gateway / API pública
│   ├── services_ingest.py         # ingestión de posiciones y entregas
│   ├── services_traffic_light.py  # semáforos
│   ├── services_congestion.py     # detección de congestión
│   ├── services_report.py         # reportes
│   ├── gateway_state.py           # estado agregado para WebSocket/API pública
│   ├── congestion_runtime.py      # lógica de congestión
│   ├── models.py                  # contratos de mensajes
│   └── db.py                      # SQLite + schema
├── scripts/
│   ├── vehicle_simulator.py
│   ├── console_monitor.py
│   └── validate_mvp.py
├── data/
├── requirements.txt
├── start_distributed_mvp.sh
├── start_mvp.sh
└── README.md
```

## Flujo distribuido MVP

1. `vehicle_simulator.py` publica posiciones al **gateway**.
2. El gateway delega la ingestión al **ingest-service**.
3. El ingest-service publica el evento al **gateway** y pide evaluación al **congestion-service**.
4. El congestion-service consulta el estado agregado del gateway, detecta congestión y persiste si aplica.
5. Los cambios de semáforos van al **traffic-light-service**, que audita y publica evento al gateway.
6. El **report-service** arma el resumen desde SQLite.
7. El **gateway** retransmite todos los eventos por WebSocket al monitor.

## Requisitos

- Python 3.11+

## Opción rápida

```bash
cd /path/to/minehaul-control
./start_distributed_mvp.sh
```

Esto:
- crea `.venv` si no existe,
- instala dependencias,
- levanta los 5 servicios,
- arranca el simulador,
- abre el monitor en modo `watch`.

`./start_mvp.sh` quedó como alias al arranque distribuido.

## Ejecución manual

### 1) Preparar entorno

```bash
cd /path/to/minehaul-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Levantar servicios

```bash
source .venv/bin/activate
uvicorn app.services_traffic_light:app --host 127.0.0.1 --port 8002
uvicorn app.services_congestion:app --host 127.0.0.1 --port 8003
uvicorn app.services_report:app --host 127.0.0.1 --port 8004
uvicorn app.services_ingest:app --host 127.0.0.1 --port 8001
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3) En otra terminal, correr simulador

```bash
source .venv/bin/activate
python scripts/vehicle_simulator.py
```

### 4) En otra terminal, abrir monitor

```bash
source .venv/bin/activate
python scripts/console_monitor.py watch
```

## Comandos útiles del monitor

### Cambiar semáforo

```bash
source .venv/bin/activate
python scripts/console_monitor.py change-light TL-02 GREEN --by operador-demo
```

### Consultar resumen

```bash
source .venv/bin/activate
python scripts/console_monitor.py summary
```

## Validación funcional automática

```bash
cd /path/to/minehaul-control
source .venv/bin/activate
python scripts/validate_mvp.py
```

El script:
- levanta los servicios en puertos aislados,
- usa una base SQLite de validación separada,
- arranca el simulador,
- escucha eventos WebSocket desde el gateway,
- cambia un semáforo,
- consulta resumen,
- genera `validation_evidence.json`.

## API pública mínima

Token demo requerido en header `x-api-token: mvts-demo-token` para operaciones sensibles.

- `POST /api/vehicles/position`
- `POST /api/deliveries`
- `POST /api/traffic-lights/change`
- `GET /api/reports/summary`
- `GET /api/state`
- `WS /ws/events`

## Regla de congestión MVP

Se dispara un evento `congestion.detected` cuando:
- hay 3 o más vehículos en la misma zona,
- la velocidad promedio es `<= 1.0`,
- la condición dura al menos 5 segundos.

## Limitaciones actuales

- La distribución sigue siendo **mínima**: múltiples servicios HTTP locales, no mensajería avanzada.
- La base sigue siendo **SQLite compartida** para simplificar la demo.
- No hay autenticación real de usuarios, solo token estático de demo.
- El simulador usa rutas fijas en memoria.
- No hay mapa gráfico ni UI web.
- El reporte es un resumen simple.

## Siguiente mejora natural

- Contenerizar servicios con Docker Compose.
- Reemplazar SQLite por una BD/cola más alineada a producción.
- Añadir observabilidad básica por servicio.
- Separar eventos con broker si la rúbrica lo exige.
