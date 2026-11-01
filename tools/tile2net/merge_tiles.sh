#!/bin/bash
# Pool the zoom-20 tiles of several areas into one tile folder so a single
# tile2net run can cover all of them. tile_list.py leaves out tiles already on
# disk under another area, so the corridor list on its own has holes where the
# nw and ninth pilot boxes were fetched earlier; this fills them with links.
#   bash tools/tile2net/merge_tiles.sh corridor nw ninth
# links every data/tile2net/tiles/{nw,ninth}/20/<x>/<y>.png that corridor lacks
# into data/tile2net/tiles/corridor/20/<x>/<y>.png. Hard links (or copies), never
# symlinks: tile2net reads a symlinked tile as a black tile (raster.py imread).
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; T="$REPO/data/tile2net/tiles"
DEST="$1"; shift; n=0
for SRC in "$@"; do
  while read -r f; do
    rel="${f#$T/$SRC/20/}"; d="$T/$DEST/20/$rel"
    [ -L "$d" ] && rm -f "$d"
    [ -s "$d" ] && continue
    mkdir -p "$(dirname "$d")"; ln "$f" "$d" 2>/dev/null || cp "$f" "$d"; n=$((n+1))
  done < <(find "$T/$SRC/20" -name '*.png' -size +0)
done
echo "$DEST: $n tiles linked in; $(find -L "$T/$DEST/20" -name '*.png' -size +0 | wc -l) tiles total"
