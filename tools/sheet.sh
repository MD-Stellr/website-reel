#!/bin/zsh
# Contact sheet of chosen frames, 4 per row.
# usage: tools/sheet.sh <frames_dir> <out.jpg> <frame> [frame ...]
#   e.g. tools/sheet.sh frames/rae-monitor debug/rae-monitor-sheet.jpg 30 180 360 560 770 955
set -euo pipefail
dir=$1; out=$2; shift 2
[[ $dir != /* ]] && dir=$PWD/$dir
mkdir -p "$(dirname "$out")"
tmp=$(mktemp -d); i=0
for f in "$@"; do ln -s "$dir/f$(printf %05d $f).jpg" "$tmp/$(printf %03d $i).jpg"; i=$((i + 1)); done
rows=$(( (i + 3) / 4 ))
ffmpeg -y -loglevel error -framerate 1 -i "$tmp/%03d.jpg" -vf "scale=720:-2,tile=4x${rows}:padding=6" -frames:v 1 "$out"
rm -rf "$tmp"; echo "$out"
