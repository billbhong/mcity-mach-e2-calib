#!/usr/bin/env python3
"""
Homogeneous transforms T_imu_from_sensor (4x4) for each sensor.

T maps a point in the sensor frame into the IMU-ref frame:  p_imu = T @ p_sensor
Rotation = sensor yaw about +z (cam pitch/roll = 0); translation = sensor origin
in IMU coords, built from the measurement tree.

Run:  python3 sensor_transforms.py            # print matrices, write JSON
Requires: numpy, pytransform3d
"""

import json
import numpy as np
from pytransform3d.transform_manager import TransformManager
import pytransform3d.transformations as pt
import pytransform3d.rotations as pr

# UNITS for the translation block of the matrix: "m" (meters) or "in" (inches).
UNITS = "m"
IN_TO_M = 0.0254
SCALE = IN_TO_M if UNITS == "m" else 1.0
IMU = "imu_ref"

# measurement tree: (child, parent, [dx, dy, dz] inches) in IMU axes (x fwd, y lat, z up)
EDGES_IN = [
    ("cam_5", IMU,    ( 24.5,    28.875,  19.875)),
    ("cam_4", IMU,    ( 23.125, -28.875,  19.875)),
    ("cam_3", "cam_5",( 44.375,   0.0,     0.0)),
    ("cam_2", "cam_4",( 42.375,   0.0,     0.0)),
    ("cam_1", "cam_2",( 15.0,    28.125,   0.0)),    # y sign-fixed
    ("cam_6", "cam_4",(-21.875,  27.25,    0.0)),    # y sign-fixed
    ("lidar", "cam_2",( 14.5,    27.0,     3.3125)), # y sign-fixed
]

YAW_SIGN = +1.0  # flip if frame handedness makes rotations come out mirrored
YAW_DEG = {"cam_1": 0, "cam_2": 300, "cam_3": 60, "cam_4": 240,
           "cam_5": 120, "cam_6": 180, "lidar": 0, IMU: 0}  # lidar heading = placeholder

# build position tree (translation-only, meters internally)
tm = TransformManager()
for child, parent, d in EDGES_IN:
    tm.add_transform(child, parent, pt.transform_from(np.eye(3), np.array(d) * IN_TO_M))

matrices = {}
for s in YAW_DEG:
    pos_m = np.zeros(3) if s == IMU else tm.get_transform(s, IMU)[:3, 3]
    R = pr.active_matrix_from_angle(2, np.deg2rad(YAW_SIGN * YAW_DEG[s]))
    T = pt.transform_from(R, pos_m * (SCALE / IN_TO_M))  # rescale translation to chosen units
    matrices[s] = np.round(T, 6)

# pretty print
for s, T in matrices.items():
    print(f"\nT_imu_from_{s}  (rot: yaw {YAW_SIGN*YAW_DEG[s]:g} deg, trans in {UNITS})")
    for row in T:
        print("  [" + "  ".join(f"{v: 10.5f}" for v in row) + "]")

# JSON: {frame: 4x4 nested list}
with open("sensor_transforms_matrices.json", "w") as f:
    json.dump({s: T.tolist() for s, T in matrices.items()}, f, indent=2)
