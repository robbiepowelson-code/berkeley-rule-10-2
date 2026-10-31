#!/bin/bash
# Run tile2net over one tile folder and turn the result into widths + a Figure 4 score.
#   bash tools/tile2net/run_area.sh <name> "<S, W, N, E>"
# Expects data/tile2net/tiles/<name>/20/<x>/<y>.png (see fetch_eval_tiles.sh) and the
# weights in tile2net/weights (TILE2NET_WEIGHTS_DIR). CPU is fine: tools/tile2net/run_cpu.py.
set -e
NAME="$1"; BBOX="$2"; export FACES="${FACES:-data/campable/faces.geojson}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
export TILE2NET_WEIGHTS_DIR="${TILE2NET_WEIGHTS_DIR:-$REPO/tile2net/weights}"; export FACES="$REPO/$FACES"
OUT="$REPO/data/tile2net/runs"; mkdir -p "$OUT"
python3 -m tile2net generate -l "$BBOX" -n "$NAME" -o "$OUT" -i "$REPO/data/tile2net/tiles/$NAME/20/x/y.png" -z 20 > "$OUT/$NAME.generate.log" 2>&1
python3 "$REPO/tools/tile2net/run_cpu.py" inference --city_info "$OUT/$NAME/tiles/${NAME}_256_info.json" --local --eval test --dump_percent 0 > "$OUT/$NAME.inference.log" 2>&1
P="$OUT/$NAME/polygons/$NAME-polygons.parquet"
mkdir -p "$REPO/data/tile2net/$NAME" && cp "$P" "$REPO/data/tile2net/$NAME/polygons.parquet"
python3 "$REPO/tools/tile2net_widths.py" "$P" "$REPO/data/tile2net/$NAME"
echo "done: $REPO/data/tile2net/$NAME"
