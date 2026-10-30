#!/usr/bin/env python3
"""Calibrate the GIS sidewalk width against tape measurements.

The GIS width (right-of-way minus pavement, or curb to OSM building face) is
the whole strip from curb to property line. Tape measurements of the clear
paved walk - tree wells, planting strips and driveways excluded - show the
walk is a fraction of that strip. This script computes that fraction from
every tape in data/field/sidewalk_widths.csv whose face has a GIS width,
writes data/field/gis_calibration.json, and the tent model applies it to
faces that have neither a tape nor an imagery clear width
(width_source becomes "gis-calibrated"). Faces taped at 0 ft (no sidewalk)
are reported but left out of the ratio, since they are a presence question.

The factor is an interim correction and is labelled as such on the map; it
is replaced face by face as the imagery clear-width run and the tape sample
grow. Its spread (sd of the ratio) is the honest error bar.

Usage: python3 tools/calibrate_gis.py
"""
import csv, json, pathlib, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]

# GIS widths as the model computed them before any tape existed, kept here so
# a re-run of the model (which now applies the tape) cannot erase the baseline.
faces = {f['properties']['id']: f['properties'] for f in json.load(open(ROOT / 'data/campable/faces.geojson'))['features']}
base = json.load(open(ROOT / 'data/field/gis_calibration.json'))['points'] if (ROOT / 'data/field/gis_calibration.json').exists() else {}
pts = {}
for r in csv.DictReader(open(ROOT / 'data/field/sidewalk_widths.csv', encoding='utf-8')):
    fid = r['centerlineid'].strip() + r['side'].strip().upper()[0]
    tape = float(r['width_ft'])
    gis = base.get(fid, {}).get('gis_ft')
    if gis is None:
        p = faces.get(fid)
        if not p: continue
        if p['width_source'] == 'measured':
            # recover the GIS number from the note "(GIS estimate X ft)" if present
            import re
            m = re.search(r'GIS estimate (?:was )?([\d.]+) ft', r.get('notes', ''))
            gis = float(m.group(1)) if m else None
        else:
            gis = p['width_ft']
    if gis is None: continue
    pts[fid] = {'street': r['street'], 'tape_ft': tape, 'gis_ft': gis, 'ratio': round(tape / gis, 3) if gis else None, 'date': r['date']}
ratios = [v['ratio'] for v in pts.values() if v['tape_ft'] > 0 and v['ratio'] is not None]
cal = {
    'method': 'clear walk width = GIS curb-to-property width x factor; factor = mean of tape/GIS over taped faces with a sidewalk',
    'factor': round(statistics.mean(ratios), 3) if ratios else None,
    'factor_sd': round(statistics.stdev(ratios), 3) if len(ratios) > 1 else None,
    'n': len(ratios), 'n_no_sidewalk': sum(1 for v in pts.values() if v['tape_ft'] == 0),
    'points': pts,
}
json.dump(cal, open(ROOT / 'data/field/gis_calibration.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in cal.items() if k != 'points'}, indent=1))
for k, v in pts.items(): print(k, v)
