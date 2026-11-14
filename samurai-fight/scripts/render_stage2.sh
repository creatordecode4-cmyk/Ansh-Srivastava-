#!/bin/bash
# Stage 2 preview set. Needs build/characters.blend (prep_characters.py) and build/arena.blend.
cd "$(dirname "$0")/.." && mkdir -p build/stage2
python3 scripts/build_stage2.py 2>&1 | grep -E "STAGE2|rror|Traceback"
for c in Oni Ronin; do python3 scripts/render_turnaround.py build/characters.blend $c build/stage2/$c --spp 24 2>&1 | grep -E "TURNAROUND|rror|Traceback"; done
python3 scripts/test_weapons.py build/stage2/katanas.png 2>&1 | grep -E "WEAPON|rror|Traceback"
python3 scripts/render.py build/stage2.blend build/stage2/arena_check.png --cam CAM_Standoff --res 1280x720 --spp 48 2>&1 | grep -E "RENDERED|rror"
python3 -I scripts/compose_stage2.py
