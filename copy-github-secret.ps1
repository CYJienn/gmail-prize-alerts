param([Parameter(Mandatory=$true)][ValidateSet('STATE_ENCRYPTION_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID')][string]$Name)
$ErrorActionPreference = 'Stop'
if ($Name -eq 'STATE_ENCRYPTION_KEY') {
    $taskSecret = (Get-Content -LiteralPath (Join-Path $PSScriptRoot '.cloud-state-key') -Raw).Trim()
} else {
    $taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $taskHelper = Join-Path $PSScriptRoot 'cloud\copy-secret.py'
    $taskEnvFile = Join-Path $PSScriptRoot '.env'
    $taskSecret = & $taskPython $taskHelper $taskEnvFile $Name
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy secret.' }
}
if ([string]::IsNullOrWhiteSpace($taskSecret)) { throw 'Secret is empty; clipboard was not changed.' }
Set-Clipboard -Value $taskSecret
Remove-Variable taskSecret
Write-Host "Copied $Name to your clipboard. Paste only into the matching GitHub repository secret, then clear clipboard. Do not paste into chat."
