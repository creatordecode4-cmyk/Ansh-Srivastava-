#!/bin/bash
# Grade (bloom, warm highlights, saturation, lifted blacks, vignette, grain) + ambience -> H.264 MP4.
# Usage: ./encode.sh <frames_dir> <ambience.wav> <out.mp4>
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
F=$(tr -d '\n' < "$HERE/grade_filter.txt")
ffmpeg -y -loglevel error -framerate 24 -i "$1/f_%04d.jpg" -i "$2" -filter_complex "$F" \
  -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 18 -profile:v high -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest -movflags +faststart -r 24 "$3"
