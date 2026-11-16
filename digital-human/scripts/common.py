"""Shared paths and helpers for the digital-human pipeline (headless bpy)."""
import os, json, bpy

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
WORK = os.environ.get("DH_WORK", os.path.join(PROJ, "work"))
MPFB = os.environ.get("DH_MPFB")  # .../anny/data/mpfb2
OUT = os.path.join(PROJ, "output")
os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(obj, collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)


def save_json(name, data):
    with open(os.path.join(WORK, name), "w") as f:
        json.dump(data, f)


def load_json(name):
    with open(os.path.join(WORK, name)) as f:
        return json.load(f)


def node(nt, typ, loc=(0, 0), **inputs):
    n = nt.nodes.new(typ)
    n.location = loc
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n
