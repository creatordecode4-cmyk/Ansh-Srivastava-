"""Small posing helpers for the character rigs (world-axis rotations, parent first)."""
import bpy, math
from mathutils import Matrix, Vector


def rot(rig, bone, axis, deg):
    """Rotate a pose bone about a world-space axis through its head (rig must sit at the origin, unrotated)."""
    pb = rig.pose.bones[bone]
    M = pb.matrix.copy()
    head = M.translation.copy()
    R = Matrix.Rotation(math.radians(deg), 4, Vector(axis))
    pb.matrix = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ M
    bpy.context.view_layer.update()


def reset(rig):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def pose(rig, steps):
    """steps: list of (bone, axis, degrees). Use 'L:'/'R:' free; mirrored steps are written out explicitly."""
    for b, axis, deg in steps:
        rot(rig, b, axis, deg)


# deformation test: arms down and bent, knees bent, torso twisted, head turned
TEST_POSE = [
    ('Spine1', (0, 0, 1), 12), ('Spine2', (0, 0, 1), 10), ('Head', (0, 0, 1), -22),
    ('LeftArm', (0, 1, 0), 62), ('RightArm', (0, 1, 0), -62),
    ('LeftForeArm', (1, 0, 0), -70), ('RightForeArm', (1, 0, 0), -55),
    ('LeftUpLeg', (1, 0, 0), 28), ('LeftLeg', (1, 0, 0), -50), ('RightUpLeg', (1, 0, 0), -12), ('RightLeg', (1, 0, 0), -18),
    ('LeftHandFingers1', (0, 1, 0), 55), ('LeftHandFingers2', (0, 1, 0), 60), ('LeftHandFingers3', (0, 1, 0), 50),
]
