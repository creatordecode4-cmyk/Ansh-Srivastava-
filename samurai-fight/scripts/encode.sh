#!/bin/bash
# Encode a rendered frame folder to MP4. Usage: bash scripts/encode.sh <frames_dir> <out.mp4> [width] [label]
set -e
W=${3:-960}
LABEL=${4:-}
VF="scale=${W}:-2:flags=lanczos"
if [ -n "$LABEL" ]; then
  VF="$VF,drawtext=text='$LABEL  f%{frame_num}':start_number=1:x=12:y=h-28:fontsize=16:fontcolor=white@0.85:box=1:boxcolor=black@0.5"
fi
ffmpeg -y -loglevel error -framerate 24 -start_number 1 -i "$1/f%04d.png" -vf "$VF" -c:v libx264 -pix_fmt yuv420p -crf 21 -movflags +faststart "$2"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,nb_frames,r_frame_rate,duration -of csv=p=0 "$2"
