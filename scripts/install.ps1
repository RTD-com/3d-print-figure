# ASCII source keeps UTF-8 without BOM compatible with Windows PowerShell 5.1.
param(
    [string]$ProjectRoot = '',
    [ValidateSet('project','user')][string]$Scope = 'project',
    [string]$DestinationRoot = '',
    [switch]$Force,
    [switch]$Update
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib/file_hash.ps1')
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8 = New-Object System.Text.UTF8Encoding($false)
$specPath = Join-Path $sourceRoot 'assets/install-manifest.json'
if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) { throw "$([regex]::Unescape('\u53D1\u884C\u767D\u540D\u5355\u4E0D\u5B58\u5728\uFF1A'))$specPath$([regex]::Unescape('\uFF1B\u8BF7\u4ECE\u6E90\u7801\u4ED3\u5E93\u8FD0\u884C\u5B89\u88C5\u547D\u4EE4\u3002'))" }
$spec = Get-Content -LiteralPath $specPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($DestinationRoot) { $targetRoot = [IO.Path]::GetFullPath($DestinationRoot) }
elseif ($Scope -eq 'user') { $targetRoot = [IO.Path]::GetFullPath($env:USERPROFILE) }
elseif ($ProjectRoot) { $targetRoot = [IO.Path]::GetFullPath($ProjectRoot) }
else { throw ([regex]::Unescape('project \u5B89\u88C5\u5FC5\u987B\u663E\u5F0F\u6307\u5B9A -ProjectRoot\uFF1B\u4E34\u65F6\u6784\u5EFA\u53EF\u7528 -DestinationRoot\u3002')) }
$skillText = Get-Content -LiteralPath (Join-Path $sourceRoot 'SKILL.md') -Raw -Encoding UTF8
$versionMatch = [regex]::Match($skillText, '\b\d+\.\d+\.\d+\b')
if (-not $versionMatch.Success) { throw ([regex]::Unescape('SKILL.md \u7F3A\u5C11\u7248\u672C\u53F7')) }
$version = $versionMatch.Value
$commit = (& git -C $sourceRoot rev-parse HEAD 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[a-f0-9]{40}$') { throw ([regex]::Unescape('\u65E0\u6CD5\u53D6\u5F97\u6E90 git commit')) }

function Assert-Contained([string]$Path, [string]$Parent) {
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Parent).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw "$([regex]::Unescape('\u8DEF\u5F84\u4E0D\u5728\u9884\u671F\u76EE\u5F55\u5185\uFF1A'))$full$([regex]::Unescape('\uFF08'))$prefix$([regex]::Unescape('\uFF09'))" }
}
function Write-Utf8([string]$Path, [string]$Value) { [IO.File]::WriteAllText($Path, $Value, $utf8) }
function Test-Closure([string]$Stage) {
    foreach ($md in Get-ChildItem -LiteralPath $Stage -Filter '*.md' -File -Recurse) {
        $text = Get-Content -LiteralPath $md.FullName -Raw -Encoding UTF8
        foreach ($resource in [regex]::Matches($text, '(?<![\w.-])((?:scripts|references|assets[\\/]templates)[\\/](?:[\w.-]+[\\/])*[\w.-]+\.(?:py|ps1|mjs|bat|json|md))\b')) {
            $resourcePath = Join-Path $Stage $resource.Groups[1].Value
            Assert-Contained $resourcePath $Stage
            if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) { throw "Unpackaged runtime resource: $($resource.Groups[1].Value) in $($md.FullName)" }
        }
        $text = [regex]::Replace($text, '(?ms)^\s*```.*?^\s*```\s*$', '')
        $links = @([regex]::Matches($text, '!?\[[^\]\r\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+["''][^\r\n]*?["''])?\)') | ForEach-Object { $_.Groups[1].Value.Trim('<','>') })
        $links += @([regex]::Matches($text, '(?m)^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)') | ForEach-Object { $_.Groups[1].Value.Trim('<','>') })
        foreach ($link in $links) {
            if ($link -match '^[a-zA-Z][a-zA-Z0-9+.-]*:' -or $link.StartsWith('#') -or $link.StartsWith('//')) { continue }
            $path = [Uri]::UnescapeDataString(($link -split '[#?]',2)[0]).Replace('/',[IO.Path]::DirectorySeparatorChar)
            if (-not $path -or $path -match '[<>{}*]' -or $path -match ([regex]::Unescape('^(1\.Codex|2\.DSH|3\.\u56FE\u7247|4\.\u6A21\u578B\u6587\u4EF6|5\.\u6253\u5370|\u624B\u529E|projects)[\\/]'))) { continue }
            $resolved = [IO.Path]::GetFullPath((Join-Path $md.DirectoryName $path))
            Assert-Contained $resolved $Stage
            if (-not (Test-Path -LiteralPath $resolved)) { throw "$([regex]::Unescape('\u5F15\u7528\u95ED\u5305\u5931\u8D25\uFF1A'))$($md.FullName) -> $link" }
        }
    }
}
$plans = @()
foreach ($key in @('dsh','codex')) {
    $package = $spec.packages.$key
    $relative = if ($key -eq 'dsh') { '.dsh/skills' } else { '.agents/skills' }
    $parent = Join-Path $targetRoot $relative
    $destination = Join-Path $parent $package.name
    Assert-Contained $destination $targetRoot
    if ((Test-Path -LiteralPath $destination) -and -not ($Force -or $Update)) { throw "$([regex]::Unescape('\u76EE\u6807\u5DF2\u5B58\u5728\uFF1A'))$destination$([regex]::Unescape('\uFF1B\u5347\u7EA7\u8BF7\u663E\u5F0F\u4F7F\u7528')) -Update $([regex]::Unescape('\u6216')) -Force$([regex]::Unescape('\u3002'))" }
    foreach ($item in @($package.entry) + @($package.files)) {
        $source = Join-Path $sourceRoot $item
        Assert-Contained $source $sourceRoot
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "$([regex]::Unescape('\u53D1\u884C\u6587\u4EF6\u7F3A\u5931\uFF1A'))$item" }
    }
    $plans += [pscustomobject]@{ package = $package; destination = $destination; parent = $parent; stage = "$destination.staging-$([guid]::NewGuid().ToString('N'))"; backup = '' }
}
try {
    foreach ($plan in $plans) {
        New-Item -ItemType Directory -Path $plan.stage -Force | Out-Null
        $mapping = @([pscustomobject]@{ source = $plan.package.entry; target = 'SKILL.md' })
        foreach ($file in $plan.package.files) { $mapping += [pscustomobject]@{ source = $file; target = $file } }
        foreach ($file in $mapping) {
            $target = Join-Path $plan.stage $file.target
            Assert-Contained $target $plan.stage
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $sourceRoot $file.source) -Destination $target
        }
        Test-Closure $plan.stage
        $hashes = @(Get-ChildItem -LiteralPath $plan.stage -File -Recurse | Sort-Object FullName | ForEach-Object {
            [ordered]@{ path = $_.FullName.Substring($plan.stage.Length + 1).Replace('\','/'); bytes = $_.Length; sha256 = (Get-Sha256 $_.FullName) }
        })
        $manifest = [ordered]@{ name = $plan.package.name; version = $version; sourceCommit = $commit; builtAt = (Get-Date).ToUniversalTime().ToString('o'); files = $hashes }
        Write-Utf8 (Join-Path $plan.stage 'manifest.json') (($manifest | ConvertTo-Json -Depth 8) + "`n")
    }
    foreach ($plan in $plans) {
        if (Test-Path -LiteralPath $plan.destination) {
            $plan.backup = "$($plan.destination).previous-$([guid]::NewGuid().ToString('N'))"
            Assert-Contained $plan.backup $targetRoot
            Move-Item -LiteralPath $plan.destination -Destination $plan.backup
        }
        Move-Item -LiteralPath $plan.stage -Destination $plan.destination
    }
    foreach ($plan in $plans) {
        if ($plan.backup -and (Test-Path -LiteralPath $plan.backup)) {
            Assert-Contained $plan.backup $targetRoot
            Remove-Item -LiteralPath $plan.backup -Recurse -Force
        }
        Write-Host "$([regex]::Unescape('\u5DF2\u6784\u5EFA\u95ED\u5408\u5B89\u88C5\u5305\uFF1A'))$($plan.destination)$([regex]::Unescape('\uFF08'))$version / $commit$([regex]::Unescape('\uFF09'))"
    }
} catch {
    foreach ($plan in $plans) {
        if ($plan.backup -and (Test-Path -LiteralPath $plan.backup)) {
            if (Test-Path -LiteralPath $plan.destination) { Assert-Contained $plan.destination $targetRoot; Remove-Item -LiteralPath $plan.destination -Recurse -Force }
            Move-Item -LiteralPath $plan.backup -Destination $plan.destination
        }
    }
    throw
} finally {
    foreach ($plan in $plans) {
        if (Test-Path -LiteralPath $plan.stage) { Assert-Contained $plan.stage $targetRoot; Remove-Item -LiteralPath $plan.stage -Recurse -Force }
    }
}
