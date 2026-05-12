$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$out = Join-Path $root "output\tester"
$spec = Join-Path $root "agency\qa\dev_test.spec.ts"

New-Item -ItemType Directory -Force $out | Out-Null
Set-Location $root

.\.venv\Scripts\python.exe -m server.scripts.check_seed scenarios/dev_test

if (-not (Test-Path $spec)) {
  throw "missing agency\qa\dev_test.spec.ts"
}

$occupied = Get-NetTCPConnection -LocalPort 8001,8081 -ErrorAction SilentlyContinue |
  Where-Object { $_.State -eq "Listen" }
if ($occupied) {
  $occupied | Select-Object LocalPort,State,OwningProcess | Format-Table | Out-String | Write-Host
  throw "ports 8001/8081 are already in use"
}

$server = Start-Process `
  -FilePath "$root\.venv\Scripts\python.exe" `
  -ArgumentList "run_api.py" `
  -WorkingDirectory "$root\server" `
  -RedirectStandardOutput "$out\server.stdout.log" `
  -RedirectStandardError "$out\server.stderr.log" `
  -WindowStyle Hidden `
  -PassThru

$client = Start-Process `
  -FilePath "npm.cmd" `
  -ArgumentList "run","web" `
  -WorkingDirectory "$root\client" `
  -RedirectStandardOutput "$out\client.stdout.log" `
  -RedirectStandardError "$out\client.stderr.log" `
  -WindowStyle Hidden `
  -PassThru

try {
  $deadline = (Get-Date).AddSeconds(90)
  do {
    Start-Sleep -Seconds 2
    $serverReady = $false
    $clientReady = $false
    try { $serverReady = (Invoke-WebRequest -Uri "http://127.0.0.1:8001/docs" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
    try { $clientReady = (Invoke-WebRequest -Uri "http://localhost:8081" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
  } until (($serverReady -and $clientReady) -or (Get-Date) -gt $deadline)

  if (-not ($serverReady -and $clientReady)) {
    throw "server/client did not become ready within 90 seconds"
  }

  playwright --version
  $env:NODE_PATH = npm root -g
  playwright test agency/qa/dev_test.spec.ts --browser=chromium
  if ($LASTEXITCODE -ne 0) {
    throw "playwright test failed with exit code $LASTEXITCODE"
  }
}
finally {
  $owners = Get-NetTCPConnection -LocalPort 8001,8081 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -ne 0 }
  if ($owners) {
    Stop-Process -Id $owners -Force -ErrorAction SilentlyContinue
  }
  Stop-Process -Id $server.Id,$client.Id -Force -ErrorAction SilentlyContinue
}
