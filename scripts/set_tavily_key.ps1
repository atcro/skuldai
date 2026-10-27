# Writes TAVILY_API_KEY into the git-ignored C:\Skuld\.env without the key ever
# appearing on screen, in chat, or in an editor buffer. Run in a PowerShell window:
#   powershell -ExecutionPolicy Bypass -File C:\Skuld\scripts\set_tavily_key.ps1
$envPath = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
$secure = Read-Host "Paste your Tavily key (input is hidden), then press Enter" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ($plain.Length -lt 20) {
    Write-Host "That is only $($plain.Length) characters; a Tavily key is longer. Nothing written."
    exit 1
}
Set-Content -Path $envPath -Value "TAVILY_API_KEY=$plain" -Encoding ascii
$plain = $null
$line = Get-Content $envPath | Select-Object -First 1
$value = $line.Substring("TAVILY_API_KEY=".Length)
$prefix = if ($value.StartsWith("tvly-")) { "yes" } else { "no" }
Write-Host "Wrote $envPath : value length $($value.Length), starts with tvly-: $prefix"
