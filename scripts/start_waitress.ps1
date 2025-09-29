param(
    [string]$ProjectRoot = "C:\Users\Administrator\Desktop\feishu_flask_bot"
)

$ErrorActionPreference = 'Stop'

$pythonExe = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$serveScript = Join-Path $ProjectRoot 'serve.py'
$logDir = Join-Path $ProjectRoot 'logs'

if (!(Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}
if (!(Test-Path $serveScript)) {
    throw "serve.py not found at $serveScript"
}
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir ("waitress-" + (Get-Date -Format 'yyyyMMdd') + '.log')

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $pythonExe
$startInfo.Arguments = '"' + $serveScript + '"'
$startInfo.WorkingDirectory = $ProjectRoot
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $startInfo
$null = $process.Start()

$stdOut = $process.StandardOutput
$stdErr = $process.StandardError

while (!$process.HasExited) {
    if (!$stdOut.EndOfStream) {
        $line = $stdOut.ReadLine()
        Add-Content -Path $logFile -Value ("[{0}] [OUT] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $line)
    }
    if (!$stdErr.EndOfStream) {
        $line = $stdErr.ReadLine()
        Add-Content -Path $logFile -Value ("[{0}] [ERR] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $line)
    }
    Start-Sleep -Milliseconds 200
}

while (!$stdOut.EndOfStream) {
    $line = $stdOut.ReadLine()
    Add-Content -Path $logFile -Value ("[{0}] [OUT] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $line)
}
while (!$stdErr.EndOfStream) {
    $line = $stdErr.ReadLine()
    Add-Content -Path $logFile -Value ("[{0}] [ERR] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $line)
}

exit $process.ExitCode
