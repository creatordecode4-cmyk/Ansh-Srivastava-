"""Download CC0 assets from Poly Haven (textures, models, HDRIs) into the local cache.

Usage:
  python3 -I fetch_polyhaven.py texture <slug> [--res 2k] [--maps Diffuse nor_gl Rough Displacement arm] [--fmt jpg]
  python3 -I fetch_polyhaven.py model   <slug> [--res 2k]
  python3 -I fetch_polyhaven.py hdri    <slug> [--res 2k]
Files land in <cache>/<slug>/..., already-present files with the right size are skipped (resumable).
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

UA = "courtyard-fetch/1.0"
CACHE = os.environ.get("PH_CACHE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_data", "cache", "polyhaven")
CACHE = os.path.abspath(CACHE)


def http_get(url, dest=None, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if dest:
                tmp = dest + ".part"
                with open(tmp, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, dest)
            return data
        except Exception as exc:  # retry with backoff
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
            print("retry", url, repr(exc), flush=True)


def files_for(slug):
    meta_path = os.path.join(CACHE, slug, "files.json")
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    if not os.path.exists(meta_path):
        http_get(f"https://api.polyhaven.com/files/{slug}", meta_path)
    return json.load(open(meta_path))


def grab(entry, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) == entry.get("size", -1):
        return "skip"
    http_get(entry["url"], dest)
    if entry.get("md5"):
        got = hashlib.md5(open(dest, "rb").read()).hexdigest()
        if got != entry["md5"]:
            raise SystemExit(f"md5 mismatch for {dest}")
    return "ok"


def main():
    kind, slug = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    res = args[args.index("--res") + 1] if "--res" in args else "2k"
    fmt = args[args.index("--fmt") + 1] if "--fmt" in args else "jpg"
    files = files_for(slug)
    out = {}
    if kind == "texture":
        maps = ["Diffuse", "nor_gl", "Rough", "Displacement", "arm"]
        if "--maps" in args:
            i = args.index("--maps") + 1
            maps = [a for a in args[i:] if not a.startswith("--")]
        for m in maps:
            if m not in files:
                out[m] = "absent"
                continue
            entry = files[m].get(res, {}).get(fmt) or files[m].get(res, {}).get("png")
            if not entry:
                out[m] = "no-" + res
                continue
            ext = entry["url"].rsplit(".", 1)[-1]
            dest = os.path.join(CACHE, slug, f"{slug}_{m}_{res}.{ext}")
            out[m] = grab(entry, dest) + ":" + os.path.basename(dest)
    elif kind == "model":
        entry = files["blend"][res]["blend"]
        base = os.path.join(CACHE, slug, res)
        dest = os.path.join(base, os.path.basename(entry["url"]))
        out["blend"] = grab(entry, dest) + ":" + dest
        for rel, inc in entry.get("include", {}).items():
            out[rel] = grab(inc, os.path.join(base, rel))
    elif kind == "hdri":
        entry = files["hdri"][res]["hdr"]
        dest = os.path.join(CACHE, slug, os.path.basename(entry["url"]))
        out["hdri"] = grab(entry, dest) + ":" + dest
    print(slug, json.dumps(out))


if __name__ == "__main__":
    main()
