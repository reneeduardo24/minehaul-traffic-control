# MVTS MVP Skeleton

MVP ejecutable para un sistema distribuido mínimo de monitoreo de tráfico en mina.

## Qué incluye

- **Servicio central FastAPI** con:
  - HTTP para posiciones, entregas, cambio de semáforos y reporte resumen.
  - WebSocket para broadcast de eventos en tiempo real.
- **Persistencia SQLite** lista desde el arranque (`data/mvts.db`).
- **Modelos JSON/Pydantic** para eventos, posiciones, semáforos, congestión y entregas.
- **Simulador mínimo de vehículos** que publica posiciones y genera entregas.
- **Monitor por consola** para observar eventos, cambiar semáforos y consultar resumen.
- **Script simple de arranque** para demo rápida.

## Estructura

```text
minehaul-control/
├── app/
│   ├── main.py          # servicio central
│   ├── models.py        # contratos de mensajes
│   ├── state.py         # estado en memoria + lógica MVP
│   └── db.py            # SQLite + schema
├── scripts/
│   ├── vehicle_simulator.py
│   └── console_monitor.py
├── data/
├── requirements.txt
├── start_mvp.sh
├── README.md
```

## Flujo MVP

1. `vehicle_simulator.py` publica posiciones por HTTP cada segundo.
2. El servicio central actualiza estado y emite eventos por WebSocket.
3. El monitor de consola escucha los eventos y los imprime.
4. Si en una zona hay 3+ vehículos lentos durante 5+ segundos, se registra una congestión.
5. Cuando un camión llega a `Z3`, el simulador registra una entrega en SQLite.
6. El operador puede cambiar un semáforo con un comando HTTP autenticado por token simple.

## Requisitos

- Python 3.11+

## Opción rápida

```bash
cd /path/to/minehaul-control
./start_mvp.sh
```

Esto:
- crea `.venv` si no existe,
- instala dependencias,
- levanta el servicio central,
- arranca el simulador,
- abre el monitor en modo `watch`.

## Ejecución manual

### 1) Preparar entorno

```bash
cd /path/to/minehaul-control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Levantar servicio central

```bash
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
- levanta el servicio en un puerto aislado,
- usa una base SQLite de validación separada,
- arranca el simulador,
- escucha eventos WebSocket,
- cambia un semáforo,
- consulta resumen,
- genera `validation_evidence.json`.

## API mínima

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

- El sistema distribuido está simplificado a **un servicio central + procesos clientes**.
- No hay autenticación real de usuarios, solo token estático de demo.
- El simulador usa rutas fijas en memoria.
- No hay mapa gráfico ni UI web.
- El reporte es un resumen simple, no agregación completa por día/semana/mes.
- La detección de congestión es deliberadamente básica para la demo.

## TODOs concretos

- Separar `traffic_light_service`, `congestion_service` y `report_service` en procesos independientes si el curso exige distribución física más explícita.
- Añadir reportes diarios/semanales/mensuales con consultas agregadas.
- Persistir histórico de posiciones si se necesita trazabilidad completa.
- Reemplazar token fijo por auth más formal si el alcance crece.
- Agregar stub específico de semáforo autónomo si se quiere mostrar otro cliente publicando estados.
