# ============================================================================
# PabloExchange - Gifts page: duration badge + product overview popup (v1)
# ============================================================================
# WHAT IT DOES
#   1. The "Will be delivered in ..." line moves OFF the card body and becomes
#      a dark pill badge on the product image (truck icon + your duration
#      text), exactly like the reference design you sent.
#   2. Tapping anywhere on a product card opens an overview popup: big
#      picture, category, product name, full description, price, a Back
#      button and a Send Gift button. Send Gift jumps straight into the
#      normal order form for that product. The card's own Send Gift button
#      still opens the order form directly.
#   3. Product cards become shorter - the tall image area and the stacked
#      empty text space are trimmed to a moderate height.
#
#   Files touched:
#     - gifts\templates\gifts\gift_sending.html
#     - gifts\static\gifts\css\gift_sending.css  (styles appended)
#     - gifts\static\gifts\js\gift_sending.js    (overview logic appended)
#
#   No database changes. Safe to re-run: each step skips when already done.
#   Originals are kept as *.bak-overview files.
#
# HOW TO RUN
#   1. Copy this file into your project folder (next to manage.py).
#   2. In PowerShell, from that folder:
#        powershell -ExecutionPolicy Bypass -File .\gift-overview-update.ps1
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
function Decode([string]$b64) { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)) }
function Backup-Once([string]$p) {
    $bak = "$p.bak-overview"
    if (-not (Test-Path $bak)) { Copy-Item $p $bak }
}
function Count-Occurrences([string]$hay, [string]$needle) {
    $n = 0; $i = 0
    while (($i = $hay.IndexOf($needle, $i)) -ge 0) { $n++; $i += $needle.Length }
    return $n
}

$root = (Get-Location).Path
if (-not (Test-Path (Join-Path $root "manage.py"))) {
    Write-Host "ERROR: manage.py not found here." -ForegroundColor Red
    Write-Host "cd into your project folder (the one that contains manage.py) and run again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Project root: $root" -ForegroundColor Cyan
Write-Host "UPDATE: gifts duration badge + overview popup (v1)" -ForegroundColor Magenta

$BADGE_B64 = "PHNwYW4gY2xhc3M9ImdpZnQtY2F0ZWdvcnktYmFkZ2UiPnt7IGNhdGVnb3J5Lm5hbWUgfX08L3NwYW4+CiAgICAgICAgICAgICAgICAgICAgICAgIHslIGlmIHByb2R1Y3QuZGVsaXZlcnlfZHVyYXRpb24gJX0KICAgICAgICAgICAgICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImdpZnQtZHVyYXRpb24tYmFkZ2UiPjxpIGNsYXNzPSJiaSBiaS10cnVjayI+PC9pPiB7eyBwcm9kdWN0LmRlbGl2ZXJ5X2R1cmF0aW9uIH19PC9zcGFuPgogICAgICAgICAgICAgICAgICAgICAgICB7JSBlbmRpZiAlfQ=="
$MODAL_B64 = "PCEtLSA9PT09PT09PT09PT09PT09PT09PSBQUk9EVUNUIE9WRVJWSUVXIE1PREFMID09PT09PT09PT09PT09PT09PT09IC0tPgo8ZGl2IGNsYXNzPSJnaWZ0LW1vZGFsIiBpZD0iZ2lmdE92ZXJ2aWV3TW9kYWwiIGhpZGRlbj4KICAgIDxkaXYgY2xhc3M9ImdpZnQtbW9kYWwtZGlhbG9nIGdpZnQtb3ZlcnZpZXctZGlhbG9nIiByb2xlPSJkaWFsb2ciIGFyaWEtbW9kYWw9InRydWUiIGFyaWEtbGFiZWxsZWRieT0iZ2lmdE92ZXJ2aWV3VGl0bGUiPgogICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iZ2lmdC1tb2RhbC1jbG9zZSIgZGF0YS1jbG9zZS1vdmVydmlldyBhcmlhLWxhYmVsPSJDbG9zZSI+CiAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS14LWxnIj48L2k+CiAgICAgICAgPC9idXR0b24+CiAgICAgICAgPGRpdiBjbGFzcz0iZ2lmdC1vdmVydmlldy1tZWRpYSI+CiAgICAgICAgICAgIDxpbWcgaWQ9ImdpZnRPdmVydmlld0ltYWdlIiBzcmM9IiIgYWx0PSIiIGhpZGRlbj4KICAgICAgICAgICAgPHNwYW4gY2xhc3M9ImdpZnQtaW1hZ2UtZmFsbGJhY2siIGlkPSJnaWZ0T3ZlcnZpZXdGYWxsYmFjayI+PGkgY2xhc3M9ImJpIGJpLWdpZnQiPjwvaT48L3NwYW4+CiAgICAgICAgICAgIDxzcGFuIGNsYXNzPSJnaWZ0LWR1cmF0aW9uLWJhZGdlIiBpZD0iZ2lmdE92ZXJ2aWV3RHVyYXRpb24iIGhpZGRlbj48aSBjbGFzcz0iYmkgYmktdHJ1Y2siPjwvaT4gPHNwYW4gaWQ9ImdpZnRPdmVydmlld0R1cmF0aW9uVGV4dCI+PC9zcGFuPjwvc3Bhbj4KICAgICAgICA8L2Rpdj4KICAgICAgICA8ZGl2IGNsYXNzPSJnaWZ0LW92ZXJ2aWV3LWJvZHkiPgogICAgICAgICAgICA8c3BhbiBjbGFzcz0iZ2lmdC1vdmVydmlldy1jYXRlZ29yeSIgaWQ9ImdpZnRPdmVydmlld0NhdGVnb3J5Ij48L3NwYW4+CiAgICAgICAgICAgIDxoMiBpZD0iZ2lmdE92ZXJ2aWV3VGl0bGUiPkdpZnQ8L2gyPgogICAgICAgICAgICA8cCBjbGFzcz0iZ2lmdC1vdmVydmlldy1kZXNjIiBpZD0iZ2lmdE92ZXJ2aWV3RGVzYyI+PC9wPgogICAgICAgICAgICA8ZGl2IGNsYXNzPSJnaWZ0LW92ZXJ2aWV3LXByaWNlIj4KICAgICAgICAgICAgICAgIDxzcGFuPlByaWNlPC9zcGFuPgogICAgICAgICAgICAgICAgPHN0cm9uZyBpZD0iZ2lmdE92ZXJ2aWV3UHJpY2UiPjwvc3Ryb25nPgogICAgICAgICAgICA8L2Rpdj4KICAgICAgICAgICAgPGRpdiBjbGFzcz0iZ2lmdC1vdmVydmlldy1hY3Rpb25zIj4KICAgICAgICAgICAgICAgIDxidXR0b24gdHlwZT0iYnV0dG9uIiBjbGFzcz0iZ2lmdC1idG4tc2Vjb25kYXJ5IiBkYXRhLWNsb3NlLW92ZXJ2aWV3PgogICAgICAgICAgICAgICAgICAgIDxpIGNsYXNzPSJiaSBiaS1hcnJvdy1sZWZ0Ij48L2k+IEJhY2sKICAgICAgICAgICAgICAgIDwvYnV0dG9uPgogICAgICAgICAgICAgICAgPGJ1dHRvbiB0eXBlPSJidXR0b24iIGNsYXNzPSJnaWZ0LWJ0bi1wcmltYXJ5IiBpZD0iZ2lmdE92ZXJ2aWV3U2VuZCI+CiAgICAgICAgICAgICAgICAgICAgPGkgY2xhc3M9ImJpIGJpLXNlbmQiPjwvaT4gU2VuZCBHaWZ0CiAgICAgICAgICAgICAgICA8L2J1dHRvbj4KICAgICAgICAgICAgPC9kaXY+CiAgICAgICAgPC9kaXY+CiAgICA8L2Rpdj4KPC9kaXY+Cgo="
$CSS_B64 = "CgovKiA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KICAgR2lmdCBjYXJkIHJlZnJlc2g6IGNvbXBhY3QgY2FyZCBoZWlnaHQsIGRlbGl2ZXJ5LWR1cmF0aW9uCiAgIGJhZGdlIG9uIHRoZSBpbWFnZSwgYW5kIHRoZSB0YXAtdG8tdmlldyBvdmVydmlldyBtb2RhbAogICA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0gKi8KCi8qIC0tLSBtb2RlcmF0ZSBjYXJkIGhlaWdodCAtLS0gKi8KLmdpZnQtcHJvZHVjdC1tZWRpYSB7IGFzcGVjdC1yYXRpbzogNCAvIDMuNjsgfQouZ2lmdC1wcm9kdWN0LWluZm8geyBtaW4taGVpZ2h0OiAwOyB9Ci5naWZ0LWNhcmQtYm9keSBoMyB7IG1pbi1oZWlnaHQ6IDIuNmVtOyB9Ci5naWZ0LXByb2R1Y3QtaW5mbyA+IHAgeyBtaW4taGVpZ2h0OiAyLjVlbTsgfQoKLyogLS0tIHdob2xlIGNhcmQgb3BlbnMgdGhlIG92ZXJ2aWV3IC0tLSAqLwouZ2lmdC1jYXJkIHsgY3Vyc29yOiBwb2ludGVyOyB9Ci5naWZ0LWNhcmQ6Zm9jdXMtdmlzaWJsZSB7IG91dGxpbmU6IDJweCBzb2xpZCB2YXIoLS1naWZ0LWdyZWVuKTsgb3V0bGluZS1vZmZzZXQ6IDJweDsgfQoKLyogLS0tIGRlbGl2ZXJ5IGR1cmF0aW9uIGJhZGdlIG9uIHRoZSBpbWFnZSAtLS0gKi8KLmdpZnQtZHVyYXRpb24tYmFkZ2UgewogICAgcG9zaXRpb246IGFic29sdXRlOwogICAgbGVmdDogMTJweDsKICAgIGJvdHRvbTogMTJweDsKICAgIHotaW5kZXg6IDI7CiAgICBkaXNwbGF5OiBpbmxpbmUtZmxleDsKICAgIGFsaWduLWl0ZW1zOiBjZW50ZXI7CiAgICBnYXA6IDZweDsKICAgIG1heC13aWR0aDogY2FsYygxMDAlIC0gMjRweCk7CiAgICBwYWRkaW5nOiA2cHggMTFweDsKICAgIGJvcmRlci1yYWRpdXM6IDk5OXB4OwogICAgYmFja2dyb3VuZDogcmdiYSgxNywgMjQsIDM5LCAuOTIpOwogICAgY29sb3I6ICNmZmY7CiAgICBmb250LXNpemU6IC42OHJlbTsKICAgIGZvbnQtd2VpZ2h0OiA3MDA7CiAgICBsaW5lLWhlaWdodDogMS4yOwogICAgd2hpdGUtc3BhY2U6IG5vd3JhcDsKICAgIG92ZXJmbG93OiBoaWRkZW47CiAgICB0ZXh0LW92ZXJmbG93OiBlbGxpcHNpczsKICAgIGJhY2tkcm9wLWZpbHRlcjogYmx1cig2cHgpOwogICAgYm94LXNoYWRvdzogMCA0cHggMTJweCByZ2JhKDAsIDAsIDAsIC4yNSk7Cn0KLmdpZnQtZHVyYXRpb24tYmFkZ2UgaSB7IGZvbnQtc2l6ZTogLjc2cmVtOyB9CgovKiAtLS0gcHJvZHVjdCBvdmVydmlldyBtb2RhbCAtLS0gKi8KLmdpZnQtb3ZlcnZpZXctZGlhbG9nIHsKICAgIHdpZHRoOiBtaW4oMTAwJSwgNDMwcHgpOwogICAgcGFkZGluZzogMDsKICAgIG92ZXJmbG93OiBoaWRkZW4gYXV0bzsKfQouZ2lmdC1vdmVydmlldy1tZWRpYSB7CiAgICBwb3NpdGlvbjogcmVsYXRpdmU7CiAgICBhc3BlY3QtcmF0aW86IDQgLyAzOwogICAgZGlzcGxheTogZmxleDsKICAgIGFsaWduLWl0ZW1zOiBjZW50ZXI7CiAgICBqdXN0aWZ5LWNvbnRlbnQ6IGNlbnRlcjsKICAgIG92ZXJmbG93OiBoaWRkZW47CiAgICBib3JkZXItYm90dG9tOiAxcHggc29saWQgI2VkZjNmMDsKICAgIGJvcmRlci1yYWRpdXM6IDIwcHggMjBweCAwIDA7CiAgICBiYWNrZ3JvdW5kOiAjZjNmN2Y1Owp9Ci5naWZ0LW92ZXJ2aWV3LW1lZGlhID4gaW1nIHsKICAgIHdpZHRoOiAxMDAlOwogICAgaGVpZ2h0OiAxMDAlOwogICAgZGlzcGxheTogYmxvY2s7CiAgICBvYmplY3QtZml0OiBjb250YWluOwp9Ci5naWZ0LW92ZXJ2aWV3LW1lZGlhIC5naWZ0LWltYWdlLWZhbGxiYWNrIHsgZm9udC1zaXplOiAzcmVtOyB9Ci5naWZ0LW92ZXJ2aWV3LWRpYWxvZyAuZ2lmdC1tb2RhbC1jbG9zZSB7CiAgICB6LWluZGV4OiAzOwogICAgYmFja2dyb3VuZDogcmdiYSgyNTUsIDI1NSwgMjU1LCAuOTIpOwogICAgYm94LXNoYWRvdzogMCAycHggOHB4IHJnYmEoMCwgMCwgMCwgLjE4KTsKfQouZ2lmdC1vdmVydmlldy1ib2R5IHsgcGFkZGluZzogMThweCAxOHB4IDIwcHg7IH0KLmdpZnQtb3ZlcnZpZXctY2F0ZWdvcnkgewogICAgZGlzcGxheTogYmxvY2s7CiAgICBjb2xvcjogdmFyKC0tZ2lmdC1ncmVlbik7CiAgICBmb250LXNpemU6IC42NnJlbTsKICAgIGZvbnQtd2VpZ2h0OiA4MDA7CiAgICBsZXR0ZXItc3BhY2luZzogLjA5ZW07CiAgICB0ZXh0LXRyYW5zZm9ybTogdXBwZXJjYXNlOwp9Ci5naWZ0LW92ZXJ2aWV3LWJvZHkgaDIgewogICAgbWFyZ2luOiA2cHggMCA4cHg7CiAgICBjb2xvcjogdmFyKC0tZ2lmdC10ZXh0KTsKICAgIGZvbnQtc2l6ZTogMS4xOHJlbTsKICAgIGZvbnQtd2VpZ2h0OiA4MDA7CiAgICBsaW5lLWhlaWdodDogMS4zOwogICAgb3ZlcmZsb3ctd3JhcDogYW55d2hlcmU7Cn0KLmdpZnQtb3ZlcnZpZXctZGVzYyB7CiAgICBtYXJnaW46IDAgMCAxNHB4OwogICAgY29sb3I6IHZhcigtLWdpZnQtbXV0ZWQpOwogICAgZm9udC1zaXplOiAuODVyZW07CiAgICBsaW5lLWhlaWdodDogMS42OwogICAgd2hpdGUtc3BhY2U6IHByZS1saW5lOwogICAgb3ZlcmZsb3ctd3JhcDogYW55d2hlcmU7Cn0KLmdpZnQtb3ZlcnZpZXctcHJpY2Ugc3BhbiB7IGRpc3BsYXk6IGJsb2NrOyBjb2xvcjogdmFyKC0tZ2lmdC1tdXRlZCk7IGZvbnQtc2l6ZTogLjY4cmVtOyB9Ci5naWZ0LW92ZXJ2aWV3LXByaWNlIHN0cm9uZyB7CiAgICBkaXNwbGF5OiBibG9jazsKICAgIG1hcmdpbi10b3A6IDJweDsKICAgIGNvbG9yOiB2YXIoLS1naWZ0LWdyZWVuKTsKICAgIGZvbnQtc2l6ZTogMS4yNXJlbTsKICAgIGZvbnQtdmFyaWFudC1udW1lcmljOiB0YWJ1bGFyLW51bXM7Cn0KLmdpZnQtb3ZlcnZpZXctYWN0aW9ucyB7CiAgICBkaXNwbGF5OiBncmlkOwogICAgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnIgMS40ZnI7CiAgICBnYXA6IDEwcHg7CiAgICBtYXJnaW4tdG9wOiAxNnB4Owp9Ci5naWZ0LW92ZXJ2aWV3LWFjdGlvbnMgYnV0dG9uIHsgd2lkdGg6IDEwMCU7IH0KCkBtZWRpYSAobWF4LXdpZHRoOiA1NjBweCkgewogICAgLmdpZnQtcHJvZHVjdC1tZWRpYSB7IGFzcGVjdC1yYXRpbzogNCAvIDMuNDsgfQogICAgLmdpZnQtZHVyYXRpb24tYmFkZ2UgewogICAgICAgIGxlZnQ6IDhweDsKICAgICAgICBib3R0b206IDhweDsKICAgICAgICBtYXgtd2lkdGg6IGNhbGMoMTAwJSAtIDE2cHgpOwogICAgICAgIHBhZGRpbmc6IDVweCA5cHg7CiAgICAgICAgZm9udC1zaXplOiAxMHB4OwogICAgfQogICAgLmdpZnQtb3ZlcnZpZXctbWVkaWEgeyBib3JkZXItcmFkaXVzOiAxOHB4IDE4cHggMCAwOyB9CiAgICAuZ2lmdC1vdmVydmlldy1ib2R5IHsgcGFkZGluZzogMTVweCAxNHB4IDE3cHg7IH0KICAgIC5naWZ0LW92ZXJ2aWV3LWJvZHkgaDIgeyBmb250LXNpemU6IDEuMDVyZW07IH0KfQoKQG1lZGlhIChtYXgtd2lkdGg6IDM1MHB4KSB7CiAgICAuZ2lmdC1wcm9kdWN0LW1lZGlhIHsgYXNwZWN0LXJhdGlvOiA0IC8gMy4yOyB9CiAgICAuZ2lmdC1vdmVydmlldy1hY3Rpb25zIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7IH0KfQo="
$JS_B64 = "CgovKiA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KICAgUHJvZHVjdCBvdmVydmlldyBtb2RhbCAtIHRhcHBpbmcgYSBjYXJkIHByZXZpZXdzIHRoZSBnaWZ0CiAgIChwaWN0dXJlLCBuYW1lLCBkZXNjcmlwdGlvbiwgcHJpY2UpIHdpdGggQmFjayBhbmQKICAgU2VuZCBHaWZ0IGJ1dHRvbnMuIFNlbmQgR2lmdCBoYW5kcyBvdmVyIHRvIHRoZSBjYXJkJ3Mgb3duCiAgIGJ1dHRvbiwgd2hpY2ggb3BlbnMgdGhlIHJlY2lwaWVudC1kZXRhaWxzIGZvcm0uCiAgID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PSAqLwooZnVuY3Rpb24gKCkgewogICAgInVzZSBzdHJpY3QiOwoKICAgIHZhciBvdmVydmlldyA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaWZ0T3ZlcnZpZXdNb2RhbCIpOwogICAgaWYgKCFvdmVydmlldykgcmV0dXJuOwoKICAgIHZhciBhY3RpdmVDYXJkID0gbnVsbDsKCiAgICBmdW5jdGlvbiBuYWlyYSh2YWx1ZSkgewogICAgICAgIHJldHVybiAiXHUyMEE2IiArIHBhcnNlRmxvYXQodmFsdWUgfHwgIjAiKS50b0xvY2FsZVN0cmluZygiZW4tVVMiLCB7CiAgICAgICAgICAgIG1pbmltdW1GcmFjdGlvbkRpZ2l0czogMiwKICAgICAgICAgICAgbWF4aW11bUZyYWN0aW9uRGlnaXRzOiAyCiAgICAgICAgfSk7CiAgICB9CgogICAgZnVuY3Rpb24gb3Blbk92ZXJ2aWV3KGNhcmQpIHsKICAgICAgICBhY3RpdmVDYXJkID0gY2FyZDsKICAgICAgICB2YXIgYnRuID0gY2FyZC5xdWVyeVNlbGVjdG9yKCIuZ2lmdC1zZW5kIik7CgogICAgICAgIHZhciBpbWFnZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaWZ0T3ZlcnZpZXdJbWFnZSIpOwogICAgICAgIHZhciBmYWxsYmFjayA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaWZ0T3ZlcnZpZXdGYWxsYmFjayIpOwogICAgICAgIHZhciBpbWFnZVVybCA9IGJ0biA/IChidG4uZ2V0QXR0cmlidXRlKCJkYXRhLWltYWdlIikgfHwgIiIpIDogIiI7CiAgICAgICAgaWYgKGltYWdlVXJsKSB7CiAgICAgICAgICAgIGltYWdlLnNyYyA9IGltYWdlVXJsOwogICAgICAgICAgICBpbWFnZS5oaWRkZW4gPSBmYWxzZTsKICAgICAgICAgICAgZmFsbGJhY2suaGlkZGVuID0gdHJ1ZTsKICAgICAgICB9IGVsc2UgewogICAgICAgICAgICBpbWFnZS5zcmMgPSAiIjsKICAgICAgICAgICAgaW1hZ2UuaGlkZGVuID0gdHJ1ZTsKICAgICAgICAgICAgZmFsbGJhY2suaGlkZGVuID0gZmFsc2U7CiAgICAgICAgfQoKICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2lmdE92ZXJ2aWV3Q2F0ZWdvcnkiKS50ZXh0Q29udGVudCA9CiAgICAgICAgICAgIGNhcmQuZ2V0QXR0cmlidXRlKCJkYXRhLWNhdGVnb3J5IikgfHwgIiI7CiAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdpZnRPdmVydmlld1RpdGxlIikudGV4dENvbnRlbnQgPQogICAgICAgICAgICBidG4gPyAoYnRuLmdldEF0dHJpYnV0ZSgiZGF0YS1wcm9kdWN0LW5hbWUiKSB8fCAiR2lmdCIpIDogIkdpZnQiOwoKICAgICAgICB2YXIgZGVzYyA9IChjYXJkLmdldEF0dHJpYnV0ZSgiZGF0YS1kZXNjIikgfHwgIiIpLnRyaW0oKTsKICAgICAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2lmdE92ZXJ2aWV3RGVzYyIpLnRleHRDb250ZW50ID0KICAgICAgICAgICAgZGVzYyB8fCAiTm8gZGVzY3JpcHRpb24gZm9yIHRoaXMgZ2lmdCB5ZXQuIjsKCiAgICAgICAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImdpZnRPdmVydmlld1ByaWNlIikudGV4dENvbnRlbnQgPQogICAgICAgICAgICBuYWlyYShidG4gPyBidG4uZ2V0QXR0cmlidXRlKCJkYXRhLXByaWNlIikgOiAiMCIpOwoKICAgICAgICB2YXIgZHVyYXRpb24gPSBidG4gPyAoYnRuLmdldEF0dHJpYnV0ZSgiZGF0YS1kdXJhdGlvbiIpIHx8ICIiKS50cmltKCkgOiAiIjsKICAgICAgICB2YXIgZHVyYXRpb25CYWRnZSA9IGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaWZ0T3ZlcnZpZXdEdXJhdGlvbiIpOwogICAgICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJnaWZ0T3ZlcnZpZXdEdXJhdGlvblRleHQiKS50ZXh0Q29udGVudCA9IGR1cmF0aW9uOwogICAgICAgIGR1cmF0aW9uQmFkZ2UuaGlkZGVuID0gIWR1cmF0aW9uOwoKICAgICAgICBvdmVydmlldy5oaWRkZW4gPSBmYWxzZTsKICAgICAgICBkb2N1bWVudC5ib2R5LnN0eWxlLm92ZXJmbG93ID0gImhpZGRlbiI7CiAgICB9CgogICAgZnVuY3Rpb24gY2xvc2VPdmVydmlldygpIHsKICAgICAgICBvdmVydmlldy5oaWRkZW4gPSB0cnVlOwogICAgICAgIGRvY3VtZW50LmJvZHkuc3R5bGUub3ZlcmZsb3cgPSAiIjsKICAgICAgICBhY3RpdmVDYXJkID0gbnVsbDsKICAgIH0KCiAgICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIuanMtZ2lmdC1vdmVydmlldyIpLmZvckVhY2goZnVuY3Rpb24gKGNhcmQpIHsKICAgICAgICBjYXJkLmFkZEV2ZW50TGlzdGVuZXIoImNsaWNrIiwgZnVuY3Rpb24gKGV2ZW50KSB7CiAgICAgICAgICAgIC8vIFRoZSBTZW5kIEdpZnQgYnV0dG9uIG9uIHRoZSBjYXJkIGtlZXBzIG9wZW5pbmcgdGhlIG9yZGVyIGZvcm0gZGlyZWN0bHkuCiAgICAgICAgICAgIGlmIChldmVudC50YXJnZXQuY2xvc2VzdCgiLmdpZnQtc2VuZCIpKSByZXR1cm47CiAgICAgICAgICAgIG9wZW5PdmVydmlldyhjYXJkKTsKICAgICAgICB9KTsKICAgICAgICBjYXJkLmFkZEV2ZW50TGlzdGVuZXIoImtleWRvd24iLCBmdW5jdGlvbiAoZXZlbnQpIHsKICAgICAgICAgICAgaWYgKGV2ZW50LnRhcmdldCAhPT0gY2FyZCkgcmV0dXJuOwogICAgICAgICAgICBpZiAoZXZlbnQua2V5ID09PSAiRW50ZXIiIHx8IGV2ZW50LmtleSA9PT0gIiAiKSB7CiAgICAgICAgICAgICAgICBldmVudC5wcmV2ZW50RGVmYXVsdCgpOwogICAgICAgICAgICAgICAgb3Blbk92ZXJ2aWV3KGNhcmQpOwogICAgICAgICAgICB9CiAgICAgICAgfSk7CiAgICB9KTsKCiAgICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCJbZGF0YS1jbG9zZS1vdmVydmlld10iKS5mb3JFYWNoKGZ1bmN0aW9uIChidG4pIHsKICAgICAgICBidG4uYWRkRXZlbnRMaXN0ZW5lcigiY2xpY2siLCBjbG9zZU92ZXJ2aWV3KTsKICAgIH0pOwoKICAgIG92ZXJ2aWV3LmFkZEV2ZW50TGlzdGVuZXIoImNsaWNrIiwgZnVuY3Rpb24gKGV2ZW50KSB7CiAgICAgICAgaWYgKGV2ZW50LnRhcmdldCA9PT0gb3ZlcnZpZXcpIGNsb3NlT3ZlcnZpZXcoKTsKICAgIH0pOwoKICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoImtleWRvd24iLCBmdW5jdGlvbiAoZXZlbnQpIHsKICAgICAgICBpZiAoZXZlbnQua2V5ID09PSAiRXNjYXBlIiAmJiAhb3ZlcnZpZXcuaGlkZGVuKSBjbG9zZU92ZXJ2aWV3KCk7CiAgICB9KTsKCiAgICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ2lmdE92ZXJ2aWV3U2VuZCIpLmFkZEV2ZW50TGlzdGVuZXIoImNsaWNrIiwgZnVuY3Rpb24gKCkgewogICAgICAgIGlmICghYWN0aXZlQ2FyZCkgcmV0dXJuOwogICAgICAgIHZhciByZWFsQnV0dG9uID0gYWN0aXZlQ2FyZC5xdWVyeVNlbGVjdG9yKCIuZ2lmdC1zZW5kIik7CiAgICAgICAgY2xvc2VPdmVydmlldygpOwogICAgICAgIGlmIChyZWFsQnV0dG9uKSByZWFsQnV0dG9uLmNsaWNrKCk7CiAgICB9KTsKfSkoKTsK"

$ART_B64 = "PGFydGljbGUgY2xhc3M9ImdpZnQtY2FyZCBqcy1naWZ0LW92ZXJ2aWV3IiB0YWJpbmRleD0iMCIgcm9sZT0iYnV0dG9uIiBkYXRhLWRlc2M9Int7IHByb2R1Y3QuZGVzY3JpcHRpb24gfX0iIGRhdGEtY2F0ZWdvcnk9Int7IGNhdGVnb3J5Lm5hbWUgfX0iPg=="

function Bump-Ver([string]$content, [string]$file) {
    $rx = New-Object System.Text.RegularExpressions.Regex([regex]::Escape($file) + "'\s*%\}\?v=(\d+)")
    $m = $rx.Match($content)
    if (-not $m.Success) { return $content }
    $v = [int]$m.Groups[1].Value + 1
    return $content.Substring(0, $m.Groups[1].Index) + $v + $content.Substring($m.Groups[1].Index + $m.Groups[1].Length)
}

$changed = @()

# ============================================================================
# STEP 1 - gifts\templates\gifts\gift_sending.html
#   - whole card becomes a button that opens the overview popup
#   - the "Will be delivered in ..." line leaves the card body and becomes a
#     dark pill badge on the product image
#   - the overview popup markup is added before the success modal
#   - css/js version numbers are bumped so browsers fetch the fresh files
# ============================================================================
Write-Host ""
Write-Host "1. gifts\templates\gifts\gift_sending.html" -ForegroundColor Cyan
$tplRel = 'gifts\templates\gifts\gift_sending.html'
$tplPath = Join-Path $root $tplRel
if (-not (Test-Path $tplPath)) {
    Write-Host "ERROR: $tplRel not found - run this from the PabloExchange project root." -ForegroundColor Red
    exit 1
}
$t = Read-Any $tplPath
if ($t.Contains('giftOverviewModal')) {
    Write-Host "[skip] template already patched" -ForegroundColor DarkGray
} else {
    $wasCrlf = $t.Contains("`r`n")
    $w = $t -replace "`r`n", "`n"
    $problems = @()

    $artAnchor = '<article class="gift-card">'
    if ((Count-Occurrences $w $artAnchor) -ne 1) { $problems += "product card tag found " + (Count-Occurrences $w $artAnchor) + " times (expected 1)" }

    $durRx = '[ \t]*\{%\s*if\s+product\.delivery_duration\s*%\}.*?\{%\s*endif\s*%\}\s*\n'
    $durCount = [regex]::Matches($w, $durRx, 'Singleline').Count
    if ($durCount -ne 1) { $problems += "delivery-duration block matched $durCount times (expected 1)" }

    $catAnchor = '<span class="gift-category-badge">{{ category.name }}</span>'
    if ((Count-Occurrences $w $catAnchor) -ne 1) { $problems += "category badge found " + (Count-Occurrences $w $catAnchor) + " times (expected 1)" }

    $succAnchor = '<div class="gift-modal" id="giftSuccessModal" hidden>'
    if ((Count-Occurrences $w $succAnchor) -ne 1) { $problems += "success modal anchor found " + (Count-Occurrences $w $succAnchor) + " times (expected 1)" }

    if ($problems.Count -gt 0) {
        Write-Host "WARNING: gift_sending.html layout differs from what this updater expects:" -ForegroundColor Yellow
        foreach ($p in $problems) { Write-Host "  - $p" -ForegroundColor Yellow }
        Write-Host "  The template was NOT modified. Send me the current file and I will adjust the patch." -ForegroundColor Yellow
    } else {
        Backup-Once $tplPath
        $w = $w.Replace($artAnchor, (Decode $ART_B64).TrimEnd("`n"))
        $w = [regex]::Replace($w, $durRx, '', 'Singleline')
        $w = $w.Replace($catAnchor, (Decode $BADGE_B64).TrimEnd("`n"))
        $w = $w.Replace($succAnchor, (Decode $MODAL_B64).TrimEnd("`n") + "`n`n" + $succAnchor)
        $w = Bump-Ver $w 'gift_sending.css'
        $w = Bump-Ver $w 'gift_sending.js'
        if ($wasCrlf) { $w = $w -replace "`n", "`r`n" }
        Write-Utf8 $tplPath $w
        $changed += $tplRel
        Write-Host "[ok] duration badge moved onto the image + overview popup added" -ForegroundColor Green
    }
}

# ============================================================================
# STEP 2 - gifts\static\gifts\css\gift_sending.css
#   appends: compact card heights, duration badge style, overview modal style
# ============================================================================
Write-Host ""
Write-Host "2. gifts\static\gifts\css\gift_sending.css" -ForegroundColor Cyan
$cssRel = 'gifts\static\gifts\css\gift_sending.css'
$cssPath = Join-Path $root $cssRel
if (-not (Test-Path $cssPath)) {
    Write-Host "WARNING: $cssRel not found - skipped" -ForegroundColor Yellow
} else {
    $c = Read-Any $cssPath
    if ($c.Contains('gift-duration-badge')) {
        Write-Host "[skip] new styles already present" -ForegroundColor DarkGray
    } else {
        Backup-Once $cssPath
        $c = $c.TrimEnd() + "`n" + (Decode $CSS_B64)
        Write-Utf8 $cssPath $c
        $changed += $cssRel
        Write-Host "[ok] styles appended (compact cards, duration badge, overview popup)" -ForegroundColor Green
    }
}

# ============================================================================
# STEP 3 - gifts\static\gifts\js\gift_sending.js
#   appends: overview popup open/close logic + Send Gift handover
# ============================================================================
Write-Host ""
Write-Host "3. gifts\static\gifts\js\gift_sending.js" -ForegroundColor Cyan
$jsRel = 'gifts\static\gifts\js\gift_sending.js'
$jsPath = Join-Path $root $jsRel
if (-not (Test-Path $jsPath)) {
    Write-Host "WARNING: $jsRel not found - skipped" -ForegroundColor Yellow
} else {
    $j = Read-Any $jsPath
    if ($j.Contains('giftOverviewModal')) {
        Write-Host "[skip] overview logic already present" -ForegroundColor DarkGray
    } else {
        Backup-Once $jsPath
        $j = $j.TrimEnd() + "`n" + (Decode $JS_B64)
        Write-Utf8 $jsPath $j
        $changed += $jsRel
        Write-Host "[ok] overview popup logic appended" -ForegroundColor Green
    }
}

# ============================================================================
# STEP 4 - commit and push
# ============================================================================
Write-Host ""
if ($changed.Count -eq 0) {
    Write-Host "Nothing to commit - everything was already applied." -ForegroundColor DarkGray
} else {
    Write-Host "Changed files:" -ForegroundColor Cyan
    foreach ($f in $changed) { Write-Host "  - $f" }
    Write-Host ""
    Write-Host "Committing and pushing to git..." -ForegroundColor Cyan
    git add -A
    git commit -m "Gifts page: duration badge on image, product overview popup, compact cards"
    git push
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "git push failed." -ForegroundColor Yellow
        Write-Host "If you saw 'Permission denied (publickey)', switch the remote to HTTPS and push again:" -ForegroundColor Yellow
        Write-Host "  git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPO.git" -ForegroundColor White
        Write-Host "  git push" -ForegroundColor White
        Write-Host "(use your real GitHub username and repo name - run 'git remote -v' to see them)" -ForegroundColor DarkGray
    }
}

# ============================================================================
# DONE - next steps
# ============================================================================
Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "  DONE" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "No database changes, so NO migrate is needed." -ForegroundColor Green
Write-Host ""
Write-Host "After Render shows 'Deploy live', open the Render Shell and run:" -ForegroundColor Cyan
Write-Host "  python manage.py collectstatic --noinput" -ForegroundColor White
Write-Host ""
Write-Host "Then hard-refresh the gifts page on your phone (pull down to refresh, or clear" -ForegroundColor Cyan
Write-Host "the browser cache) so it loads the new css/js." -ForegroundColor Cyan
Write-Host ""
Write-Host "TIP: the badge shows exactly what is typed in the product's 'Delivery" -ForegroundColor Yellow
Write-Host "duration' field in admin. For the clean look in your screenshot, keep it" -ForegroundColor Yellow
Write-Host "short - e.g. type  1-7 days  (not '1-7 days delivery')." -ForegroundColor Yellow
Write-Host ""
Write-Host "If anything looks off, the original files are next to the patched ones with" -ForegroundColor DarkGray
Write-Host "the .bak-overview ending - restore them and send me a screenshot." -ForegroundColor DarkGray
