#!/bin/bash
# 20 s ambient bed: waterfall rumble + spray, river, wind in leaves, birds, soft pad. Output: ambience.wav
D=20
ffmpeg -y -loglevel error \
 -f lavfi -i "anoisesrc=d=$D:c=brown:a=0.9:seed=11" \
 -f lavfi -i "anoisesrc=d=$D:c=pink:a=0.5:seed=12" \
 -f lavfi -i "anoisesrc=d=$D:c=white:a=0.35:seed=13" \
 -f lavfi -i "aevalsrc='0.10*sin(2*PI*3600*t+40*sin(2*PI*30*t))*between(mod(t,2.3),2.0,2.12)*pow(sin(PI*(mod(t,2.3)-2.0)/0.12),2)+0.08*sin(2*PI*4700*t+60*sin(2*PI*22*t))*between(mod(t+0.9,3.7),3.0,3.09)*pow(sin(PI*(mod(t+0.9,3.7)-3.0)/0.09),2)+0.07*sin(2*PI*2900*t+80*sin(2*PI*14*t))*between(mod(t+1.7,5.3),5.0,5.25)*pow(sin(PI*(mod(t+1.7,5.3)-5.0)/0.25),2)':s=48000:d=$D" \
 -f lavfi -i "aevalsrc='(1-clip((t-9)/2,0,1))*(sin(2*PI*110*t)+0.8*sin(2*PI*164.81*t)+0.6*sin(2*PI*220*t)+0.45*sin(2*PI*277.18*t)+0.35*sin(2*PI*329.63*t))*0.035+clip((t-9)/2,0,1)*(sin(2*PI*92.5*t)+0.8*sin(2*PI*138.59*t)+0.6*sin(2*PI*185*t)+0.45*sin(2*PI*220*t)+0.35*sin(2*PI*277.18*t))*0.035':s=48000:d=$D" \
 -filter_complex "\
[0:a]lowpass=f=700,volume=1.4[fall];\
[1:a]asplit[pk1][pk2];[pk1]highpass=f=1800,lowpass=f=7000,volume=0.25[spray];\
[pk2]bandpass=f=900:width_type=h:w=1400,tremolo=f=0.35:d=0.35,volume=0.5[river];\
[2:a]bandpass=f=3200:width_type=h:w=3000,tremolo=f=0.12:d=0.8,volume=0.18[wind];\
[3:a]aecho=0.8:0.6:40|90:0.25|0.15,volume=0.9[birds];\
[4:a]lowpass=f=1200,tremolo=f=0.1:d=0.4,aecho=0.8:0.7:120|240:0.35|0.2,volume=1.0[pad];\
[fall][spray][river][wind][birds][pad]amix=inputs=6:normalize=0,afade=t=in:d=1.5,afade=t=out:st=17.8:d=2.2,alimiter=limit=0.9,aformat=channel_layouts=stereo[out]" \
 -map "[out]" -ar 48000 ambience.wav
