param(
    [int]$Port = 8000,
    [string]$ModelId = "gemma4",
    [string]$CloudflaredLogDir = (Join-Path $env:TEMP "trpg-release"),
    [int]$TimeoutSeconds = 180,
    [int]$DnsTimeoutSeconds = 30,
    [int]$TunnelAttempts = 3,
    [string]$ReadyFile,
    [string]$ErrorFile
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

function Write-StatusFile {
    param([string]$Path, [string]$Text)
    if (-not $Path) { return }
    $dir = Split-Path -Parent $Path
    if ($dir) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Value $Text -Encoding UTF8
}

New-Item -ItemType Directory -Path $CloudflaredLogDir -Force | Out-Null

$outLog = Join-Path $CloudflaredLogDir "cloudflared.out.log"
$errLog = Join-Path $CloudflaredLogDir "cloudflared.err.log"
Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue

function Stop-CloudflaredProcess {
    param($Process)
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

function Start-QuickTunnel {
    param(
        [string]$Origin,
        [string]$OutLog,
        [string]$ErrLog
    )
    Remove-Item -LiteralPath $OutLog, $ErrLog -Force -ErrorAction SilentlyContinue
    Start-Process `
        -FilePath "cloudflared" `
        -ArgumentList @("tunnel", "--url", $Origin) `
        -WorkingDirectory $CloudflaredLogDir `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru
}

function Wait-TunnelUrl {
    param(
        [string]$OutLog,
        [string]$ErrLog,
        [int]$TimeoutSeconds
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        $text = (Get-FileText $outLog) + (Get-FileText $errLog)

        $match = [regex]::Match($text, "https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            return $match.Value
        }
    }
    return $null
}

function Resolve-HostAddresses {
    param([string]$HostName)
    $addresses = @()
    $lastError = $null

    try {
        $addresses += [System.Net.Dns]::GetHostAddresses($HostName) | ForEach-Object { $_.IPAddressToString }
    }
    catch {
        $lastError = $_.Exception.Message
    }

    foreach ($server in @("1.1.1.1", "8.8.8.8")) {
        try {
            $addresses += Resolve-DnsName -Name $HostName -Server $server -Type A -ErrorAction Stop |
                Where-Object { $_.IPAddress } |
                ForEach-Object { $_.IPAddress }
        }
        catch {
            $lastError = $_.Exception.Message
        }
    }

    return @{
        Addresses = @($addresses | Where-Object { $_ } | Select-Object -Unique)
        Error = $lastError
    }
}

function Test-ModelsEndpoint {
    param(
        [string]$ModelsUrl,
        [string]$HostName,
        [string[]]$Addresses
    )
    try {
        Invoke-RestMethod -Method Get -Uri $ModelsUrl -TimeoutSec 20 | Out-Null
        return @{ Ready = $true; Error = $null }
    }
    catch {
        $lastError = $_.Exception.Message
    }

    if (-not (Get-Command "curl.exe" -ErrorAction SilentlyContinue)) {
        return @{ Ready = $false; Error = $lastError }
    }

    foreach ($address in $Addresses) {
        $curlOutput = & curl.exe -fsS --connect-timeout 20 --max-time 30 --resolve "$HostName`:443`:$address" $ModelsUrl 2>&1
        if ($LASTEXITCODE -eq 0) {
            return @{ Ready = $true; Error = $null }
        }
        $lastError = ($curlOutput | Out-String).Trim()
    }

    return @{ Ready = $false; Error = $lastError }
}

function Wait-TunnelReady {
    param(
        [string]$TunnelUrl,
        [int]$TimeoutSeconds,
        [int]$DnsTimeoutSeconds
    )
    $modelsUrl = "$tunnelUrl/v1/models"
    $hostName = ([Uri]$TunnelUrl).Host
    $dnsDeadline = (Get-Date).AddSeconds($DnsTimeoutSeconds)
    $lastReadyError = $null
    $addresses = @()
    while ((Get-Date) -lt $dnsDeadline) {
        $resolved = Resolve-HostAddresses -HostName $hostName
        $addresses = @($resolved.Addresses)
        if ($addresses.Count -gt 0) {
            break
        }
        $lastReadyError = $resolved.Error
        Start-Sleep -Seconds 2
    }
    if ($addresses.Count -eq 0) {
        return @{ Ready = $false; Error = $lastReadyError; Phase = "dns" }
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $ready = Test-ModelsEndpoint -ModelsUrl $modelsUrl -HostName $hostName -Addresses $addresses
        if ($ready.Ready) {
            return @{ Ready = $true; Error = $null; Phase = "http" }
        }
        $lastReadyError = $ready.Error
        Start-Sleep -Seconds 2
    }
    return @{ Ready = $false; Error = $lastReadyError; Phase = "http" }
}

$origin = "http://127.0.0.1:$Port"
$cloudflared = $null
$tunnelUrl = $null
$lastError = $null

try {
    for ($attempt = 1; $attempt -le $TunnelAttempts; $attempt++) {
        Write-Host "Opening Cloudflare quick tunnel ($attempt/$TunnelAttempts)..."
        $cloudflared = Start-QuickTunnel -Origin $origin -OutLog $outLog -ErrLog $errLog
        $tunnelUrl = Wait-TunnelUrl -OutLog $outLog -ErrLog $errLog -TimeoutSeconds $TimeoutSeconds
        if (-not $tunnelUrl) {
            $lastError = "Could not find a trycloudflare URL in cloudflared output."
            Write-Host "$lastError Retrying..."
            Stop-CloudflaredProcess $cloudflared
            $cloudflared = $null
            Start-Sleep -Seconds 3
            continue
        }

        Write-Host "Tunnel URL: $tunnelUrl"
        $ready = Wait-TunnelReady -TunnelUrl $tunnelUrl -TimeoutSeconds $TimeoutSeconds -DnsTimeoutSeconds $DnsTimeoutSeconds
        if ($ready.Ready) {
            break
        }

        $lastError = "Cloudflare tunnel URL was created, but $tunnelUrl/v1/models did not become reachable during $($ready.Phase) check. Last error: $($ready.Error)"
        if ($attempt -lt $TunnelAttempts) {
            Write-Host "$lastError Retrying with a new tunnel..."
            Stop-CloudflaredProcess $cloudflared
            $cloudflared = $null
            Start-Sleep -Seconds 3
            continue
        }

        throw $lastError
    }

    if (-not $tunnelUrl -or -not $cloudflared) {
        throw $lastError
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
    Write-StatusFile -Path $ReadyFile -Text "ready $llmBaseUrl"
    Wait-Process -Id $cloudflared.Id
}
catch {
    Write-StatusFile -Path $ErrorFile -Text $_.Exception.Message
    throw
}
finally {
    Stop-CloudflaredProcess $cloudflared
}
