#!/usr/bin/env python3
"""Score tile2net sidewalk detections against the City's own sidewalk map.

Reference: Figure 4 of the City of Berkeley 2020 Pedestrian Plan ("Existing
Sidewalk Coverage in Berkeley"), georeferenced and read per block face by
tools/fig4_extract.py into data/field/fig4_face_categories.csv. Its classes:
5ft_or_wider, under_5ft, width_unknown, no_sidewalk, trail, no_data.

Test: for every block face inside the imagery run, does tile2net see a
sidewalk along it, and (where the City gives a width class) is it 5 ft or
wider? A face "has a sidewalk" in the detections when at least COVER of its
length lies within NEAR_M of a tile2net sidewalk polygon. Width is the
length-weighted median skeleton width of those polygons (tile2net_widths.py).

Reported: confusion matrix for presence, accuracy with a 95 % Wilson interval,
sensitivity/specificity for "no sidewalk", Cohen's kappa, and the same for the
width class on faces where both sides give one. A sweep over COVER shows how
sensitive the result is to that choice; the value used is fixed in advance
from the nw area and applied unchanged to the ninth area (held-out).

Usage:
  python3 tools/tile2net_eval.py <outdir> <name>=<polygons.parquet> [<name>=<...> ...]
"""
import sys, json, math, pathlib
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import box
from shapely.ops import unary_union

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from tile2net_widths import width_stats, FT  # noqa: E402

NEAR_M = 5.0      # sidewalk polygon within this of the curb-side face line counts as on that face
COVER = 0.30      # fraction of the face length that must be covered (fixed before the held-out test)
EDGE_M = 20.0     # faces this close to the imagery edge are not scored (partial tiles)
MIN_FACE_M = 25.0 # very short faces (corner stubs) are not scored


def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'), float('nan'))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def kappa(a, b):
    a = np.asarray(a); b = np.asarray(b); n = len(a)
    if n == 0: return float('nan')
    po = (a == b).mean(); cats = set(a) | set(b)
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


def load_polys(path):
    g = gpd.read_parquet(path) if str(path).endswith('.parquet') else gpd.read_file(path)
    g = g.to_crs(26910); sw = g[g.f_type == 'sidewalk'].copy()
    st = [width_stats(p) for p in sw.geometry]
    sw['med_ft'] = [s['med_ft'] if s else np.nan for s in st]
    sw['len_ft'] = [s['len_ft'] if s else np.nan for s in st]
    return g, sw


def score_faces(sw, bounds, faces, fig4, cover=COVER):
    inner = box(*bounds).buffer(-EDGE_M)
    rows = []
    for _, r in faces[faces.within(inner) & (faces.geometry.length >= MIN_FACE_M)].iterrows():
        line = r.geometry
        near = sw[sw.distance(line) < NEAR_M]
        covered = 0.0
        if len(near):
            zone = unary_union(near.geometry.buffer(NEAR_M).tolist())
            covered = line.intersection(zone).length / line.length
        ok = near[near.med_ft.notna()]
        w = float((ok.med_ft * ok.len_ft).sum() / ok.len_ft.sum()) if len(ok) else np.nan
        f4 = fig4.get(r['id'], {})
        rows.append(dict(face=r['id'], street=r['street'], side=r['side'], cat=r['cat'],
                         gis_width_ft=r['width_ft'], model_spots=r['count'],
                         fig4=f4.get('fig4', 'none'), fig4_share=f4.get('fig4_share', np.nan),
                         t2n_cover=round(covered, 2), t2n_width_ft=w,
                         t2n_sidewalk=covered >= cover, face_len_ft=line.length * FT))
    return pd.DataFrame(rows)


def presence_metrics(df):
    d = df[df.fig4.isin(['5ft_or_wider', 'under_5ft', 'width_unknown', 'no_sidewalk'])]
    ref = d.fig4 != 'no_sidewalk'; det = d.t2n_sidewalk
    tp = int((ref & det).sum()); tn = int((~ref & ~det).sum()); fp = int((~ref & det).sum()); fn = int((ref & ~det).sum())
    n = len(d); acc = (tp + tn) / n if n else float('nan')
    return dict(n=n, city_sidewalk_detected=tp, city_none_detected_none=tn,
                city_none_but_detected=fp, city_sidewalk_but_missed=fn,
                accuracy=acc, accuracy_ci95=wilson(tp + tn, n),
                no_sidewalk_sensitivity=tn / (tn + fp) if tn + fp else float('nan'),
                no_sidewalk_specificity=tp / (tp + fn) if tp + fn else float('nan'),
                kappa=kappa(ref.values, det.values))


def segment_metrics(df):
    """Figure 4 draws one line per street, not per side: a red street means at least
    one side lacks a sidewalk. So compare at segment level: City red vs 'tile2net
    finds no sidewalk on at least one side'."""
    d = df[df.fig4.isin(['5ft_or_wider', 'under_5ft', 'width_unknown', 'no_sidewalk'])].copy()
    d['seg'] = d.face.str[:-1]
    seg = d.groupby('seg').agg(red=('fig4', lambda x: bool((x == 'no_sidewalk').any())),
                               missing=('t2n_sidewalk', lambda x: bool((~x).any())))
    ref, det = seg.red, seg.missing; n = len(seg)
    tp = int((ref & det).sum()); tn = int((~ref & ~det).sum()); fp = int((~ref & det).sum()); fn = int((ref & ~det).sum())
    return dict(n_segments=n, city_red=int(ref.sum()), red_detected=tp, red_missed=fn, nonred_false_missing=fp,
                accuracy=(tp + tn) / n if n else float('nan'), accuracy_ci95=wilson(tp + tn, n),
                red_sensitivity=tp / (tp + fn) if tp + fn else float('nan'), kappa=kappa(ref.values, det.values))


def width_metrics(df):
    d = df[df.fig4.isin(['5ft_or_wider', 'under_5ft']) & df.t2n_sidewalk & df.t2n_width_ft.notna()]
    ref = d.fig4 == '5ft_or_wider'; det = d.t2n_width_ft >= 5
    n = len(d); k = int((ref == det).sum())
    return dict(n=n, agree=k, accuracy=k / n if n else float('nan'), accuracy_ci95=wilson(k, n),
                kappa=kappa(ref.values, det.values), city_under5_n=int((~ref).sum()),
                t2n_width_on_city_5plus_median=float(d[ref].t2n_width_ft.median()) if ref.any() else float('nan'))


def main(outdir, runs):
    outdir = pathlib.Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    faces = gpd.read_file(ROOT / 'data/campable/faces.geojson').to_crs(26910)
    fig4 = pd.read_csv(ROOT / 'data/field/fig4_face_categories.csv').set_index('face').to_dict('index')
    report = {'params': dict(NEAR_M=NEAR_M, COVER=COVER, EDGE_M=EDGE_M, MIN_FACE_M=MIN_FACE_M), 'areas': {}}
    frames = []
    for name, path in runs.items():
        g, sw = load_polys(path)
        df = score_faces(sw, g.total_bounds, faces, fig4); df.insert(0, 'area', name); frames.append(df)
        rep = {'presence': presence_metrics(df), 'segment': segment_metrics(df), 'width_class': width_metrics(df),
               'cover_sweep': {str(c): presence_metrics(score_faces(sw, g.total_bounds, faces, fig4, c))['accuracy']
                               for c in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)}}
        report['areas'][name] = rep
        print(f"\n== {name}: {len(df)} faces scored ==")
        print(json.dumps(rep, indent=1, default=float))
    all_df = pd.concat(frames)
    all_df.round(2).to_csv(outdir / 'face_scores.csv', index=False)
    report['all'] = {'presence': presence_metrics(all_df), 'segment': segment_metrics(all_df), 'width_class': width_metrics(all_df)}
    print("\n== all areas ==\n" + json.dumps(report['all'], indent=1, default=float))
    print("\nmodel tent spots on faces the City marks no-sidewalk: "
          f"{int(all_df[all_df.fig4 == 'no_sidewalk'].model_spots.sum())}; "
          f"of those faces tile2net also finds no sidewalk on "
          f"{int((~all_df[all_df.fig4 == 'no_sidewalk'].t2n_sidewalk).sum())} of {int((all_df.fig4 == 'no_sidewalk').sum())}")
    json.dump(report, open(outdir / 'metrics.json', 'w'), indent=1, default=float)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1], dict(a.split('=', 1) for a in sys.argv[2:]))
