param(
    [int]$Port = 8000,
    [string]$ModelId = "gemma4",
    [string]$CloudflaredLogDir = (Join-Path $env:TEMP "trpg-release"),
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib.ps1")

Assert-Env "RENDER_API_KEY" "RENDER_API_KEY is not set. Set it to your Render API key before running this script."
Assert-Env "RENDER_SERVICE_ID" "RENDER_SERVICE_ID is not set. Set it to your Render backend service id before running this script."

function Get-FileText {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return Get-Content -LiteralPath $Path -Raw
    }
    return ""
}

function Invoke-RenderApi {
    param(
        [string]$ServiceId,
        [hashtable]$Headers,
        [string]$Method,
        [string]$Path,
        [object]$Body
    )
    $request = @{
        Method = $Method
        Uri = "https://api.render.com/v1/services/$ServiceId/$Path"
        Headers = $Headers
    }
    if ($null -ne $Body) {
        $request.Body = $Body | ConvertTo-Json -Compress
    }
    Invoke-RestMethod @request | Out-Null
}

New-Item -ItemType Directory -Path $CloudflaredLogDir -Force | Out-Null

$outLog = Join-Path $CloudflaredLogDir "cloudflared.out.log"
$errLog = Join-Path $CloudflaredLogDir "cloudflared.err.log"
Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue

$origin = "http://127.0.0.1:$Port"
$cloudflared = Start-Process `
    -FilePath "cloudflared" `
    -ArgumentList @("tunnel", "--url", $origin) `
    -WorkingDirectory $CloudflaredLogDir `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

try {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $tunnelUrl = $null
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        $text = (Get-FileText $outLog) + (Get-FileText $errLog)

        $match = [regex]::Match($text, "https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            $tunnelUrl = $match.Value
            break
        }
    }

    if (-not $tunnelUrl) {
        throw "Could not find a trycloudflare URL in cloudflared output."
    }

    $modelsUrl = "$tunnelUrl/v1/models"
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-RestMethod -Method Get -Uri $modelsUrl -TimeoutSec 20 | Out-Null
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }

    if (-not $ready) {
        throw "Cloudflare tunnel URL was created, but $modelsUrl did not become reachable."
    }

    $llmBaseUrl = "$tunnelUrl/v1"
    $headers = @{
        Authorization = "Bearer $env:RENDER_API_KEY"
        Accept = "application/json"
        "Content-Type" = "application/json"
    }

    $serviceId = $env:RENDER_SERVICE_ID
    $envVars = @{
        LLM_ROUTE_DEFAULT = "local/$ModelId"
        LLM_LOCAL_BASE_URL = $llmBaseUrl
        LLM_LOCAL_API_KEYS = "llama-cpp"
        LLM_LOCAL_THINK_OPT = $ModelId
    }

    foreach ($name in $envVars.Keys) {
        Invoke-RenderApi -ServiceId $serviceId -Headers $headers -Method Put -Path "env-vars/$name" -Body @{ value = $envVars[$name] }
    }

    Invoke-RenderApi -ServiceId $serviceId -Headers $headers -Method Post -Path "deploys" -Body @{ deployMode = "deploy_only" }

    Write-Host "Render LLM URL updated: $llmBaseUrl"
    Write-Host "Model route: local/$ModelId"
    Write-Host "Deploy triggered for service $serviceId."
    Write-Host "Leave this window open while Render uses the local LLM."
    Wait-Process -Id $cloudflared.Id
}
finally {
    if ($cloudflared -and -not $cloudflared.HasExited) {
        Stop-Process -Id $cloudflared.Id -Force -ErrorAction SilentlyContinue
    }
}
