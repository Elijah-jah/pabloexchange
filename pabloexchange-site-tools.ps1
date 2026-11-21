#Requires -Version 5.1
<#
    PabloExchange - Site tools installer (v1)
    =========================================
    1. GIFT CARDS: the "Will be delivered in X days" line is rewritten as a
       plain grey description-style line (same look as the reference site) -
       no green colour, no icon. The text itself (and your duration field)
       is preserved automatically.
    2. SITE LOGO: new "Site settings" record in the admin (Pages -> Site
       settings) where you upload the website logo. The favicon on every
       page and the brand badge (sidebar, mobile menu, login, sign up,
       landing page) automatically use the uploaded logo, falling back to
       the current icon when no logo is uploaded yet.

    Safe to re-run: every step checks whether it is already applied.
    A backup (.bak-sitetools) is created for every file before it is touched.
#>

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "   PabloExchange - Site tools installer  v1" -ForegroundColor Magenta
Write-Host "   gift duration style + admin site logo / favicon" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host ""

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
function Read-Utf8([string]$Path) {
    return [IO.File]::ReadAllText($Path, (New-Object System.Text.UTF8Encoding($false)))
}
function Write-Utf8([string]$Path, [string]$Content) {
    [IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding($false)))
}
function Decode([string]$B64) {
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($B64))
}
function Backup-Once([string]$Path) {
    $bak = "$Path.bak-sitetools"
    if (-not (Test-Path $bak)) { Copy-Item $Path $bak -Force }
}
function Count-Occurrences([string]$Haystack, [string]$Needle) {
    $n = 0; $i = 0
    while (($i = $Haystack.IndexOf($Needle, $i)) -ge 0) { $n++; $i += $Needle.Length }
    return $n
}
function Normalize-LF([string]$s) { return ($s -replace "`r`n", "`n") }
function Restore-CRLF([string]$s) { return (($s -replace "`r`n", "`n") -replace "`n", "`r`n") }
function Ok([string]$m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Skip([string]$m) { Write-Host "  [SKIP] $m" -ForegroundColor DarkGray }
function Warn([string]$m) { $script:Warnings += $m; Write-Host "  [WARN] $m" -ForegroundColor Yellow }

function Bump-StaticVersion([string]$Content, [string]$StaticName) {
    # Bumps  {% static 'NAME' %}?v=N  ->  v=N+1   (single or double quotes)
    $pat = "(" + [regex]::Escape($StaticName) + ")(['""]\s*%\}\?v=)(\d+)"
    $m = [regex]::Match($Content, $pat)
    if ($m.Success) {
        $v = [int]$m.Groups[3].Value + 1
        $rep = $m.Groups[1].Value + $m.Groups[2].Value + $v
        return $Content.Remove($m.Index, $m.Length).Insert($m.Index, $rep)
    }
    return $Content
}

$script:Warnings = @()
$script:Changed  = @()

# ---------------------------------------------------------------
# Locate project root
# ---------------------------------------------------------------
$root = (Get-Location).Path
if (-not (Test-Path (Join-Path $root 'manage.py')) -or
    -not (Test-Path (Join-Path $root 'config\settings.py'))) {
    Write-Host ""
    Write-Host "ERROR: manage.py / config\settings.py not found." -ForegroundColor Red
    Write-Host "Run this script from the project root, e.g.:" -ForegroundColor Red
    Write-Host "  cd C:\Users\user\OneDrive\Desktop\Pabloexchange" -ForegroundColor Red
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\pabloexchange-site-tools.ps1" -ForegroundColor Red
    exit 1
}
Write-Host "Project root: $root" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------
# Payloads (base64-encoded file contents)
# ---------------------------------------------------------------
$B64_MODEL_PY = 'CgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyBTaXRlIHNldHRpbmdzIChzaW5nbGV0b24pIC0gdGhlIHVwbG9hZGVkIGxvZ28gcG93ZXJzIHRoZSBmYXZpY29uICsgYnJhbmQKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KY2xhc3MgU2l0ZVNldHRpbmdzKG1vZGVscy5Nb2RlbCk6CiAgICBzaXRlX25hbWUgPSBtb2RlbHMuQ2hhckZpZWxkKG1heF9sZW5ndGg9MTAwLCBkZWZhdWx0PSJQYWJsb0V4Y2hhbmdlIikKICAgIGxvZ28gPSBtb2RlbHMuSW1hZ2VGaWVsZCh1cGxvYWRfdG89InNpdGUvIiwgYmxhbms9VHJ1ZSwgbnVsbD1UcnVlLCBtYXhfbGVuZ3RoPTI1NSkKICAgIHVwZGF0ZWRfYXQgPSBtb2RlbHMuRGF0ZVRpbWVGaWVsZChhdXRvX25vdz1UcnVlKQoKICAgIGNsYXNzIE1ldGE6CiAgICAgICAgdmVyYm9zZV9uYW1lID0gIlNpdGUgc2V0dGluZ3MiCiAgICAgICAgdmVyYm9zZV9uYW1lX3BsdXJhbCA9ICJTaXRlIHNldHRpbmdzIgoKICAgIGRlZiBfX3N0cl9fKHNlbGYpOgogICAgICAgIHJldHVybiAiU2l0ZSBzZXR0aW5ncyIK'
$B64_ADMIN_PY = 'CgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyBTaXRlIHNldHRpbmdzIC0gYSBzaW5nbGUgZWRpdGFibGUgcmVjb3JkIChzaXRlIG5hbWUgKyBsb2dvKQojIC0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLQpmcm9tIGRqYW5nby5zaG9ydGN1dHMgaW1wb3J0IHJlZGlyZWN0IGFzIF9yZWRpcmVjdApmcm9tIGRqYW5nby51dGlscy5odG1sIGltcG9ydCBmb3JtYXRfaHRtbCBhcyBfZm9ybWF0X2h0bWwKCmZyb20gLm1vZGVscyBpbXBvcnQgU2l0ZVNldHRpbmdzCgoKQGFkbWluLnJlZ2lzdGVyKFNpdGVTZXR0aW5ncykKY2xhc3MgU2l0ZVNldHRpbmdzQWRtaW4oYWRtaW4uTW9kZWxBZG1pbik6CiAgICBsaXN0X2Rpc3BsYXkgPSAoInNpdGVfbmFtZSIsICJsb2dvX3ByZXZpZXciLCAidXBkYXRlZF9hdCIpCiAgICByZWFkb25seV9maWVsZHMgPSAoImxvZ29fcHJldmlldyIsICJ1cGRhdGVkX2F0IikKICAgIGZpZWxkcyA9ICgic2l0ZV9uYW1lIiwgImxvZ28iLCAibG9nb19wcmV2aWV3IiwgInVwZGF0ZWRfYXQiKQoKICAgIEBhZG1pbi5kaXNwbGF5KGRlc2NyaXB0aW9uPSJDdXJyZW50IGxvZ28iKQogICAgZGVmIGxvZ29fcHJldmlldyhzZWxmLCBvYmopOgogICAgICAgIGlmIG9iaiBhbmQgb2JqLmxvZ286CiAgICAgICAgICAgIHJldHVybiBfZm9ybWF0X2h0bWwoCiAgICAgICAgICAgICAgICAnPGltZyBzcmM9Int9IiBhbHQ9IiIgc3R5bGU9ImhlaWdodDo0OHB4O21heC13aWR0aDoyMjBweDtib3JkZXItcmFkaXVzOjhweDtiYWNrZ3JvdW5kOiNmZmY7cGFkZGluZzo0cHg7Ij4nLAogICAgICAgICAgICAgICAgb2JqLmxvZ28udXJsLAogICAgICAgICAgICApCiAgICAgICAgcmV0dXJuICJObyBsb2dvIHVwbG9hZGVkIHlldCIKCiAgICBkZWYgaGFzX2FkZF9wZXJtaXNzaW9uKHNlbGYsIHJlcXVlc3QpOgogICAgICAgICMgT25seSBvbmUgU2l0ZSBzZXR0aW5ncyByZWNvcmQgbWF5IGV2ZXIgZXhpc3QuCiAgICAgICAgcmV0dXJuIG5vdCBTaXRlU2V0dGluZ3Mub2JqZWN0cy5leGlzdHMoKQoKICAgIGRlZiBjaGFuZ2VsaXN0X3ZpZXcoc2VsZiwgcmVxdWVzdCwgZXh0cmFfY29udGV4dD1Ob25lKToKICAgICAgICAjIEp1bXAgc3RyYWlnaHQgaW50byB0aGUgc2luZ2xlIHJlY29yZCBpbnN0ZWFkIG9mIHNob3dpbmcgYSBsaXN0LgogICAgICAgIG9iaiA9IFNpdGVTZXR0aW5ncy5vYmplY3RzLmZpcnN0KCkKICAgICAgICBpZiBvYmogaXMgbm90IE5vbmU6CiAgICAgICAgICAgIHJldHVybiBfcmVkaXJlY3QoImFkbWluOnBhZ2VzX3NpdGVzZXR0aW5nc19jaGFuZ2UiLCBvYmoucGspCiAgICAgICAgcmV0dXJuIHN1cGVyKCkuY2hhbmdlbGlzdF92aWV3KHJlcXVlc3QsIGV4dHJhX2NvbnRleHQpCg=='
$B64_CTX_PY = 'IiIiVGVtcGxhdGUgY29udGV4dCBwcm9jZXNzb3JzIGZvciB0aGUgcGFnZXMgYXBwLiIiIgoKZnJvbSAubW9kZWxzIGltcG9ydCBTaXRlU2V0dGluZ3MKCgpkZWYgc2l0ZV9zZXR0aW5ncyhyZXF1ZXN0KToKICAgICIiIkV4cG9zZSB0aGUgU2l0ZSBzZXR0aW5ncyByZWNvcmQgdG8gZXZlcnkgdGVtcGxhdGUgYXMgYHNpdGVfc2V0dGluZ3NgLgoKICAgIFdyYXBwZWQgaW4gdHJ5L2V4Y2VwdCBzbyB0aGUgc2l0ZSBrZWVwcyB3b3JraW5nIGV2ZW4gYmVmb3JlIHRoZQogICAgbWlncmF0aW9uIGZvciB0aGUgbmV3IHRhYmxlIGhhcyBiZWVuIGFwcGxpZWQuCiAgICAiIiIKICAgIHRyeToKICAgICAgICByZXR1cm4geyJzaXRlX3NldHRpbmdzIjogU2l0ZVNldHRpbmdzLm9iamVjdHMuZmlyc3QoKX0KICAgIGV4Y2VwdCBFeGNlcHRpb246CiAgICAgICAgcmV0dXJuIHsic2l0ZV9zZXR0aW5ncyI6IE5vbmV9Cg=='
$B64_MIGRATION_PY = 'IyBHZW5lcmF0ZWQgYnkgcGFibG9leGNoYW5nZS1zaXRlLXRvb2xzLnBzMQpmcm9tIGRqYW5nby5kYiBpbXBvcnQgbWlncmF0aW9ucywgbW9kZWxzCgoKY2xhc3MgTWlncmF0aW9uKG1pZ3JhdGlvbnMuTWlncmF0aW9uKToKCiAgICBpbml0aWFsID0gVHJ1ZQoKICAgIGRlcGVuZGVuY2llcyA9IFsKICAgIF0KCiAgICBvcGVyYXRpb25zID0gWwogICAgICAgIG1pZ3JhdGlvbnMuQ3JlYXRlTW9kZWwoCiAgICAgICAgICAgIG5hbWU9J1NpdGVTZXR0aW5ncycsCiAgICAgICAgICAgIGZpZWxkcz1bCiAgICAgICAgICAgICAgICAoJ2lkJywgbW9kZWxzLkJpZ0F1dG9GaWVsZChhdXRvX2NyZWF0ZWQ9VHJ1ZSwgcHJpbWFyeV9rZXk9VHJ1ZSwgc2VyaWFsaXplPUZhbHNlLCB2ZXJib3NlX25hbWU9J0lEJykpLAogICAgICAgICAgICAgICAgKCdzaXRlX25hbWUnLCBtb2RlbHMuQ2hhckZpZWxkKGRlZmF1bHQ9J1BhYmxvRXhjaGFuZ2UnLCBtYXhfbGVuZ3RoPTEwMCkpLAogICAgICAgICAgICAgICAgKCdsb2dvJywgbW9kZWxzLkltYWdlRmllbGQoYmxhbms9VHJ1ZSwgbWF4X2xlbmd0aD0yNTUsIG51bGw9VHJ1ZSwgdXBsb2FkX3RvPSdzaXRlLycpKSwKICAgICAgICAgICAgICAgICgndXBkYXRlZF9hdCcsIG1vZGVscy5EYXRlVGltZUZpZWxkKGF1dG9fbm93PVRydWUpKSwKICAgICAgICAgICAgXSwKICAgICAgICAgICAgb3B0aW9ucz17CiAgICAgICAgICAgICAgICAndmVyYm9zZV9uYW1lJzogJ1NpdGUgc2V0dGluZ3MnLAogICAgICAgICAgICAgICAgJ3ZlcmJvc2VfbmFtZV9wbHVyYWwnOiAnU2l0ZSBzZXR0aW5ncycsCiAgICAgICAgICAgIH0sCiAgICAgICAgKSwKICAgIF0K'
$B64_CSS_LOGO = 'CgovKiA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KICAgVVBMT0FERUQgU0lURSBMT0dPICAoQWRtaW4gLT4gUGFnZXMgLT4gU2l0ZSBzZXR0aW5ncykKICAgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09ICovCi5sb2dvLWJhZGdlLmxvZ28tYmFkZ2UtaW1nIHsKICAgIHBhZGRpbmc6IDNweDsKICAgIG92ZXJmbG93OiBoaWRkZW47CiAgICBiYWNrZ3JvdW5kOiB2YXIoLS1weC13aGl0ZSwgI2ZmZmZmZik7Cn0KLmxvZ28tYmFkZ2UubG9nby1iYWRnZS1pbWc6OmFmdGVyIHsgZGlzcGxheTogbm9uZTsgfQoubG9nby1iYWRnZS5sb2dvLWJhZGdlLWltZyBpbWcgewogICAgZGlzcGxheTogYmxvY2s7CiAgICB3aWR0aDogMTAwJTsKICAgIGhlaWdodDogMTAwJTsKICAgIGJvcmRlci1yYWRpdXM6IDhweDsKICAgIG9iamVjdC1maXQ6IGNvbnRhaW47Cn0K'
$B64_CSS_DURATION = 'CgovKiA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KICAgR0lGVCBERUxJVkVSWSBEVVJBVElPTiAtIHBsYWluIGdyZXkgZGVzY3JpcHRpb24gc3R5bGUKICAgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09ICovCnAuZ2lmdC1kdXJhdGlvbi1wbGFpbiB7CiAgICBkaXNwbGF5OiAtd2Via2l0LWJveDsKICAgIG1pbi1oZWlnaHQ6IDMuMWVtOwogICAgbWFyZ2luOiA3cHggMCAwOwogICAgb3ZlcmZsb3c6IGhpZGRlbjsKICAgIGNvbG9yOiB2YXIoLS1naWZ0LW11dGVkLCAjNmI3MjgwKTsKICAgIGZvbnQtc2l6ZTogLjhyZW07CiAgICBmb250LXdlaWdodDogNDAwOwogICAgbGluZS1oZWlnaHQ6IDEuNTU7CiAgICBvdmVyZmxvdy13cmFwOiBhbnl3aGVyZTsKICAgIC13ZWJraXQtYm94LW9yaWVudDogdmVydGljYWw7CiAgICAtd2Via2l0LWxpbmUtY2xhbXA6IDI7Cn0KcC5naWZ0LWR1cmF0aW9uLXBsYWluLmlzLWVtcHR5IHsgdmlzaWJpbGl0eTogaGlkZGVuOyB9Cg=='

# ===============================================================
# PART 1 - pages/models.py : SiteSettings model
# ===============================================================
Write-Host "1. pages\models.py - SiteSettings model" -ForegroundColor Cyan
$modelsPath = Join-Path $root 'pages\models.py'
if (-not (Test-Path $modelsPath)) { throw "pages\models.py not found." }
$models = Read-Utf8 $modelsPath
if ($models.Contains('class SiteSettings')) {
    Skip "SiteSettings model already present"
} else {
    Backup-Once $modelsPath
    if (-not $models.Contains('from django.db import models')) {
        $models = "from django.db import models`n" + $models
    }
    $models = $models.TrimEnd() + "`n" + (Decode $B64_MODEL_PY)
    Write-Utf8 $modelsPath $models
    $script:Changed += 'pages\models.py'
    Ok "SiteSettings model added"
}

# ===============================================================
# PART 2 - pages/admin.py : singleton admin with logo preview
# ===============================================================
Write-Host "2. pages\admin.py - Site settings admin" -ForegroundColor Cyan
$adminPath = Join-Path $root 'pages\admin.py'
if (-not (Test-Path $adminPath)) { throw "pages\admin.py not found." }
$admin = Read-Utf8 $adminPath
if ($admin.Contains('SiteSettingsAdmin')) {
    Skip "SiteSettingsAdmin already registered"
} else {
    Backup-Once $adminPath
    if (-not $admin.Contains('from django.contrib import admin')) {
        $admin = "from django.contrib import admin`n" + $admin
    }
    $admin = $admin.TrimEnd() + "`n" + (Decode $B64_ADMIN_PY)
    Write-Utf8 $adminPath $admin
    $script:Changed += 'pages\admin.py'
    Ok "Site settings admin registered (single record, logo preview)"
}

# ===============================================================
# PART 3 - pages/context_processors.py : expose site_settings
# ===============================================================
Write-Host "3. pages\context_processors.py - expose logo to templates" -ForegroundColor Cyan
$ctxPath = Join-Path $root 'pages\context_processors.py'
if ((Test-Path $ctxPath) -and (Read-Utf8 $ctxPath).Contains('def site_settings')) {
    Skip "context processor already exists"
} else {
    Write-Utf8 $ctxPath (Decode $B64_CTX_PY)
    $script:Changed += 'pages\context_processors.py'
    Ok "pages\context_processors.py created"
}

# ===============================================================
# PART 4 - pages/migrations/0001_initial.py
# ===============================================================
Write-Host "4. pages\migrations - database migration" -ForegroundColor Cyan
$migDir = Join-Path $root 'pages\migrations'
if (-not (Test-Path $migDir)) { New-Item -ItemType Directory -Path $migDir -Force | Out-Null }
$initFile = Join-Path $migDir '__init__.py'
if (-not (Test-Path $initFile)) { Write-Utf8 $initFile "" }
$numbered = Get-ChildItem $migDir -Filter '0*.py' -ErrorAction SilentlyContinue
$hasMig = $false
foreach ($f in $numbered) {
    if ((Read-Utf8 $f.FullName).Contains('SiteSettings')) { $hasMig = $true }
}
if ($hasMig) {
    Skip "a SiteSettings migration already exists"
} elseif ($numbered.Count -eq 0) {
    Write-Utf8 (Join-Path $migDir '0001_initial.py') (Decode $B64_MIGRATION_PY)
    $script:Changed += 'pages\migrations\0001_initial.py'
    Ok "pages\migrations\0001_initial.py written"
} else {
    Warn "pages already has migrations but none for SiteSettings. Run:  python manage.py makemigrations pages  then commit the new file."
}

# ===============================================================
# PART 5 - config/settings.py : register the context processor
# ===============================================================
Write-Host "5. config\settings.py - template context processor" -ForegroundColor Cyan
$settingsPath = Join-Path $root 'config\settings.py'
$settings = Read-Utf8 $settingsPath
if ($settings.Contains('pages.context_processors.site_settings')) {
    Skip "context processor already registered"
} else {
    $anchor = "'wallet.context_processors.global_balance',"
    if ((Count-Occurrences $settings $anchor) -ne 1) {
        throw "Anchor not found once in config\settings.py: $anchor"
    }
    Backup-Once $settingsPath
    $settings = $settings.Replace($anchor, $anchor + "`n                'pages.context_processors.site_settings',")
    Write-Utf8 $settingsPath $settings
    $script:Changed += 'config\settings.py'
    Ok "context processor registered"
}

# ===============================================================
# PART 6 - Templates: favicon + brand badge use the uploaded logo
# ===============================================================
Write-Host "6. Templates - favicon + brand badge" -ForegroundColor Cyan

$favOld = '<link rel="icon" type="image/png" href="{% static ''img/favicon.png'' %}">'
$favNew = '{% if site_settings and site_settings.logo %}' +
          '<link rel="icon" href="{{ site_settings.logo.url }}">' +
          '{% else %}' + $favOld + '{% endif %}'

$badgeA  = '<span class="logo-badge"><i class="bi bi-globe2"></i></span>'
$badgeB  = '<span class="logo-badge"><i class="bi bi-globe2" aria-hidden="true"></i></span>'
$badgeImg = '<span class="logo-badge logo-badge-img"><img src="{{ site_settings.logo.url }}" alt="PabloExchange logo"></span>'

$templateJobs = @(
    @{ Path = 'templates\base.html';                Css = 'css/base.css'  },
    @{ Path = 'templates\accounts\login.html';      Css = 'css/login.css' },
    @{ Path = 'templates\accounts\signup.html';     Css = 'css/login.css' },
    @{ Path = 'templates\pages\home.html';          Css = 'css/home.css'  }
)

foreach ($job in $templateJobs) {
    $tplPath = Join-Path $root $job.Path
    if (-not (Test-Path $tplPath)) { Warn "$($job.Path) not found - skipped"; continue }
    $t = Read-Utf8 $tplPath
    if ($t.Contains('site_settings.logo')) {
        Skip "$($job.Path) already uses the uploaded logo"
        continue
    }
    Backup-Once $tplPath
    $nFav = Count-Occurrences $t $favOld
    $nA   = Count-Occurrences $t $badgeA
    $nB   = Count-Occurrences $t $badgeB
    if ($nFav -gt 0) {
        $t = $t.Replace($favOld, $favNew)
    }
    if ($nA -gt 0) {
        $t = $t.Replace($badgeA, '{% if site_settings and site_settings.logo %}' + $badgeImg + '{% else %}' + $badgeA + '{% endif %}')
    }
    if ($nB -gt 0) {
        $t = $t.Replace($badgeB, '{% if site_settings and site_settings.logo %}' + $badgeImg + '{% else %}' + $badgeB + '{% endif %}')
    }
    if ($nFav + $nA + $nB -eq 0) {
        Warn "$($job.Path): no favicon / logo-badge anchors found - left unchanged"
        continue
    }
    $t = Bump-StaticVersion $t $job.Css
    Write-Utf8 $tplPath $t
    $script:Changed += $job.Path
    Ok "$($job.Path): favicon=$nFav, brand badge=$(($nA + $nB))"
}

# ===============================================================
# PART 7 - CSS: image-badge styles in base/login/home stylesheets
# ===============================================================
Write-Host "7. CSS - uploaded-logo badge styles" -ForegroundColor Cyan
$cssLogo = Decode $B64_CSS_LOGO
foreach ($cssRel in @('static\css\base.css', 'static\css\login.css', 'static\css\home.css')) {
    $cssPath = Join-Path $root $cssRel
    if (-not (Test-Path $cssPath)) { Warn "$cssRel not found - skipped"; continue }
    $c = Read-Utf8 $cssPath
    if ($c.Contains('logo-badge-img')) {
        Skip "$cssRel already has logo-badge-img styles"
        continue
    }
    Backup-Once $cssPath
    $c = $c.TrimEnd() + "`n" + $cssLogo
    Write-Utf8 $cssPath $c
    $script:Changed += $cssRel
    Ok "$cssRel updated"
}

# ===============================================================
# PART 8 - gift_sending.html: restyle the "Will be delivered" line
#          as a plain grey description line (like the reference site)
# ===============================================================
Write-Host "8. gifts\templates\gifts\gift_sending.html - delivery duration style" -ForegroundColor Cyan
$giftTplPath = Join-Path $root 'gifts\templates\gifts\gift_sending.html'
if (-not (Test-Path $giftTplPath)) {
    Warn "gifts\templates\gifts\gift_sending.html not found - skipped"
} else {
    $g = Read-Utf8 $giftTplPath
    if ($g.Contains('gift-duration-plain')) {
        Skip "delivery duration already restyled"
    } else {
        $wasCrlf = $g.Contains("`r`n")
        $w = Normalize-LF $g
        # Find the INNERMOST element (p/div/span) that renders the "delivered in" text.
        $pattern = '(?=(<(p|div|span)\b[^>]*>(?:(?!</\2>).)*?delivered\s+in(?:(?!</\2>).)*?</\2>))'
        $rx = New-Object System.Text.RegularExpressions.Regex($pattern, 'IgnoreCase, Singleline')
        $best = $null
        foreach ($mm in $rx.Matches($w)) {
            if ($null -eq $best -or $mm.Groups[1].Index -gt $best.Groups[1].Index) { $best = $mm }
        }
        if ($null -eq $best) {
            Warn "Could not find the 'Will be delivered' element in gift_sending.html."
            Warn "Send me the current gift_sending.html and I will adjust the patch."
        } else {
            $start = $best.Groups[1].Index
            $full  = $best.Groups[1].Value
            $inner = [regex]::Replace($full,  '^<(?:p|div|span)\b[^>]*>', '', 'IgnoreCase, Singleline')
            $inner = [regex]::Replace($inner, '</(?:p|div|span)>\s*$', '', 'IgnoreCase, Singleline').Trim()
            # strip any icon tags (<i class="bi bi-truck"></i> etc.), keep the text
            $inner = [regex]::Replace($inner, '<i\b[^>]*>\s*</i>', '')
            $inner = [regex]::Replace($inner, '<i\b[^>]*/\s*>', '')
            $inner = ([regex]::Replace($inner, '\s+', ' ')).Trim()
            # reuse the product variable inside {{ ... }} for the empty-check
            $vm = [regex]::Match($inner, '\{\{\s*(?<expr>[^}|]+?)(?:\|[^}]*)?\s*\}\}')
            if ($vm.Success) {
                $expr = $vm.Groups['expr'].Value.Trim()
                $newEl = '<p class="gift-duration-plain{% if not ' + $expr + ' %} is-empty{% endif %}"' +
                         '{% if not ' + $expr + ' %} aria-hidden="true"{% endif %}>' + $inner + '</p>'
            } else {
                $newEl = '<p class="gift-duration-plain">' + $inner + '</p>'
            }
            Backup-Once $giftTplPath
            # also remove an icon sitting immediately BEFORE the element (sibling icon)
            $pre = [regex]::Replace($w.Substring(0, $start), '<i\b[^>]*>\s*</i>\s*$', '', 'IgnoreCase')
            $w = $pre + $newEl + $w.Substring($start + $full.Length)
            $w = Bump-StaticVersion $w 'gift_sending.css'
            if ($wasCrlf) { $w = Restore-CRLF $w }
            Write-Utf8 $giftTplPath $w
            $script:Changed += 'gifts\templates\gifts\gift_sending.html'
            Ok "restyled line: $inner"
        }
    }
}

# ===============================================================
# PART 9 - gifts/css/gift_sending.css: plain description styles
# ===============================================================
Write-Host "9. gifts\static\gifts\css\gift_sending.css - duration styles" -ForegroundColor Cyan
$giftCssPath = Join-Path $root 'gifts\static\gifts\css\gift_sending.css'
if (-not (Test-Path $giftCssPath)) {
    Warn "gifts\static\gifts\css\gift_sending.css not found - skipped"
} else {
    $gc = Read-Utf8 $giftCssPath
    if ($gc.Contains('gift-duration-plain')) {
        Skip "duration styles already present"
    } else {
        Backup-Once $giftCssPath
        $gc = $gc.TrimEnd() + "`n" + (Decode $B64_CSS_DURATION)
        Write-Utf8 $giftCssPath $gc
        $script:Changed += 'gifts\static\gifts\css\gift_sending.css'
        Ok "duration styles appended"
    }
}

# ===============================================================
# Summary + git
# ===============================================================
Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "   SUMMARY" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta
if ($script:Changed.Count -gt 0) {
    Write-Host "Changed files:" -ForegroundColor Cyan
    foreach ($f in $script:Changed) { Write-Host "  - $f" }
} else {
    Write-Host "No files needed changes (everything already applied)." -ForegroundColor DarkGray
}
foreach ($wmsg in $script:Warnings) { Write-Host "  WARNING: $wmsg" -ForegroundColor Yellow }

if ($script:Changed.Count -gt 0) {
    Write-Host ""
    Write-Host "Committing and pushing..." -ForegroundColor Cyan
    try {
        git add -A
        git commit -m "Site logo (admin upload -> favicon + brand) and plain delivery-duration style"
        git push
        Ok "pushed to git"
    } catch {
        Warn "git commit/push failed - run these yourself:"
        Write-Host "  git add -A" -ForegroundColor Yellow
        Write-Host "  git commit -m ""Site logo + delivery duration style""" -ForegroundColor Yellow
        Write-Host "  git push" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "NEXT STEPS" -ForegroundColor Magenta
Write-Host "  Local test:   python manage.py migrate   then  python manage.py runserver" -ForegroundColor White
Write-Host "  Render Shell (after deploy finishes):" -ForegroundColor White
Write-Host "     python manage.py migrate" -ForegroundColor White
Write-Host "     python manage.py collectstatic --noinput" -ForegroundColor White
Write-Host "  Then in the admin:  Pages -> Site settings -> upload your logo." -ForegroundColor White
Write-Host "  Hard-refresh the site (Ctrl+Shift+R). Browsers cache favicons" -ForegroundColor White
Write-Host "  aggressively, so the tab icon can take a little while to swap." -ForegroundColor White
Write-Host ""
