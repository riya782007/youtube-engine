# check_setup.ps1 - verifies this PC has everything the pipeline needs.
# Launched by check_setup.bat (which sets the working dir to the project root).
# Writes a plain-text summary to setup_report.txt and prints it.

$ErrorActionPreference = 'SilentlyContinue'
$lines = @()
$lines += "=== YouTube Engine - setup check ==="
$lines += ("Run at: " + (Get-Date))
$lines += ""

function Check-Cmd($label, $exe, $verArg) {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $v = (& $exe $verArg 2>&1 | Select-Object -First 1)
        return "{0,-22}: FOUND   {1}" -f $label, $v
    } else {
        return "{0,-22}: NOT FOUND on PATH" -f $label
    }
}

$lines += Check-Cmd "Node.js (need v22+)" "node"    "-v"
$lines += Check-Cmd "npm"                 "npm"     "-v"
$lines += Check-Cmd "Python"              "python"  "--version"

# requests module
if (Get-Command python -ErrorAction SilentlyContinue) {
    $r = (& python -c "import requests; print(requests.__version__)" 2>&1)
    if ($LASTEXITCODE -eq 0) {
        $lines += "{0,-22}: OK      {1}" -f "requests module", $r
    } else {
        $lines += "{0,-22}: NOT installed  (run: pip install requests)" -f "requests module"
    }
} else {
    $lines += "{0,-22}: skipped (python not found)" -f "requests module"
}

$lines += Check-Cmd "FFmpeg"  "ffmpeg"  "-version"
$lines += Check-Cmd "FFprobe" "ffprobe" "-version"

# Sarvam key - report STATUS ONLY, never print the key itself
if (Test-Path ".env") {
    $envline = Select-String -Path ".env" -Pattern '^\s*SARVAM_API_KEY=' | Select-Object -First 1
    if (-not $envline) {
        $lines += "{0,-22}: MISSING from .env" -f "Sarvam key"
    } elseif ($envline.Line -match 'sk_your_key_here') {
        $lines += "{0,-22}: NOT SET (still placeholder - edit .env)" -f "Sarvam key"
    } else {
        $lines += "{0,-22}: present" -f "Sarvam key"
    }
} else {
    $lines += "{0,-22}: .env not found in this folder" -f "Sarvam key"
}

$lines += ""
$lines += "Must-haves to render: Node v22+, FFmpeg, FFprobe, requests, a real Sarvam key."
$lines | Tee-Object -FilePath "setup_report.txt"
