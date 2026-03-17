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
$env:MVTS_INGEST_URL = if ($env:MVTS_INGEST_URL) { $env:MVTS_INGEST_URL } else { 'http://127.0.0.1:8001' }
$env:MVTS_TRAFFIC_LIGHT_URL = if ($env:MVTS_TRAFFIC_LIGHT_URL) { $env:MVTS_TRAFFIC_LIGHT_URL } else { 'http://127.0.0.1:8002' }
$env:MVTS_CONGESTION_URL = if ($env:MVTS_CONGESTION_URL) { $env:MVTS_CONGESTION_URL } else { 'http://127.0.0.1:8003' }
$env:MVTS_REPORT_URL = if ($env:MVTS_REPORT_URL) { $env:MVTS_REPORT_URL } else { 'http://127.0.0.1:8004' }

$procs = @()

$procs += Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.services_traffic_light:app','--host','127.0.0.1','--port','8002' -PassThru
$procs += Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.services_congestion:app','--host','127.0.0.1','--port','8003' -PassThru
$procs += Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.services_report:app','--host','127.0.0.1','--port','8004' -PassThru
$procs += Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.services_ingest:app','--host','127.0.0.1','--port','8001' -PassThru

Start-Sleep -Seconds 2

$procs += Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -PassThru

Start-Sleep -Seconds 2

$procs += Start-Process -FilePath $Python -ArgumentList 'scripts\vehicle_simulator.py' -PassThru

try {
    & $Python 'scripts\console_monitor.py' 'watch'
}
finally {
    foreach ($proc in $procs) {
        if ($null -ne $proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
