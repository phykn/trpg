param(
    [switch]$ClientOnly,
    [string]$CommitMessage
)

$ErrorActionPreference = "Stop"

$ReleaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ReleaseDir
$ClientDir = Join-Path $RepoRoot "client"
$LlmLauncher = Join-Path $ReleaseDir "run_llm.bat"
$LocalWrangler = Join-Path $ClientDir "node_modules\.bin\wrangler.cmd"
$ServerReleaseEnv = Join-Path $RepoRoot "server\.env.release"

function Step {
    param([string]$Title, [scriptblock]$Body)
    Write-Host ""
    Write-Host "==> $Title"
    & $Body
}

function Need {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Resolve-Command {
    param([string]$Name, [string]$FallbackPath)
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        return $Name
    }
    if ($FallbackPath -and (Test-Path -LiteralPath $FallbackPath)) {
        return $FallbackPath
    }
    throw "Required command not found: $Name"
}

function Run {
    param([string]$Command, [string[]]$Arguments, [string]$Cwd = $RepoRoot)
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

function Load-EnvFile {
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

function Load-OptionalEnvFile {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Load-EnvFile $Path
    }
}

function Get-CurrentBranch {
    $branch = (& git -C $RepoRoot branch --show-current).Trim()
    if (-not $branch) { throw "Cannot determine current git branch" }
    return $branch
}

function Deploy-Client {
    Step "Build and deploy client" {
        Load-EnvFile (Join-Path $ClientDir ".env.shared")
        Load-EnvFile (Join-Path $ClientDir ".env.release")

        $sha = (& git -C $RepoRoot rev-parse --short HEAD).Trim()
        if (-not $sha) { throw "Could not resolve git sha" }
        $env:EXPO_PUBLIC_GIT_SHA = $sha

        Remove-Item -LiteralPath (Join-Path $ClientDir "dist") -Recurse -Force -ErrorAction SilentlyContinue
        Run -Command "npx" -Arguments @("expo", "export", "-p", "web", "--clear") -Cwd $ClientDir

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

        Run -Command $script:WranglerCommand -Arguments @("deploy") -Cwd $ClientDir
    }
}

Load-OptionalEnvFile $ServerReleaseEnv

Step "Preflight" {
    Need "git"
    Need "npm"
    Need "npx"
    $script:WranglerCommand = Resolve-Command "wrangler" $LocalWrangler
    if (-not $env:RENDER_API_KEY) {
        throw "RENDER_API_KEY is not set. Render LLM env cannot be updated."
    }
    if (-not $env:RENDER_SERVICE_ID) {
        throw "RENDER_SERVICE_ID is not set. Render LLM env cannot be updated."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $ClientDir "package.json"))) {
        throw "client/package.json is missing"
    }
    if (-not (Test-Path -LiteralPath $LlmLauncher)) {
        throw "release/run_llm.bat is missing"
    }
}

if (-not $ClientOnly) {
    Step "Start local LLM tunnel" {
        Start-Process -FilePath $LlmLauncher -WorkingDirectory $ReleaseDir
        Write-Host "Started release/run_llm.bat in a separate window."
        Write-Host "That window must stay open while Render uses the local LLM."
        Start-Sleep -Seconds 10
    }

    Step "Commit current workspace" {
        $branch = Get-CurrentBranch
        Write-Host "Branch: $branch"

        Run -Command "git" -Arguments @("add", "-A")
        $dirty = (& git -C $RepoRoot status --porcelain)
        if ($dirty) {
            $message = $CommitMessage
            if (-not $message) {
                $message = "chore: release $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
            }
            Run -Command "git" -Arguments @("commit", "-m", $message)
        }
        else {
            Write-Host "No tracked changes to commit."
        }
    }

    Step "Push current branch" {
        $branch = Get-CurrentBranch
        Run -Command "git" -Arguments @("push", "origin", $branch)
    }
}

Deploy-Client

Write-Host ""
Write-Host "Release deploy completed."
