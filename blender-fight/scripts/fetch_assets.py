"""Download the free CC0 Poly Haven assets used by the arena into ./assets (not committed).
Run:  python3 scripts/fetch_assets.py
"""
import json, os, sys, urllib.request
os.environ.setdefault('SSL_CERT_FILE', '/root/.ccr/ca-bundle.crt') if os.path.exists('/root/.ccr/ca-bundle.crt') else None
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
UA = {'User-Agent': 'blender-arena-script'}

HDRIS = ['kloppenheim_02_puresky']
TEXTURES = ['monastery_stone_floor', 'stone_tiles_02', 'slab_tiles', 'mossy_rock', 'japanese_stone_wall',
            'weathered_planks', 'grey_roof_tiles_02', 'ceramic_roof_01', 'sakura_bark', 'rock_boulder_dry']
MODELS = ['rock_moss_set_01', 'boulder_01']
TEX_MAPS = ['Diffuse', 'nor_gl', 'Rough', 'Displacement', 'AO']

def get_json(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))

def dl(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(path + '.part', 'wb') as f:
        f.write(r.read())
    os.replace(path + '.part', path)
    print('  got', os.path.relpath(path, ROOT), os.path.getsize(path) // 1024, 'KB')

def main():
    for h in HDRIS:
        f = get_json(f'https://api.polyhaven.com/files/{h}')
        dl(f['hdri']['2k']['hdr']['url'], os.path.join(ROOT, 'hdri', h + '_2k.hdr'))
    for t in TEXTURES:
        f = get_json(f'https://api.polyhaven.com/files/{t}')
        for m in TEX_MAPS:
            if m in f and '2k' in f[m] and 'jpg' in f[m]['2k']:
                dl(f[m]['2k']['jpg']['url'], os.path.join(ROOT, 'tex', t, f'{m}.jpg'))
    for m in MODELS:
        f = get_json(f'https://api.polyhaven.com/files/{m}')
        g = f['gltf']['1k']['gltf'] if '1k' in f['gltf'] else list(f['gltf'].values())[0]['gltf']
        base = os.path.join(ROOT, 'models', m)
        dl(g['url'], os.path.join(base, m + '.gltf'))
        for rel, inc in g.get('include', {}).items():
            dl(inc['url'], os.path.join(base, rel))

if __name__ == '__main__':
    main()
