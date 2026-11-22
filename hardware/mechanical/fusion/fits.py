"""Fastener and fit sizes shared by the Tilter and Controller generators (mm). Pure Python: no Fusion needed.

Where two parts use different values today, each keeps its own named constant (changing one would change a print).
"""

import math

# ---- the blind's headrail and tilt rod
RAIL_W, RAIL_H, RAIL_WALL = 55.5, 36.5, 2.0     # inside width, height, wall
LIP_IN, LIP_H = 4.5, 3.0                        # the lips along the rail's top: how far in, how tall
ROD_Z = 24.0                                    # tilt rod's axis above the rail floor
ROD = 4.0                                       # square tilt rod
ROD_CORNER_R = ROD * math.sqrt(2) / 2           # half its diagonal (2.83): what a turning rod sweeps
ROD_BORE = 4.3                                  # every square bore the rod slides through (carrier hub, sensor sleeve)
ROD_HOLE_R = 3.2                                # round hole a long rod passes through (clears its corners)

# ---- M3 bolts and heat-set inserts
M3_R = 1.7                                      # clearance hole (Ø3.4)
INSERT_R = 2.0                                  # heat-set insert hole (Ø4.0)
INSERT_LEN_MIN = 6.7                            # the bought M3 inserts need a hole at least this deep
INSERT_LEN = 6.7                                # insert hole depth: Controller
INSERT_LEN_TILTER = 6.9                         # Tilter: 0.2 deeper than the minimum (room for melted plastic)
CSINK_R, CSINK_H = 3.4, 1.7                     # Tilter: 90° countersink Ø6.8, 1.7 deep (a Ø6 head sits 0.4 under)
CSINK_CTRL_R, CSINK_CTRL_R_TOP, CSINK_CTRL_H = 3.1, 1.45, 1.65   # Controller: cone Ø6.2 -> Ø2.9 over 1.65 (differs)

# ---- N20 motor's M1.6 screws
M1_6_R = 0.95                                   # screw hole (Ø1.9)
M1_6_HEAD_R = 1.75                              # well for the screw head (Ø3.5)

# ---- locating pins and their holes
PEG_D, PEG_H = 2.5, 2.0                         # printed pin: diameter, height
PEG_CLEAR = 0.15                                # hole radius = pin radius + this
PEG_DEPTH_EXTRA = 0.4                           # hole depth = pin height + this
