#!/bin/bash
# Fetch the tile2net model weights and the Alameda County 2023 aerial tiles
# for the sample block (the block bounded by Seventh, Eighth, Heinz and Grayson, Berkeley).
# Run this in Terminal on the Mac itself:
#   bash tools/tile2net/fetch_inputs.sh
set -e
REPO="$HOME/BerkeleyHomelessUnion/berkeley-rule-10-2"
W="$REPO/tile2net/weights"
T="$REPO/data/tile2net/tiles/sample/20"
mkdir -p "$W" "$T"

echo "== model weights (about 890 MB total, from figshare) =="
[ -s "$W/satellite_2021.pth" ] || curl -L --progress-bar -o "$W/satellite_2021.pth" "https://ndownloader.figshare.com/files/67765602"
[ -s "$W/hrnetv2_w48_imagenet_pretrained.pth" ] || curl -L --progress-bar -o "$W/hrnetv2_w48_imagenet_pretrained.pth" "https://ndownloader.figshare.com/files/67765578"
echo "weights:"; ls -la "$W"

echo "== aerial tiles: Alameda County 2023 (Pictometry WMTS), zoom 20, 100 tiles =="
BASE="https://svc.pictometry.com/Image/6D9E15C5-C6B4-4ACB-A244-4C44ECA33D90/wmts/PICT-CAALAM20-OQ74EOAkBw/default/GoogleMapsCompatible"
n=0
for x in $(seq 168081 168090); do
  mkdir -p "$T/$x"
  for y in $(seq 404999 405008); do
    f="$T/$x/$y.png"
    [ -s "$f" ] || curl -sS -L -o "$f" "$BASE/20/$x/$y.png" || echo "failed $x/$y"
    n=$((n+1))
  done
done
echo "tiles fetched: $n"; find "$T" -name '*.png' -size +0 | wc -l; du -sh "$T"
echo "done - tell Claude the files are in place"
