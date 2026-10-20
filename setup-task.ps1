param([switch]$EnableAfterManualTest)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Virtual environment is missing.' }
if ((Get-TimeZone).Id -ne 'Singapore Standard Time') { throw 'Set Windows time zone to (UTC+08:00) Kuala Lumpur, Singapore before registering.' }
$action = New-ScheduledTaskAction -Execute $python -Argument '-m prize_alerts run' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At '08:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Description 'Gmail prize alerts; Asia/Kuala_Lumpur 08:00. Local Python and SQLite recovery.'
$task.Settings.Enabled = [bool]$EnableAfterManualTest
if ($EnableAfterManualTest) {
    $answer = Read-Host 'Only after Gmail dry-run and Telegram manual delivery passed: type ENABLE to activate daily scans'
    if ($answer -cne 'ENABLE') { throw 'Task was not enabled.' }
}
Register-ScheduledTask -TaskName 'Gmail Prize Alerts' -InputObject $task | Select-Object TaskName,State
