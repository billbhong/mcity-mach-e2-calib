"""Quick sanity-check 3D plot of sensor placements relative to the IMU reference.

Each entry in sensor_transforms_matrices.json is a 4x4 homogeneous transform
T (sensor -> IMU frame): the last column is the position (x, y, z) and the
upper-left 3x3 is the orientation. The local X axis is treated as the sensor
"forward"/boresight direction.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
DATA = HERE / "sensor_transforms_matrices.json"

with open(DATA) as f:
    transforms = {name: np.array(T, dtype=float) for name, T in json.load(f).items()}

# --- pull out positions and orientations -----------------------------------
positions = {name: T[:3, 3] for name, T in transforms.items()}
rotations = {name: T[:3, :3] for name, T in transforms.items()}

# --- figure ----------------------------------------------------------------
fig = plt.figure(figsize=(11, 8))
ax = fig.add_subplot(111, projection="3d")

AXIS_LEN = 0.35        # length of the small XYZ triad arrows (meters)
FWD_LEN = 0.6          # length of the boresight (forward) arrow (meters)
triad_colors = ("r", "g", "b")  # X, Y, Z

for name, T in transforms.items():
    p = positions[name]
    R = rotations[name]
    is_imu = name == "imu_ref"

    # position marker
    ax.scatter(*p, color="k", s=40 if not is_imu else 70,
               marker="o" if not is_imu else "*", zorder=5)
    ax.text(p[0], p[1], p[2] + 0.08, name, fontsize=9, weight="bold")

    # small XYZ triad to show full orientation
    for i, c in enumerate(triad_colors):
        d = R[:, i] * AXIS_LEN
        ax.quiver(p[0], p[1], p[2], d[0], d[1], d[2],
                  color=c, linewidth=1.2, alpha=0.9)

    # longer forward/boresight arrow (local +X) for sensors
    if not is_imu:
        f = R[:, 0] * FWD_LEN
        ax.quiver(p[0], p[1], p[2], f[0], f[1], f[2],
                  color="orange", linewidth=2.0, arrow_length_ratio=0.25)

# --- equal aspect so geometry is not distorted -----------------------------
pts = np.array(list(positions.values()))
ranges = pts.max(axis=0) - pts.min(axis=0)
center = (pts.max(axis=0) + pts.min(axis=0)) / 2
r = max(ranges.max(), 1.0) / 2 * 1.3
ax.set_xlim(center[0] - r, center[0] + r)
ax.set_ylim(center[1] - r, center[1] + r)
ax.set_zlim(center[2] - r, center[2] + r)
try:
    ax.set_box_aspect((1, 1, 1))
except Exception:
    pass

ax.set_xlabel("X (forward, m)")
ax.set_ylabel("Y (left, m)")
ax.set_zlabel("Z (up, m)")
ax.set_title("Sensor placements relative to IMU reference\n"
             "orange = forward/boresight, RGB triad = sensor XYZ axes")
ax.view_init(elev=35, azim=-60)

# legend proxies
from matplotlib.lines import Line2D
legend = [
    Line2D([0], [0], color="orange", lw=2, label="forward (+X local)"),
    Line2D([0], [0], color="r", lw=2, label="sensor X"),
    Line2D([0], [0], color="g", lw=2, label="sensor Y"),
    Line2D([0], [0], color="b", lw=2, label="sensor Z"),
    Line2D([0], [0], marker="*", color="k", lw=0, label="imu_ref (origin)"),
]
ax.legend(handles=legend, loc="upper left", fontsize=8)

plt.tight_layout()
out = HERE / "sensor_placements_3d.png"
plt.savefig(out, dpi=150)
print(f"saved {out}")

# --- also print a quick top-down summary table -----------------------------
print("\nsensor      x       y       z      yaw(deg)")
for name, R in rotations.items():
    p = positions[name]
    yaw = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    print(f"{name:9s} {p[0]:7.3f} {p[1]:7.3f} {p[2]:7.3f}  {yaw:7.1f}")

plt.show()
