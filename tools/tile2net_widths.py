#!/usr/bin/env python3
"""Sidewalk widths from tile2net polygons, compared with the campable model's widths.

tile2net (Hosseini et al. 2023, BSD-3, github.com/VIDA-NYU/tile2net) segments
sidewalks from aerial tiles and writes polygons. This script turns those
polygons into widths and lines them up against the block faces in
data/campable/faces.geojson so the two sources can be checked against each
other and against tape measurements in data/field/sidewalk_widths.csv.

Width method (same idea as meliharvey/sidewalkwidths-nyc): rasterise each
sidewalk polygon at 10 cm, take the Euclidean distance transform, skeletonise,
and read 2 x distance along the skeleton. That gives a width at every point of
the sidewalk's centreline; the median is reported, with the 10th and 90th
percentiles to show pinch points and flares.

Usage:
  python3 tools/tile2net_widths.py <polygons.parquet|.geojson> <outdir>

Outputs in <outdir>:
  sidewalks.geojson      the tile2net sidewalk polygons with width stats attached
  sidewalk_widths.csv    one row per polygon: length, median/p10/p90 width (ft)
  face_compare.csv       one row per campable block face inside the run's bounds:
                         GIS width, tile2net width, difference
"""
import sys, pathlib
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
from scipy import ndimage
from skimage.morphology import skeletonize
from rasterio import features
from affine import Affine

ROOT = pathlib.Path(__file__).resolve().parents[1]
FT = 3.28084
RES = 0.10          # metres per pixel for the width raster
NEAR_M = 4.0        # a sidewalk polygon within this distance of a face belongs to it
EDGE_M = 15.0       # ignore faces within this distance of the run's edge (partial tiles)


def width_stats(poly):
    minx, miny, maxx, maxy = poly.bounds
    pad = 1.0
    W = int((maxx - minx + 2 * pad) / RES) + 1
    H = int((maxy - miny + 2 * pad) / RES) + 1
    tr = Affine(RES, 0, minx - pad, 0, -RES, maxy + pad)
    m = features.rasterize([(poly, 1)], out_shape=(H, W), transform=tr).astype(bool)
    dt = ndimage.distance_transform_edt(m) * RES
    w = 2 * dt[skeletonize(m)]
    w = w[w > 0.5]
    if not len(w):
        return None
    return dict(len_ft=len(w) * RES * FT, med_ft=float(np.median(w)) * FT,
                p10_ft=float(np.percentile(w, 10)) * FT, p90_ft=float(np.percentile(w, 90)) * FT)


def main(src, outdir):
    outdir = pathlib.Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    g = gpd.read_parquet(src) if str(src).endswith('.parquet') else gpd.read_file(src)
    g = g.to_crs(26910)                                   # UTM 10N, metres
    sw = g[g.f_type == 'sidewalk'].copy()
    stats = {i: width_stats(r.geometry) for i, r in sw.iterrows()}
    for k in ('len_ft', 'med_ft', 'p10_ft', 'p90_ft'):
        sw[k] = [stats[i][k] if stats[i] else None for i in sw.index]
    sw['area_sqft'] = sw.geometry.area * FT * FT
    sw.to_crs(4326).to_file(outdir / 'sidewalks.geojson', driver='GeoJSON')
    sw.drop(columns='geometry').round(1).to_csv(outdir / 'sidewalk_widths.csv', index=True, index_label='poly')

    faces = gpd.read_file(ROOT / 'data/campable/faces.geojson').to_crs(26910)
    inner = box(*g.total_bounds).buffer(-EDGE_M)
    rows = []
    for i, r in faces[faces.intersects(inner)].iterrows():
        near = sw[sw.distance(r.geometry) < NEAR_M]
        near = near[near.med_ft.notna()]
        tw = float((near.med_ft * near.len_ft).sum() / near.len_ft.sum()) if len(near) else None
        rows.append(dict(face=r['id'], street=r['street'], side=r['side'], cat=r['cat'],
                         gis_width_ft=r['width_ft'], gis_source=r['width_source'], model_spots=r['count'],
                         tile2net_width_ft=tw, polygons=len(near), face_len_ft=r.geometry.length * FT))
    cmp = pd.DataFrame(rows)
    cmp['diff_ft'] = cmp.tile2net_width_ft - cmp.gis_width_ft
    cmp.round(1).to_csv(outdir / 'face_compare.csv', index=False)
    print(cmp.round(1).to_string(index=False))
    print(f"\n{len(sw)} sidewalk polygons, {len(cmp)} block faces compared -> {outdir}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
