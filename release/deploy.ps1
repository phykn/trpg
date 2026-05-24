param(
    [switch]$ClientOnly,
    [string]$CommitMessage,
    [int]$LlmReadyTimeoutSeconds = 900
)

$ErrorActionPreference = "Stop"

$ReleaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ReleaseDir "lib.ps1")

$RepoRoot = Split-Path -Parent $ReleaseDir
$ClientDir = Join-Path $RepoRoot "client"
$LlmLauncher = Join-Path $ReleaseDir "llm.bat"
$LocalWrangler = Join-Path $ClientDir "node_modules\.bin\wrangler.cmd"
$ServerReleaseEnv = Join-Path $RepoRoot "server\.env.release"

function Get-CurrentBranch {
    $branch = (& git -C $RepoRoot branch --show-current).Trim()
    if (-not $branch) { throw "Cannot determine current git branch" }
    return $branch
}

function Deploy-Client {
    Invoke-Step "Build and deploy client" {
        Write-Host "Client deploy: started."
        Import-EnvFile (Join-Path $ClientDir ".env.shared")
        Import-EnvFile (Join-Path $ClientDir ".env.release")

        $sha = (& git -C $RepoRoot rev-parse --short HEAD).Trim()
        if (-not $sha) { throw "Could not resolve git sha" }
        $env:EXPO_PUBLIC_GIT_SHA = $sha

        Remove-Item -LiteralPath (Join-Path $ClientDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
        Invoke-Native -Command "npx" -Arguments @("expo", "export", "-p", "web", "--clear") -Cwd $ClientDir

        $jsDir = Join-Path $ClientDir "dist\_expo\static\js\web"
        $entry = Get-ChildItem -LiteralPath $jsDir -Filter "entry-*.js" | Select-Object -First 1
        if (-not $entry) { throw "Expo export is missing the web entry bundle" }
        $source = Get-Content -LiteralPath $entry.FullName -Raw
        if (-not $source.Contains($env:EXPO_PUBLIC_API_URL)) {
            throw "Expo export did not inline EXPO_PUBLIC_API_URL"
        }
        if ($source.Contains("EXPO_PUBLIC_API_URL is not set")) {
            throw "Expo export contains a missing EXPO_PUBLIC_API_URL guard"
        }

        Write-Host "Client deploy: running wrangler deploy."
        Invoke-NativeRetry -Command $script:WranglerCommand -Arguments @("deploy") -Cwd $ClientDir
        Write-Host "Client deploy: completed."
    }
}

function Wait-LlmReady {
    param(
        [string]$ReadyFile,
        [string]$ErrorFile,
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $ReadyFile) {
            return Get-Content -LiteralPath $ReadyFile -Raw
        }
        if (Test-Path -LiteralPath $ErrorFile) {
            $message = Get-Content -LiteralPath $ErrorFile -Raw
            throw "Local LLM tunnel failed: $message"
        }
        if ($Process.HasExited) {
            throw "Local LLM launcher exited before the tunnel was ready. Check the LLM window for details."
        }
        Start-Sleep -Seconds 2
    }

    throw "Timed out waiting for the local LLM tunnel after $TimeoutSeconds seconds."
}

Invoke-Step "Preflight" {
    Assert-Command "git"
    Assert-Command "npm"
    Assert-Command "npx"
    $script:WranglerCommand = Resolve-Executable "wrangler" $LocalWrangler
    if (-not (Test-Path -LiteralPath (Join-Path $ClientDir "package.json"))) {
        throw "client/package.json is missing"
    }

    if (-not $ClientOnly) {
        Assert-Command "cloudflared"
        Assert-Command "wsl"
        Import-OptionalEnvFile $ServerReleaseEnv
        Assert-Env "RENDER_API_KEY" "RENDER_API_KEY is not set. Render LLM env cannot be updated."
        Assert-Env "RENDER_SERVICE_ID" "RENDER_SERVICE_ID is not set. Render LLM env cannot be updated."
        Assert-Env "LLAMA_CPP_SUDO_PASSWORD" "LLAMA_CPP_SUDO_PASSWORD is not set. Local llama.cpp cannot start through WSL Docker."
        if (-not (Test-Path -LiteralPath $LlmLauncher)) {
            throw "release/llm.bat is missing"
        }
    }
}

if (-not $ClientOnly) {
    Invoke-Step "Start local LLM tunnel" {
        $statusDir = Join-Path $env:TEMP "trpg-release"
        New-Item -ItemType Directory -Path $statusDir -Force | Out-Null
        $stamp = Get-Date -Format "yyyyMMddHHmmss"
        $readyFile = Join-Path $statusDir "llm-ready-$PID-$stamp.txt"
        $errorFile = Join-Path $statusDir "llm-error-$PID-$stamp.txt"
        Remove-Item -LiteralPath $readyFile, $errorFile -Force -ErrorAction SilentlyContinue

        $previousReadyFile = $env:TRPG_LLM_READY_FILE
        $previousErrorFile = $env:TRPG_LLM_ERROR_FILE
        $env:TRPG_LLM_READY_FILE = $readyFile
        $env:TRPG_LLM_ERROR_FILE = $errorFile
        try {
            $llmProcess = Start-Process -FilePath $LlmLauncher -WorkingDirectory $ReleaseDir -PassThru
        }
        finally {
            if ($null -eq $previousReadyFile) {
                Remove-Item Env:TRPG_LLM_READY_FILE -ErrorAction SilentlyContinue
            }
            else {
                $env:TRPG_LLM_READY_FILE = $previousReadyFile
            }
            if ($null -eq $previousErrorFile) {
                Remove-Item Env:TRPG_LLM_ERROR_FILE -ErrorAction SilentlyContinue
            }
            else {
                $env:TRPG_LLM_ERROR_FILE = $previousErrorFile
            }
        }

        Write-Host "Started release/llm.bat in a separate window."
        Write-Host "That window must stay open while Render uses the local LLM."
        $ready = Wait-LlmReady -ReadyFile $readyFile -ErrorFile $errorFile -Process $llmProcess -TimeoutSeconds $LlmReadyTimeoutSeconds
        Write-Host "Local LLM tunnel is ready: $ready"
    }
}
else {
    Write-Host "Local LLM tunnel: skipped because -ClientOnly was specified."
}

if (-not $ClientOnly) {
    Invoke-Step "Commit current workspace" {
        $branch = Get-CurrentBranch
        Write-Host "Branch: $branch"

        Write-Host "Git add: started."
        Invoke-Native -Command "git" -Arguments @("add", "-A") -Cwd $RepoRoot
        Write-Host "Git add: completed."
        $dirty = (& git -C $RepoRoot status --porcelain)
        if ($dirty) {
            $message = $CommitMessage
            if (-not $message) {
                $message = "chore: release $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
            }
            Write-Host "Git commit: creating commit."
            Invoke-Native -Command "git" -Arguments @("commit", "-m", $message) -Cwd $RepoRoot
            Write-Host "Git commit: completed."
        }
        else {
            Write-Host "Git commit: skipped because there are no tracked changes."
        }
    }

    Invoke-Step "Push current branch" {
        $branch = Get-CurrentBranch
        Write-Host "Git push: started for origin/$branch."
        Invoke-Native -Command "git" -Arguments @("push", "origin", $branch) -Cwd $RepoRoot
        Write-Host "Git push: completed for origin/$branch."
    }
}
else {
    Write-Host "Git commit and push: skipped because -ClientOnly was specified."
}

Deploy-Client

Write-Host ""
Write-Host "Release deploy completed."
