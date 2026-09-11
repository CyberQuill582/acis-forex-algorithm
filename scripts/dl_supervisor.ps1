# ACIS Dukascopy download supervisor (Windows).
#
# Keeps scripts/download_dukascopy.js running until the COMPLETE marker exists:
#   * single instance (named mutex) - the scheduled task can fire it repeatedly, harmlessly
#   * keeps the PC from idle-sleeping while downloading (SetThreadExecutionState; released
#     automatically when this process exits - no power settings are changed)
#   * restarts the downloader whenever it exits, with a growing delay if it crash-loops
#
# Launched by the scheduled task "ACIS Dukascopy Download" (at logon + every 30 min), so a
# reboot, logoff, or crash resumes on its own. Run by hand:
#   powershell -ExecutionPolicy Bypass -File scripts\dl_supervisor.ps1
# Stop for good:  Unregister-ScheduledTask -TaskName "ACIS Dukascopy Download" -Confirm:$false
#                 then end the node.exe / powershell.exe processes.

$ErrorActionPreference = 'Continue'
$Root     = Split-Path -Parent $PSScriptRoot
$Node     = 'C:\Program Files\nodejs\node.exe'
$Data     = Join-Path $Root 'data\dukascopy'
$Log      = Join-Path $Data 'supervisor.log'
$Complete = Join-Path $Data 'COMPLETE'
New-Item -ItemType Directory -Force -Path $Data | Out-Null

function Log([string]$m) {
    $line = '{0}  {1}' -f (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'), $m
    Add-Content -Path $Log -Value $line -Encoding utf8
}

if (Test-Path $Complete) { exit 0 }

$created = $false
$mutex = [System.Threading.Mutex]::new($true, 'Local\ACIS_Dukascopy_Download', [ref]$created)
if (-not $created) { exit 0 }          # a supervisor is already running

if (-not (Test-Path $Node)) { Log "node.exe not found at $Node - cannot run"; exit 1 }

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
        & $Node (Join-Path $Root 'scripts\download_dukascopy.js') *> $null
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
