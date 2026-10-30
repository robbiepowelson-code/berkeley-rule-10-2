#!/usr/bin/env python3
"""Read the City's sidewalk-coverage map (Pedestrian Plan 2020, Figure 4) per block face.

The City does not publish the GIS layer behind Figure 4 ("Existing Sidewalk
Coverage in Berkeley"); neither the open-data portal nor gis.cityofberkeley.info
carries a sidewalk inventory. So the figure itself is used as the reference:

1. Georeference the figure. Five BART station icons give tie points for an
   affine fit; the fit is refined by matching the figure's street grid to the
   city street centerlines (chamfer distance), then refined again over the
   West Berkeley pilot area with a small shift/scale/rotation. Median offset
   between our centerlines and the figure's street lines is 1 px (~8 m) in
   the pilot area. The affine is stored in data/reference/figure4_affine.json.
2. Classify pixels by colour into the legend classes: red = no sidewalk,
   orange = under 5 ft, blue = presence known/width unknown, grey = 5 ft or
   wider, green = trail/stairway, dark grey = no data (also street labels).
3. For each block face in data/campable/faces.geojson, sample points every
   8 m along the face, look at a 5x5 pixel window, and take the majority
   class; coloured classes outrank grey because they are drawn over the
   street line. `fig4_share` is the share of samples agreeing with the result.

Limits to state when relying on this: the figure draws one line per street,
not per side, so both faces of a segment get the same class; the figure's
data date is not stated (the Plan notes sidewalks added around Gilman St in
summer 2019); 8 m pixels can blur the class at block ends and where streets
are close together. It is the City's own characterisation, which is why it
is used as the reference, but it is a map, not the dataset.

Usage: python3 tools/fig4_extract.py   (writes data/field/fig4_face_categories.csv)
"""
import json, math, collections, csv, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAMES = {1: 'no_sidewalk', 2: 'under_5ft', 3: 'width_unknown', 4: 'trail', 5: 'no_data', 6: '5ft_or_wider', 0: 'none'}


def classify(im):
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    red = (r > 190) & (g < 80) & (b < 80)
    orange = (r > 220) & (g > 130) & (g < 200) & (b < 60)
    blue = (b > 220) & (r < 160) & (g > 150) & (g < 210)
    green = (g > 190) & (r < 120) & (b < 60)
    black = (r < 100) & (g < 100) & (b < 100) & (abs(r - g) < 12) & (abs(g - b) < 12)
    gray = (abs(r - g) < 8) & (abs(g - b) < 8) & (r >= 165) & (r <= 190)
    return np.select([red, orange, blue, green, black, gray], [1, 2, 3, 4, 5, 6], 0).astype(np.uint8)


def main():
    im = np.array(Image.open(ROOT / 'data/reference/pedestrian-plan-2020-figure4.png').convert('RGB')).astype(int)
    H, W, _ = im.shape
    cls = classify(im)
    pn = json.load(open(ROOT / 'data/reference/figure4_affine.json'))['pilot_area']
    fc = json.load(open(ROOT / 'data/campable/faces.geojson'))
    rows = []
    for f in fc['features']:
        pr = f['properties']; g = f['geometry']
        cs = g['coordinates'] if g['type'] == 'LineString' else sum(g['coordinates'], [])
        pts = []
        for (x1, y1), (x2, y2) in zip(cs, cs[1:]):
            n = max(2, int(math.hypot((x2 - x1) * 87860, (y2 - y1) * 110540) / 8))
            for t in np.linspace(0, 1, n, endpoint=False): pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
        votes = collections.Counter()
        for lon, lat in pts:
            px = int(round(pn[0] * lon + pn[1] * lat + pn[2])); py = int(round(pn[3] * lon + pn[4] * lat + pn[5]))
            if not (2 <= px < W - 2 and 2 <= py < H - 2): continue
            win = cls[py - 2:py + 3, px - 2:px + 3]
            c = collections.Counter(win[win > 0].tolist())
            if not c: votes[0] += 1; continue
            col = {k: v for k, v in c.items() if k in (1, 2, 3, 4, 5)}
            if col and max(col.values()) >= 3: votes[max(col, key=col.get)] += 1
            else: votes[max(c, key=c.get)] += 1
        tot = sum(votes.values()) or 1
        real = {k: v for k, v in votes.items() if k not in (0, 5)}
        if real: k = max(real, key=real.get); conf = real[k] / tot
        else: k = max(votes, key=votes.get) if votes else 0; conf = votes[k] / tot if votes else 0
        rows.append(dict(face=pr['id'], street=pr['street'], side=pr['side'], cat=pr['cat'], zone=pr['zone'],
                         gis_width_ft=pr['width_ft'], gis_source=pr['width_source'], model_spots=pr['count'],
                         fig4=NAMES[k], fig4_share=round(conf, 2), fig4_red_share=round(votes[1] / tot, 2), n_samples=tot))
    out = ROOT / 'data/field/fig4_face_categories.csv'
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(len(rows), 'faces ->', out)
    print(collections.Counter(r['fig4'] for r in rows))


if __name__ == '__main__':
    main()
