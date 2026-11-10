# ASCII source keeps UTF-8 without BOM compatible with Windows PowerShell 5.1.
param(
    [string]$Workdir = (Get-Location).Path,
    [int]$MinDiskGB = 5,
    [string]$BlenderExe = '',
    [switch]$BrowserProbe,
    [switch]$SkipBrowserProbe,
    [switch]$Json,
    [switch]$Quiet
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib/file_hash.ps1')
if ($BrowserProbe -and $SkipBrowserProbe) { throw ([regex]::Unescape('-BrowserProbe \u4E0E -SkipBrowserProbe \u4E0D\u80FD\u540C\u65F6\u4F7F\u7528\u3002')) }
$result = [ordered]@{ ok = $true; checks = @(); warnings = @(); errors = @(); timestamp = (Get-Date).ToString('o'); browserProbe = [bool]$BrowserProbe }
function Add-Check($Name, $Ok, $Detail) {
    $script:result.checks += [ordered]@{ name = $Name; ok = [bool]$Ok; detail = $Detail }
    if (-not $Ok) { $script:result.ok = $false; $script:result.errors += "$Name : $Detail" }
}
function Add-Warn($Name, $Detail) { $script:result.warnings += [ordered]@{ name = $Name; detail = $Detail } }
foreach ($name in @('codex','git','python','node')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    Add-Check $name ([bool]$command) $(if($command){$command.Source}else{([regex]::Unescape('\u547D\u4EE4\u672A\u627E\u5230'))})
}
$candidate = $BlenderExe
if (-not $candidate) { $candidate = $env:BLENDER_EXE }
if (-not $candidate) {
    $command = Get-Command blender -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { $candidate = $command.Source }
}
if (-not $candidate) {
    foreach ($key in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe')) {
        if (Test-Path -LiteralPath $key) { $candidate = (Get-Item -LiteralPath $key).GetValue(''); if($candidate){break} }
    }
}
if (-not $candidate -and $env:ProgramFiles) {
    $foundation = Join-Path $env:ProgramFiles 'Blender Foundation'
    if (Test-Path -LiteralPath $foundation) {
        $found = Get-ChildItem -LiteralPath $foundation -Filter 'blender.exe' -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) { $candidate = $found.FullName }
    }
}
$exists = $candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)
Add-Check 'blender-exe' $exists $(if($exists){$candidate}else{([regex]::Unescape('\u672A\u627E\u5230 Blender\uFF1B\u8BF7\u4F20 -BlenderExe <path> \u6216\u8BBE\u7F6E BLENDER_EXE\u3002'))})
if ($env:APPDATA) {
    $addonRoot = Join-Path $env:APPDATA 'Blender Foundation/Blender'
    $addons = if (Test-Path -LiteralPath $addonRoot) { @(Get-ChildItem -LiteralPath $addonRoot -Filter 'blender_mcp.py' -File -Recurse -ErrorAction SilentlyContinue) } else { @() }
    if ($addons.Count) { Add-Check 'blender-mcp-addon-file' $true ($addons.FullName -join '; ') }
    else { Add-Warn 'blender-mcp-addon-file' ([regex]::Unescape('\u672A\u627E\u5230\u63D2\u4EF6\u6587\u4EF6\uFF1B\u6587\u4EF6\u5B58\u5728\u4E5F\u4E0D\u8BC1\u660E\u63D2\u4EF6\u5DF2\u542F\u7528\u3002')) }
}
if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 9876 -ErrorAction SilentlyContinue)
    if ($listeners.Count) { Add-Check 'mcp-listener' $true ([regex]::Unescape('\u672C\u673A9876\u7AEF\u53E3\u5B58\u5728\u76D1\u542C\uFF1B\u672A\u8BF7\u6C42MCP\u6216\u68C0\u67E5API\u3002')) }
    else { Add-Warn 'mcp-listener' ([regex]::Unescape('9876\u7AEF\u53E3\u672A\u76D1\u542C\uFF1B\u771F\u5B9E\u6267\u884C\u524D\u9700\u542F\u52A8\u5DF2\u914D\u7F6E\u7684Blender/MCP\u3002')) }
}
try {
    $resolved = [IO.Path]::GetFullPath($Workdir)
    $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($resolved))
    $free = [math]::Round($drive.AvailableFreeSpace / 1GB,1)
    Add-Check 'disk-free' ($free -ge $MinDiskGB) "$free GB$([regex]::Unescape('\uFF08\u8981\u6C42\u81F3\u5C11')) $MinDiskGB GB$([regex]::Unescape('\uFF09'))"
} catch { Add-Warn 'disk-free' $_.Exception.Message }
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pillow = (& $python.Source -c 'import PIL; print(PIL.__version__)' 2>&1 | Out-String).Trim()
    Add-Check 'python-pillow' ($LASTEXITCODE -eq 0) $pillow
}
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    $nodeInfo = (& $node.Source -e "console.log(process.version+' WebSocket='+typeof WebSocket)" 2>&1 | Out-String).Trim()
    $versionMatch = [regex]::Match($nodeInfo,'v(\d+)\.')
    Add-Check 'node-websocket' ($versionMatch.Success -and [int]$versionMatch.Groups[1].Value -ge 22 -and $nodeInfo -match 'WebSocket=function') $nodeInfo
}
if ($BrowserProbe) {
    if (-not $node) { Add-Check 'cdp-probe' $false ([regex]::Unescape('\u7F3A\u5C11Node\uFF0C\u65E0\u6CD5\u6267\u884C\u663E\u5F0F\u63A2\u9488\u3002')) }
    else {
        try {
            $raw = (& $node.Source (Join-Path $PSScriptRoot 'cdp_probe.mjs') 2>$null | Out-String).Trim()
            $probe = $raw | ConvertFrom-Json
            Add-Check 'cdp-probe' ([bool]$probe.ok) $raw
        } catch { Add-Check 'cdp-probe' $false $_.Exception.Message }
    }
} else { Add-Warn 'cdp-probe' ([regex]::Unescape('\u9ED8\u8BA4\u8DF3\u8FC7\uFF1B\u4EC5 -BrowserProbe \u4F1A\u542F\u52A8\u63A2\u9488\u6D4F\u89C8\u5668\u3002')) }
foreach ($relative in @('.dsh/skills/3d-print-figure','.agents/skills/3d-print-blender')) {
    $installed = Join-Path $Workdir $relative
    if (-not (Test-Path -LiteralPath $installed)) { continue }
    $manifestPath = Join-Path $installed 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { Add-Warn 'installed-drift' "$installed $([regex]::Unescape('\u7F3A\u5C11'))manifest$([regex]::Unescape('\uFF1B\u65E0\u6CD5\u8BC1\u660E\u4E0E\u6E90\u7801\u4E00\u81F4\u3002'))"; continue }
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $drift = @()
        foreach ($entry in $manifest.files) {
            $path = [IO.Path]::GetFullPath((Join-Path $installed $entry.path))
            if (-not $path.StartsWith(([IO.Path]::GetFullPath($installed).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) { $drift += "$([regex]::Unescape('\u8D8A\u754C'))manifest$([regex]::Unescape('\u8DEF\u5F84\uFF1A'))$($entry.path)"; continue }
            if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Sha256 $path) -ne $entry.sha256) { $drift += $entry.path }
        }
        if ($drift.Count) { Add-Warn 'installed-drift' "$installed$([regex]::Unescape('\uFF1A'))$($drift -join ', ')" }
        else { Add-Check 'installed-manifest' $true "$installed version=$($manifest.version) sourceCommit=$($manifest.sourceCommit)$([regex]::Unescape('\uFF08\u4EC5'))manifest$([regex]::Unescape('\u5B8C\u6574\u6027\uFF09'))" }
    } catch { Add-Warn 'installed-drift' "$installed$([regex]::Unescape('\uFF1A'))$($_.Exception.Message)" }
}
if ($Json) { $result | ConvertTo-Json -Depth 8 }
elseif (-not $Quiet) {
    foreach ($check in $result.checks) { Write-Host ('[{0}] {1} - {2}' -f $(if($check.ok){'OK'}else{'FAIL'}),$check.name,$check.detail) }
    foreach ($warning in $result.warnings) { Write-Host "[WARN] $($warning.name) - $($warning.detail)" }
}
if ($result.ok) { exit 0 } else { exit 1 }
