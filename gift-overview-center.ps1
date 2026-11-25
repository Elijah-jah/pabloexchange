# ============================================================================
# PabloExchange - center the gift overview popup on phones (v1)
# ============================================================================
# WHY: the site's mobile CSS turns every ".gift-modal" into a bottom sheet
#      (align-items: flex-end inside @media max-width: 560px). The new
#      overview popup inherited that, so on phones it hangs off the bottom
#      of the screen. This update pins ONLY the overview popup back to the
#      vertical center. The order form keeps its bottom-sheet style.
#
#   Files touched:
#     - gifts\static\gifts\css\gift_sending.css   (one small block appended)
#     - gifts\templates\gifts\gift_sending.html   (css version number bumped)
#
#   No database changes. Safe to re-run: it skips when already applied.
#   Originals are kept as *.bak-center files.
#
# HOW TO RUN
#   1. Copy this file into your project folder (next to manage.py):
#        Copy-Item "$env:USERPROFILE\Downloads\gift-overview-center.ps1" .
#   2. Then:
#        powershell -ExecutionPolicy Bypass -File .\gift-overview-center.ps1
#   3. After Render shows "Deploy live", in the Render Shell run:
#        python manage.py collectstatic --noinput
#   4. Hard-refresh the gifts page on your phone.
# ============================================================================

$ErrorActionPreference = "Stop"

function Read-Any([string]$p) {
    $bytes = [IO.File]::ReadAllBytes($p)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        return [Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        return [Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        return [Text.Encoding]::BigEndianUnicode.GetString($bytes, 2, $bytes.Length - 2)
    }
    $probe = [Math]::Min($bytes.Length, 8000)
    for ($i = 0; $i -lt $probe; $i++) {
        if ($bytes[$i] -eq 0) {
            if (($i % 2) -eq 0) { return [Text.Encoding]::BigEndianUnicode.GetString($bytes) }
            return [Text.Encoding]::Unicode.GetString($bytes)
        }
    }
    return [Text.Encoding]::UTF8.GetString($bytes)
}
function Write-Utf8([string]$p, [string]$c) {
    [IO.File]::WriteAllText($p, $c, (New-Object System.Text.UTF8Encoding($false)))
}
function Backup-Once([string]$p) {
    $bak = "$p.bak-center"
    if (-not (Test-Path $bak)) { Copy-Item $p $bak }
}

$root = (Get-Location).Path
if (-not (Test-Path (Join-Path $root "manage.py"))) {
    Write-Host "ERROR: manage.py not found here." -ForegroundColor Red
    Write-Host "cd into your PabloExchange project folder and run again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Project root: $root" -ForegroundColor Cyan
Write-Host "FIX: center the gift overview popup on phones (v1)" -ForegroundColor Magenta

$cssBlock = @"

/* ---- keep the overview popup centered on phones (not a bottom sheet) ---- */
@media (max-width: 560px) {
    #giftOverviewModal { align-items: center; }
    #giftOverviewModal .gift-overview-dialog { max-height: calc(100dvh - 32px); }
}
"@

$changed = @()

# --- STEP 1: append the centering rule to the gifts css ---------------------
Write-Host ""
Write-Host "1. gifts\static\gifts\css\gift_sending.css" -ForegroundColor Cyan
$cssRel = 'gifts\static\gifts\css\gift_sending.css'
$cssPath = Join-Path $root $cssRel
if (-not (Test-Path $cssPath)) {
    Write-Host "ERROR: $cssRel not found." -ForegroundColor Red
    exit 1
}
$c = Read-Any $cssPath
if ($c.Contains('keep the overview popup centered')) {
    Write-Host "[skip] centering rule already present" -ForegroundColor DarkGray
} elseif (-not $c.Contains('gift-overview-dialog')) {
    Write-Host "ERROR: this css has no overview styles yet." -ForegroundColor Red
    Write-Host "Run gift-overview-update.ps1 first, then this one." -ForegroundColor Yellow
    exit 1
} else {
    Backup-Once $cssPath
    $c = $c.TrimEnd() + "`n" + ($cssBlock -replace "`r`n", "`n").TrimStart("`n")
    Write-Utf8 $cssPath $c
    $changed += $cssRel
    Write-Host "[ok] overview popup will stay centered on phones" -ForegroundColor Green
}

# --- STEP 2: bump the css version in the template so phones refetch it ------
Write-Host ""
Write-Host "2. gifts\templates\gifts\gift_sending.html (css version bump)" -ForegroundColor Cyan
$tplRel = 'gifts\templates\gifts\gift_sending.html'
$tplPath = Join-Path $root $tplRel
if (-not (Test-Path $tplPath)) {
    Write-Host "WARNING: $tplRel not found - version not bumped, do a hard refresh later" -ForegroundColor Yellow
} else {
    $t = Read-Any $tplPath
    $m = [regex]::Match($t, "gift_sending\.css'\s*%\}\?v=(\d+)")
    if (-not $m.Success) {
        Write-Host "WARNING: css version tag not found - skipped bump" -ForegroundColor Yellow
    } else {
        $v = [int]$m.Groups[1].Value + 1
        Backup-Once $tplPath
        $t = $t.Substring(0, $m.Groups[1].Index) + $v + $t.Substring($m.Groups[1].Index + $m.Groups[1].Length)
        Write-Utf8 $tplPath $t
        $changed += $tplRel
        Write-Host "[ok] gift_sending.css version bumped to v$v" -ForegroundColor Green
    }
}

# --- STEP 3: commit and push -------------------------------------------------
Write-Host ""
if ($changed.Count -eq 0) {
    Write-Host "Nothing to commit - already applied." -ForegroundColor DarkGray
} else {
    Write-Host "Changed files:" -ForegroundColor Cyan
    foreach ($f in $changed) { Write-Host "  - $f" }
    Write-Host ""
    Write-Host "Committing and pushing to git..." -ForegroundColor Cyan
    git add -A
    git commit -m "Center the gift overview popup on phones"
    git push
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "git push failed - run these two commands manually:" -ForegroundColor Yellow
        Write-Host "  git push" -ForegroundColor White
        Write-Host "If it says 'Permission denied (publickey)', ask me for the HTTPS fix." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "  DONE" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "After Render shows 'Deploy live', in the Render Shell run:" -ForegroundColor Cyan
Write-Host "  python manage.py collectstatic --noinput" -ForegroundColor White
Write-Host "Then hard-refresh the gifts page on your phone and tap a product." -ForegroundColor Cyan
Write-Host ""
