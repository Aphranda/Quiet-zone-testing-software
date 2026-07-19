param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$PreferredPython = "D:\Microsoft\uv-venvs\catr-loss-calibrator\Scripts\python.exe"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvConfig = Join-Path $Root ".venv\pyvenv.cfg"
$AppMain = Join-Path $Root "catr_loss_calibrator\src\catr_loss_calibrator\app\main.py"
$AppSrc = Join-Path $Root "catr_loss_calibrator\src"

function Test-Python {
    param([string]$PythonPath)
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        return $false
    }
    & $PythonPath --version *> $null
    return ($LASTEXITCODE -eq 0)
}

function Get-PythonMinorVersion {
    param([string]$PythonPath)
    if (-not (Test-Python $PythonPath)) {
        return ""
    }
    $version = & $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    return [string]$version
}

function Get-ConfigValue {
    param(
        [string[]]$Lines,
        [string]$Key
    )
    $prefix = "$Key = "
    foreach ($line in $Lines) {
        if ($line.StartsWith($prefix)) {
            return $line.Substring($prefix.Length).Trim()
        }
    }
    return ""
}

function Set-ConfigValue {
    param(
        [string[]]$Lines,
        [string]$Key,
        [string]$Value
    )
    $prefix = "$Key = "
    $updated = $false
    $result = foreach ($line in $Lines) {
        if ($line.StartsWith($prefix)) {
            $updated = $true
            "$prefix$Value"
        } else {
            $line
        }
    }
    if (-not $updated) {
        $result += "$prefix$Value"
    }
    return $result
}

function Repair-VenvHome {
    if (-not (Test-Path -LiteralPath $VenvConfig)) {
        throw "Missing venv config: $VenvConfig"
    }

    $lines = Get-Content -Encoding UTF8 -LiteralPath $VenvConfig
    $configuredHome = Get-ConfigValue $lines "home"
    $configuredVersion = Get-ConfigValue $lines "version_info"
    $targetMinor = ""
    if ($configuredVersion -match "^(\d+\.\d+)") {
        $targetMinor = $Matches[1]
    }

    $candidateHomes = @()
    if ($env:CATR_PYTHON_HOME) {
        $candidateHomes += $env:CATR_PYTHON_HOME
    }
    if ($configuredHome) {
        $candidateHomes += $configuredHome
    }
    $candidateHomes += @(
        "D:\Microsoft\Miniconda",
        "D:\Microsoft\Miniconda3",
        "D:\Microsoft\Miniconda3\pkgs\python-3.12.0-h1d929f7_0"
    )

    $seen = @{}
    foreach ($home in $candidateHomes) {
        $normalizedHome = [string]$home
        if (-not $normalizedHome -or $seen.ContainsKey($normalizedHome.ToLowerInvariant())) {
            continue
        }
        $seen[$normalizedHome.ToLowerInvariant()] = $true
        $candidatePython = Join-Path $normalizedHome "python.exe"
        $candidateMinor = Get-PythonMinorVersion $candidatePython
        if (-not $candidateMinor) {
            continue
        }
        if ($targetMinor -and $candidateMinor -ne $targetMinor) {
            continue
        }

        $fullVersion = & $candidatePython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
        $newLines = Set-ConfigValue $lines "home" $normalizedHome
        $newLines = Set-ConfigValue $newLines "version_info" ([string]$fullVersion)
        Set-Content -Encoding UTF8 -LiteralPath $VenvConfig -Value $newLines
        return $normalizedHome
    }

    throw "No compatible Python home found. Set CATR_PYTHON_HOME to a Python $targetMinor home directory."
}

$SelectedPython = ""

if ($env:CATR_PROJECT_PYTHON -and (Test-Python $env:CATR_PROJECT_PYTHON)) {
    $SelectedPython = $env:CATR_PROJECT_PYTHON
} elseif (Test-Python $PreferredPython) {
    $SelectedPython = $PreferredPython
} else {
    if (-not (Test-Python $VenvPython)) {
        $selectedHome = Repair-VenvHome
        Write-Host "Repaired .venv Python home: $selectedHome"
    }
    if (Test-Python $VenvPython) {
        $SelectedPython = $VenvPython
    }
}

if (-not $SelectedPython) {
    throw "No runnable Python found. Tried CATR_PROJECT_PYTHON, $PreferredPython, and $VenvPython."
}

$env:PYTHONPATH = if ($env:PYTHONPATH) { "$AppSrc;$env:PYTHONPATH" } else { $AppSrc }
& $SelectedPython $AppMain @AppArgs
exit $LASTEXITCODE
