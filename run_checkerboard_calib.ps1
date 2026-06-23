# Run checkerboard intrinsics calibration for all 6 cameras.
# Windows / PowerShell equivalent of run_checkerboard_calib.sh
#
# Run from PowerShell (in the repo root):
#     .\run_checkerboard_calib.ps1
#
# If you see "running scripts is disabled on this system", run it as:
#     powershell -ExecutionPolicy Bypass -File .\run_checkerboard_calib.ps1

Set-Location $PSScriptRoot   # work from the script's own folder, whatever the CWD

for ($i = 1; $i -le 6; $i++) {
    $raw = "intrinsics/images$i/raw"
    if (-not (Test-Path $raw)) {
        Write-Host "Skipping camera $i  (no images at $raw)"
        continue
    }
    Write-Host "=== Calibrating camera $i  ($raw) ==="
    python ./checkerboard_calib.py $raw
    Write-Host "Completed calibration for camera $i"
}
