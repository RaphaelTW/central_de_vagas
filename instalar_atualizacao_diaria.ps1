$taskName = "CentralDeVagas-AtualizacaoDiaria"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $project ".venv\Scripts\python.exe"
$script = Join-Path $project "daily_scan.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente Python não encontrado. Rode executar_windows.bat uma vez antes de instalar a atualização diária."
}

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Description "Atualiza diariamente as vagas da Central de Vagas às 08:00" -Force | Out-Null
Write-Host "Atualização diária instalada para as 08:00. O computador deve estar ligado e sua sessão aberta."
