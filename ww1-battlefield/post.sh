#!/usr/bin/env bash
# Join the PNG sequence into a graded H.264 MP4 (24 fps).
set -euo pipefail
cd "$(dirname "$0")"
ffmpeg -y -loglevel error -framerate 24 -start_number 1 -i out/frames/frame_%04d.png \
  -vf "eq=contrast=1.14:saturation=0.82:gamma=0.95,\
colorbalance=rs=-0.05:gs=0.01:bs=0.06:rh=0.06:gh=0.01:bh=-0.06,\
vignette=PI/4.5,noise=alls=7:allf=t+u,format=yuv420p" \
  -c:v libx264 -preset slow -crf 15 -movflags +faststart out/ww1_battlefield.mp4
ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration,pix_fmt \
  -of default=nw=1 out/ww1_battlefield.mp4
