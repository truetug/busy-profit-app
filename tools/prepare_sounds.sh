#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
for name in cha-ching applause; do
  ffmpeg -nostdin -y -loglevel error -i "$root/assets/sounds/$name.wav" \
    -ac 1 -ar 44100 -f s16le "$root/src/sounds/$name.snd"
done
