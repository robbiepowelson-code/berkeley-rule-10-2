#!/usr/bin/env python3
"""Footprint of the aerial tiles an imagery run actually had.

The corridor tile set is not a rectangle (tile_list.py fetches the tiles
within 25 m of the commercial and manufacturing faces), so the run's bounding
box overstates what the detector saw: a block face inside the box but outside
the fetched tiles would be scored "no sidewalk" when the truth is "no image".
This returns the union of the zoom-20 tile squares on disk for an area, in
EPSG:26910, so callers can test faces against what was imaged.
"""
import math, pathlib
from shapely.geometry import box
from shapely.ops import unary_union
import geopandas as gpd

ROOT = pathlib.Path(__file__).resolve().parents[1]
Z = 20


def tile_bounds(x, y):
    n = 2 ** Z
    def lat(yy): return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return (x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y))


def coverage(area, crs=26910):
    tiles = ROOT / 'data/tile2net/tiles' / area / str(Z)
    sq = [box(*tile_bounds(int(p.parent.name), int(p.stem)))
          for p in tiles.glob('*/*.png') if p.stat().st_size > 0]
    if not sq:
        return None
    return gpd.GeoSeries([unary_union(sq)], crs=4326).to_crs(crs).iloc[0]
