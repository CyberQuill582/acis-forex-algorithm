# ACIS market-data download supervisor (Windows).
#
#   -Job s3         scripts/download_dukascopy_s3.py run   (PRIMARY: Dukascopy official S3 archive)
#   -Job histdata   scripts/download_histdata.py run       (cross-check source)
#
# Keeps the chosen downloader running until its COMPLETE marker exists:
#   * single instance per job (named mutex) - the scheduled task can fire it repeatedly
#   * keeps the PC from idle-sleeping while downloading (SetThreadExecutionState; released
#     automatically when this process exits - no power settings are changed)
#   * restarts the downloader whenever it exits, with a growing delay if it crash-loops
#
# Launched by a scheduled task (at logon + every 30 min), so a reboot, logoff, or crash
# resumes on its own. Run by hand:
#   powershell -ExecutionPolicy Bypass -File scripts\dl_supervisor.ps1 -Job histdata
# Stop for good: Unregister-ScheduledTask -TaskName "<task name>" -Confirm:$false
#                then end the python.exe / node.exe and powershell.exe processes.
# Absolute paths are used throughout: this machine's PATH cannot be relied on.

param([Parameter(Mandatory = $true)][ValidateSet('s3', 'histdata')][string]$Job)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$Python = 'C:\Users\USER\AppData\Local\Programs\Python\Python311\python.exe'
$Jobs = @{
    s3       = @{ Exe = $Python; Args = @((Join-Path $Root 'scripts\download_dukascopy_s3.py'), 'run')
                  Data = 'data\dukascopy'; Mutex = 'Local\ACIS_DukascopyS3_Download' }
    histdata = @{ Exe = $Python; Args = @((Join-Path $Root 'scripts\download_histdata.py'), 'run')
                  Data = 'data\histdata'; Mutex = 'Local\ACIS_HistData_Download' }
}
$J        = $Jobs[$Job]
$Data     = Join-Path $Root $J.Data
$Log      = Join-Path $Data 'supervisor.log'
$Complete = Join-Path $Data 'COMPLETE'
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Log([string]$m) {
    $line = '{0}  [{1}] {2}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $Job, $m
    Add-Content -Path $Log -Value $line -Encoding utf8
}

if (Test-Path $Complete) { exit 0 }

$created = $false
$mutex = [System.Threading.Mutex]::new($true, $J.Mutex, [ref]$created)
if (-not $created) { exit 0 }          # this job's supervisor is already running

if (-not (Test-Path $J.Exe)) { Log "interpreter not found at $($J.Exe) - cannot run"; exit 1 }

Add-Type -Namespace AcisDl -Name Power -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [uint32]'0x80000000'
$ES_SYSTEM_REQUIRED = [uint32]'0x00000001'
[AcisDl.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED) | Out-Null

Log "supervisor started (pid $PID)"
$delay = 60
try {
    Set-Location $Root
    while (-not (Test-Path $Complete)) {
        $t0 = Get-Date
        Log 'launching downloader'
        & $J.Exe @($J.Args) *> $null
        $code = $LASTEXITCODE
        $ranMin = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)
        Log "downloader exited code=$code after $ranMin min"
        if (Test-Path $Complete) { break }
        if ($code -eq 3) { Start-Sleep -Seconds 300; continue }   # someone else holds the lock
        # a healthy long run resets the backoff; a quick death grows it (crash-loop guard)
        if ($ranMin -ge 10) { $delay = 60 } else { $delay = [math]::Min(1800, $delay * 2) }
        Log "restarting in $delay s"
        Start-Sleep -Seconds $delay
    }
    Log 'COMPLETE - supervisor exiting'
}
finally {
    [AcisDl.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
    $mutex.ReleaseMutex()
}
