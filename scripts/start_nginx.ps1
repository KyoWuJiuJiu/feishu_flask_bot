$nginxRoot = 'C:\nginx'
$nginxExe  = Join-Path $nginxRoot 'nginx.exe'

try {
    if (Test-Path $nginxExe) {
        $alive = Get-Process -Name nginx -ErrorAction SilentlyContinue
        if (-not $alive) {
            Start-Process -FilePath $nginxExe -WorkingDirectory $nginxRoot -WindowStyle Hidden
        }
    }
} catch { }

