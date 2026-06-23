# Camera Intrinsic Calibration

Per-camera **intrinsics** (focal length, principal point, lens distortion) for the
6-camera rig, from images of a plain black/white **checkerboard**. Used to feed
known intrinsics into COLMAP / 3DGS reconstruction.

Two interchangeable implementations that produce the same OpenCV/COLMAP-compatible
output:

| | Script | Runs all 6 |
|---|---|---|
| **OpenCV (Python)** | `checkerboard_calib.py` | `run_checkerboard_calib.ps1` (Windows) / `.sh` (Linux/macOS) |
| **MATLAB** | `checkerboard_calib_matlab.m` | `run_checkerboard_calib_matlab.m` |

> Intrinsics only. The rig **extrinsics** (relative camera poses) are a separate
> step — see `extrinsics/`. A plain checkerboard is fine for intrinsics but not
> for multi-camera extrinsics.

Hardware this was set up for: Lucid Triton 2.3 MP (IMX392) + Edmund Optics 4 mm
fixed lens, images at **1920×1200**.

---

## 1. Directory layout

```
mach-e2-manual-calib/
├─ checkerboard_calib.py             # OpenCV (Python) calibrator
├─ run_checkerboard_calib.ps1        # Windows  : all 6 cameras (OpenCV)
├─ run_checkerboard_calib.sh         # Linux/mac: all 6 cameras (OpenCV)
├─ checkerboard_calib_matlab.m       # MATLAB calibrator
├─ run_checkerboard_calib_matlab.m   # MATLAB : all 6 cameras
└─ intrinsics/
   ├─ images1/raw/    <- put camera 1 PNGs here
   ├─ images2/raw/    <- put camera 2 PNGs here
   ├─ ...
   └─ images6/raw/    <- put camera 6 PNGs here
```

**Input:** raw images go in `intrinsics/imagesX/raw/` — one folder per camera.
**Output:** results are written to the parent `intrinsics/imagesX/` (next to `raw/`).

---

## 2. Capturing good calibration images

- **Format:** lossless **PNG**, at the camera's **native resolution** — the same
  resolution you will use downstream. (These intrinsics are only valid for that
  resolution.)
- **Whole board visible** with a light margin around it in every shot. Detection
  is all-or-nothing; a board touching the frame edge is rejected.
- **30+ views (around 60 is most likely good)**, varied: different angles, tilts, distances, and positions —
  including the board pushed into **all four corners** of the frame (this is what
  constrains lens distortion at the edges; see the coverage map in §5). Make sure to get pitch and yaw throughout each spot of the picture at different distances.
- **Lock focus and aperture** on the lens, and calibrate at roughly the working
  distance you'll use. Re-focusing after calibration invalidates the intrinsics.

---

## 3. Board configuration

The detector counts **inner corners** (where 4 squares meet), not squares:
a board of *N×M* squares has *(N−1)×(M−1)* inner corners. Partial/cut-off border
squares still form valid corners, so count what the detector sees, not the squares.

- **OpenCV:** set these at the top of `checkerboard_calib.py`:
  ```python
  CHESS_COLS    = 13         # inner corners across
  CHESS_ROWS    = 8          # inner corners down
  SQUARE_LENGTH = 0.079375   # one square's side, in METERS (measure it!)
  ```
  Not sure of the count? Let the script find it (see §4, `--probe`).
- **MATLAB:** auto-detects the board size — nothing to set. Only `squareSize`
  (optional arg, default `0.079375`) matters, and only for board pose, not the
  intrinsics themselves.

---

## 4. OpenCV (Python)

### Install
Requires Python 3.9+ (3.13 is fine):
```powershell
pip install "opencv-contrib-python>=4.7" numpy
```
(Optional, recommended — isolate in a venv first:)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "opencv-contrib-python>=4.7" numpy
```

### Find the inner-corner count (once, optional)
```powershell
python ./checkerboard_calib.py intrinsics/images1/raw --probe
```
Copy the `==> Most likely full board` numbers into `CHESS_COLS` / `CHESS_ROWS`.

### Run one camera
```powershell
python ./checkerboard_calib.py intrinsics/images2/raw
```

### Run all six
Windows (PowerShell):
```powershell
.\run_checkerboard_calib.ps1
```
If you see *"running scripts is disabled on this system"*:
```powershell
powershell -ExecutionPolicy Bypass -File .\run_checkerboard_calib.ps1
```
Linux/macOS:
```bash
bash run_checkerboard_calib.sh
```

### Outputs (written to `intrinsics/imagesX/`)
- `intrinsics_opencv.json` — fx, fy, cx, cy, distortion, camera matrix
- `coverage_opencv.png` — where corners landed across all views (see §5)
- `detections/ok_*.jpg` / `skip_*.jpg` — per-image overlays of what was detected

---

## 5. MATLAB

### Requirements
- MATLAB **R2021a+** recommended
- **Computer Vision Toolbox** (calibration) + **Image Processing Toolbox** (coverage map)

### Run one camera
From the repo root in MATLAB:
```matlab
checkerboard_calib_matlab('intrinsics/images2/raw')
% with an explicit square size (meters):
checkerboard_calib_matlab('intrinsics/images2/raw', 0.079375)
```

### Run all six
```matlab
run_checkerboard_calib_matlab
```

### Outputs (written to `intrinsics/imagesX/`)
- `intrinsics_matlab.json`
- `coverage_matlab.png`
- `detections_matlab/ok_*.jpg` / `skip_*.jpg`

The `_matlab` outputs sit next to the `_opencv` ones so you can compare them.

---

## 6. Reading the results

- **Reprojection error:** aim for **< 0.5 px**
  (OpenCV prints RMS; MATLAB prints mean, so they won't match
  exactly even for an identical calibration.)
- **Sanity check fx/fy:** for the 4 mm lens at 1920×1200, expect
  **fx ≈ fy ≈ 1160–1190 px** and **cx, cy ≈ 960, 600**. Wildly different values
  mean a bad square size or bad detections.
- **Coverage map:** dark grey = no corners ever landed there; bright = many.
  You want color reaching into **all four frame corners** — that's where the wide
  lens distorts most. If the edges/corners are dark, capture more views with the
  board pushed into those corners and re-run.

---

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Every image `skip (0 corners)` | Wrong `CHESS_COLS/ROWS` → run `--probe`; or the board is cut off at the frame edge in every shot |
| `skip (unreadable)` | Corrupt/truncated PNG (capture or copy interrupted). Check file size vs. good files and re-export |
| `skip (resolution mismatch)` | All images for a camera must be the same resolution |
| Few usable views (`< 8`) | Board not fully visible / too oblique / motion-blurred in most frames |
| High reproj error | Mixed focus, unlocked lens, wrong square size, or a few bad views (inspect `detections/`) |
| PowerShell won't run the `.ps1` | Use the `-ExecutionPolicy Bypass` form in §4 |

---

## 8. OpenCV vs MATLAB — known differences

- **Pixel origin:** MATLAB is 1-based, OpenCV is 0-based. The MATLAB script
  exports the principal point as `(cx−1, cy−1)` so both JSONs are directly
  comparable / COLMAP-ready. Focal lengths are unaffected.
- **Board size:** OpenCV needs `CHESS_COLS/ROWS`; MATLAB auto-detects it.
- **Error metric:** RMS (OpenCV) vs mean (MATLAB) — see §6.
- **Distortion model:** both estimate `k1, k2, p1, p2, k3` (OpenCV `OPENCV` /
  COLMAP `OPENCV` model order).
