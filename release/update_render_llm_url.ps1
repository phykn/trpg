param(
    [int]$Port = 8000,
    [string]$ModelId = "qwen35-9b",
    [string]$CloudflaredLogDir = $PSScriptRoot,
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

if (-not $env:RENDER_API_KEY) {
    throw "RENDER_API_KEY is not set. Set it to your Render API key before running this script."
}
if (-not $env:RENDER_SERVICE_ID) {
    throw "RENDER_SERVICE_ID is not set. Set it to your Render backend service id before running this script."
}

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
        $text = ""
        if (Test-Path -LiteralPath $outLog) {
            $text += Get-Content -LiteralPath $outLog -Raw
        }
        if (Test-Path -LiteralPath $errLog) {
            $text += Get-Content -LiteralPath $errLog -Raw
        }

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
    Invoke-RestMethod -Method Get -Uri $modelsUrl -TimeoutSec 20 | Out-Null

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
        $body = @{ value = $envVars[$name] } | ConvertTo-Json -Compress
        Invoke-RestMethod `
            -Method Put `
            -Uri "https://api.render.com/v1/services/$serviceId/env-vars/$name" `
            -Headers $headers `
            -Body $body | Out-Null
    }

    $deployBody = @{ deployMode = "deploy_only" } | ConvertTo-Json -Compress
    Invoke-RestMethod `
        -Method Post `
        -Uri "https://api.render.com/v1/services/$serviceId/deploys" `
        -Headers $headers `
        -Body $deployBody | Out-Null

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
