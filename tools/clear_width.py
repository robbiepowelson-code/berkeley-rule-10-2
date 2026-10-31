#!/usr/bin/env python3
"""Clear-walk width profile along every block face, from the 2023 aerial.

Why: a sidewalk polygon from tile2net runs from the curb to the property line
and so includes tree wells, planting strips and driveway aprons. AR 10.2's
path of travel is about the paved walk a person can actually use, and that
width changes along a block (a tree well here, a bulb-out there, a driveway
flare at the corner). One number per block face is not good enough.

Method, per block face (the curb-side line in data/campable/faces.geojson):
  1. Every STEP m along the face, take a cross-section perpendicular to it,
     from IN_M on the road side of the GIS curb line to OUT_M on the property
     side (the GIS curb line is often several feet off, so the section must
     span the whole sidewalk regardless), sampled every 0.1 m from the aerial
     tiles (zoom 20, ~0.12 m/px). The sidewalk is wherever the section lies
     inside a tile2net sidewalk polygon.
  2. Classify each sample as paved or not. Paved = low colour saturation and
     not dark (concrete, asphalt); vegetation, bark, dirt and mulch are
     saturated (green/brown) and are not paved. Tree canopy over the walk is
     also "not paved", so sections under heavy canopy under-read; they are
     dropped when fewer than MIN_VALID of the samples are classifiable.
  3. Clear width = the longest contiguous paved run in the section that lies
     within a tile2net sidewalk polygon (so the road itself is excluded even
     where there is no curb visible). A planting strip between curb and walk
     breaks the run, so the run is the walk alone.
  4. Sections within DRIVE_M of an OSM driveway (service=driveway) or a
     tile2net crosswalk polygon are marked `driveway` and excluded from the
     width statistics (a driveway apron is not sidewalk for a tent).
  5. Adjacent sections whose width agrees within 1 ft are merged into runs.

Outputs (per area, in data/tile2net/<area>/):
  clear_width_profile.geojson  one short LineString per section with
                               clear_ft, paved_ft (gross), driveway flag
  clear_width_runs.geojson     merged runs of near-constant width
  clear_width_faces.csv        per face: n sections, min, p10, median, max,
                               share of face at driveways, share under canopy
Tape measurements in data/field/sidewalk_widths.csv are compared where a
face has one (column tape_ft, diff_ft).

Usage: python3 tools/clear_width.py <area> [<area> ...]
"""
import sys, math, json, pathlib
import numpy as np, pandas as pd, geopandas as gpd
from PIL import Image
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from pyproj import Transformer
from shapely import contains_xy
TO4326 = Transformer.from_crs(26910, 4326, always_xy=True)

ROOT = pathlib.Path(__file__).resolve().parents[1]
FT = 3.28084
STEP = 1.0        # m between cross-sections along the face
OUT_M = 9.0       # m outward (toward the property) from the GIS curb line to sample
IN_M = 6.0        # m inward (toward the road) as well: the GIS curb line can sit inside the sidewalk, so the section spans both ways
SAMPLE = 0.1      # m between samples across the section
DRIVE_M = 4.0     # sections within this of a driveway/crossing are excluded
MIN_VALID = 0.5   # section dropped if fewer than this share of samples are classifiable (canopy/shadow)
SAT_MAX = 0.36    # paved: saturation at or below this ...
VAL_MIN = 0.28    # ... and brightness at or above this (0-1)
Z = 20


class Tiles:
    def __init__(self, folder):
        self.folder = pathlib.Path(folder); self.cache = {}
    def pix(self, lon, lat):
        n = 2 ** Z
        x = (lon + 180) / 360 * n
        y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
        tx, ty = int(x), int(y)
        t = self.cache.get((tx, ty))
        if t is None:
            p = self.folder / str(tx) / f"{ty}.png"
            t = np.asarray(Image.open(p).convert('RGB')) if p.exists() else False
            self.cache[(tx, ty)] = t
        if t is False: return None
        return t[min(255, int((y - ty) * 256)), min(255, int((x - tx) * 256))]


def paved(rgb):
    r, g, b = [c / 255 for c in rgb]
    mx, mn = max(r, g, b), min(r, g, b)
    sat = 0 if mx == 0 else (mx - mn) / mx
    if mx < 0.18: return None            # deep shadow: unknown
    return sat <= SAT_MAX and mx >= VAL_MIN


def run(area):
    out = ROOT / 'data/tile2net' / area
    sw_all = gpd.read_parquet(out / 'polygons.parquet').to_crs(26910)
    sw = sw_all[sw_all.f_type == 'sidewalk']; cw = sw_all[sw_all.f_type == 'crosswalk']
    swtree = STRtree(sw.geometry.values)
    drives = gpd.read_file(ROOT / 'data/gis/osm-ways.geojson').to_crs(26910)
    drives = drives[drives.k.astype(str).str.startswith('service:driveway')]
    excl = list(drives.geometry.values) + list(cw.geometry.values)
    extree = STRtree(excl) if excl else None
    faces = gpd.read_file(ROOT / 'data/campable/faces.geojson').to_crs(26910)
    inner = sw_all.unary_union.envelope.buffer(-20)
    faces = faces[faces.within(inner)]
    twin = {r['id']: r.geometry for _, r in faces.iterrows()}
    tiles = Tiles(ROOT / 'data/tile2net/tiles' / area / str(Z))
    tape = pd.read_csv(ROOT / 'data/field/sidewalk_widths.csv')
    tape['face'] = tape.centerlineid.astype(str) + tape.side
    tape = tape.set_index('face').width_ft.to_dict()

    secs, rows = [], []
    for _, f in faces.iterrows():
        line = f.geometry; L = line.length
        if L < 10: continue
        # which way is "outward": away from the twin face (other side of the street)
        tw = twin.get(f['id'][:-1] + ('L' if f['id'].endswith('R') else 'R'))
        widths, flags = [], []
        for s in np.arange(STEP / 2, L, STEP):
            p = line.interpolate(s); p2 = line.interpolate(min(L, s + 0.5)); p1 = line.interpolate(max(0, s - 0.5))
            dx, dy = p2.x - p1.x, p2.y - p1.y; nrm = math.hypot(dx, dy) or 1
            nx, ny = -dy / nrm, dx / nrm
            if tw is not None and Point(p.x + nx, p.y + ny).distance(tw) < Point(p.x - nx, p.y - ny).distance(tw): nx, ny = -nx, -ny
            sec = LineString([(p.x - nx * IN_M, p.y - ny * IN_M), (p.x + nx * OUT_M, p.y + ny * OUT_M)])
            drive = bool(extree is not None and any(excl[i].distance(p) < DRIVE_M for i in extree.query(p.buffer(DRIVE_M))))
            cand = [sw.geometry.values[i] for i in swtree.query(sec)]
            insw = [g for g in cand if g.intersects(sec)]
            ks = np.arange(-int(IN_M / SAMPLE), int(OUT_M / SAMPLE)) * SAMPLE
            qx, qy = p.x + nx * ks, p.y + ny * ks
            inside_arr = np.zeros(len(ks), bool)
            for g in insw: inside_arr |= contains_xy(g, qx, qy)
            lons, lats = TO4326.transform(qx, qy)
            samples = []
            for inside, lon, lat in zip(inside_arr, lons, lats):
                rgb = tiles.pix(lon, lat)
                samples.append((bool(inside), paved(rgb) if rgb is not None else None))
            valid = [s for s in samples if s[1] is not None]
            if len(valid) < MIN_VALID * len(samples) or not insw:
                clear = np.nan; gross = sum(1 for s in samples if s[0]) * SAMPLE
            else:
                gross = sum(1 for s in samples if s[0]) * SAMPLE
                best = cur = 0
                for inside, pv in samples:
                    if inside and pv: cur += 1; best = max(best, cur)
                    elif pv is None and inside and cur: cur += 1; best = max(best, cur)   # shadow continues a paved run but cannot start one
                    else: cur = 0
                clear = best * SAMPLE
            g1 = gpd.GeoSeries([LineString([line.interpolate(max(0, s - STEP / 2)), line.interpolate(min(L, s + STEP / 2))])], crs=26910).to_crs(4326)[0]
            secs.append(dict(face=f['id'], street=f['street'], side=f['side'], s_m=round(float(s), 1),
                             clear_ft=None if np.isnan(clear) else round(clear * FT, 1), paved_ft=round(gross * FT, 1),
                             driveway=drive, canopy=bool(np.isnan(clear) and gross > 0), geometry=g1))
            if not drive and not np.isnan(clear): widths.append(clear * FT)
            flags.append((drive, np.isnan(clear)))
        n = len(flags)
        w = np.array(widths)
        rows.append(dict(face=f['id'], street=f['street'], side=f['side'], face_len_ft=round(L * FT), n_sections=n,
                         n_measured=len(w), driveway_share=round(sum(1 for d, _ in flags if d) / n, 2),
                         canopy_share=round(sum(1 for d, c in flags if c and not d) / n, 2),
                         clear_min_ft=round(w.min(), 1) if len(w) else None, clear_p10_ft=round(float(np.percentile(w, 10)), 1) if len(w) else None,
                         clear_med_ft=round(float(np.median(w)), 1) if len(w) else None, clear_max_ft=round(w.max(), 1) if len(w) else None,
                         tape_ft=tape.get(f['id'])))
    prof = gpd.GeoDataFrame(secs, crs=4326)
    prof.to_file(out / 'clear_width_profile.geojson', driver='GeoJSON')
    merge_runs(prof, out)
    df = pd.DataFrame(rows); df['diff_ft'] = df.clear_med_ft - df.tape_ft
    return finish(df, out, area, prof)


def band(w):
    return 0 if w < 5 else 1 if w < 6 else 2 if w < 10 else 3


def merge_runs(prof, out, window=11):
    """Smooth each face's profile with a rolling median over `window` sections
    (11 m) and merge adjacent sections that fall in the same width band
    (under 5 ft, 5-6, 6-10, 10 ft and over) into runs; the run carries the
    median width of its sections. Bands rather than feet so a run only breaks
    where the width crosses a threshold that matters under AR 10.2."""
    runs = []
    for fid, g in prof.groupby('face', sort=False):
        g = g.sort_values('s_m').copy()
        g['clear_ft'] = g.clear_ft.astype(float).rolling(window, center=True, min_periods=1).median()
        cur = None
        for _, r in g.iterrows():
            key = ('drive' if r.driveway else ('canopy' if r.clear_ft is None or (isinstance(r.clear_ft, float) and np.isnan(r.clear_ft)) else band(r.clear_ft)))
            if cur and cur['key'] == key:
                cur['geoms'].append(r.geometry); cur['vals'].append(r.clear_ft)
            else:
                if cur: runs.append(cur)
                cur = dict(face=fid, street=r.street, side=r.side, key=key, geoms=[r.geometry], vals=[r.clear_ft])
        if cur: runs.append(cur)
    from shapely.ops import linemerge, unary_union
    rr = []
    for u in runs:
        vals = [v for v in u['vals'] if v is not None and not (isinstance(v, float) and np.isnan(v))]
        rr.append(dict(face=u['face'], street=u['street'], side=u['side'], kind='driveway' if u['key'] == 'drive' else ('canopy' if u['key'] == 'canopy' else 'walk'),
                       clear_ft=round(float(np.median(vals)), 1) if vals else None, len_ft=round(len(u['geoms']) * STEP * FT),
                       geometry=linemerge(unary_union(u['geoms'])) if len(u['geoms']) > 1 else u['geoms'][0]))
    gpd.GeoDataFrame(rr, crs=4326).to_file(out / 'clear_width_runs.geojson', driver='GeoJSON')
    return len(rr)


def finish(df, out, area, prof):
    # Governing width for AR 10.2 is the pinch point. Imagery sees the walk between
    # obstructions; at a street tree the canopy hides the tree well and the walk
    # beside it, so the pinch cannot be read from above. Rule: tape first; otherwise
    # the median clear width between obstructions where the face is essentially tree-free
    # (canopy_share < TREE_SHARE); otherwise no imagery number - tape needed.
    TREE_SHARE = 0.10
    def gov(r):
        if pd.notna(r.tape_ft): return r.tape_ft, 'tape'
        if r.canopy_share < TREE_SHARE and r.n_measured >= 5: return r.clear_med_ft, 'imagery median between obstructions (no street trees)'
        return None, 'tape needed: street trees hide the pinch point'
    g = df.apply(gov, axis=1); df['governing_ft'] = [a for a, _ in g]; df['governing_source'] = [b for _, b in g]
    df.to_csv(out / 'clear_width_faces.csv', index=False)
    print(f"{area}: {len(df)} faces, {len(prof)} sections")
    print(df[df.tape_ft.notna()][['face', 'street', 'side', 'tape_ft', 'clear_min_ft', 'clear_p10_ft', 'clear_med_ft', 'clear_max_ft', 'driveway_share', 'canopy_share']].to_string(index=False))
    print(df[['clear_min_ft', 'clear_p10_ft', 'clear_med_ft', 'clear_max_ft']].describe().round(1).to_string())
    print(df.governing_source.value_counts().to_string())
    return df


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == '--remerge':          # rebuild runs from an existing profile without re-reading imagery
        for a in args[1:]:
            out = ROOT / 'data/tile2net' / a
            n = merge_runs(gpd.read_file(out / 'clear_width_profile.geojson'), out); print(a, n, 'runs')
    else:
        for a in args: run(a)
