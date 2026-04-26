# Minehaul Traffic Control

Construí este proyecto como un sistema distribuido para controlar y monitorear el tráfico de camiones en una mina. Lo separé en servicios pequeños para que cada parte tenga una responsabilidad clara: telemetría, semáforos, congestión, entregas, reportes, eventos y acceso externo.

Mi objetivo es que el sistema pueda ejecutarse localmente, pero que la arquitectura ya esté lista para moverse a procesos o nodos separados cambiando URLs y puertos.

## Qué hace

Trabajo con estos flujos principales:

- Recibo telemetría de vehículos en tiempo real por WebSocket.
- Mantengo el estado actual de cada camión por servicio.
- Cambio semáforos desde una estación central.
- Propago eventos internos con un broker de publicación-suscripción.
- Detecto y despejo congestiones a partir de eventos de posición.
- Registro entregas de material.
- Construyo reportes desde un modelo de lectura separado.
- Publico eventos en vivo hacia el monitor por WebSocket.
- Protejo rutas y canales con tokens por rol.

## Arquitectura actual

Organicé el backend en estos componentes:

- En `app.main` cargo el Gateway público.
- En `app.services_gateway` expongo la API principal, valido roles, consulto servicios internos y publico eventos al monitor externo.
- En `app.services_broker` manejo el broker interno de eventos por suscripción.
- En `app.services_telemetry` recibo posiciones, guardo el último estado de cada vehículo y publico `vehicle.position.updated`.
- En `app.services_traffic_light_controller` recibo órdenes del Gateway y las enruto al servicio de semáforos.
- En `app.services_traffic_light` mantengo el estado real de los semáforos, guardo auditoría y publico `traffic_light.changed`.
- En `app.services_congestion` consumo telemetría, evalúo zonas lentas y publico `congestion.detected` o `congestion.cleared`.
- En `app.services_delivery` registro entregas de material y publico `delivery.created`.
- En `app.report_consumer` consumo eventos de entregas y congestión para actualizar el modelo de reportes.
- En `app.services_report` respondo consultas de reportes leyendo solo su propia base.

Uso estos puertos por defecto:

```text
8000  Gateway API
8001  Telemetry Service
8002  Traffic-Light Device Service
8003  Congestion Service
8004  Report Service
8005  Event Broker
8006  Delivery Service
8007  Traffic-Light Controller
```

## Comunicación entre servicios

Uso cada mecanismo donde tiene más sentido:

- WebSocket para la telemetría continua del simulador hacia `Telemetry Service`.
- HTTP/REST para comandos, consultas y operaciones puntuales.
- Broker interno para eventos de dominio entre servicios.
- WebSocket externo del Gateway para que el monitor reciba eventos en vivo.

Con esta separación evito depender de polling constante y dejo que cada servicio publique lo que cambió cuando realmente ocurre.

## Persistencia

Separé la persistencia por responsabilidad:

- En `data/telemetry.db` guardo la última posición conocida por vehículo.
- En `data/traffic_light.db` guardo semáforos y auditoría de cambios.
- En `data/congestion.db` guardo congestiones activas e historial.
- En `data/delivery.db` guardo entregas de material.
- En `data/report.db` guardo el modelo de lectura para reportes.

Uso SQLite para mantener el proyecto fácil de correr, pero la separación ya evita una única base compartida para todo el sistema.

## Seguridad

Manejo autenticación con `Authorization: Bearer <token>` y roles separados.

Uso estos actores:

- Con `operator` consulto el estado operativo y cambio semáforos.
- Con `manager` consulto reportes gerenciales.
- Con `simulator` envío telemetría y registro entregas.
- Con `service` identifico llamadas internas entre componentes.

Tokens por defecto para uso local:

- Operador: `mvts-operator-token`
- Gerente: `mvts-manager-token`
- Simulador: `mvts-simulator-token`

También dejé tokens internos configurables por variables de entorno para gateway, broker, telemetría, semáforos, congestión, entregas, reportes y consumidor de reportes.

## Eventos

Publico estos eventos de dominio en el broker:

- `vehicle.position.updated`
- `traffic_light.changed`
- `delivery.created`
- `congestion.detected`
- `congestion.cleared`

## Flujos principales

Flujo de telemetría:

1. Desde el simulador abro un WebSocket contra `Telemetry Service`.
2. Envío posiciones de cada camión con zona, velocidad, coordenadas y destino.
3. En `Telemetry Service` guardo la última posición y publico `vehicle.position.updated`.
4. En `Congestion Service` consumo el evento y actualizo la evaluación de tráfico.
5. En `Gateway` consumo el mismo evento y lo retransmito al monitor externo.

Flujo de semáforos:

1. Como operador envío un cambio al Gateway.
2. En el Gateway valido el rol y llamo al `Traffic-Light Controller`.
3. En el controller valido el semáforo y enruto la orden al servicio de dispositivo.
4. En `Traffic-Light Device Service` cambio el estado, guardo auditoría y publico `traffic_light.changed`.
5. Desde el simulador consumo el cambio para ajustar el movimiento de los camiones.
6. Desde el Gateway retransmito el evento al monitor.

Flujo de entregas:

1. Desde el simulador registro una entrega en `Delivery Service`.
2. En `Delivery Service` persisto la entrega y publico `delivery.created`.
3. En `Report Consumer` consumo el evento y actualizo `report.db`.
4. Desde el Gateway retransmito la entrega al monitor.

Flujo de reportes:

1. En `Report Consumer` mantengo actualizado el modelo de lectura.
2. Consulto reportes desde el Gateway.
3. En el Gateway valido permisos y consulto `Report Service`.
4. En `Report Service` respondo desde `report.db` sin depender del broker en tiempo de consulta.

## API pública

Expongo estas rutas desde el Gateway:

- `GET /api/state`
- `GET /api/topology`
- `POST /api/vehicles/position`
- `POST /api/deliveries`
- `POST /api/traffic-lights/change`
- `GET /api/reports/summary`
- `GET /api/reports/material`
- `GET /api/reports/congestions`
- `WS /ws/events`

Mantengo `POST /api/vehicles/position` para cargas puntuales o pruebas. Para el flujo normal uso el WebSocket directo de telemetría.

## Estructura

```text
minehaul-traffic-control/
├── app/
│   ├── auth.py
│   ├── broker_client.py
│   ├── congestion_runtime.py
│   ├── gateway_state.py
│   ├── main.py
│   ├── material_catalog.py
│   ├── models.py
│   ├── persistence.py
│   ├── report_consumer.py
│   ├── service_config.py
│   ├── services_broker.py
│   ├── services_congestion.py
│   ├── services_delivery.py
│   ├── services_gateway.py
│   ├── services_report.py
│   ├── services_telemetry.py
│   ├── services_traffic_light.py
│   ├── services_traffic_light_controller.py
│   └── topology.py
├── scripts/
│   ├── console_monitor.py
│   ├── validate_mvp.py
│   └── vehicle_simulator.py
├── requirements.txt
├── start_distributed_mvp.ps1
└── start_distributed_mvp.sh
```

## Ejecución rápida en Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\start_distributed_mvp.ps1
```

Con el script abro ventanas separadas para el broker, servicios internos, Gateway, simulador y monitor.

## Ejecución manual

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_broker:app --host 127.0.0.1 --port 8005
```

Terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_telemetry:app --host 127.0.0.1 --port 8001
```

Terminal 3:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_traffic_light:app --host 127.0.0.1 --port 8002
```

Terminal 4:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_traffic_light_controller:app --host 127.0.0.1 --port 8007
```

Terminal 5:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_delivery:app --host 127.0.0.1 --port 8006
```

Terminal 6:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_congestion:app --host 127.0.0.1 --port 8003
```

Terminal 7:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.services_report:app --host 127.0.0.1 --port 8004
```

Terminal 8:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.report_consumer
```

Terminal 9:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 10:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\vehicle_simulator.py
```

Terminal 11:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\console_monitor.py watch
```

## Comandos útiles

Cambio un semáforo como operador:

```powershell
python scripts\console_monitor.py change-light TL-02 RED --by operador-demo
```

Consulto el resumen operativo:

```powershell
python scripts\console_monitor.py summary
```

Consulto material como gerente:

```powershell
python scripts\console_monitor.py --actor manager report-material day
```

Consulto congestiones como gerente:

```powershell
python scripts\console_monitor.py --actor manager report-congestions
```

## Validación

Valido el flujo completo con:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\validate_mvp.py
```

Con esta validación levanto servicios en puertos temporales y compruebo:

- bootstrap WebSocket del Gateway.
- eventos de telemetría.
- cambio de semáforo.
- registro de entrega.
- congestión detectada y despejada.
- persistencia por servicio.
- reportes gerenciales.
- autorización por rol.

Genero la evidencia en `validation_evidence.json`.
