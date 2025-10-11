Param(
    [switch]$Force
)

$root = Split-Path -Path $PSScriptRoot -Parent
$exe  = Join-Path $root 'venv\Scripts\python.exe'
$wd   = $root

try {
    if ($Force) {
        $pids = (netstat -ano | Select-String '127\.0\.0\.1:9876' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique)
        foreach($pid in $pids){ try { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } catch {} }
    }

    $running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.ExecutablePath -eq $exe }
    if (-not $running) {
        Start-Process -FilePath $exe -ArgumentList 'serve.py' -WorkingDirectory $wd -WindowStyle Hidden
    }
} catch { }

