# Arquitectura - MVTS Distributed MVP

## Objetivo

Este proyecto implementa un **sistema distribuido mínimo** para monitoreo de tráfico en mina.

El sistema permite:
- recibir posiciones de vehículos,
- detectar congestión en zonas críticas,
- administrar semáforos,
- registrar entregas de material,
- generar reportes resumidos,
- publicar eventos en tiempo real para monitoreo.

## Decisión de arquitectura

Se eligió una arquitectura **multi-servicio simple por HTTP** en lugar de un monolito único.

La idea no fue construir microservicios complejos de producción, sino una separación suficiente para demostrar:
- responsabilidades independientes,
- comunicación entre procesos,
- estado agregado para monitoreo,
- persistencia común,
- validación extremo a extremo.

## Componentes

### 1. Gateway
Archivo: `app/main.py`

Responsabilidades:
- expone la API pública,
- recibe solicitudes externas,
- mantiene un estado agregado en memoria,
- retransmite eventos por WebSocket,
- actúa como punto de entrada del sistema.

### 2. Ingest Service
Archivo: `app/services_ingest.py`

Responsabilidades:
- recibir posiciones de vehículos,
- recibir entregas de material,
- persistir entregas,
- publicar eventos de posición y entrega,
- disparar evaluación de congestión.

### 3. Traffic Light Service
Archivo: `app/services_traffic_light.py`

Responsabilidades:
- administrar estados de semáforos,
- auditar cambios realizados por el operador,
- publicar eventos de cambio de semáforo.

### 4. Congestion Service
Archivo: `app/services_congestion.py`

Responsabilidades:
- consultar el estado agregado del gateway,
- evaluar congestión por zona,
- persistir eventos de congestión,
- publicar eventos cuando se detecta congestión.

### 5. Report Service
Archivo: `app/services_report.py`

Responsabilidades:
- consultar la base SQLite,
- construir el reporte resumen del sistema,
- exponer una interfaz interna de consulta.

### 6. Vehicle Simulator
Archivo: `scripts/vehicle_simulator.py`

Responsabilidades:
- simular camiones en ruta,
- generar posiciones periódicas,
- generar entregas al llegar a destino.

### 7. Console Monitor
Archivo: `scripts/console_monitor.py`

Responsabilidades:
- escuchar eventos WebSocket,
- mostrar estado inicial y cambios en tiempo real,
- permitir consulta de resumen,
- permitir cambio manual de semáforos.

## Diagrama de arquitectura

```mermaid
flowchart LR
    SIM[Vehicle Simulator] -->|POST /api/vehicles/position| GW[Gateway]
    SIM -->|POST /api/deliveries| GW
    MON[Console Monitor] <-->|WS /ws/events| GW
    MON -->|summary / change-light| GW

    GW -->|forward position/delivery| ING[Ingest Service]
    GW -->|forward traffic-light change| TL[Traffic Light Service]
    GW -->|GET summary| REP[Report Service]

    ING -->|event: vehicle.position.updated| GW
    ING -->|event: delivery.created| GW
    ING -->|trigger evaluate zone| CONG[Congestion Service]

    CONG -->|GET /api/state| GW
    CONG -->|event: congestion.detected| GW

    TL -->|event: traffic_light.changed| GW

    ING --> DB[(SQLite)]
    TL --> DB
    CONG --> DB
    REP --> DB
```

## Flujo principal

### Flujo de posiciones
1. El simulador envía una posición al gateway.
2. El gateway reenvía la solicitud al ingest service.
3. El ingest service publica un evento `vehicle.position.updated` en el gateway.
4. El gateway actualiza su estado agregado y retransmite el evento al monitor.
5. El ingest service solicita evaluación de congestión para la zona afectada.
6. El congestion service consulta el estado del gateway.
7. Si corresponde, registra un evento `congestion.detected` en SQLite y lo publica vía gateway.

### Flujo de entregas
1. El simulador envía una entrega al gateway.
2. El gateway delega al ingest service.
3. El ingest service persiste la entrega en SQLite.
4. El ingest service publica el evento `delivery.created` al gateway.
5. El gateway retransmite el evento al monitor.

### Flujo de semáforos
1. El operador ejecuta un cambio desde el monitor.
2. El gateway reenvía la orden al traffic-light service.
3. El servicio actualiza el estado y registra auditoría en SQLite.
4. El servicio publica un evento `traffic_light.changed` al gateway.
5. El gateway actualiza su estado agregado y retransmite el evento.

### Flujo de reportes
1. El operador consulta resumen.
2. El gateway solicita el resumen al report service.
3. El report service consulta SQLite.
4. El resultado vuelve al operador por la API pública.

## Persistencia

Se usa **SQLite** como base de datos persistente del MVP.

Tablas principales:
- `traffic_lights`
- `material_deliveries`
- `congestion_events`
- `traffic_light_audit`

### Justificación

SQLite se eligió porque:
- simplifica la ejecución local,
- no requiere servidor adicional,
- permite persistencia real en archivo,
- reduce complejidad para una demo académica.

### Limitación reconocida

En esta versión, varios servicios comparten la misma base SQLite. Eso es válido para un MVP académico, pero en una arquitectura de producción normalmente se evaluaría:
- una BD dedicada por servicio,
- un broker de eventos,
- o una capa más robusta de integración.

## Por qué sí cuenta como sistema distribuido mínimo

Este proyecto ya no es un monolito único porque:
- existen **múltiples procesos/servicios separados**,
- cada servicio tiene **una responsabilidad específica**,
- la interacción ocurre por **HTTP entre procesos**,
- el monitoreo usa **eventos WebSocket**,
- la lógica está desacoplada por componente.

Aunque corre localmente en la misma máquina, el diseño es trasladable a nodos distintos cambiando URLs y puertos.

## Validación realizada

El proyecto incluye `scripts/validate_mvp.py`, que valida automáticamente:
- arranque de servicios,
- recepción de eventos WebSocket,
- posiciones de vehículos,
- entregas,
- detección de congestión,
- cambio de semáforo,
- persistencia de datos,
- generación de resumen.

La evidencia se guarda en:
- `validation_evidence.json`

## Limitaciones del MVP

- no hay broker de mensajería,
- no hay autenticación real de usuarios,
- la persistencia está centralizada en SQLite,
- no hay tolerancia a fallos distribuida,
- no hay interfaz gráfica web,
- el simulador usa rutas predefinidas.

## Mejoras futuras

- Docker Compose para desplegar servicios separados,
- base de datos más robusta,
- broker de eventos,
- UI web operativa,
- métricas y observabilidad,
- desacoplamiento completo de persistencia por servicio.
