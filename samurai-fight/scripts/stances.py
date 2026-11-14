"""Fighting stances for the control rigs, in character-local space (character faces -Y, its left is +X)."""
import bpy, math
from mathutils import Matrix, Vector
import posing as P


def sword_matrix(pos, blade, edge):
    Z = Vector(blade).normalized()
    e = Vector(edge)
    e = (e - e.dot(Z) * Z).normalized()
    Y = -e
    X = Y.cross(Z)
    M = Matrix((X, Y, Z)).transposed().to_4x4()
    M.translation = Vector(pos)
    return M


def set_local(ob, M):
    """Set an object's transform relative to its parent (the character root)."""
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = M


def apply(name, st):
    rig = bpy.data.objects[name + '_Rig']
    vl = bpy.context.view_layer
    for s, side in (('L', 'Left'), ('R', 'Right')):
        f = st['feet'][s]
        foot = bpy.data.objects[f'{name}_FOOT_{s}']
        rest = rig.data.bones[side + 'Foot'].matrix_local
        loc = Vector((f[0], f[1], rest.translation.z + (f[3] if len(f) > 3 else 0.0)))
        R = Matrix.Rotation(math.radians(f[2]), 4, 'Z')
        if len(f) > 4:                                   # heel lift: pitch about the foot's side axis
            R = R @ Matrix.Rotation(math.radians(f[4]), 4, 'X')
        set_local(foot, Matrix.Translation(loc) @ R @ rest.to_3x3().to_4x4())
        k = st.get('knees', {}).get(s)
        fwd = R @ Vector((0, -1, 0))
        set_local(bpy.data.objects[f'{name}_KNEE_{s}'], Matrix.Translation(Vector(k) if k else loc + fwd * 0.75 + Vector((0, 0, 0.45))))
        e = st.get('elbows', {}).get(s)
        if e:
            set_local(bpy.data.objects[f'{name}_ELBOW_{s}'], Matrix.Translation(Vector(e)))
    for sname, (pos, blade, edge) in st['swords'].items():
        set_local(bpy.data.objects[sname], sword_matrix(pos, blade, edge))
    hb = rig.pose.bones['Hips']
    hp, yaw, pitch, roll = st['hips']
    rest = rig.data.bones['Hips'].matrix_local
    R = Matrix.Rotation(math.radians(yaw), 4, 'Z') @ Matrix.Rotation(math.radians(pitch), 4, 'X') @ Matrix.Rotation(math.radians(roll), 4, 'Y')
    hb.matrix = Matrix.Translation(Vector(hp)) @ R @ rest.to_3x3().to_4x4()
    vl.update()
    P.pose(rig, st.get('fk', []))
    vl.update()


STANCES = {
    # two-handed middle guard, right foot forward, point at the opponent's throat
    'Oni_guard': dict(
        feet={'R': (-0.17, -0.36, 8), 'L': (0.27, 0.38, 50)},
        hips=((0.0, 0.02, 0.85), 16, 6, 0),
        swords={'Oni_Katana': ((0.0, -0.44, 1.07), (0.0, -0.90, 0.43), (0, -0.43, -0.90))},
        elbows={'R': (-0.60, 0.10, 0.70), 'L': (0.60, 0.10, 0.65)},
        fk=[('Spine', (1, 0, 0), 3), ('Spine2', (0, 0, 1), -10), ('Neck', (1, 0, 0), 5), ('Head', (0, 0, 1), -5)]),
    # twin blades: right sword leads low at the opponent, left sword held higher across the body, hat brim low
    'Ronin_guard': dict(
        feet={'L': (0.17, -0.34, -8), 'R': (-0.25, 0.36, -48)},
        hips=((0.0, 0.04, 0.87), -16, 6, 0),
        swords={'Ronin_Katana_R': ((-0.27, -0.40, 0.99), (0.18, -0.94, 0.28), (0.0, -0.28, -0.94)),
                'Ronin_Katana_L': ((0.27, -0.22, 1.30), (-0.24, -0.82, 0.52), (0.0, -0.52, -0.82))},
        elbows={'R': (-0.62, 0.20, 0.70), 'L': (0.68, 0.25, 0.85)},
        fk=[('Spine', (1, 0, 0), 4), ('Spine2', (0, 0, 1), 8), ('Neck', (1, 0, 0), 5), ('Head', (1, 0, 0), 4)]),
}
