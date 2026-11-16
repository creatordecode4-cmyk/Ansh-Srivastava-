#!/bin/bash
# final outputs (CPU Cycles). Turntable frames -> mp4 via ffmpeg.
cd "$(dirname "$0")"; . ./env.sh
R="$PY scripts/s6_render.py"
$R final 192 100 2>&1 | grep -E "wrote|Error"
$R face 192 100 2>&1 | grep -E "wrote|Error"
$R clay 64 60 2>&1 | grep -E "wrote|Error"
$R wire 32 60 2>&1 | grep -E "wrote|Error"
$R rigtest 32 50 2>&1 | grep -E "wrote|Error"
TT_FRAMES=96 $R turntable 20 50 2>&1 | grep -E "tt frame|Error"
ffmpeg -y -loglevel error -framerate 24 -i $DH_WORK/renders/tt/tt_%04d.png -vf "pad=ceil(iw/2)*2:ceil(ih/2)*2" -c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart output/turntable.mp4 && echo "wrote turntable.mp4"
echo RENDER_ALL_DONE
