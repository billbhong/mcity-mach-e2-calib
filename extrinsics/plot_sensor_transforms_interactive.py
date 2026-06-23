"""Interactive 3D plot of sensor placements relative to the IMU reference.

Writes a self-contained HTML file (open in any browser) where you can rotate,
zoom, pan, hover for per-sensor info, and toggle layers via the legend.

Each entry in sensor_transforms_matrices.json is a 4x4 homogeneous transform
T (sensor -> IMU frame): last column is position (x, y, z), upper-left 3x3 is
orientation. Local +X is treated as the sensor "forward"/boresight.
"""
import json
import webbrowser
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

HERE = Path(__file__).parent
DATA = HERE / "sensor_transforms_matrices.json"

with open(DATA) as f:
    transforms = {name: np.array(T, dtype=float) for name, T in json.load(f).items()}

positions = {name: T[:3, 3] for name, T in transforms.items()}
rotations = {name: T[:3, :3] for name, T in transforms.items()}

AXIS_LEN = 0.35   # small XYZ triad length (m)
FWD_LEN = 0.6     # forward/boresight arrow length (m)
triad_axes = [("X", "red"), ("Y", "green"), ("Z", "blue")]

fig = go.Figure()

# --- sensor position markers (with hover) ----------------------------------
names = list(transforms.keys())
P = np.array([positions[n] for n in names])
yaws = [np.degrees(np.arctan2(rotations[n][1, 0], rotations[n][0, 0])) for n in names]
hover = [f"<b>{n}</b><br>x={p[0]:.3f} y={p[1]:.3f} z={p[2]:.3f} m<br>yaw={y:.1f}&deg;"
         for n, p, y in zip(names, P, yaws)]
fig.add_trace(go.Scatter3d(
    x=P[:, 0], y=P[:, 1], z=P[:, 2],
    mode="markers+text",
    marker=dict(size=[9 if n == "imu_ref" else 5 for n in names],
                color=["black" if n == "imu_ref" else "dimgray" for n in names],
                symbol=["diamond" if n == "imu_ref" else "circle" for n in names]),
    text=names, textposition="top center",
    hovertext=hover, hoverinfo="text",
    name="sensors",
))

# --- orientation triads (grouped so legend toggles each axis color) --------
for axis_idx, (axis_name, color) in enumerate(triad_axes):
    xs, ys, zs = [], [], []
    for n in names:
        p, R = positions[n], rotations[n]
        d = R[:, axis_idx] * AXIS_LEN
        xs += [p[0], p[0] + d[0], None]
        ys += [p[1], p[1] + d[1], None]
        zs += [p[2], p[2] + d[2], None]
    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(color=color, width=4),
        name=f"sensor {axis_name}", hoverinfo="skip",
    ))

# --- forward / boresight arrows (line shaft + cone head) -------------------
shaft_x, shaft_y, shaft_z = [], [], []
cone_x, cone_y, cone_z, cone_u, cone_v, cone_w = [], [], [], [], [], []
for n in names:
    if n == "imu_ref":
        continue
    p, R = positions[n], rotations[n]
    f = R[:, 0] * FWD_LEN
    tip = p + f
    shaft_x += [p[0], tip[0], None]
    shaft_y += [p[1], tip[1], None]
    shaft_z += [p[2], tip[2], None]
    cone_x.append(tip[0]); cone_y.append(tip[1]); cone_z.append(tip[2])
    cone_u.append(R[0, 0]); cone_v.append(R[1, 0]); cone_w.append(R[2, 0])

fig.add_trace(go.Scatter3d(
    x=shaft_x, y=shaft_y, z=shaft_z, mode="lines",
    line=dict(color="orange", width=6),
    name="forward (+X)", hoverinfo="skip",
))
fig.add_trace(go.Cone(
    x=cone_x, y=cone_y, z=cone_z, u=cone_u, v=cone_v, w=cone_w,
    sizemode="absolute", sizeref=0.15, anchor="tip",
    colorscale=[[0, "orange"], [1, "orange"]], showscale=False,
    name="forward head", hoverinfo="skip",
))

# --- equal aspect so geometry is not distorted -----------------------------
mins, maxs = P.min(axis=0), P.max(axis=0)
center = (maxs + mins) / 2
r = max((maxs - mins).max(), 1.0) / 2 * 1.3
rng = [[center[i] - r, center[i] + r] for i in range(3)]

# View = looking from the IMU forward toward cam_1 (down the +X axis), Z up.
# The Y axis is reversed (range high->low) so that, in this forward-looking
# view, screen-left reads negative Y and screen-right reads positive Y.
y_rng_reversed = [rng[1][1], rng[1][0]]
forward_camera = dict(eye=dict(x=-1.9, y=0.0, z=0.35),
                      center=dict(x=0, y=0, z=0),
                      up=dict(x=0, y=0, z=1))

fig.update_layout(
    title="Sensor placements relative to IMU reference — view: IMU &rarr; cam_1 (looking forward)"
          "<br><sup>orange = forward/boresight, RGB = sensor XYZ axes; "
          "Y flipped so screen-left = &minus;Y, screen-right = +Y</sup>",
    scene=dict(
        xaxis=dict(title="X forward (m)", range=rng[0]),
        yaxis=dict(title="Y (m)  [left −  /  right +]", range=y_rng_reversed),
        zaxis=dict(title="Z up (m)", range=rng[2]),
        aspectmode="cube",
        camera=forward_camera,
    ),
    legend=dict(itemsizing="constant"),
    margin=dict(l=0, r=0, t=55, b=0),
)

out = HERE / "sensor_placements_3d.html"
fig.write_html(out, include_plotlyjs="cdn", auto_open=False)
print(f"saved {out}")

# static preview of the default (IMU -> cam_1) view, if kaleido is available
try:
    png = HERE / "sensor_placements_3d_view.png"
    fig.write_image(png, width=1100, height=800, scale=2)
    print(f"saved {png}")
except Exception as e:
    print(f"(PNG preview skipped: {e})")

try:
    webbrowser.open(out.as_uri())
except Exception as e:
    print(f"(could not auto-open browser: {e})")
