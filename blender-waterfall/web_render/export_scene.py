"""Export the Step 1 geometry (dry run of build_waterfall_scene.py) for the Three.js renderer.
Adds vertex colours (grass, gravel, strata, moss, golden lichen, snow) and converts
Blender Z-up coordinates to Three.js Y-up: (x, y, z) -> (x, z, -y).
Usage: python3 export_scene.py   (writes ./scene_data/)
"""
import importlib.util
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("wf", os.path.join(HERE, "..", "build_waterfall_scene.py"))
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)
OUT = os.path.join(HERE, "scene_data")
os.makedirs(OUT, exist_ok=True)


def srgb(c):
    return np.power(np.clip(np.asarray(c, float), 0, 1), 2.2)


def tris(faces):
    out = []
    for f in faces:
        for k in range(1, len(f) - 1):
            out.append((f[0], f[k], f[k + 1]))
    return np.array(out, np.uint32)


def normals(V, T):
    n = np.zeros_like(V)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    for k in range(3):
        np.add.at(n, T[:, k], fn)
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


def noise_arr(P, scale, seed, octaves=3):
    return np.array([wf.fbm(x * scale, y * scale, z * scale, octaves, seed) for x, y, z in P])


def mix(a, b, t):
    t = np.clip(t, 0, 1)[:, None]
    return a * (1 - t) + b * t


def to_three(V):
    return np.stack([V[:, 0], V[:, 2], -V[:, 1]], 1)


groups = {}


def add(name, V, T, C, N=None, UV=None):
    g = groups.setdefault(name, {"V": [], "T": [], "C": [], "N": [], "UV": [], "n": 0})
    if N is None:
        N = normals(V, T)
    g["T"].append(T + g["n"])
    g["V"].append(V); g["C"].append(C); g["N"].append(N)
    if UV is not None:
        g["UV"].append(UV)
    g["n"] += len(V)


B = wf.main()
pines, bushes = [], []
sx, sy = wf.mx(44), 100.0   # waterfall location (for wet rock)
for name, verts, faces, coll in B.records:
    V = np.array(verts, float)
    T = tris(faces)
    if name == "Terrain_Valley":
        N = normals(V, T)
        N[N[:, 2] < 0] *= -1
        info = np.array([wf.river_info(x, y) for x, y, _ in V])
        e = info[:, 0] - info[:, 1]
        n1 = noise_arr(V, 0.08, 31)
        n2 = noise_arr(V, 0.6, 32, 2)
        grass = mix(srgb((0.30, 0.52, 0.08)), srgb((0.58, 0.74, 0.16)), 0.5 + 0.9 * n1)
        grass *= (0.9 + 0.2 * n2)[:, None]
        earth = srgb((0.46, 0.42, 0.34))
        C = mix(grass, earth, (0.82 - N[:, 2]) * 5)
        gravel = mix(srgb((0.62, 0.58, 0.50)), srgb((0.48, 0.46, 0.42)), 0.5 + n2)
        C = mix(C, gravel, 1 - np.clip((e - 0.5) / 2.5, 0, 1))
        bed = mix(srgb((0.36, 0.33, 0.25)), srgb((0.22, 0.30, 0.24)), -V[:, 2] * 1.2)
        C = mix(C, bed, np.clip(-e * 0.8, 0, 1))
        add("terrain", V, T, C, N)
    elif name == "Terrain_Mountains":
        N = normals(V, T)
        N[N[:, 2] < 0] *= -1
        n1 = noise_arr(V, 0.02, 41)
        rock = mix(srgb((0.42, 0.44, 0.50)), srgb((0.55, 0.55, 0.58)), 0.5 + n1)
        forest = srgb((0.14, 0.22, 0.12))
        C = mix(forest, rock, (V[:, 2] - 40 + 30 * n1) / 40)
        snow = srgb((0.93, 0.95, 0.98))
        C = mix(C, snow, ((V[:, 2] - 130 + 40 * n1) / 30) * np.clip((N[:, 2] - 0.45) * 4, 0, 1))
        add("mountains", V, T, C, N)
    elif name.startswith("Cliff"):
        N = normals(V, T)
        lt = 3.4
        layer = np.floor((V[:, 2] + 2.0 * noise_arr(V, 0.015, 51, 2)) / lt)
        lh = np.array([wf.hash1(i, 77) for i in layer])
        base = mix(srgb((0.72, 0.68, 0.60)), srgb((0.80, 0.68, 0.50)), lh)
        base = mix(base, srgb((0.55, 0.53, 0.50)), (np.array([wf.hash1(i, 78) for i in layer]) - 0.6) * 2.5)
        n1 = noise_arr(V, 0.12, 52)
        n2 = noise_arr(V, 0.5, 53, 2)
        C = base * (0.85 + 0.3 * n2)[:, None]
        C = mix(C, srgb((0.30, 0.40, 0.14)), (N[:, 2] - 0.35) * 3 + n1)            # moss on ledges
        C = mix(C, srgb((0.78, 0.64, 0.26)), (n1 - 0.32) * 4 * (N[:, 2] > -0.2))    # golden lichen
        C = mix(C, srgb((0.30, 0.30, 0.27)), 1 - V[:, 2] / 3.0)                      # wet base
        wet = np.hypot(V[:, 0] - sx, V[:, 1] - sy)
        C = mix(C, C * 0.55, (14 - wet) / 8)                                        # spray-darkened rock
        add("cliffs", V, T, C, N)
    elif name.startswith("Waterfall"):
        cols = 24 if name.endswith("Main") else 6
        rows = len(V) // (cols + 1)
        UV = np.array([(i / cols, j / (rows - 1)) for i in range(cols + 1) for j in range(rows)], float)
        C = np.ones_like(V)
        add("waterfall_main" if name.endswith("Main") else "waterfall_strand", V, T, C, UV=UV)
        if name.endswith("Main"):
            bottom = V[np.argsort(V[:, 2])[:cols + 1]].mean(0)
            top = V[np.argsort(-V[:, 2])[:cols + 1]].mean(0)
    elif name.startswith(("Boulder", "Pebble")):
        N = normals(V, T)
        c = V.mean(0)
        flip = np.einsum("ij,ij->i", N, V - c) < 0
        if flip.mean() > 0.5:
            T = T[:, ::-1].copy(); N = -N
        n1 = noise_arr(V, 0.7, 61, 2)
        C = mix(srgb((0.62, 0.61, 0.58)), srgb((0.74, 0.72, 0.68)), 0.5 + 1.2 * n1)
        C = mix(C, srgb((0.34, 0.44, 0.16)), (N[:, 2] - 0.75) * 3 + n1 * 1.5)       # moss caps
        C = mix(C, srgb((0.72, 0.64, 0.42)), (n1 - 0.42) * 3)                       # faint lichen
        C = mix(C, C * 0.5, (0.35 - V[:, 2]) * 2)                                   # wet at waterline
        add("rocks", V, T, C, N)
    elif name.startswith("Pine"):
        pines.append([float(V[:, 0].mean()), float(V[:, 1].mean()), float(V[:, 2].min()),
                      float(V[:, 2].max() - V[:, 2].min())])
    elif name.startswith("Bush"):
        bushes.append([float(V[:, 0].mean()), float(V[:, 1].mean()), float(V[:, 2].min()),
                       float((V[:, 0].max() - V[:, 0].min()) / 2)])

manifest = {"groups": {}}
for name, g in groups.items():
    V = to_three(np.concatenate(g["V"])).astype(np.float32)
    N = to_three(np.concatenate(g["N"])).astype(np.float32)
    C = np.concatenate(g["C"]).astype(np.float32)
    T = np.concatenate(g["T"]).astype(np.uint32)
    files = {"position": V, "normal": N, "color": C, "index": T}
    if g["UV"]:
        files["uv"] = np.concatenate(g["UV"]).astype(np.float32)
    manifest["groups"][name] = {}
    for k, arr in files.items():
        fn = f"{name}_{k}.bin"
        arr.tofile(os.path.join(OUT, fn))
        manifest["groups"][name][k] = fn
    print(name, len(V), "verts", len(T), "tris")

rocks_near_water = []
for name, verts, faces, coll in B.records:
    if name.startswith("Boulder"):
        V = np.array(verts)
        r = (V[:, 0].max() - V[:, 0].min()) / 2
        if V[:, 2].min() < 0.2 < V[:, 2].max():
            rocks_near_water.append([float(V[:, 0].mean()), float(V[:, 1].mean()), float(r)])

manifest.update({
    "pines": pines, "bushes": bushes,
    "rocksInWater": rocks_near_water[:48],
    "river": [list(p) for p in wf.RIVER_PTS], "riverHalfW": wf.RIVER_HALF_W,
    "pool": [wf.POOL_C[0], wf.POOL_C[1], wf.POOL_R],
    "fallBottom": bottom.tolist(), "fallTop": top.tolist(),
    "camera": {"loc": list(wf.CAM_LOC), "pitch": wf.CAM_PITCH_DEG, "lens": wf.CAM_LENS},
    "terrainGrid": {"x0": -90, "y0": -30, "step": 1.0, "nx": 181, "ny": 201},
    "mirror": wf.MIRROR_X,
})
with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f)
print("pines", len(pines), "bushes", len(bushes), "rocks in water", len(rocks_near_water))
