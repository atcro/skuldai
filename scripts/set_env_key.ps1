# Writes or replaces one KEY=value line in the git-ignored C:\Skuld\.env with hidden
# input, so the value never appears on screen, in chat, or in an editor buffer.
# Other lines in .env (for example TAVILY_API_KEY) are kept. Run in a PowerShell window:
#   powershell -ExecutionPolicy Bypass -File C:\Skuld\scripts\set_env_key.ps1 -Name NEBIUS_TOKEN_FACTORY_API_KEY
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [int]$MinLength = 20
)
if ($Name -notmatch '^[A-Z][A-Z0-9_]*$') { Write-Host "Name must look like AN_ENV_VAR"; exit 1 }
$envPath = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
$secure = Read-Host "Paste the value for $Name (input is hidden), then press Enter" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ($plain.Length -lt $MinLength) {
    Write-Host "That is only $($plain.Length) characters; nothing written."
    exit 1
}
$lines = @()
if (Test-Path $envPath) {
    $lines = @(Get-Content $envPath | Where-Object { $_ -notmatch "^$Name=" })
}
$lines += "$Name=$plain"
$plain = $null
# LF line endings and ASCII: the WSL loader strips CRs anyway, but keep the file clean
[IO.File]::WriteAllText($envPath, (($lines -join "`n") + "`n"), [Text.Encoding]::ASCII)
$written = (Get-Content $envPath | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1)
$len = $written.Length - ($Name.Length + 1)
Write-Host "Wrote $envPath : $Name set, value length $len; $(@($lines).Count) line(s) in file"
