"""Download the Mixkit free sound effects the film's sound uses (the ids in sd/samples.py) into
out/sound/mixkit/raw/<id>.wav. They are not kept in the repository: the Mixkit Sound Effects Free License
lets them be used in a project, not handed out on their own (https://mixkit.co/license/).

    python3 -I tools/mixkit_fetch.py          (needs network access to mixkit.co and assets.mixkit.co)
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from sd import samples as SM  # noqa: E402

os.makedirs(SM.ROOT, exist_ok=True)
got = failed = 0
for i in SM.ids():
    p = os.path.join(SM.ROOT, f"{i}.wav")
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        continue
    r = subprocess.run(["curl", "-sS", "--max-time", "60", "-A", "Mozilla/5.0", "-o", p, "-w", "%{http_code}",
                        f"https://assets.mixkit.co/active_storage/sfx/{i}/{i}.wav"], capture_output=True, text=True)
    if r.stdout.strip() == "200" and os.path.getsize(p) > 1000:
        got += 1
    else:
        failed += 1
        print("failed", i, r.stdout.strip())
        if os.path.exists(p):
            os.remove(p)
    time.sleep(0.5)
print(f"downloaded {got}, failed {failed}, in {SM.ROOT}")
