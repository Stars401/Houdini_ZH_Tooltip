param(
    [Parameter(Mandatory = $true)]
    [string]$PackZip,

    [Parameter(Mandatory = $true)]
    [string]$DestinationRoot
)

$ErrorActionPreference = "Stop"

function Assert-PathWithin {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd("\") + "\"
    if (-not $resolvedPath.StartsWith(
        $resolvedRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Path escapes destination root: $resolvedPath"
    }
}

function Restore-HelpNodes {
    param(
        [Parameter(Mandatory = $true)]
        [string]$NodesPath,
        [Parameter(Mandatory = $true)]
        [string]$BackupNodes,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )

    if (Test-Path -LiteralPath $NodesPath) {
        Assert-PathWithin -Path $NodesPath -Root $Destination
        Remove-Item -LiteralPath $NodesPath -Recurse -Force
    }
    if (Test-Path -LiteralPath $BackupNodes) {
        Move-Item -LiteralPath $BackupNodes -Destination $NodesPath
    }
}

$packPath = (Resolve-Path -LiteralPath $PackZip).Path
$destination = [System.IO.Path]::GetFullPath($DestinationRoot).TrimEnd("\")
$helpRoot = Join-Path $destination "help"
$nodesPath = Join-Path $helpRoot "nodes"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $destination "backups"
$backupNodes = Join-Path $backupRoot "help_nodes_$timestamp"
$stagingRoot = Join-Path $destination "install_staging_$timestamp"
$stagingNodes = Join-Path $stagingRoot "help\nodes"
$backupCreated = $false
$installStarted = $false

Assert-PathWithin -Path $nodesPath -Root $destination
Assert-PathWithin -Path $backupNodes -Root $destination
Assert-PathWithin -Path $stagingRoot -Root $destination

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($packPath)
    try {
        $expectedFiles = @(
            $archive.Entries |
                Where-Object { -not [string]::IsNullOrEmpty($_.Name) }
        ).Count
        $hasNodesRoot = @(
            $archive.Entries |
                Where-Object { $_.FullName.Replace("\", "/").StartsWith("help/nodes/") }
        ).Count -gt 0
    }
    finally {
        $archive.Dispose()
    }

    if (-not $hasNodesRoot) {
        throw "Pack does not contain help/nodes."
    }

    New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
    Expand-Archive -LiteralPath $packPath -DestinationPath $stagingRoot -Force
    if (-not (Test-Path -LiteralPath $stagingNodes -PathType Container)) {
        throw "Expanded pack is missing help\nodes."
    }

    if (Test-Path -LiteralPath $nodesPath) {
        New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
        Assert-PathWithin -Path $backupNodes -Root $backupRoot
        Move-Item -LiteralPath $nodesPath -Destination $backupNodes
        $backupCreated = $true
    }

    New-Item -ItemType Directory -Force -Path $helpRoot | Out-Null
    Copy-Item -LiteralPath $stagingNodes -Destination $nodesPath -Recurse
    $installStarted = $true

    $installedFiles = @(Get-ChildItem -LiteralPath $nodesPath -Recurse -File).Count
    if ($installedFiles -ne $expectedFiles) {
        throw "Installed file count mismatch: expected $expectedFiles, got $installedFiles."
    }

    $requiredSamples = @(
        "sop\pyrosolver.txt",
        "dop\popCommonParms.txt",
        "apex\Abs.txt",
        "lop\usd_rop.txt",
        "vop\mtlxLamaConductor.txt"
    )
    foreach ($sample in $requiredSamples) {
        $samplePath = Join-Path $nodesPath $sample
        if (-not (Test-Path -LiteralPath $samplePath -PathType Leaf)) {
            throw "Installed pack is missing sample: $sample"
        }
    }

    [pscustomobject]@{
        Destination = $destination
        InstalledFiles = $installedFiles
        Backup = if ($backupCreated) { $backupNodes } else { $null }
    }
}
catch {
    if ($backupCreated) {
        Restore-HelpNodes `
            -NodesPath $nodesPath `
            -BackupNodes $backupNodes `
            -Destination $destination
    }
    elseif ($installStarted -and (Test-Path -LiteralPath $nodesPath)) {
        Assert-PathWithin -Path $nodesPath -Root $destination
        Remove-Item -LiteralPath $nodesPath -Recurse -Force
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Assert-PathWithin -Path $stagingRoot -Root $destination
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
