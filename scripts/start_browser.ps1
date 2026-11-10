# ASCII source preserves Windows PowerShell 5.1 support without a UTF-8 BOM.
param(
    [string]$Browser = "edge",
    [int]$Port = 9229,
    [string]$Workdir = (Get-Location).Path,
    [string]$Url = "https://3d.hunyuan.tencent.com/creation",
    [switch]$Headless
)
$ErrorActionPreference = "Continue"
function PortAlive([int]$p) {
    try { $r = Invoke-RestMethod "http://127.0.0.1:$p/json/version" -TimeoutSec 2; return $r } catch { return $null }
}
$existing = PortAlive $Port
if ($existing) {
    [ordered]@{ ok = $true; reused = $true; port = $Port; browser = $existing.Browser; wsUrl = $existing.webSocketDebuggerUrl } | ConvertTo-Json -Depth 4
    exit 0
}
$candidates = if ($Browser -eq "chrome") {
    @("C:\Program Files\Google\Chrome\Application\chrome.exe","C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")
} else {
    @("C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe","C:\Program Files\Microsoft\Edge\Application\msedge.exe")
}
$exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) { Write-Host "$([char]0x672A)$([char]0x627E)$([char]0x5230) $Browser"; exit 1 }
$profileDir = Join-Path $Workdir ".browser-profiles\hunyuan"
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
$args = @(
    '--remote-debugging-address=127.0.0.1',
    "--remote-debugging-port=$Port",
    ('--user-data-dir="{0}"' -f $profileDir),
    "--no-first-run", "--no-default-browser-check",
    $(if ($Headless) { "--headless=new" } else { "--start-maximized" }),
    $Url
)
Write-Host "$([char]0x542F)$([char]0x52A8) $exe$([char]0xFF08)profile=$profileDir, port=$Port$([char]0xFF09)..."
Start-Process -FilePath $exe -ArgumentList $args | Out-Null
$info = $null
for ($i = 0; $i -lt 40 -and -not $info; $i++) { Start-Sleep -Milliseconds 500; $info = PortAlive $Port }
if (-not $info) {
    [ordered]@{ ok = $false; port = $Port; error = "CDP $([char]0x672A)$([char]0x5C31)$([char]0x7EEA)$([char]0xFF1B)$([char]0x8BF7)$([char]0x786E)$([char]0x8BA4)$([char]0x6D4F)$([char]0x89C8)$([char]0x5668)$([char]0x672A)$([char]0x88AB)$([char]0x7B56)$([char]0x7565)$([char]0x62E6)$([char]0x622A)$([char]0xFF0C)$([char]0x6216)$([char]0x6539)$([char]0x7528) -Headless" } | ConvertTo-Json -Depth 4
    exit 1
}
[ordered]@{ ok = $true; reused = $false; port = $Port; browser = $info.Browser; wsUrl = $info.webSocketDebuggerUrl; profile = $profileDir } | ConvertTo-Json -Depth 4
Write-Host "$([char]0x6D4F)$([char]0x89C8)$([char]0x5668)$([char]0x4FDD)$([char]0x6301)$([char]0x6253)$([char]0x5F00)$([char]0xFF1B)$([char]0x767B)$([char]0x5F55)$([char]0x540E)$([char]0x56DE)$([char]0x6765)$([char]0x7EE7)$([char]0x7EED)$([char]0x6D41)$([char]0x7A0B)$([char]0xFF08)$([char]0x4E0D)$([char]0x8981)$([char]0x5173)$([char]0x95ED)$([char]0x6B64)$([char]0x7A97)$([char]0x53E3)$([char]0xFF09)$([char]0x3002)"
