#!/bin/bash
# full rebuild: body -> head -> clothes -> pose+sim -> scene
set -e
cd "$(dirname "$0")"; . ./env.sh
$PY scripts/s1_body.py | grep -E "OK|missing"
$PY scripts/s2_head.py 2>&1 | grep -E "OK|Error"
$PY scripts/s3_clothes.py 2>&1 | grep -E "OK|Error"
$PY scripts/s4_pose_sim.py 2>&1 | grep -E "OK|Error|sim frame"
$PY scripts/s5_scene.py 2>&1 | grep -E "OK|Error"
