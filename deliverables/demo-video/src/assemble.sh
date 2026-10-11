#!/usr/bin/env bash
# Assemble scenes/*.webm → piratehunter-demo.mp4 (H.264 1920x1080 30fps, no audio).
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p build/norm
rm -f build/norm/*.mp4 build/concat.txt

for f in scenes/*.webm; do
  name=$(basename "$f" .webm)
  ffmpeg -y -loglevel error -i "$f" \
    -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#EDEDED,fps=30" \
    -an -c:v libx264 -preset medium -crf 21 -pix_fmt yuv420p \
    "build/norm/$name.mp4"
  # concat demuxer resolves paths relative to the list file (build/)
  echo "file 'norm/$name.mp4'" >> build/concat.txt
done

ffmpeg -y -loglevel error -f concat -safe 0 -i build/concat.txt -c copy piratehunter-demo.mp4
echo "--- result:"
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate -of default=nw=1 piratehunter-demo.mp4
