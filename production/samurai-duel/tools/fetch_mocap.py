"""Fetch the free motion-capture clips used as a base for body motion.

    python3 tools/fetch_mocap.py

The clips are the DeepMimic reference motions that ship inside the 'pybullet' package on PyPI
(zlib licence: free for any use, including commercial). Only the motion text files are taken out
of the package; nothing from it is installed or run.

    walk, run, jump, kick, spinkick, spin, punch, roll, backflip, cartwheel, crawl, dance_a/b, getup

They go to assets/mocap/deepmimic/ (not kept in git). sd/mocap.py reads them.
"""
import io
import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(HERE, "assets", "mocap", "deepmimic")
INDEX = "https://pypi.org/pypi/pybullet/3.2.7/json"
AGENT = {"User-Agent": "blender-scene-builder/1.0"}


def main():
    os.makedirs(DEST, exist_ok=True)
    if len([f for f in os.listdir(DEST) if f.startswith("humanoid3d_")]) >= 15 and "--force" not in sys.argv:
        print("already there:", DEST)
        return
    meta = json.load(urllib.request.urlopen(urllib.request.Request(INDEX, headers=AGENT), timeout=60))
    wheels = sorted((u for u in meta["urls"] if u["packagetype"] == "bdist_wheel"), key=lambda u: u["size"])
    url = wheels[0]["url"]                                   # any wheel carries the same data files; take the smallest
    print("downloading", wheels[0]["filename"], f"({wheels[0]['size'] / 1e6:.0f} MB)")
    blob = urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=900).read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    n = 0
    for name in z.namelist():
        base = os.path.basename(name)
        if (name.startswith("pybullet_data/data/motions/humanoid3d_") and name.endswith(".txt")) or name.endswith(".dist-info/LICENSE.txt"):
            with open(os.path.join(DEST, base), "wb") as fh:
                fh.write(z.read(name))
            n += 1
    print(f"{n} files written to {DEST}")


main()
