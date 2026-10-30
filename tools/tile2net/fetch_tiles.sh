#!/bin/bash
# Fetch the Alameda County 2023 aerial tiles listed in data/tile2net/tiles/corridor_tiles.txt
# (made by tools/tile2net/tile_list.py) into data/tile2net/tiles/corridor/20/<x>/<y>.png.
# Run in Terminal on the Mac (the county imagery host is not reachable from Claude's shells):
#   cd ~/BerkeleyHomelessUnion/berkeley-rule-10-2 && bash tools/tile2net/fetch_tiles.sh
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="https://svc.pictometry.com/Image/6D9E15C5-C6B4-4ACB-A244-4C44ECA33D90/wmts/PICT-CAALAM20-OQ74EOAkBw/default/GoogleMapsCompatible"
T="$REPO/data/tile2net/tiles/corridor/20"; LIST="$REPO/data/tile2net/tiles/corridor_tiles.txt"
n=0; bad=0; total=$(wc -l < "$LIST")
while read -r x y; do
  [ -z "$x" ] && continue
  mkdir -p "$T/$x"; f="$T/$x/$y.png"
  if [ ! -s "$f" ]; then curl -sS -L --retry 3 -o "$f" "$BASE/20/$x/$y.png" || { bad=$((bad+1)); rm -f "$f"; }; fi
  n=$((n+1)); [ $((n % 100)) -eq 0 ] && printf "\r%d / %d tiles, %d failed" "$n" "$total" "$bad"
done < "$LIST"
echo; echo "corridor tiles on disk: $(find "$T" -name '*.png' -size +0 | wc -l)"
cd "$REPO/data/tile2net/tiles" && tar czf corridor_tiles.tgz corridor && ls -la corridor_tiles.tgz
echo "done - tell Claude the tiles are in place"
