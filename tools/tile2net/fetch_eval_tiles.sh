#!/bin/bash
# Fetch the Alameda County 2023 aerial tiles (Pictometry WMTS, zoom 20) for the
# two tile2net evaluation areas used to test the detector against Figure 4 of
# the City's 2020 Pedestrian Plan:
#   nw    - Harrison / Page / Sixth / Fifth, Second St to San Pablo, Gilman to Camelia
#   ninth - Ninth St and neighbours between Carleton and Potter
# Run in Terminal on the Mac (the City's imagery host is not reachable from Claude's shells):
#   cd ~/BerkeleyHomelessUnion/berkeley-rule-10-2 && bash tools/tile2net/fetch_eval_tiles.sh
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="https://svc.pictometry.com/Image/6D9E15C5-C6B4-4ACB-A244-4C44ECA33D90/wmts/PICT-CAALAM20-OQ74EOAkBw/default/GoogleMapsCompatible"
fetch_box () {  # name x0 x1 y0 y1
  local T="$REPO/data/tile2net/tiles/$1/20"; mkdir -p "$T"
  local n=0 bad=0
  for x in $(seq $2 $3); do
    mkdir -p "$T/$x"
    for y in $(seq $4 $5); do
      f="$T/$x/$y.png"
      if [ ! -s "$f" ]; then curl -sS -L --retry 3 -o "$f" "$BASE/20/$x/$y.png" || { bad=$((bad+1)); rm -f "$f"; }; fi
      n=$((n+1))
    done
    printf "\r%s: %d tiles, %d failed" "$1" "$n" "$bad"
  done
  echo; find "$T" -name '*.png' -size +0 | wc -l | xargs echo "$1 tiles on disk:"
}
fetch_box nw    168043 168086 404894 404927
fetch_box ninth 168070 168094 404986 405014
cd "$REPO/data/tile2net/tiles" && tar czf eval_tiles.tgz nw ninth && ls -la eval_tiles.tgz
echo "done - tell Claude the tiles are in place"
