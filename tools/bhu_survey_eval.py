#!/usr/bin/env python3
"""Score every width source against the Berkeley Homeless Union tape survey.

Input: data/field/bhu_sidewalk_measurements_2026-09.tsv, the BHU volunteer
survey (one row per measured block face: street, cross streets, a Google
Maps pin at mid-block, clear path of travel, total sidewalk width, space
remaining). Each row is matched to the nearest block face in
data/campable/faces.geojson (the pin is on the street, so the nearest face
is taken; when the pin is within 3 m of equidistant between the two sides
the row is flagged side-ambiguous and both faces are kept).

Compared, per matched face: raw GIS strip width, GIS x calibration factor,
tile2net polygon width, imagery clear-walk median (where an imagery run
covers the face). Reports mean error, mean absolute error, RMSE and the
share within 2 ft for each source, overall and for West Berkeley only.

Usage: python3 tools/bhu_survey_eval.py
"""
import re, json, csv, pathlib
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point

ROOT = pathlib.Path(__file__).resolve().parents[1]


def parse_ft(s):
    s = str(s).strip().replace('’', "'").replace('"', '')
    if not s: return np.nan
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|')?\s*(?:(\d+)\s*(?:inches|inch|in|\")?)?\s*$", s)
    if m:
        ft = float(m.group(1)); inch = float(m.group(2)) if m.group(2) else 0
        return ft + inch / 12
    return np.nan


def parse_latlon(s):
    s = str(s).replace('°', ' ').replace('′', "'").replace('″', '"')
    dms = re.findall(r"(\d+)\s*[° ]\s*(\d+)'\s*([\d.]+)\"?\s*([NSEW])", s)
    if len(dms) == 2:
        out = []
        for d, m, sec, h in dms:
            v = float(d) + float(m) / 60 + float(sec) / 3600
            out.append(-v if h in 'SW' else v)
        return out[0], out[1]
    nums = re.findall(r"-?\d+\.\d+", s)
    if len(nums) >= 2:
        lat, lon = float(nums[0]), float(nums[1])
        if lon > 0: lon = -lon
        return lat, lon
    return None, None


def main():
    # two files: the August form export (99 rows, with side and obstacle notes) and the September
    # 'clean' sample (52 rows, mostly West Berkeley). Rows are deduplicated on street + block + pin.
    rows = []
    for fn, tag in (('bhu_sidewalk_survey_form_2026-08.tsv', 'form 2026-08'), ('bhu_sidewalk_measurements_2026-09.tsv', 'clean 2026-09')):
        for r in csv.DictReader(open(ROOT / 'data/field' / fn, encoding='utf-8'), delimiter='\t'):
            vals = list(r.values())
            if not any(vals): continue
            k = list(r.keys())
            g = lambda pat: next((r[c] for c in k if pat in c), '')
            rows.append(dict(street=g('Name of street').strip(), block=g('Cross streets').strip(), side_txt=g('Side of street').strip(),
                             gps=g('GPS'), clear=g('Clear path'), total=g('Total width'), remaining=g('Available space'),
                             surface=g('suitable'), obstacles=g('Obstacles'), src=tag))
    seen = set(); dedup = []
    for r in rows:
        key = (r['street'].lower(), r['block'].lower(), r['gps'].strip()[:18])
        if key in seen: continue
        seen.add(key); dedup.append(r)
    rows = dedup
    faces = pd.concat([gpd.read_file(ROOT / 'data/campable/faces.geojson').assign(area='pilot'),
                       gpd.read_file(ROOT / 'data/campable_south/faces.geojson').assign(area='south')]).to_crs(26910).reset_index(drop=True)
    cl = gpd.read_file(ROOT / 'data/gis/centerlines.geojson').to_crs(26910)
    cal = json.load(open(ROOT / 'data/field/gis_calibration.json'))['factor']
    # GIS baseline widths before any tape: faces.geojson now carries calibrated/measured widths, so recover raw GIS
    raw = {}
    for _, f in faces.iterrows():
        w, src = f['width_ft'], f['width_source']
        raw[f['id']] = f['gis_width_ft'] if 'gis_width_ft' in f and pd.notna(f['gis_width_ft']) else (w / cal if src == 'gis-calibrated' else (w if src in ('gis', 'default', 'osm-building') else np.nan))
    t2n = {}
    for a in ('nw', 'ninth', 'south', 'corridor'):   # corridor last: it pools the others' tiles and governs shared faces
        p = ROOT / 'data/tile2net' / a / 'clear_width_faces.csv'
        if p.exists():
            for _, r in pd.read_csv(p).iterrows():
                if r.face not in t2n or pd.notna(r.governing_ft): t2n[r.face] = r
        p = ROOT / 'data/tile2net' / a / 'face_compare.csv'
        if p.exists():
            for _, r in pd.read_csv(p).iterrows(): t2n.setdefault(r.face, pd.Series(dtype=object)); t2n[r.face] = t2n[r.face].copy(); t2n[r.face]['poly_ft'] = r.tile2net_width_ft
    out = []
    for r in rows:
        lat, lon = parse_latlon(r['gps'])
        if lat is None: continue
        pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(26910)[0]
        faces['d'] = faces.distance(pt)
        near = faces.nsmallest(2, 'd')
        f0 = near.iloc[0]; f1 = near.iloc[1]
        ambiguous = f1['id'][:-1] == f0['id'][:-1] and abs(f1.d - f0.d) < 3
        total = parse_ft(r['total']); clear = parse_ft(r['clear'])
        for f in ([f0, f1] if ambiguous else [f0]):
            fid = f['id']; tr = t2n.get(fid)
            out.append(dict(street=r['street'], block=r['block'], side_txt=r['side_txt'], obstacles=r['obstacles'], surface=r['surface'], survey=r['src'],
                            lat=lat, lon=lon, face=fid, face_street=f['street'], side=f['side'], area=f['area'],
                            dist_m=round(f.d, 1), side_ambiguous=ambiguous, zone_cat=f['cat'],
                            bhu_total_ft=total, bhu_clear_path_ft=clear,
                            gis_raw_ft=raw.get(fid), gis_cal_ft=raw.get(fid) * cal if raw.get(fid) == raw.get(fid) else np.nan,
                            t2n_poly_ft=(tr.get('poly_ft') if tr is not None else np.nan),
                            t2n_clear_med_ft=(tr.get('clear_med_ft') if tr is not None else np.nan),
                            t2n_governing_ft=(tr.get('governing_ft') if tr is not None else np.nan),
                            model_width_ft=f['width_ft'], model_source=f['width_source']))
    df = pd.DataFrame(out)
    df.to_csv(ROOT / 'data/field/bhu_survey_matched.csv', index=False)
    # strip widths the model can use: BHU 'total width' is curb to property line (it tracks the GIS strip
    # and the tile2net polygon, not the clear walk). One row per matched face within 50 m of the pin.
    sw = df[(df.dist_m < 50) & df.bhu_total_ft.notna()].copy()
    sw = sw.groupby('face').agg(strip_ft=('bhu_total_ft', 'median'), street=('street', 'first'), block=('block', 'first'),
                                n=('bhu_total_ft', 'size'), side_ambiguous=('side_ambiguous', 'any')).reset_index()
    sw['source'] = 'BHU volunteer tape survey, Sept 2026 (total width, curb to property line)'
    sw.round(2).to_csv(ROOT / 'data/field/strip_widths.csv', index=False)
    print(len(sw), 'faces with a BHU strip width -> data/field/strip_widths.csv')
    df = df[df.dist_m < 50]            # pins more than 50 m from any face are outside both areas
    west = df[df.area == 'pilot']; south = df[df.area == 'south']

    def stats(d, col):
        e = (d[col] - d.bhu_total_ft).dropna()
        if not len(e): return dict(n=0)
        return dict(n=int(len(e)), mean_err=round(e.mean(), 2), mae=round(e.abs().mean(), 2), rmse=round(float(np.sqrt((e ** 2).mean())), 2),
                    within_2ft=round(float((e.abs() <= 2).mean()), 2), within_1ft=round(float((e.abs() <= 1).mean()), 2))
    report = {}
    for name, d in (('all', df), ('west_berkeley', west), ('west_com_man', west[west.zone_cat.isin(['com', 'man'])]), ('south_berkeley', south)):
        report[name] = {c: stats(d, c) for c in ('gis_raw_ft', 'gis_cal_ft', 't2n_poly_ft', 't2n_clear_med_ft', 'model_width_ft')}
        report[name]['bhu_total_median'] = float(d.bhu_total_ft.median()); report[name]['rows'] = int(len(d))
    json.dump(report, open(ROOT / 'data/field/bhu_survey_metrics.json', 'w'), indent=1)
    print(json.dumps(report, indent=1))
    print(df[['area', 'street', 'block', 'side_txt', 'face', 'dist_m', 'bhu_total_ft', 'gis_raw_ft', 't2n_poly_ft', 't2n_clear_med_ft', 'obstacles']].round(1).to_string(index=False, max_colwidth=28))


if __name__ == '__main__':
    main()
