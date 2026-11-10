# ASCII source preserves Windows PowerShell 5.1 support without a UTF-8 BOM.
param(
    [string]$Workdir = (Get-Location).Path,
    [Parameter(Mandatory=$true)][string]$Name,
    [string]$ImagePath = "",
    [int]$HeightMm = 150,
    [string]$Printer = "resin",
    [double]$WallMinMm = 1.0,
    [string]$ProjectDate = (Get-Date -Format "yyyyMMdd")
)
$ErrorActionPreference = "Stop"
$safe = ($Name -replace '[\\/:*?"<>|]', '_').Trim()
$projectRoot = Join-Path (Join-Path $Workdir "$([char]0x624B)$([char]0x529E)") ("{0}-{1}" -f $safe, $ProjectDate)
if (Test-Path $projectRoot) { throw "$([char]0x9879)$([char]0x76EE)$([char]0x76EE)$([char]0x5F55)$([char]0x5DF2)$([char]0x5B58)$([char]0x5728)$([char]0xFF1A)$projectRoot$([char]0xFF08)$([char]0x7981)$([char]0x6B62)$([char]0x8986)$([char]0x76D6)$([char]0xFF09)" }
$dirs = @(
    "1.Codex\01-$([char]0x63D0)$([char]0x793A)$([char]0x8BCD)$([char]0x5BA1)$([char]0x6838)","1.Codex\02-$([char]0x751F)$([char]0x6210)$([char]0x8BB0)$([char]0x5F55)","1.Codex\03-$([char]0x4F1A)$([char]0x8BDD)$([char]0x65E5)$([char]0x5FD7)","1.Codex\04-Blender$([char]0x811A)$([char]0x672C)","1.Codex\05-$([char]0x56DE)$([char]0x4F20)$([char]0x6E32)$([char]0x67D3)","1.Codex\06-$([char]0x4FEE)$([char]0x590D)","1.Codex\99-$([char]0x4E34)$([char]0x65F6)",
    "2.DSH\00-$([char]0x8F93)$([char]0x5165)","2.DSH\01-$([char]0x9700)$([char]0x6C42)$([char]0x5361)","2.DSH\02-$([char]0x63D0)$([char]0x793A)$([char]0x8BCD)","2.DSH\03-$([char]0x5BA1)$([char]0x6838)$([char]0x62A5)$([char]0x544A)","2.DSH\03-$([char]0x786E)$([char]0x8BA4)","2.DSH\04-$([char]0x6D4F)$([char]0x89C8)$([char]0x5668)$([char]0x8BB0)$([char]0x5F55)","2.DSH\05-$([char]0x51B3)$([char]0x7B56)$([char]0x8BB0)$([char]0x5F55)","2.DSH\99-$([char]0x4E34)$([char]0x65F6)",
    "3.$([char]0x56FE)$([char]0x7247)\v1",
    "4.$([char]0x6A21)$([char]0x578B)$([char]0x6587)$([char]0x4EF6)\4.1$([char]0x521D)$([char]0x7248)\renders","4.$([char]0x6A21)$([char]0x578B)$([char]0x6587)$([char]0x4EF6)\4.2$([char]0x8868)$([char]0x9762)$([char]0x4FEE)$([char]0x590D)$([char]0x7248)\renders","4.$([char]0x6A21)$([char]0x578B)$([char]0x6587)$([char]0x4EF6)\4.9$([char]0x5F52)$([char]0x6863)",
    "5.$([char]0x6253)$([char]0x5370)"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $d) | Out-Null }
if ($ImagePath -and (Test-Path -LiteralPath $ImagePath)) {
    $ext = [IO.Path]::GetExtension($ImagePath)
    Copy-Item -LiteralPath $ImagePath -Destination (Join-Path $projectRoot ("2.DSH\00-$([char]0x8F93)$([char]0x5165)\$([char]0x539F)$([char]0x56FE)" + $ext)) -Force
}
$project = [ordered]@{
    schemaVersion = 1
    projectId = ("{0}-{1}" -f ($safe -replace '\s+',''), $ProjectDate)
    name = $Name
    workdir = $projectRoot
    createdAt = (Get-Date).ToString("o")
    target = [ordered]@{ heightMm = $HeightMm; printer = $Printer; wallMinMm = $WallMinMm }
    status = [ordered]@{ S0="done"; S1="pending"; S2="pending"; S3="pending"; S4="pending"; S5="pending"; S6="pending"; S7="pending"; S8="pending"; S9="pending"; S10="pending"; S11="pending" }
    gates = @{}
    versions = @()
    artifacts = @()
    decisions = @()
    credits = [ordered]@{ hunyuan = 0; codexImageGenCalls = 0 }
    resume = [ordered]@{ nextStage = "S1"; note = "" }
}
[IO.File]::WriteAllText((Join-Path $projectRoot "2.DSH\project.json"), (($project | ConvertTo-Json -Depth 8) + "`n"), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "$([char]0x9879)$([char]0x76EE)$([char]0x5DF2)$([char]0x521B)$([char]0x5EFA)$([char]0xFF1A)$projectRoot"
Write-Host "$([char]0x4E0B)$([char]0x4E00)$([char]0x6B65)$([char]0xFF1A)S1 $([char]0x9700)$([char]0x6C42)$([char]0x5361)$([char]0xFF08)$([char]0x8BFB) references/10-eight-view-prompts.md$([char]0xFF09)$([char]0xFF0C)$([char]0x5B8C)$([char]0x6210)$([char]0x540E)$([char]0x66F4)$([char]0x65B0) project.json"
