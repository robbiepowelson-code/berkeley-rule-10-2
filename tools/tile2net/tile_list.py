#!/usr/bin/env python3
"""List the zoom-20 aerial tiles needed to cover every commercial and
manufacturing block face in the pilot corridor (faces buffered 25 m), minus
tiles already on disk. Writes data/tile2net/tiles/corridor_tiles.txt as
"x y" lines for tools/tile2net/fetch_tiles.sh.

Usage: python3 tools/tile2net/tile_list.py
"""
import math, pathlib
import geopandas as gpd

ROOT = pathlib.Path(__file__).resolve().parents[2]
Z = 20
def tile(lat, lon):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

faces = gpd.read_file(ROOT / 'data/campable/faces.geojson')
cm = faces[faces['cat'].isin(['com', 'man', 'mixres'])].to_crs(26910)
cm['geometry'] = cm.buffer(25)
cm = cm.to_crs(4326)
need = set()
for g in cm.geometry:
    minx, miny, maxx, maxy = g.bounds
    x0, y1 = tile(miny, minx); x1, y0 = tile(maxy, maxx)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            need.add((x, y))
have = set()
for p in (ROOT / 'data/tile2net/tiles').glob('*/20/*/*.png'):
    if p.stat().st_size > 0: have.add((int(p.parent.name), int(p.stem)))
todo = sorted(need - have)
out = ROOT / 'data/tile2net/tiles/corridor_tiles.txt'
out.write_text('\n'.join(f'{x} {y}' for x, y in todo) + '\n')
print(f'{len(need)} tiles cover the com/man/mixres faces; {len(need & have)} already on disk; {len(todo)} to fetch (~{len(todo)*0.08:.0f} MB) -> {out}')
