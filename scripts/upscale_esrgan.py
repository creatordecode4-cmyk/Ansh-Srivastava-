#!/usr/bin/env python3
"""4x upscale with Real-ESRGAN (realesr-general-x4v3, BSD-3) on CPU, numpy only.

PyTorch is not needed: the .pth is read with a tiny unpickler and the compact
SRVGG network (conv3x3 + PReLU x33, pixel-shuffle) is run with BLAS matmuls.

  python3 scripts/upscale_esrgan.py in.png out.png [weights.pth]
"""
import pickle
import sys
import urllib.request
import zipfile
import os

import cv2
import numpy as np

URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"


def load_pth(path):
    zf = zipfile.ZipFile(path)
    root = [n for n in zf.namelist() if n.endswith("data.pkl")][0][:-len("data.pkl")]

    class Storage:
        def __init__(self, dtype):
            self.dtype = dtype

    def rebuild(storage, offset, size, stride, *_):
        arr, _ = storage
        n = int(np.prod(size)) if size else 1
        return arr[offset:offset + n].reshape(size).copy()

    class U(pickle.Unpickler):
        def find_class(self, mod, name):
            if name == "_rebuild_tensor_v2":
                return rebuild
            if name.endswith("Storage"):
                return Storage({"FloatStorage": np.float32, "HalfStorage": np.float16, "LongStorage": np.int64}[name])
            if mod == "collections" and name == "OrderedDict":
                import collections
                return collections.OrderedDict
            if name == "_rebuild_parameter":
                return lambda data, *_: data
            raise pickle.UnpicklingError(f"unsupported {mod}.{name}")

        def persistent_load(self, pid):
            _, st, key, _, _ = pid
            return np.frombuffer(zf.read(f"{root}data/{key}"), st.dtype), key

    sd = U(zf.open(root + "data.pkl")).load()
    return sd.get("params", sd)


def conv3(x, w, b):
    """x: (H,W,Cin) float32, w: (Cout,Cin,3,3) -> (H,W,Cout)"""
    H, W, _ = x.shape
    xp = np.pad(x, ((1, 1), (1, 1), (0, 0)), mode="constant")
    out = np.empty((H, W, w.shape[0]), np.float32)
    out[:] = b
    for i in range(3):
        for j in range(3):
            out += xp[i:i + H, j:j + W] @ w[:, :, i, j].T
    return out


def upscale(img_bgr, sd):
    x = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    keys = sorted({int(k.split(".")[1]) for k in sd})
    h = x
    for k in keys:
        w = np.asarray(sd[f"body.{k}.weight"], np.float32)
        if w.ndim == 4:
            h = conv3(h, w, np.asarray(sd[f"body.{k}.bias"], np.float32))
        else:                                  # PReLU, one slope per channel
            h = np.where(h >= 0, h, h * w)
    H, W, _ = h.shape                          # pixel shuffle x4: channel = c*16 + i*4 + j
    h = h.reshape(H, W, 3, 4, 4).transpose(0, 3, 1, 4, 2).reshape(H * 4, W * 4, 3)
    h += cv2.resize(x, (W * 4, H * 4), interpolation=cv2.INTER_NEAREST)
    return cv2.cvtColor(np.clip(h * 255, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    wpath = sys.argv[3] if len(sys.argv) > 3 else "output/work/realesr-general-x4v3.pth"
    if not os.path.exists(wpath):
        urllib.request.urlretrieve(URL, wpath)
    im = cv2.imread(src)
    out = np.zeros((im.shape[0] * 4, im.shape[1] * 4, 3), np.uint8)
    sd = load_pth(wpath)
    T, P = 256, 16                              # tiles keep memory low
    for y in range(0, im.shape[0], T):
        for x in range(0, im.shape[1], T):
            y0, x0 = max(0, y - P), max(0, x - P)
            y1, x1 = min(im.shape[0], y + T + P), min(im.shape[1], x + T + P)
            o = upscale(im[y0:y1, x0:x1], sd)
            ty, tx = min(T, im.shape[0] - y), min(T, im.shape[1] - x)
            out[y * 4:(y + ty) * 4, x * 4:(x + tx) * 4] = o[(y - y0) * 4:(y - y0 + ty) * 4, (x - x0) * 4:(x - x0 + tx) * 4]
    cv2.imwrite(dst, out)
    print("wrote", dst, out.shape)
