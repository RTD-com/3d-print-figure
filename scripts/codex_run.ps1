# ASCII source keeps UTF-8 without BOM compatible with Windows PowerShell 5.1.
param(
    [Parameter(Mandatory=$true)][string]$PromptFile,
    [Parameter(Mandatory=$true)][string]$Workdir,
    [string[]]$Images = @(),
    [string]$OutFile = '',
    [string]$LogFile = '',
    [ValidateRange(1,86400)][int]$TimeoutSec = 600,
    [string]$Sandbox = 'workspace-write',
    [string]$OutputSchema = '',
    [string]$Model = '',
    [string]$ReasoningEffort = '',
    [switch]$Ephemeral,
    [ValidateRange(1,3)][int]$MaxAttempts = 3,
    [ValidateRange(0,300)][int]$RetryDelaySec = 20,
    [string]$ArtifactManifest = '',
    [switch]$MissingOnly,
    [string]$CodexExe = 'codex'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib/file_hash.ps1')
$utf8 = New-Object System.Text.UTF8Encoding($false)
if (-not (Test-Path -LiteralPath $PromptFile -PathType Leaf)) { throw "PromptFile $([regex]::Unescape('\u4E0D\u5B58\u5728\uFF1A'))$PromptFile" }
if (-not (Test-Path -LiteralPath $Workdir -PathType Container)) { throw "Workdir $([regex]::Unescape('\u4E0D\u5B58\u5728\uFF1A'))$Workdir" }
$Workdir = [IO.Path]::GetFullPath($Workdir)
$PromptFile = (Resolve-Path -LiteralPath $PromptFile).Path
if ($Images.Count -eq 1 -and $Images[0] -match ',') { $Images = @($Images[0] -split ',') }
$missingImages = @($Images | Where-Object { -not $_ -or -not (Test-Path -LiteralPath $_ -PathType Leaf) })
if ($missingImages.Count) { throw (([regex]::Unescape('\u53C2\u8003\u56FE\u7F3A\u5931\uFF0C\u672A\u542F\u52A8 Codex\uFF1A')) + ($missingImages -join ', ')) }
$Images = @($Images | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
if ($OutputSchema -and -not (Test-Path -LiteralPath $OutputSchema -PathType Leaf)) { throw "OutputSchema $([regex]::Unescape('\u4E0D\u5B58\u5728\uFF1A'))$OutputSchema" }
if ($MissingOnly -and -not $ArtifactManifest) { throw ([regex]::Unescape('-MissingOnly \u5FC5\u987B\u63D0\u4F9B -ArtifactManifest\uFF08artifacts[path,sha256]\uFF09\u3002')) }
function Write-Utf8([string]$Path, [string]$Text) { [IO.File]::WriteAllText($Path, $Text, $utf8) }
function Quote-Argument([string]$Value) {
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
function Read-Artifacts {
    if (-not $ArtifactManifest) { return @() }
    if (-not (Test-Path -LiteralPath $ArtifactManifest -PathType Leaf)) { throw "ArtifactManifest $([regex]::Unescape('\u4E0D\u5B58\u5728\uFF1A'))$ArtifactManifest" }
    $contract = Get-Content -LiteralPath $ArtifactManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $items = @()
    foreach ($artifact in @($contract.artifacts)) {
        if (-not $artifact.path -or $artifact.sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw ([regex]::Unescape('\u4EA7\u7269\u6E05\u5355\u5FC5\u987B\u5305\u542B path \u548C64\u4F4D sha256\u3002')) }
        $path = [IO.Path]::GetFullPath((Join-Path $Workdir $artifact.path))
        $prefix = $Workdir.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
        if (-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw "$([regex]::Unescape('\u4EA7\u7269\u8DEF\u5F84\u8D8A\u754C\uFF1A'))$path" }
        $exists = Test-Path -LiteralPath $path -PathType Leaf
        $hash = if ($exists) { Get-Sha256 $path } else { $null }
        if ($exists -and $hash -ne $artifact.sha256.ToLowerInvariant()) { throw "$([regex]::Unescape('\u5DF2\u5B58\u5728\u4EA7\u7269\u54C8\u5E0C\u4E0D\u7B26\uFF0C\u505C\u6B62\u7EED\u8DD1\uFF1A'))$($artifact.path)" }
        $items += [ordered]@{ path = $artifact.path; expectedSha256 = $artifact.sha256; sha256 = $hash; exists = [bool]$exists }
    }
    return $items
}
$initialArtifacts = @(Read-Artifacts)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$logDir = Join-Path $Workdir ([regex]::Unescape('1.Codex/03-\u4F1A\u8BDD\u65E5\u5FD7'))
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if (-not $LogFile) { $LogFile = Join-Path $logDir "$stamp-codex.jsonl" }
$LogFile = [IO.Path]::GetFullPath($LogFile)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
if (-not $OutFile) { $OutFile = Join-Path $Workdir "1.Codex/02-$([regex]::Unescape('\u751F\u6210\u8BB0\u5F55'))/$stamp-last.md" }
$OutFile = [IO.Path]::GetFullPath($OutFile)
if (Test-Path -LiteralPath $OutFile) { throw "$([regex]::Unescape('\u6700\u7EC8\u56DE\u590D\u5DF2\u5B58\u5728\uFF0C\u8BF7\u4F7F\u7528\u65B0\u8DEF\u5F84\uFF1A'))$OutFile" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
$prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8
if ($MissingOnly) {
    $keep = @($initialArtifacts | Where-Object { $_.exists } | ForEach-Object { $_.path })
    $missing = @($initialArtifacts | Where-Object { -not $_.exists } | ForEach-Object { $_.path })
    $prompt += "`n$([regex]::Unescape('\u7EED\u8DD1\u7EA6\u675F\uFF1A\u4EC5\u8865\u7F3A\u5931\u4EA7\u7269\uFF1B\u7981\u6B62\u8986\u76D6'))/$([regex]::Unescape('\u91CD\u505A\u5DF2\u6821\u9A8C\u6587\u4EF6\u3002\u5DF2\u6821\u9A8C\uFF1A'))$($keep -join ', ')$([regex]::Unescape('\u3002\u7F3A\u5931\uFF1A'))$($missing -join ', ')$([regex]::Unescape('\u3002'))`n"
}
$effectivePrompt = Join-Path $logDir "$stamp-input.txt"
Write-Utf8 $effectivePrompt $prompt
$summaryPath = Join-Path $logDir "$stamp-run.json"
$attempts = @()
$started = Get-Date
$success = $false
$finalCode = 1
$command = Get-Command $CodexExe -ErrorAction SilentlyContinue | Select-Object -First 1
$executable = if ($command) { $command.Source } else { $CodexExe }
function Get-WorkSnapshot {
    $snapshot = @{}
    foreach ($file in Get-ChildItem -LiteralPath $Workdir -File -Recurse -Force -ErrorAction Stop) {
        $path = $file.FullName
        if ($path -match '[\\/]\.git[\\/]' -or $path.StartsWith($logDir + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith($OutFile,[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith([IO.Path]::ChangeExtension($LogFile,''),[StringComparison]::OrdinalIgnoreCase)) { continue }
        $snapshot[$path] = "$( $file.Length ):$(Get-Sha256 $path)"
    }
    return $snapshot
}
function Same-Snapshot($Before, $After) {
    if ($Before.Count -ne $After.Count) { return $false }
    foreach ($key in $Before.Keys) { if (-not $After.ContainsKey($key) -or $After[$key] -ne $Before[$key]) { return $false } }
    return $true
}
for ($number = 1; $number -le $MaxAttempts; $number++) {
    $artifactState = @(Read-Artifacts)
    $before = Get-WorkSnapshot
    $attemptLog = if ($number -eq 1) { $LogFile } else { [IO.Path]::ChangeExtension($LogFile,".attempt$number.jsonl") }
    $stderrLog = [IO.Path]::ChangeExtension($attemptLog,'.stderr.log')
    $attemptLast = "$OutFile.attempt$number"
    $attemptStarted = Get-Date
    $timedOut = $false
    $launchFailed = $false
    $process = $null
    $launcherError = ''
    $processCode = 1
    $codexArgs = @('exec','--json','-C',$Workdir,'-s',$Sandbox,'--skip-git-repo-check')
    if ($Model) { $codexArgs += @('-m',$Model) }
    if ($ReasoningEffort) { $codexArgs += @('-c',('model_reasoning_effort="{0}"' -f $ReasoningEffort)) }
    if ($Ephemeral) { $codexArgs += '--ephemeral' }
    if ($OutputSchema) { $codexArgs += @('--output-schema',(Resolve-Path -LiteralPath $OutputSchema).Path) }
    foreach ($image in $Images) { $codexArgs += @('-i',$image) }
    $codexArgs += @('--output-last-message',$attemptLast,'-')
    $argumentLine = ($codexArgs | ForEach-Object { Quote-Argument $_ }) -join ' '
    $launchExe = $executable
    if ([IO.Path]::GetExtension($executable) -in @('.cmd','.bat')) {
        $launchExe = $env:ComSpec
        if (-not $launchExe) {
            $launchExe = Join-Path ([Environment]::SystemDirectory) 'cmd.exe'
        }
        $argumentLine = '/d /s /c "' + (Quote-Argument $executable) + ' ' + $argumentLine + '"'
    }
    try {
        $process = Start-Process -FilePath $launchExe -ArgumentList $argumentLine -WorkingDirectory $Workdir -RedirectStandardInput $effectivePrompt -RedirectStandardOutput $attemptLog -RedirectStandardError $stderrLog -PassThru -WindowStyle Hidden
        $processHandle = $process.Handle
        try {
            Wait-Process -Id $process.Id -Timeout $TimeoutSec -ErrorAction Stop
            $process.WaitForExit()
            $process.Refresh()
            $processCode = $process.ExitCode
            if ($null -eq $processCode) { $processCode = 1 }
        } catch {
            $process.Refresh()
            if (-not $process.HasExited) {
                $timedOut = $true
                $processCode = 124
                try {
                    & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw "Could not terminate the Codex process tree." }
                } finally {
                    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
                }
            } else {
                $processCode = $process.ExitCode
            }
        }
    } catch {
        $launchFailed = ($null -eq $process)
        $launcherError = [IO.Path]::ChangeExtension($attemptLog,'.launcher-error.log')
        Write-Utf8 $launcherError ($_ | Out-String)
        if ($timedOut) { $processCode = 124 }
    } finally {
        if ($process) {
            try {
                if ($process.WaitForExit(5000)) { $process.WaitForExit() }
            } finally { $process.Dispose() }
        }
    }
    $lastPresent = -not $timedOut -and (Test-Path -LiteralPath $attemptLast -PathType Leaf) -and -not [string]::IsNullOrWhiteSpace([IO.File]::ReadAllText($attemptLast,$utf8))
    $success = ($processCode -eq 0 -and $lastPresent -and -not $timedOut)
    $finalCode = if ($success) { 0 } elseif ($processCode -ne 0) { [int]$processCode } else { 1 }
    $logsText = ''
    $unchanged = $false
    if (-not $timedOut) {
        foreach ($path in @($attemptLog,$stderrLog,$launcherError)) {
            if ($path -and (Test-Path -LiteralPath $path)) { $logsText += [IO.File]::ReadAllText($path) + "`n" }
        }
        $unchanged = Same-Snapshot $before (Get-WorkSnapshot)
    }
    $startupRefresh = $logsText -match 'failed to refresh available models:\s*request timed out'
    $taskStarted = $logsText -match '"type"\s*:\s*"(?:turn\.started|item\.(?:started|completed))"'
    $retryable = -not $success -and -not $timedOut -and -not $lastPresent -and $unchanged -and -not $taskStarted -and ($launchFailed -or $startupRefresh)
    $attempts += [ordered]@{ attempt = $number; startedAt = $attemptStarted.ToString('o'); finishedAt = (Get-Date).ToString('o'); exitCode = $processCode; ok = $success; timedOut = $timedOut; retryable = $retryable; artifactsUnchanged = $unchanged; artifactsBefore = $artifactState; log = $attemptLog; stderr = $stderrLog; launcherError = $launcherError; lastMessage = $attemptLast }
    if ($success) { Copy-Item -LiteralPath $attemptLast -Destination $OutFile; break }
    if (-not $retryable -or $number -eq $MaxAttempts) { break }
    if ($RetryDelaySec) { Start-Sleep -Seconds $RetryDelaySec }
}
$summary = [ordered]@{ ok = $success; exitCode = $finalCode; attempts = $attempts; startedAt = $started.ToString('o'); finishedAt = (Get-Date).ToString('o'); durationSec = [math]::Round(((Get-Date)-$started).TotalSeconds,1); workdir = $Workdir; promptFile = $PromptFile; log = $attempts[-1].log; lastMessage = $OutFile; images = $Images; timeoutSec = $TimeoutSec; missingOnly = [bool]$MissingOnly; artifactManifest = $ArtifactManifest }
Write-Utf8 $summaryPath (($summary | ConvertTo-Json -Depth 10) + "`n")
Write-Host "codex exit=$finalCode ok=$success attempts=$($attempts.Count) summary=$summaryPath"
exit $finalCode
