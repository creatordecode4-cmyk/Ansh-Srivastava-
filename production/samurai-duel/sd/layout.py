"""World layout measured from the TOP-DOWN LAYOUT panel of refs/arena_breakdown.png.

The panel is 820 x 387 px (crop 848,545 of the sheet). Mapping:
    world_x = (px - AXIS_X) * M_PER_PX      (+X = east)
    world_y = (CENTER_Y - py) * M_PER_PX    (+Y = north, toward the torii)
Scale comes from the paving: one flagstone is ~22 px, set to a 1.2 m pitch.
The torii axis is x = 0 and the middle of the open fighting area is the origin.
"""
import math

M_PER_PX = 0.055
AXIS_X, CENTER_Y = 434.0, 240.0


def w(px, py):
    return ((px - AXIS_X) * M_PER_PX, (CENTER_Y - py) * M_PER_PX)


TILE = 1.2  # flagstone pitch

# --- open fighting area (regular paving); outside of it the paving breaks up into rubble
PAVED = dict(x0=-9.6, x1=11.4, y0=-14.4, y1=8.4)
FIGHT_AREA = dict(x0=-6.0, x1=9.0, y0=-7.0, y1=6.5)

# --- torii and the stairs behind it (north end)
TORII = dict(pos=(0.0, 9.3), yaw=0.0, pillar_spacing=4.2, beam=7.5, height=6.4)
FRONT_STEPS = dict(y_bottom=8.05, steps=2, rise=0.17, run=0.42, half_width=5.2)  # low terrace the torii stands on
TERRACE1_Z = 0.34
BACK_STAIRS = dict(y_bottom=10.9, steps=15, rise=0.17, run=0.32, half_width=2.3)
TERRACE2_Z = TERRACE1_Z + 15 * 0.17
REAR_HALL = dict(pos=(0.5, 27.0), yaw=math.radians(-90.0))  # faces south, toward the torii

# --- main temple hall (west): facade faces east-south-east, stairs run down along the facade normal
TEMPLE_YAW = math.radians(-28.0)  # direction the facade faces, measured from +X
TEMPLE = dict(facade_mid=(-12.35, 7.35), yaw=TEMPLE_YAW, width=12.5, depth=9.0, platform=1.9, deck=2.3,
              stair_width=3.4, stair_steps=11)

# --- stone lanterns: (x, y, yaw, broken)
LANTERNS = [
    (*w(307, 99), 0.3, False),    # A: foot of the temple stairs
    (*w(543, 96), -0.2, False),   # B: right of the torii
    (*w(258, 228), 0.9, False),   # C: west edge
    (*w(622, 244), -0.6, False),  # D: east edge
    (*w(336, 305), 0.5, True),    # E: south-west rubble (broken)
    (*w(547, 305), -0.4, True),   # F: south-east rubble (broken)
]

# --- east side: ruined roofed corridor running NNW -> SSE, plus small roofs
CORRIDOR = dict(start=w(662, 105), end=w(728, 387), width=2.6)
SMALL_ROOFS = [
    dict(pos=w(640, 35), yaw=math.radians(-25), size=(5.0, 3.6)),    # north-east gate house
    dict(pos=w(678, 358), yaw=math.radians(-15), size=(3.0, 3.2)),   # south-east shed
    dict(pos=w(182, 282), yaw=math.radians(8), size=(2.6, 3.6)),     # west shed
    dict(pos=w(208, 350), yaw=math.radians(12), size=(4.0, 4.4)),    # south-west gate
    dict(pos=w(120, 178), yaw=TEMPLE_YAW, size=(6.0, 4.5)),          # temple south wing
]

# --- cherry trees: (x, y, height, crown radius)
CHERRY = [
    (*w(95, 262), 9.5, 6.5),    # big tree south-west
    (*w(292, 368), 5.0, 2.8),   # small, south-west corner
    (*w(285, 38), 6.0, 3.2),    # left of the torii
    (*w(530, 22), 6.5, 3.4),    # right of the torii
    (*w(645, 130), 4.5, 2.2),   # by the corridor
    (*w(760, 105), 9.0, 5.5),   # east, behind the corridor
    (*w(775, 245), 9.5, 6.0),   # east, behind the corridor
    (*w(600, 372), 4.8, 2.6),   # south-east corner
    (*w(800, 350), 8.0, 4.5),   # far south-east
]

# --- rubble fields: (x0, y0, x1, y1, density)
RUBBLE = [
    (*w(200, 360), *w(335, 190), 1.0),   # south-west
    (*w(545, 355), *w(645, 268), 1.0),   # south-east
    (*w(300, 118), *w(398, 52), 0.7),    # left of the torii
    (*w(480, 128), *w(600, 55), 0.8),    # right of the torii
    (*w(600, 262), *w(650, 150), 0.4),   # along the corridor
]

# --- direction of the blood moon (azimuth from +Y toward +X, elevation), fixed for every shot
MOON = dict(azimuth=math.radians(-2.0), elevation=math.radians(24.0), angular_diameter=math.radians(10.0))
