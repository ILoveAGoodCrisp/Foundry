param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',

    [ValidateSet('x64')]
    [string]$Platform = 'x64',

    [switch]$Deploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-MSBuildPath {
    $candidates = @(
        'C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\amd64\MSBuild.exe',
        'C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\amd64\MSBuild.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw 'MSBuild.exe was not found in the expected Visual Studio locations.'
}

$msbuild = Get-MSBuildPath
$outputSubdir = if ($Configuration -eq 'Debug') { 'debug' } else { 'release' }

$targets = @(
    @{
        Name = 'Omaha / HREK'
        Project = Join-Path $PSScriptRoot 'FoundryPluginOmaha\FoundryPluginOmaha.csproj'
        Output = Join-Path $PSScriptRoot "FoundryPluginOmaha\bin\$outputSubdir\FoundryPlugin.dll"
        DeployPath = 'S:\Halo\Modding\Main\HREK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll'
    },
    @{
        Name = 'Midnight / H4EK'
        Project = Join-Path $PSScriptRoot 'FoundryPluginMidnight\FoundryPluginMidnight.csproj'
        Output = Join-Path $PSScriptRoot "FoundryPluginMidnight\bin\$outputSubdir\FoundryPlugin.dll"
        DeployPath = 'S:\Halo\Modding\Main\H4EK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll'
    },
    @{
        Name = 'Groundhog / H2AMPEK'
        Project = Join-Path $PSScriptRoot 'FoundryPluginGroundhog\FoundryPluginGroundhog.csproj'
        Output = Join-Path $PSScriptRoot "FoundryPluginGroundhog\bin\$outputSubdir\FoundryPlugin.dll"
        DeployPath = 'S:\Halo\Modding\Main\H2AMPEK\bin\tools\bonobo\FoundryPlugin\FoundryPlugin.dll'
    }
)

foreach ($target in $targets) {
    Write-Host "Building $($target.Name)..." -ForegroundColor Cyan
    & $msbuild $target.Project "/p:Configuration=$Configuration" "/p:Platform=$Platform"
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed for $($target.Name)."
    }

    if (-not (Test-Path -LiteralPath $target.Output)) {
        throw "Expected output was not produced for $($target.Name): $($target.Output)"
    }

    $hash = (Get-FileHash -LiteralPath $target.Output -Algorithm SHA256).Hash
    Write-Host "  Output: $($target.Output)" -ForegroundColor DarkGray
    Write-Host "  SHA256: $hash" -ForegroundColor DarkGray

    if ($Deploy) {
        Write-Host "  Deploying to $($target.DeployPath)..." -ForegroundColor Yellow
        Copy-Item -LiteralPath $target.Output -Destination $target.DeployPath -Force
    }
}

Write-Host 'All FoundryPlugin targets completed successfully.' -ForegroundColor Green
