# MVTS Distributed MVP

MVP ejecutable para un **sistema distribuido mínimo** de monitoreo de tráfico en mina.

## Resumen

El proyecto modela un escenario básico de control operativo en mina donde varios servicios cooperan para:
- recibir posiciones de camiones,
- detectar congestión,
- cambiar semáforos,
- registrar entregas de material,
- generar reportes,
- y publicar eventos en tiempo real.

La implementación actual ya está separada en procesos por responsabilidad, de modo que el sistema **se presenta como arquitectura distribuida mínima**, no como un monolito único.

## Arquitectura

Servicios principales:
- **Gateway** (`app.main`) → API pública, estado agregado, WebSocket
- **Ingest service** (`app.services_ingest`) → posiciones y entregas
- **Traffic-light service** (`app.services_traffic_light`) → control de semáforos
- **Congestion service** (`app.services_congestion`) → detección de congestión
- **Report service** (`app.services_report`) → resumen y consulta de datos

Documentación de arquitectura:
- `docs/ARCHITECTURE.md`

### Diagrama rápido

```mermaid
flowchart LR
    SIM[Vehicle Simulator] -->|POST /api/vehicles/position| GW[Gateway]
    SIM -->|POST /api/deliveries| GW
    MON[Console Monitor] <-->|WS /ws/events| GW
    MON -->|summary / change-light| GW

    GW --> ING[Ingest Service]
    GW --> TL[Traffic Light Service]
    GW --> REP[Report Service]

    ING -->|trigger evaluate| CONG[Congestion Service]
    ING --> DB[(SQLite)]
    TL --> DB
    CONG --> DB
    REP --> DB
    ING --> GW
    TL --> GW
    CONG --> GW
```

## Qué incluye

- **5 servicios/procesos** con responsabilidad separada
- **Persistencia SQLite** (`data/mvts.db`)
- **WebSocket** para eventos en tiempo real
- **Simulador de vehículos**
- **Monitor por consola**
- **Validación funcional automática**
- **Script de arranque distribuido**

## Estructura

```text
minehaul-control/
├── app/
│   ├── main.py                    # gateway / API pública
│   ├── services_ingest.py         # ingestión de posiciones y entregas
│   ├── services_traffic_light.py  # semáforos
│   ├── services_congestion.py     # detección de congestión
│   ├── services_report.py         # reportes
│   ├── gateway_state.py           # estado agregado
│   ├── congestion_runtime.py      # lógica de congestión
│   ├── models.py                  # contratos de mensajes
│   ├── service_config.py          # configuración de URLs/tokens
│   └── db.py                      # SQLite + schema
├── docs/
│   └── ARCHITECTURE.md
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

## Sobre la base de datos SQLite

La base **sí es una base de datos real**.

No necesitas instalar un servidor aparte como MySQL o PostgreSQL. En SQLite, la base vive en un **archivo** (`data/mvts.db`) y Python la usa directamente mediante la librería estándar `sqlite3`.

Eso significa:
- el archivo `.db` **ya es la base de datos**,
- no hace falta levantar un servicio externo,
- las tablas se crean automáticamente al arrancar,
- mientras exista ese archivo, los datos persisten.

En otras palabras: para este proyecto, SQLite es totalmente válida como persistencia real del MVP.

## Limitaciones actuales

- La distribución sigue siendo **mínima**: múltiples servicios HTTP locales, no mensajería avanzada.
- La base sigue siendo **SQLite compartida** para simplificar la demo.
- No hay autenticación real de usuarios, solo token estático de demo.
- El simulador usa rutas fijas en memoria.
- No hay mapa gráfico ni UI web.
- El reporte es un resumen simple.

## Siguiente mejora natural

- evidencia visual de demo,
- documento corto de entrega,
- Docker Compose,
- observabilidad básica,
- broker/event bus si la rúbrica lo exige.
