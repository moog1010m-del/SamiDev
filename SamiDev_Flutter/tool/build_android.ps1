param(
    [Parameter(Mandatory=$true)][string]$ServerUrl,
    [ValidateSet('debug','release')][string]$Mode = 'debug'
)
$ErrorActionPreference = 'Stop'
$server = [Uri]$ServerUrl
if (-not $server.IsAbsoluteUri -or $server.Scheme -ne 'https' -or $server.UserInfo -or $server.Query -or $server.Fragment -or $server.AbsolutePath -ne '/') {
    throw 'ServerUrl must be the HTTPS server origin, without a path or credentials.'
}
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if ($Mode -eq 'release') {
        & python tool/build_play.py --server-url "$($server.GetLeftPart([UriPartial]::Authority))"
        if ($LASTEXITCODE -ne 0) { throw 'Play AAB preflight/build failed. Resolve the reported facts before submission.' }
        return
    }
    & python tool/sync_assets.py
    if ($LASTEXITCODE -ne 0) { throw 'Asset sync failed; APK was not built.' }
    & flutter pub get
    if ($LASTEXITCODE -ne 0) { throw 'Dependency resolution failed.' }
    & python tool/test_play_preflight.py
    if ($LASTEXITCODE -ne 0) { throw 'Play preflight tests failed.' }
    & flutter analyze --no-pub --no-fatal-infos
    if ($LASTEXITCODE -ne 0) { throw 'Flutter analysis failed.' }
    & flutter test
    if ($LASTEXITCODE -ne 0) { throw 'Flutter tests failed.' }
    & flutter build apk "--$Mode" "--dart-define=SAMIDEV_SERVER_URL=$($server.GetLeftPart([UriPartial]::Authority))"
    if ($LASTEXITCODE -ne 0) { throw 'APK build failed.' }
    Write-Host "APK: $((Get-Location).Path)\build\app\outputs\flutter-apk\app-$Mode.apk"
} finally { Pop-Location }
