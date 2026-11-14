"""Download CC0 assets from Poly Haven into assets/polyhaven/ (cached, safe to re-run).

Everything fetched here is CC0, so it can be re-downloaded in any new session instead of
being stored in git.
"""
import json
import os
import urllib.request

API = "https://api.polyhaven.com"
UA = {"User-Agent": "blender-scene-builder/1.0"}
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "polyhaven")


def _get(url, dest=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if dest is None:
        return data
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    return dest


def files(asset):
    """File tree for one asset (cached)."""
    cache = os.path.join(ROOT, "_files", asset + ".json")
    if not os.path.exists(cache):
        _get(f"{API}/files/{asset}", cache)
    return json.load(open(cache))


def _fetch(url, dest):
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        _get(url, dest)
    return dest


def texture(asset, res="2k", maps=("Diffuse", "nor_gl", "Rough", "Displacement", "AO"), fmt="jpg"):
    """Download PBR maps for a texture asset. Returns {map_name: local_path}."""
    tree = files(asset)
    out = {}
    for m in maps:
        node = tree.get(m, {}).get(res)
        if not node:
            continue
        f = node.get(fmt) or node.get("png") or node.get("jpg") or node.get("exr")
        if not f:
            continue
        ext = f["url"].rsplit(".", 1)[-1]
        out[m] = _fetch(f["url"], os.path.join(ROOT, "textures", asset, f"{asset}_{m}_{res}.{ext}"))
    return out


def hdri(asset, res="2k", fmt="hdr"):
    f = files(asset)["hdri"][res][fmt]
    return _fetch(f["url"], os.path.join(ROOT, "hdris", f"{asset}_{res}.{fmt}"))


def model(asset, res="1k"):
    """Download a model as glTF with its textures. Returns the local .gltf path."""
    node = files(asset)["gltf"][res]["gltf"]
    base = os.path.join(ROOT, "models", asset, res)
    path = _fetch(node["url"], os.path.join(base, os.path.basename(node["url"])))
    for rel, inc in node.get("include", {}).items():
        _fetch(inc["url"], os.path.join(base, rel))
    return path


if __name__ == "__main__":
    import sys
    kind, name = sys.argv[1], sys.argv[2]
    res = sys.argv[3] if len(sys.argv) > 3 else None
    fn = {"texture": texture, "hdri": hdri, "model": model}[kind]
    print(fn(name, res) if res else fn(name))
