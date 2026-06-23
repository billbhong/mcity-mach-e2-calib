#!/usr/bin/env bash
# Run checkerboard intrinsics calibration for all 6 cameras (Linux/macOS).
# Windows users: use run_checkerboard_calib.ps1 instead.
set -u
for i in 1 2 3 4 5 6; do
    raw="intrinsics/images$i/raw"
    if [ ! -d "$raw" ]; then
        echo "Skipping camera $i  (no folder: $raw)"
        continue
    fi
    echo "=== Calibrating camera $i  ($raw) ==="
    python ./checkerboard_calib.py "$raw"
    echo "Completed calibration for camera $i"
done
