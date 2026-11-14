#!/bin/bash
# Stage 1 preview set. Usage: bash scripts/render_stage1.sh
cd "$(dirname "$0")/.." && mkdir -p build/stage1
R="python3 scripts/render.py build/arena.blend"
$R build/stage1/hero_beauty.png --cam CAM_Hero  --res 1280x720 --spp 64
$R build/stage1/hero_clay.png   --cam CAM_Hero  --res 1280x720 --spp 32 --clay --no-fx
$R build/stage1/top_beauty.png  --cam CAM_Top   --res 1300x790 --spp 24 --no-fog --no-fx --exposure 1.5
$R build/stage1/top_clay.png    --cam CAM_Top   --res 1300x790 --spp 16 --clay --no-fx
$R build/stage1/fight_beauty.png --cam CAM_Fight --res 1280x720 --spp 48
$R build/stage1/drone_beauty.png --cam CAM_Wide  --res 1280x720 --spp 48
