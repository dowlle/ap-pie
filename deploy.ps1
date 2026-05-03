# deploy.ps1 -- Deploy Archipelago Pie to a remote host
#
# Usage:
#   $env:DEPLOY_SERVER="user@host"; .\deploy.ps1   # git pull + docker compose up --build -d
#   .\deploy.ps1 -NoPull                            # skip git pull, just rebuild & restart
#   .\deploy.ps1 -LogsOnly                          # tail container logs (no deploy)
#
# Requirements: SSH key access to $env:DEPLOY_SERVER.

param(
    [switch]$NoPull,
    [switch]$LogsOnly
)

if (-not $env:DEPLOY_SERVER) {
    Write-Host "Set DEPLOY_SERVER (e.g. user@host) before running deploy.ps1" -ForegroundColor Red
    exit 1
}
$Server    = $env:DEPLOY_SERVER
$RemoteDir = if ($env:DEPLOY_DIR)       { $env:DEPLOY_DIR }       else { "~/ap-pie" }
$Container = if ($env:DEPLOY_CONTAINER) { $env:DEPLOY_CONTAINER } else { "ap-pie-ap-web-1" }

function Info($msg)    { Write-Host "==> $msg" -ForegroundColor Cyan }
function OK($msg)      { Write-Host " OK $msg"  -ForegroundColor Green }
function Step($msg)    { Write-Host "    $msg"  -ForegroundColor Gray }

if ($LogsOnly) {
    Info "Tailing logs on $Server..."
    ssh $Server "docker logs --tail 50 -f $Container"
    exit 0
}

Info "Deploying Archipelago Pie -> ${Server}:${RemoteDir}"
Write-Host ""

# 1. Git pull
if ($NoPull) {
    Step "Skipping git pull (-NoPull)"
} else {
    Info "Pulling latest code..."
    ssh $Server "cd $RemoteDir ; git pull --ff-only"
    if ($LASTEXITCODE -ne 0) { Write-Host "git pull failed" -ForegroundColor Red; exit 1 }
    OK "Code up to date"
    Write-Host ""
}

# 2. Docker build + restart
Info "Building and restarting containers..."
ssh $Server "cd $RemoteDir ; docker compose up --build -d"
if ($LASTEXITCODE -ne 0) { Write-Host "docker compose failed" -ForegroundColor Red; exit 1 }
OK "Containers restarted"
Write-Host ""

# 3. Health check
Info "Waiting for app to come up..."
$healthy = $false
for ($i = 1; $i -le 10; $i++) {
    $result = ssh $Server "curl -sf http://localhost:5001/api/apworlds/installed > /dev/null 2>&1 ; echo `$?"
    if ($result -eq "0") {
        OK "App is healthy (port 5001 responding)"
        $healthy = $true
        break
    }
    if ($i -eq 10) {
        Write-Host "  App did not respond after 10 attempts -- check logs below" -ForegroundColor Yellow
    } else {
        Step "Attempt $i/10, retrying in 3s..."
        Start-Sleep -Seconds 3
    }
}
Write-Host ""

# 4. Recent logs
Info "Recent container logs:"
Write-Host ("=" * 50)
ssh $Server "docker logs --since 30s $Container 2>&1 | tail -40"
Write-Host ("=" * 50)
Write-Host ""
OK "Deploy complete!"
