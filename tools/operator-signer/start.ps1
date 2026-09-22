param(
    [string]$Php = "php",
    [string]$Origin = "https://jsinteractive.ru",
    [int]$Port = 17843
)

$ErrorActionPreference = "Stop"
$Router = Join-Path $PSScriptRoot "router.php"

if (-not (Test-Path $Router)) {
    throw "Не найден router.php: $Router"
}

$Token = (& $Php -r "echo bin2hex(random_bytes(24));").Trim()
if ($LASTEXITCODE -ne 0 -or $Token -notmatch '^[0-9a-f]{48}$') {
    throw "Не удалось создать pairing token через PHP."
}

$env:OPERATOR_SIGNER_TOKEN = $Token
$env:OPERATOR_SIGNER_ORIGIN = $Origin

Write-Host ""
Write-Host "Workspace Organizer Operator Signer"
Write-Host "-----------------------------------"
Write-Host "Слушает только: http://127.0.0.1:$Port"
Write-Host "Разрешённая страница: $Origin"
Write-Host ""
Write-Host "КОД ПОДКЛЮЧЕНИЯ:"
Write-Host $Token
Write-Host ""
Write-Host "Вставьте этот код во вкладке «Лицензии» или «Релизы»."
Write-Host "Закройте это окно после завершения выпуска/подписи."
Write-Host ""

Push-Location $PSScriptRoot
try {
    & $Php -d display_errors=0 -S "127.0.0.1:$Port" $Router
}
finally {
    Pop-Location
    Remove-Item Env:OPERATOR_SIGNER_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:OPERATOR_SIGNER_ORIGIN -ErrorAction SilentlyContinue
}
