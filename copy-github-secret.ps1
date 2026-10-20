param([Parameter(Mandatory=$true)][ValidateSet('STATE_ENCRYPTION_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID')][string]$Name)
$ErrorActionPreference = 'Stop'
if ($Name -eq 'STATE_ENCRYPTION_KEY') {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot '.cloud-state-key') -Raw | Set-Clipboard
} else {
    $taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    & $taskPython -c 'import sys; from dotenv import dotenv_values; from pathlib import Path; values=dotenv_values(Path(sys.argv[1])/".env"); value=values.get(sys.argv[2]); assert value and value!="replace_locally", "Missing local setting"; sys.stdout.write(value)' $PSScriptRoot $Name | Set-Clipboard
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy secret.' }
}
Write-Host "Copied $Name to your clipboard. Paste only into the matching GitHub repository secret, then clear clipboard. Do not paste into chat."
