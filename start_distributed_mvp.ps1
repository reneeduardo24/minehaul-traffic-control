$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path '.venv')) {
    py -m venv .venv
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Pip = Join-Path $Root '.venv\Scripts\pip.exe'

& $Pip install -r requirements.txt

$env:MVTS_GATEWAY_URL = if ($env:MVTS_GATEWAY_URL) { $env:MVTS_GATEWAY_URL } else { 'http://127.0.0.1:8000' }
$env:MVTS_TELEMETRY_URL = if ($env:MVTS_TELEMETRY_URL) { $env:MVTS_TELEMETRY_URL } else { 'http://127.0.0.1:8001' }
$env:MVTS_TRAFFIC_LIGHT_URL = if ($env:MVTS_TRAFFIC_LIGHT_URL) { $env:MVTS_TRAFFIC_LIGHT_URL } else { 'http://127.0.0.1:8002' }
$env:MVTS_TRAFFIC_LIGHT_CONTROLLER_URL = if ($env:MVTS_TRAFFIC_LIGHT_CONTROLLER_URL) { $env:MVTS_TRAFFIC_LIGHT_CONTROLLER_URL } else { 'http://127.0.0.1:8007' }
$env:MVTS_CONGESTION_URL = if ($env:MVTS_CONGESTION_URL) { $env:MVTS_CONGESTION_URL } else { 'http://127.0.0.1:8003' }
$env:MVTS_REPORT_URL = if ($env:MVTS_REPORT_URL) { $env:MVTS_REPORT_URL } else { 'http://127.0.0.1:8004' }
$env:MVTS_BROKER_URL = if ($env:MVTS_BROKER_URL) { $env:MVTS_BROKER_URL } else { 'http://127.0.0.1:8005' }
$env:MVTS_BROKER_WS_URL = if ($env:MVTS_BROKER_WS_URL) { $env:MVTS_BROKER_WS_URL } else { 'ws://127.0.0.1:8005/internal/events/ws' }
$env:MVTS_DELIVERY_URL = if ($env:MVTS_DELIVERY_URL) { $env:MVTS_DELIVERY_URL } else { 'http://127.0.0.1:8006' }
$env:MVTS_TELEMETRY_WS_URL = if ($env:MVTS_TELEMETRY_WS_URL) { $env:MVTS_TELEMETRY_WS_URL } else { 'ws://127.0.0.1:8001/ingest/telemetry/ws' }
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root;$env:PYTHONPATH" } else { $Root }

function ConvertTo-EncodedCommand {
    param([string]$Command)

    [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
}

function Join-PowerShellArguments {
    param([string[]]$Items)

    ($Items | ForEach-Object { "'" + ($_.Replace("'", "''")) + "'" }) -join ' '
}

function Start-MvtsWindow {
    param(
        [string]$Title,
        [string[]]$PythonArgs
    )

    $escapedTitle = $Title.Replace("'", "''")
    $escapedRoot = $Root.Replace("'", "''")
    $escapedPython = $Python.Replace("'", "''")
    $encodedArgs = Join-PowerShellArguments $PythonArgs
    $command = "`$Host.UI.RawUI.WindowTitle = '$escapedTitle'; Set-Location -LiteralPath '$escapedRoot'; & '$escapedPython' $encodedArgs; if (`$LASTEXITCODE -ne 0) { Write-Host ''; Write-Host 'Proceso finalizado. Revisa el error anterior.' -ForegroundColor Yellow; Read-Host 'Presiona Enter para cerrar' }"
    $encodedCommand = ConvertTo-EncodedCommand $command

    Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',$encodedCommand -PassThru
}

$windows = @()

$windows += Start-MvtsWindow 'MVTS 01 - Broker 8005' @('-m','uvicorn','app.services_broker:app','--host','127.0.0.1','--port','8005')
$windows += Start-MvtsWindow 'MVTS 02 - Telemetry Service 8001' @('-m','uvicorn','app.services_telemetry:app','--host','127.0.0.1','--port','8001')
$windows += Start-MvtsWindow 'MVTS 03 - Traffic-Lights Device 8002' @('-m','uvicorn','app.services_traffic_light:app','--host','127.0.0.1','--port','8002')
$windows += Start-MvtsWindow 'MVTS 04 - Traffic-Lights Controller 8007' @('-m','uvicorn','app.services_traffic_light_controller:app','--host','127.0.0.1','--port','8007')
$windows += Start-MvtsWindow 'MVTS 05 - Delivery Service 8006' @('-m','uvicorn','app.services_delivery:app','--host','127.0.0.1','--port','8006')
$windows += Start-MvtsWindow 'MVTS 06 - Congestion Service 8003' @('-m','uvicorn','app.services_congestion:app','--host','127.0.0.1','--port','8003')
$windows += Start-MvtsWindow 'MVTS 07 - Report Service 8004' @('-m','uvicorn','app.services_report:app','--host','127.0.0.1','--port','8004')
$windows += Start-MvtsWindow 'MVTS 08 - Report consumer' @('-m','app.report_consumer')

Start-Sleep -Seconds 2

$windows += Start-MvtsWindow 'MVTS 09 - Gateway API 8000' @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000')

Start-Sleep -Seconds 2

$windows += Start-MvtsWindow 'MVTS 10 - Vehicle Simulator' @('scripts\vehicle_simulator.py')
$windows += Start-MvtsWindow 'MVTS 11 - Monitor WS' @('scripts\console_monitor.py','watch')

Write-Host 'Proyecto iniciado en ventanas renombradas:'
Write-Host '  MVTS 01..11 identifican cada servicio, simulador y monitor.'
Write-Host '  Gateway: http://127.0.0.1:8000'
Write-Host '  Para detener el proyecto, cierra las ventanas MVTS abiertas.'
