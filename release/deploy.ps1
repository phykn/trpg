param(
    [switch]$StartLocalLlm,
    [string]$CommitMessage
)

$ErrorActionPreference = "Stop"

$ReleaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ReleaseDir
$ClientDir = Join-Path $RepoRoot "client"
$LocalLlmLauncher = "C:\Users\KN\Desktop\LLM\run_llm.bat"

function Run-Step {
    param(
        [string]$Title,
        [scriptblock]$Body
    )

    Write-Host ""
    Write-Host "==> $Title"
    & $Body
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Run-Command {
    param(
        [string]$Command,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $RepoRoot
    )

    Push-Location $WorkingDirectory
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

Run-Step "Preflight" {
    Require-Command "git"
    Require-Command "npm"
    if (-not (Test-Path -LiteralPath $ClientDir)) {
        throw "Client directory is missing: $ClientDir"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $ClientDir "package.json"))) {
        throw "client/package.json is missing"
    }
    if ($StartLocalLlm -and -not (Test-Path -LiteralPath $LocalLlmLauncher)) {
        throw "Local LLM launcher is missing: $LocalLlmLauncher"
    }
}

if ($StartLocalLlm) {
    Run-Step "Start local LLM tunnel" {
        Start-Process -FilePath $LocalLlmLauncher -WorkingDirectory (Split-Path -Parent $LocalLlmLauncher)
        Write-Host "Started local LLM launcher in a separate window."
    }
}

Run-Step "Capture current worktree in a release commit" {
    $branch = (& git -C $RepoRoot branch --show-current).Trim()
    if (-not $branch) {
        throw "Cannot determine current git branch"
    }
    Write-Host "Branch: $branch"

    Run-Command "git" @("add", "-A")
    $dirty = (& git -C $RepoRoot status --porcelain)
    if ($dirty) {
        $message = $CommitMessage
        if (-not $message) {
            $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
            $message = "chore: release $stamp"
        }
        Run-Command "git" @("commit", "-m", $message)
    }
    else {
        Write-Host "No tracked changes to commit."
    }
}

Run-Step "Push current branch to origin" {
    $branch = (& git -C $RepoRoot branch --show-current).Trim()
    Run-Command "git" @("push", "origin", $branch)
}

Run-Step "Deploy client to Cloudflare" {
    Run-Command "npm" @("run", "deploy") $ClientDir
}

Write-Host ""
Write-Host "Release deploy completed."
