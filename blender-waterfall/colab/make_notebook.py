"""Builds Waterfall_Valley_Colab.ipynb with every script embedded (%%writefile cells)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def code(src): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}
def md(src): return {"cell_type": "markdown", "metadata": {}, "source": src}
def embed(path, dest):
    with open(path) as f:
        return code(f"%%writefile {dest}\n" + f.read())

cells = [
md("""# 🌄 Waterfall Valley: photoreal Blender Cycles render (free Colab GPU)

**How to use it (on your phone too):**
1. Top menu **Runtime → Change runtime type → T4 GPU → Save**.
2. Run the cells **in order, one at a time** (▶ button). Every cell shows its output.
3. **Cell 6 (preview)** renders a test frame. Check it; if there's an error, send a screenshot to Claude.
4. **Cell 7** renders all 480 frames. Frames are saved to Google Drive, so if Colab disconnects,
   run cells 1-3 again and then cell 7: it continues from where it stopped.
5. **Cell 8** builds the graded MP4 with sound and downloads it.

Time on a T4: roughly 60-120 s per frame, so about 8-16 hours in total, split across several Colab sessions.
To go faster, set `SAMPLES_FINAL = 32` in cell 4 (a bit more noise; the denoiser cleans most of it)."""),
code("""# 1) GPU check
!nvidia-smi -L"""),
code("""# 2) Storage: Google Drive (recommended, so a disconnect does not lose frames)
USE_DRIVE = True
import os
if USE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
    OUT = '/content/drive/MyDrive/waterfall_valley'
else:
    OUT = '/content/waterfall_valley'
os.makedirs(OUT + '/frames', exist_ok=True)
print('Output folder:', OUT)"""),
code("""# 3) Install Blender 4.2 LTS (headless) - about 2 minutes
import re, urllib.request, os
if not os.path.exists('/content/blender/blender'):
    html = urllib.request.urlopen('https://download.blender.org/release/Blender4.2/').read().decode()
    vers = sorted(set(re.findall(r'blender-(4\\.2\\.\\d+)-linux-x64\\.tar\\.xz', html)), key=lambda v: int(v.split('.')[-1]))
    v = vers[-1]
    print('Downloading Blender', v)
    !wget -q https://download.blender.org/release/Blender4.2/blender-{v}-linux-x64.tar.xz -O /content/blender.tar.xz
    !mkdir -p /content/blender && tar -xf /content/blender.tar.xz -C /content/blender --strip-components=1 && rm /content/blender.tar.xz
!apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libice6 > /dev/null 2>&1
!/content/blender/blender -b --version | head -1
os.makedirs('/content/wf', exist_ok=True)"""),
md("## 4) Scripts (just run these cells; they only write files)"),
embed(os.path.join(ROOT, "build_waterfall_scene.py"), "/content/wf/build_waterfall_scene.py"),
embed(os.path.join(ROOT, "final_scene.py"), "/content/wf/final_scene.py"),
embed(os.path.join(ROOT, "gpu.py"), "/content/wf/gpu.py"),
embed(os.path.join(ROOT, "web_render", "make_audio.sh"), "/content/wf/make_audio.sh"),
embed(os.path.join(ROOT, "web_render", "grade_filter.txt"), "/content/wf/grade_filter.txt"),
code("""# 5) Build the scene and save it to Drive (about 3-6 minutes, CPU)
!cd /content/wf && /content/blender/blender -b -P final_scene.py -- --save {OUT}/waterfall_final.blend 2>&1 | grep -v -E "^(Read|Fra:)" | tail -n 25"""),
code("""# 6) PREVIEW: frame 1 at 960x540 with low samples (a few minutes)
!cd /content/wf && /content/blender/blender -b {OUT}/waterfall_final.blend -P gpu.py --python-expr "import bpy; s=bpy.context.scene; s.render.resolution_percentage=50; s.cycles.samples=24; s.render.use_overwrite=True" -o {OUT}/preview_#### -F PNG -f 1 2>&1 | grep -E "GPU|Saved|Error|error" | tail -n 8
import glob
from IPython.display import Image, display
for f in sorted(glob.glob(OUT + '/preview_*.png'))[-1:]:
    display(Image(f, width=960))"""),
code("""# 7) FULL RENDER: 480 frames, 1920x1080 (resumable - just run again after a disconnect)
!cd /content/wf && /content/blender/blender -b {OUT}/waterfall_final.blend -P gpu.py -o {OUT}/frames/f_#### -F PNG -s 1 -e 480 -a 2>&1 | grep --line-buffered -E "Saved|Error|GPU"
!ls {OUT}/frames | wc -l"""),
code("""# 8) Colour grade + film grain/vignette + ambient sound -> MP4, then download
!cd /content/wf && bash make_audio.sh && cp ambience.wav {OUT}/
F = open('/content/wf/grade_filter.txt').read().replace('\\n', '')
!ffmpeg -y -loglevel error -framerate 24 -i {OUT}/frames/f_%04d.png -i {OUT}/ambience.wav -filter_complex "{F}" -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart {OUT}/waterfall_valley_cycles.mp4
!ls -lh {OUT}/waterfall_valley_cycles.mp4
from google.colab import files
files.download(OUT + '/waterfall_valley_cycles.mp4')"""),
]
nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
      "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
with open(os.path.join(HERE, "Waterfall_Valley_Colab.ipynb"), "w") as f:
    json.dump(nb, f, indent=1)
print("notebook written")
