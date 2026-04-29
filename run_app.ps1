Write-Host "Starting Retail POS..."
$root = $PSScriptRoot

function Kill-Port($port) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $pid_to_kill = $conn.OwningProcess
            if ($pid_to_kill -ne 0) {
                Write-Host "Killing process on port $port (PID: $pid_to_kill)..."
                Stop-Process -Id $pid_to_kill -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Host "Port $port is free."
    }
}

# Clear ports
Write-Host "Checking ports..."
Kill-Port 8000
Kill-Port 8080
Kill-Port 8081

# Start Backend
Write-Host "Launching Backend (Port 8000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; py -m poetry run uvicorn app.api.main:app --reload --port 8000"

# Wait for backend to init
Write-Host "Waiting for backend to initialize..."
Start-Sleep -Seconds 5

# Start Frontend
Write-Host "Launching Frontend (Port 8080)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\modern_client'; py -m poetry run python main.py"

# Start SuperAdmin Portal
Write-Host "Launching SuperAdmin Portal (Port 8081)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\super_admin_client'; py -m poetry run python main.py"

Write-Host "Done! Check the new windows."
