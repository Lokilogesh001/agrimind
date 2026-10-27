# AgriMind Unified Application Launcher
# Usage: .\start.ps1

$ErrorActionPreference = "Stop"

# Determine project paths from script location (handles paths with spaces)
$Root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$WebDir = Join-Path $Root "web"

function Write-AgriLog ($Message, $Color = "Cyan") {
    Write-Host "[AgriMind] $Message" -ForegroundColor $Color
}

function Write-AgriErr ($Message) {
    Write-Host "[AgriMind] ERROR: $Message" -ForegroundColor Red
}

function Stop-ProcessTree ($ProcessId) {
    if (-not $ProcessId) { return }
    try {
        $p = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($p -and -not $p.HasExited) {
            & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
        }
    } catch {
        # Process already terminated
    }
}

function Stop-PortProcess ($Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            $pidToKill = $conn.OwningProcess
            if ($pidToKill -and $pidToKill -ne 0 -and $pidToKill -ne $PID) {
                & taskkill.exe /PID $pidToKill /T /F 2>$null | Out-Null
            }
        }
    } catch {}
}

# 1. Discover Python / Virtual Environment
$PythonCandidates = @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path $Root "venv\Scripts\python.exe"),
    (Join-Path $Root "env\Scripts\python.exe")
)

if ($env:VIRTUAL_ENV) {
    $PythonCandidates = @((Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")) + $PythonCandidates
}

$PythonExe = $null
foreach ($candidate in $PythonCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        $PythonExe = $candidate
        break
    }
}

if (-not $PythonExe) {
    $sysPython = Get-Command "python" -ErrorAction SilentlyContinue
    if ($sysPython) {
        $PythonExe = $sysPython.Source
    } else {
        $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
        if ($pyLauncher) {
            $PythonExe = $pyLauncher.Source
        }
    }
}

if (-not $PythonExe) {
    Write-AgriErr "Python was not found. Please install Python 3.10+ or create a virtual environment in .venv."
    exit 1
}

# Verify Python requirements
& "$PythonExe" -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-AgriErr "Required Python packages (fastapi, uvicorn) are not available in $PythonExe."
    Write-Host "[AgriMind] Please run: pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# 2. Discover Frontend Directory and npm
$FrontendCandidateDirs = @(
    (Join-Path $Root "web"),
    (Join-Path $Root "frontend"),
    (Join-Path $Root "client"),
    $Root
)

$WebDir = $null
foreach ($dir in $FrontendCandidateDirs) {
    if (Test-Path -LiteralPath (Join-Path $dir "package.json")) {
        $WebDir = $dir
        break
    }
}

if (-not $WebDir) {
    Write-AgriErr "Frontend directory containing package.json was not found."
    exit 1
}

# Discover Backend Entry Point
$BackendApp = $null
if (Test-Path -LiteralPath (Join-Path $Root "api\main.py")) {
    $BackendApp = "api.main:app"
} elseif (Test-Path -LiteralPath (Join-Path $Root "main.py")) {
    $BackendApp = "main:app"
} else {
    Write-AgriErr "Backend entry point (api/main.py or main.py) not found."
    exit 1
}

$NpmCmd = (Get-Command "npm.cmd" -ErrorAction SilentlyContinue).Source
if (-not $NpmCmd) {
    $NpmCmd = (Get-Command "npm" -ErrorAction SilentlyContinue).Source
}
if (-not $NpmCmd) {
    Write-AgriErr "'npm' command was not found in PATH. Please install Node.js."
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $WebDir "node_modules"))) {
    Write-Host "[AgriMind] node_modules not found in web directory. Running npm install..." -ForegroundColor Yellow
    Push-Location $WebDir
    try {
        & "$NpmCmd" install
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Write-AgriErr "Frontend dependencies installation failed."
        exit 1
    }
}

# 3. Check and clean up pre-existing port conflicts
function Test-PortListening ($Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $wait = $connect.AsyncWaitHandle.WaitOne(200, $false)
        if ($wait) {
            $client.EndConnect($connect)
            $client.Close()
            return $true
        }
        $client.Close()
    } catch {}
    return $false
}

if (Test-PortListening 8000) {
    Write-AgriLog "Port 8000 is occupied by a stale process. Releasing..." "Yellow"
    Stop-PortProcess 8000
    Start-Sleep -Milliseconds 600
}

if (Test-PortListening 3000) {
    Write-AgriLog "Port 3000 is occupied by a stale process. Releasing..." "Yellow"
    Stop-PortProcess 3000
    Start-Sleep -Milliseconds 600
}

# 4. Prepare Logs and Start Child Processes
$LogsDir = Join-Path $Root "logs"
if (-not (Test-Path -LiteralPath $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}
$BackendLog = Join-Path $LogsDir "backend.log"
# Clear previous run log
if (Test-Path -LiteralPath $BackendLog) {
    Remove-Item -LiteralPath $BackendLog -Force -ErrorAction SilentlyContinue
}

$backendProc = $null
$frontendProc = $null

try {
    # Start Backend with unbuffered diagnostics redirected to log
    Write-AgriLog "Starting backend (logging to $BackendLog)..."
    $backendInfo = New-Object System.Diagnostics.ProcessStartInfo
    $backendInfo.FileName = "cmd.exe"
    $backendInfo.Arguments = "/c `"`"$PythonExe`" -u -m uvicorn $BackendApp --host 127.0.0.1 --port 8000 > `"$BackendLog`" 2>&1`""
    $backendInfo.WorkingDirectory = $Root
    $backendInfo.UseShellExecute = $false
    $backendProc = [System.Diagnostics.Process]::Start($backendInfo)

    if (-not $backendProc -or $backendProc.HasExited) {
        Write-AgriErr "Failed to launch backend process."
        exit 1
    }
    Write-AgriLog "Backend spawned with PID $($backendProc.Id)." "Cyan"

    # Start Frontend
    Write-AgriLog "Starting frontend..."
    $frontendInfo = New-Object System.Diagnostics.ProcessStartInfo
    $frontendInfo.FileName = $NpmCmd
    $frontendInfo.Arguments = "run dev"
    $frontendInfo.WorkingDirectory = $WebDir
    $frontendInfo.UseShellExecute = $false
    $frontendProc = [System.Diagnostics.Process]::Start($frontendInfo)

    if (-not $frontendProc -or $frontendProc.HasExited) {
        Write-AgriErr "Failed to launch frontend process."
        exit 1
    }
    Write-AgriLog "Frontend spawned with PID $($frontendProc.Id)." "Cyan"

    # 5. Wait for readiness
    $backendReady = $false
    $frontendReady = $false
    $timeoutSeconds = if ($env:AGRIMIND_STARTUP_TIMEOUT) { [int]$env:AGRIMIND_STARTUP_TIMEOUT } else { 60 }
    $startTime = [System.Diagnostics.Stopwatch]::StartNew()
    $lastReport = 0

    while ($startTime.Elapsed.TotalSeconds -lt $timeoutSeconds) {
        if ($backendProc.HasExited) {
            Write-AgriErr "Backend process exited prematurely with exit code $($backendProc.ExitCode)."
            if (Test-Path -LiteralPath $BackendLog) {
                Write-Host "`n--- Backend Diagnostic Traceback ---" -ForegroundColor Yellow
                Get-Content -LiteralPath $BackendLog -Tail 30
                Write-Host "------------------------------------`n" -ForegroundColor Yellow
            }
            Write-Host "[AgriMind] ACTION: Check $BackendLog for details." -ForegroundColor Yellow
            exit 1
        }
        if ($frontendProc.HasExited) {
            Write-AgriErr "Frontend process exited prematurely with code $($frontendProc.ExitCode)."
            exit 1
        }

        # Check backend with fast non-blocking TCP check followed by HTTP health query
        if (-not $backendReady) {
            if (Test-PortListening 8000) {
                try {
                    $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:8000/health")
                    $req.Timeout = 1500
                    $resp = $req.GetResponse()
                    if ($resp -and [int]$resp.StatusCode -eq 200) {
                        $backendReady = $true
                    }
                    $resp.Close()
                } catch {
                    # Port open, app still warming up lifespan
                }
            }
        }

        # Check frontend
        if (-not $frontendReady) {
            if (Test-PortListening 3000) {
                $frontendReady = $true
            }
        }

        if ($backendReady -and $frontendReady) {
            break
        }

        # Progress reporting every 5 seconds
        $elapsedSec = [int]$startTime.Elapsed.TotalSeconds
        if ($elapsedSec -ge ($lastReport + 5)) {
            $lastReport = $elapsedSec
            $waitTarget = if (-not $backendReady) { "backend API" } else { "frontend server" }
            Write-AgriLog "Waiting for $waitTarget to initialize... (${elapsedSec}s / ${timeoutSeconds}s)" "Yellow"
        }

        Start-Sleep -Milliseconds 400
    }

    if (-not $backendReady) {
        Write-AgriErr "Backend failed to become healthy on http://127.0.0.1:8000 within $timeoutSeconds seconds."
        if (Test-Path -LiteralPath $BackendLog) {
            Write-Host "`n--- Last 30 Lines of Backend Log ---" -ForegroundColor Yellow
            Get-Content -LiteralPath $BackendLog -Tail 30
            Write-Host "------------------------------------`n" -ForegroundColor Yellow
        }
        Write-Host "[AgriMind] ACTION: Set AGRIMIND_STARTUP_TIMEOUT=90 if model initialization needs more time." -ForegroundColor Yellow
        exit 1
    }

    if (-not $frontendReady) {
        Write-AgriErr "Frontend failed to start on http://localhost:3000 within $timeoutSeconds seconds."
        exit 1
    }

    Write-AgriLog "Backend API:  http://127.0.0.1:8000 (Swagger: http://127.0.0.1:8000/docs)" "Green"
    Write-AgriLog "Frontend Web: http://localhost:3000" "Green"
    Write-Host "[AgriMind] Both services are running smoothly. Press Ctrl+C to terminate." -ForegroundColor Cyan

    # 6. Keep both running simultaneously and monitor lifecycle
    while (-not $backendProc.HasExited -and -not $frontendProc.HasExited) {
        Start-Sleep -Milliseconds 500
    }

    if ($backendProc.HasExited) {
        Write-AgriErr "Backend stopped unexpectedly (exit code $($backendProc.ExitCode))."
    }
    if ($frontendProc.HasExited) {
        Write-AgriErr "Frontend stopped unexpectedly (exit code $($frontendProc.ExitCode))."
    }
}
finally {
    Write-Host "`n[AgriMind] Shutting down services..." -ForegroundColor Yellow
    if ($backendProc) {
        Stop-ProcessTree -ProcessId $backendProc.Id
    }
    if ($frontendProc) {
        Stop-ProcessTree -ProcessId $frontendProc.Id
    }
    Stop-PortProcess 8000
    Stop-PortProcess 3000
    Write-Host "[AgriMind] All services stopped cleanly." -ForegroundColor Green
}

