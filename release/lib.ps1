$ErrorActionPreference = "Stop"

function Get-ReleaseRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Assert-Env {
    param([string]$Name, [string]$Message)
    if (-not (Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue).Value) {
        throw $Message
    }
}

function Resolve-Executable {
    param([string]$Name, [string]$FallbackPath)
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        return $Name
    }
    if ($FallbackPath -and (Test-Path -LiteralPath $FallbackPath)) {
        return $FallbackPath
    }
    throw "Required command not found: $Name"
}

function Invoke-Step {
    param([string]$Title, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==> $Title"
    & $Body
}

function Invoke-Native {
    param([string]$Command, [string[]]$Arguments, [string]$Cwd)
    if (-not $Cwd) { $Cwd = Get-ReleaseRoot }
    Push-Location $Cwd
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Command $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-NativeRetry {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [string]$Cwd,
        [int]$Attempts = 2
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-Native -Command $Command -Arguments $Arguments -Cwd $Cwd
            return
        }
        catch {
            if ($attempt -ge $Attempts) { throw }
            Write-Host "$Command $($Arguments -join ' ') failed; retrying ($($attempt + 1)/$Attempts)."
            Start-Sleep -Seconds 3
        }
    }
}

function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Path is missing"
    }
    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $index = $line.IndexOf("=")
        if ($index -lt 1) { continue }
        $key = $line.Substring(0, $index).Trim()
        $value = $line.Substring($index + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$key" -Value $value
    }
}

function Import-OptionalEnvFile {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Import-EnvFile $Path
    }
}
