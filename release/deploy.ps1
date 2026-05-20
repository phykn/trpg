param(
    [switch]$ClientOnly,
    [string]$CommitMessage
)

$ErrorActionPreference = "Stop"

$ReleaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ReleaseDir "_common.ps1")

$RepoRoot = Split-Path -Parent $ReleaseDir
$ClientDir = Join-Path $RepoRoot "client"
$LlmLauncher = Join-Path $ReleaseDir "run_llm.bat"
$LocalWrangler = Join-Path $ClientDir "node_modules\.bin\wrangler.cmd"
$ServerReleaseEnv = Join-Path $RepoRoot "server\.env.release"

function Get-CurrentBranch {
    $branch = (& git -C $RepoRoot branch --show-current).Trim()
    if (-not $branch) { throw "Cannot determine current git branch" }
    return $branch
}

function Deploy-Client {
    Invoke-Step "Build and deploy client" {
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

        Invoke-NativeRetry -Command $script:WranglerCommand -Arguments @("deploy") -Cwd $ClientDir
    }
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
            throw "release/run_llm.bat is missing"
        }
    }
}

if (-not $ClientOnly) {
    Invoke-Step "Start local LLM tunnel" {
        Start-Process -FilePath $LlmLauncher -WorkingDirectory $ReleaseDir
        Write-Host "Started release/run_llm.bat in a separate window."
        Write-Host "That window must stay open while Render uses the local LLM."
        Start-Sleep -Seconds 10
    }

    Invoke-Step "Commit current workspace" {
        $branch = Get-CurrentBranch
        Write-Host "Branch: $branch"

        Invoke-Native -Command "git" -Arguments @("add", "-A") -Cwd $RepoRoot
        $dirty = (& git -C $RepoRoot status --porcelain)
        if ($dirty) {
            $message = $CommitMessage
            if (-not $message) {
                $message = "chore: release $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
            }
            Invoke-Native -Command "git" -Arguments @("commit", "-m", $message) -Cwd $RepoRoot
        }
        else {
            Write-Host "No tracked changes to commit."
        }
    }

    Invoke-Step "Push current branch" {
        $branch = Get-CurrentBranch
        Invoke-Native -Command "git" -Arguments @("push", "origin", $branch) -Cwd $RepoRoot
    }
}

Deploy-Client

Write-Host ""
Write-Host "Release deploy completed."
