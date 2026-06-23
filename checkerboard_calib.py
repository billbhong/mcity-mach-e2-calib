#!/usr/bin/env python3
"""
Camera intrinsics calibration from a plain checkerboard (black/white squares),
for 3DGS / photogrammetry capture.

Requires OpenCV >= 4.7:  pip install "opencv-contrib-python>=4.7"

    python charuco_calib.py intrinsics/images2/raw
    python charuco_calib.py intrinsics/images2/raw --probe

Pass the folder of RAW images (intrinsics/imagesX/raw). Outputs are written to its
parent (intrinsics/imagesX):
    intrinsics_opencv.json   estimated intrinsics
    coverage_opencv.png      corner-coverage map across all views
    detections/              per-image overlays (ok_*.jpg / skip_*.jpg)

IMPORTANT: set CHESS_COLS / CHESS_ROWS to your board's INNER-corner count and
re-measure SQUARE_LENGTH on the mounted print with calipers.

NOTE: a plain checkerboard must be fully visible in every frame and carries no
cross-camera correspondence. For the 6-camera rig EXTRINSICS step you'll want a
ChArUco / AprilGrid target instead; this script only does per-camera intrinsics.
"""

import argparse
import glob
import json
import os

import cv2
import numpy as np

# ----------------------------------------------------------------------
# BOARD CONFIG -- must match the physical checkerboard you print & measure
# ----------------------------------------------------------------------
# Detection counts INNER corners, not squares: a board of N x M squares has
# (N-1) x (M-1) inner corners. Set these to YOUR board.
CHESS_COLS    = 13           # inner corners across (squares_across - 1)
CHESS_ROWS    = 8          # inner corners down   (squares_down   - 1)
SQUARE_LENGTH = 0.079375        # side of one square, in METERS (measure the print!)


def _chessboard_object_points():
    objp = np.zeros((CHESS_COLS * CHESS_ROWS, 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESS_COLS, 0:CHESS_ROWS].T.reshape(-1, 2)
    objp *= SQUARE_LENGTH
    return objp


def detect_chessboard(img, gray):
    """Return (obj_pts, img_pts, n_corners, annotated_image).

    A plain checkerboard is all-or-nothing: the WHOLE board must be visible with a
    quiet border, or detection fails. Uses the robust SB detector, falling back to
    the classic detector + subpixel refinement.
    """
    size = (CHESS_COLS, CHESS_ROWS)
    found, corners = cv2.findChessboardCornersSB(
        gray, size, flags=cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_EXHAUSTIVE)
    if not found:
        f2, c2 = cv2.findChessboardCorners(
            gray, size, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
        if f2:
            crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, c2, (11, 11), (-1, -1), crit)
            found = True

    vis = img.copy()
    if not found:
        return None, None, 0, vis
    cv2.drawChessboardCorners(vis, size, corners, found)
    return _chessboard_object_points(), corners.reshape(-1, 1, 2), len(corners), vis


def probe(image_dir, pattern="*.png", lo=4, hi=16):
    """Sweep candidate inner-corner sizes on the first readable image and report
    which ones the detector locks onto -- use this to set CHESS_COLS/CHESS_ROWS.

    The SB detector also matches SUB-grids of the real board, so small sizes are
    usually false positives. The true board is the LARGEST grid that detects."""
    files = sorted(glob.glob(os.path.join(image_dir, pattern)))
    img = next((cv2.imread(f) for f in files if cv2.imread(f) is not None), None)
    if img is None:
        raise SystemExit(f"No readable image matched {os.path.join(image_dir, pattern)}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"Probing inner-corner sizes {lo}..{hi} (this takes a moment)...")

    hits = []
    for c in range(lo, hi + 1):
        for r in range(lo, hi + 1):
            found, _ = cv2.findChessboardCornersSB(
                gray, (c, r),
                flags=cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_EXHAUSTIVE)
            if found:
                hits.append((c, r))

    if not hits:
        print("No size detected. Ensure the WHOLE board is in view with a light")
        print("border, try another image, or widen the lo/hi range.")
        return

    hits.sort(key=lambda cr: cr[0] * cr[1], reverse=True)
    best = hits[0]
    print(f"\n==> Most likely full board: CHESS_COLS={best[0]}  CHESS_ROWS={best[1]}"
          f"  ({best[0] * best[1]} corners)")
    print("    Smaller sizes below are sub-grids / false positives -- ignore them.\n")
    print("All sizes that detected (largest first):")
    for c, r in hits:
        print(f"  {c:>2} x {r:<2}  ({c * r} corners)")
    print(f"\nSet CHESS_COLS={best[0]} / CHESS_ROWS={best[1]} at the top of this file,")
    print("then run a real calibration and check that ok_*.jpg overlays the whole board.")


def save_coverage(all_img, image_size, path):
    """Render one image showing where detected corners landed across ALL views.
    Dark = no coverage; bright/red = many corners. Use it to see whether you have
    samples out at the frame edges/corners (critical for wide-lens distortion)."""
    w, h = image_size
    radius = max(6, w // 160)
    heat = np.zeros((h, w), np.float32)
    n_pts = 0
    for pts in all_img:
        for p in pts.reshape(-1, 2):
            x, y = int(round(p[0])), int(round(p[1]))
            if 0 <= x < w and 0 <= y < h:
                cv2.circle(heat, (x, y), radius, 1.0, -1)
                n_pts += 1

    if heat.max() > 0:
        heat = cv2.GaussianBlur(heat, (0, 0), radius)
        heat /= heat.max()
    heat_u8 = (heat * 255).astype(np.uint8)
    cov = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    cov[heat_u8 == 0] = (30, 30, 30)                       # uncovered -> dark grey

    cv2.rectangle(cov, (0, 0), (w - 1, h - 1), (255, 255, 255), 2)
    for fr in (1 / 3, 2 / 3):                              # rule-of-thirds guides
        cv2.line(cov, (int(fr * w), 0), (int(fr * w), h - 1), (90, 90, 90), 1)
        cv2.line(cov, (0, int(fr * h)), (w - 1, int(fr * h)), (90, 90, 90), 1)
    cv2.putText(cov, f"{len(all_img)} views, {n_pts} corners", (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    cv2.imwrite(path, cov)
    return n_pts


def calibrate(image_dir, pattern="*.png", save=None, coverage=None, debug_dir=None):
    print(f"Detecting plain checkerboard {CHESS_COLS}x{CHESS_ROWS} inner corners")

    files = sorted(glob.glob(os.path.join(image_dir, pattern)))
    if not files:
        raise SystemExit(f"No images matched {os.path.join(image_dir, pattern)}")

    # Outputs go to the parent of the raw-image folder, e.g.
    # intrinsics/imagesX/raw  ->  intrinsics/imagesX
    out_dir = os.path.dirname(os.path.normpath(image_dir)) or "."
    if save is None:
        save = os.path.join(out_dir, "intrinsics_opencv.json")
    if coverage is None:
        coverage = os.path.join(out_dir, "coverage_opencv.png")
    if debug_dir is None:
        debug_dir = os.path.join(out_dir, "detections")
    os.makedirs(debug_dir, exist_ok=True)

    all_obj, all_img, image_size, used = [], [], None, 0

    for f in files:
        img = cv2.imread(f)
        if img is None:
            print(f"  skip (unreadable): {f}");  continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if image_size is None:
            image_size = gray.shape[::-1]            # (width, height)
        elif gray.shape[::-1] != image_size:
            print(f"  skip (resolution mismatch): {f}");  continue

        obj_pts, img_pts, n, vis = detect_chessboard(img, gray)

        base = os.path.basename(f)
        status = "ok" if obj_pts is not None else "skip"
        cv2.imwrite(os.path.join(debug_dir, f"{status}_{os.path.splitext(base)[0]}.jpg"), vis)

        if obj_pts is None:
            print(f"  skip ({n:>3} corners): {base}");  continue

        all_obj.append(obj_pts);  all_img.append(img_pts);  used += 1
        print(f"  ok  ({n:>3} corners): {base}")

    print(f"\nAnnotated detections written to: {debug_dir}")

    if image_size is not None and all_img:
        n_pts = save_coverage(all_img, image_size, coverage)
        print(f"Coverage map written to        : {coverage}  ({n_pts} corners)")

    if used < 8:
        raise SystemExit(f"Only {used} usable views; aim for ~15-30.")

    # Add cv2.CALIB_RATIONAL_MODEL for very wide / strongly distorted lenses.
    flags = 0
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        all_obj, all_img, image_size, None, None, flags=flags)

    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    w, h = image_size

    print("\n=== Calibration result ===")
    print(f"views used        : {used}")
    print(f"RMS reproj error  : {rms:.4f} px   (aim < ~0.5; < 1.0 usable)")
    print(f"resolution (w x h): {w} x {h}")
    print(f"fx, fy            : {fx:.3f}, {fy:.3f}")
    print(f"cx, cy            : {cx:.3f}, {cy:.3f}")
    print(f"dist coeffs       : {dist.ravel()}")

    out = {
        "image_width": w, "image_height": h,
        "camera_matrix": K.tolist(),
        "dist_coeffs": dist.ravel().tolist(),
        "fx": fx, "fy": fy, "cx": cx, "cy": cy,
        "rms_reproj_error": rms,
        "model": "OPENCV (k1,k2,p1,p2[,k3])",
    }
    with open(save, "w") as fp:
        json.dump(out, fp, indent=2)
    print(f"\nSaved -> {save}")

    d = dist.ravel()
    colmap = [fx, fy, cx, cy, d[0], d[1], d[2], d[3]]   # COLMAP OPENCV order
    print("COLMAP OPENCV params:", ", ".join(f"{v:.6f}" for v in colmap))
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image_dir",
                    help="folder of RAW images, e.g. intrinsics/images2/raw")
    ap.add_argument("--pattern", default="*.png")
    ap.add_argument("--save", default=None,
                    help="output JSON (default: <parent>/intrinsics_opencv.json)")
    ap.add_argument("--coverage", default=None,
                    help="output coverage map (default: <parent>/coverage_opencv.png)")
    ap.add_argument("--debug-dir", default=None,
                    help="annotated detections folder (default: <parent>/detections)")
    ap.add_argument("--probe", action="store_true",
                    help="sweep inner-corner sizes on the first image and exit "
                         "(use to find CHESS_COLS / CHESS_ROWS)")

    args = ap.parse_args()
    if args.probe:
        probe(args.image_dir, args.pattern)
    else:
        calibrate(args.image_dir, args.pattern, save=args.save,
                  coverage=args.coverage, debug_dir=args.debug_dir)


if __name__ == "__main__":
    main()
