# How sidewalk presence and width were established, and how wrong they can be

Prepared 30 October 2026 for the "Where Rule 10.2 Applies" map
(github.com/robbiepowelson-code/berkeley-rule-10-2). Every number below can be
regenerated from the files in this repository with the commands listed at the
end. Nothing here is a legal conclusion.

## 1. The question

Berkeley Administrative Regulation 10.2 permits personal belongings on
sidewalks in commercial and manufacturing districts, subject to keeping a path
of travel clear (6 ft where the sidewalk is under 14 ft wide, 10 ft where it is
14 ft or wider). The map asks: on which block faces in the West Berkeley pilot
corridor (Gilman St to Ashby Ave) does a standard two-person tent (5 x 7 ft)
fit under those terms? Two facts about each block face decide the answer:

1. **Is there a sidewalk at all?** (presence)
2. **How wide is it?** (width)

## 2. The three sources, and what each can and cannot see

### 2a. City GIS: right-of-way minus pavement (the model's original source)

The City's street centerline layer carries a curb-to-curb pavement width
(`PAV_WIDTH_RD`), and the right-of-way layer gives the public strip's total
width. The difference, split between the two sides, was the model's estimate of
sidewalk width. **This method cannot detect whether a sidewalk exists.** The
strip between curb and property line may be concrete sidewalk, asphalt
parking apron, dirt, or grass; the arithmetic is identical. Tested against the
City's own sidewalk-coverage map (2c), the GIS "width" on faces the City marks
*no sidewalk* averages 14.2 ft; on faces the City marks *5 ft or wider* it
averages 14.0 ft. The two populations are indistinguishable. The split between
the two sides is also unreliable (e.g. Grayson St: 3.2 ft one side, 17.9 ft the
other; aerial imagery shows about 10 ft on both), because the centerline is not
always centred in the right-of-way.

*Consequence:* 247 of the model's 1,081 tent locations (23 %) were placed on
block faces the City's map marks as having no sidewalk.

### 2b. 2023 aerial imagery read by a published detector (tile2net)

tile2net (Hosseini, Sevtsuk, Miranda, Cesar & Silva, *Computers, Environment
and Urban Systems* 101, 2023; code BSD-3 at github.com/VIDA-NYU/tile2net) is a
peer-reviewed semantic-segmentation model that outlines sidewalks, roads and
crosswalks in sub-metre aerial imagery. Reported sidewalk-class accuracy on its
own test set: IoU 82.7 %, precision 0.90, recall 0.92. It was trained on
Cambridge MA, Washington DC and New York; the authors recommend retraining for
new regions, and note tree canopy and heavy shadow as weak spots.

We ran it, unmodified, on the Alameda County 2023 orthophoto (Pictometry /
EagleView WMTS, zoom 20, ~0.12 m per pixel) over two areas:

| area | extent | tiles | sidewalk polygons | block faces scored |
|---|---|---|---|---|
| `nw` | Second St to San Pablo Ave, Gilman St to Camelia St | 1,496 | 595 | 271 |
| `ninth` | Seventh to Tenth St, Carleton St to Potter St | 725 | 298 | 72 |

Width was then measured from each polygon with the method of the open
*sidewalkwidths* projects (NYC, Boston, Toronto, Berlin): rasterise at 10 cm,
take the distance transform, read twice the distance along the skeleton, report
the median along the face (`tools/tile2net_widths.py`).

**What it sees:** paved strips beside a road, and their width.
**What it cannot see:** the curb. A concrete sidewalk raised 6 inches above the
road and an asphalt parking apron flush with the road look the same from above.

### 2c. The City's own sidewalk-coverage map (Pedestrian Plan 2020, Figure 4)

The City publishes no sidewalk inventory layer: neither data.cityofberkeley.info
(65 datasets, none for sidewalks) nor gis.cityofberkeley.info (checked every
public service; it has curb ramps and crosswalks but no sidewalk layer). The
City's only published characterisation is Figure 4 of the 2020 Pedestrian Plan,
"Existing Sidewalk Coverage in Berkeley", with legend classes *5 ft or wider*,
*under 5 ft*, *presence known / width unknown*, *no sidewalk*, *no data*,
*trail*. The Plan does not state the data's source or date; it does say the
City added sidewalks around Gilman St in summer 2019, so the figure's data
predates that.

We georeferenced the figure (`tools/fig4_extract.py`): an affine fit from the
five BART station icons, refined by matching the figure's street grid to the
City centerlines, then refined again over the pilot area. Residual: median 1
pixel (about 8 m) between our centerlines and the figure's street lines. Each
legend class was read along every block face by colour (majority of samples
every 8 m; `fig4_share` records the agreement). Result for the pilot corridor's
640 commercial/manufacturing faces: 390 *5 ft or wider*, 114 *width unknown*,
100 *no sidewalk*, 36 no data or trail.

**What it sees:** the City's own assessment of presence and a coarse width class.
**What it cannot see:** which side. The figure draws one line per street. A red
street means at least one side lacks a sidewalk, not necessarily both. And it is
at least seven years old.

### 2d. Street View / field check

Google Street View at the exact coordinates, with imagery dates, was used to
look at nine of the City's *no sidewalk* faces, chosen because they carry the
model's tent locations (`data/field/streetview_audit_2026-10-30.csv`).
This is the only source that sees the curb directly. It is a spot check, not a
survey; the volunteer tape-measure protocol replaces it face by face.

## 3. Testing the imagery against the City's map

`tools/tile2net_eval.py` scores every block face inside an imagery run. A face
"has a sidewalk" in the imagery when at least 30 % of its length lies within
5 m of a detected sidewalk polygon (threshold fixed on the `nw` area before the
`ninth` area was scored; a sweep from 10 % to 60 % moves the result by under 3
points). Width class is *5 ft or wider* when the median detected width is
5 ft or more.

| test | n | agreement | 95 % CI (Wilson) | Cohen's κ |
|---|---|---|---|---|
| **Width class** (5 ft+ vs under 5 ft), faces where both sources give one | 252 | 251 (99.6 %) | 97.8 – 99.9 % | n/a (one under-5 face) |
| Presence, per face, `nw` | 271 | 74.9 % | 69.4 – 79.7 % | 0.14 |
| Presence, per face, `ninth` (held out) | 72 | 98.6 % | 92.5 – 99.8 % | — (no red faces) |
| Presence, per street segment (at least one side missing), `nw` | 145 | 74.5 % | 66.8 – 80.9 % | 0.19 |
| Presence, per face, both areas | 343 | 79.9 % | 75.3 – 83.8 % | 0.16 |

Breaking the presence disagreement down:

- Where the City says *sidewalk*, the imagery agrees 263 of 274 times (96 %).
- Where the City says *no sidewalk* (69 faces, all in `nw`), the imagery finds
  a sidewalk on 58. Sensitivity to "no sidewalk" is 16 % per face, 21 % per
  segment.

So on its own the imagery is a poor detector of *absence*. The Street View
check shows why, and shows that the fault is shared:

| face | City map | imagery | Street View (date) |
|---|---|---|---|
| Harrison St 1211 north side | no sidewalk | sidewalk, 8.6 ft | **no sidewalk** — asphalt apron, nose-in parking, no curb (Mar 2025) |
| Harrison St 1211 south side | no sidewalk | sidewalk, 8.5 ft | sidewalk with curb (Mar 2025; also Jan 2018) |
| Sixth St 6736, both sides | no sidewalk | sidewalk, 8.4–8.9 ft | sidewalk with curb, both sides (Mar 2025) |
| Sixth St 6737 west side | no sidewalk | sidewalk, 8.6 ft | sidewalk with planted strip (Mar 2025) |
| Ninth St 6800 / 6805 | no sidewalk | sidewalk, 7.9 / 8.6 ft | narrow sidewalk, red curb (2024–25) |
| Page St 413 north side | no sidewalk | **no sidewalk** (7 % cover) | **dirt shoulder** (Feb 2019) |
| Eastshore Hwy 1465 | no sidewalk | sidewalk, 9.4 ft (edge of run) | **grass embankment** at I-80 fence (Mar 2025) |

Two distinct errors are mixed together in the 58 disagreements:

1. **The imagery calls a parking apron a sidewalk** (Harrison north side,
   Eastshore). From above, flush pavement beside a road is a sidewalk. The
   width profile of these false detections (10th/50th/90th percentile 5.8 / 8.6
   / 12.6 ft) is the same as for real sidewalks (6.2 / 9.2 / 12.1 ft), so no
   setting of the detector separates them.
2. **The City's map is out of date or one-sided** (Sixth, Ninth, Harrison
   south). Seven of the nine audited "no sidewalk" faces have a curbed sidewalk
   today; one of those has had it since at least January 2018. The Plan's own
   text (sidewalks added around Gilman in 2019) explains some of this.

We also tested the City's curb-ramp layer (2,127 ramps in the pilot area) as an
independent signal of curbs: it does not discriminate (ramps are present at the
corners of 87 % of *no sidewalk* faces and 90 % of *5 ft or wider* faces),
because ramps serve the crossing of the cross street. Rejected.

## 4. The methodology adopted

Because no single source sees both presence and width, the map now records all
of them per block face (`tools/inject_sources.py` writes them into the map;
every popup shows them) and applies this rule:

> A tent location is **counted** only where every available source agrees a
> sidewalk exists on that face: the City's map shows a sidewalk on the street,
> the 2023 imagery (where run) finds one along the face, and no Street View or
> field check contradicts it. Width comes from the imagery where it has been
> run, otherwise from the GIS estimate, and is overridden by a tape measurement
> wherever one exists. Faces where the sources disagree, or where the City's
> map shows no sidewalk and the side has not been checked, are drawn red-dashed
> and their tent boxes amber-dotted: **not counted until verified on the ground.**

Applied to the 1,038 tent locations in commercial and manufacturing districts:

| status | faces | tent locations |
|---|---|---|
| sidewalk — City map and 2023 imagery agree | 119 | 336 |
| sidewalk — City map; imagery not yet run on this block | 380 | 436 |
| sidewalk now — Street View; City map outdated | 6 | 153 |
| **counted** | **505** | **925** |
| City map: no sidewalk, side not verified | 91 | 12 |
| City map: no data (I-80 ramps, Eastshore, alleys) | 36 | 18 |
| imagery finds no sidewalk — unverified | 5 | 1 |
| no sidewalk — Street View confirmed (Page St, Eastshore Hwy) | 3 | 82 |
| **not counted pending field check** | **135** | **113** |

This is what "meeting the City's map" means in practice: the map defers to the
City's characterisation wherever it is the only source, overrides it only where
later imagery and a dated street-level photograph both show otherwise, and
flags everything in between for the tape measure.

## 5. Margin of error, stated honestly

- **Width.** Where a sidewalk exists, the imagery's width class agrees with the
  City's in 251 of 252 faces (99.6 %, 95 % CI 97.8–99.9 %). The City gives a
  class, not a number, so the numeric error of the imagery width is not yet
  measured. The one tape measurement so far (Camelia St north side, 12.0 ft)
  reads 8.9 ft in the imagery: the detector outlines the paved walk and leaves
  out the planting strip and curb. Until the volunteer tape sample (target
  n ≥ 30 faces) is in, imagery widths should be presented as **paved-walk
  width, likely low by 0–3 ft where there is a planting strip**, and the
  tent-fit test should be run both ways.
- **Presence.** No source is reliable alone: imagery sensitivity to "no
  sidewalk" is 16–21 %; the City's map is per street and at least seven years
  old (7 of 9 audited red faces have sidewalks today). The adopted rule
  therefore makes no presence claim without agreement, and the 113 uncounted
  locations are the error budget made explicit: the true count lies between
  925 and 1,038 for these sources, and field verification closes the gap.
- **Registration of the City's map:** ~1 pixel (8 m) median; classes can blur
  within a block of a corner or where streets are under 16 m apart. The
  `fig4_share` column records per-face agreement (median 1.00; 90 % of faces
  ≥ 0.75).
- **The 5 x 7 ft fit itself** depends on the clearance rules in
  `tools/ar102_rules.json`, two of which (18 in curb setback, corner radius)
  are our assumptions, marked as such; the count should be reported with and
  without them.

## 6. What this does not establish

- It does not say a tent is lawful, safe or available at any counted location;
  it says the sidewalk exists and is wide enough under AR 10.2's stated
  distances as of the 2023 imagery.
- It has not been field-measured except at one face. The volunteer protocol
  (tape at the narrowest point and mid-block, photo of the tape, obstacles
  noted, one-paragraph declaration) is what turns these numbers into evidence
  of present conditions.
- The authoritative dataset behind Figure 4 should be requested from the City
  under the Public Records Act; a per-side layer with a data date would replace
  section 2c outright.

## 7. Reproducing every number

```
python3 tools/fig4_extract.py                      # City map -> data/field/fig4_face_categories.csv
bash tools/tile2net/fetch_eval_tiles.sh            # 2023 aerial tiles (run on a machine that can reach the county WMTS)
bash tools/tile2net/run_area.sh nw    "37.8750, -122.3070, 37.8840, -122.2920"
bash tools/tile2net/run_area.sh ninth "37.8515, -122.2975, 37.8590, -122.2895"
python3 tools/tile2net_eval.py data/tile2net/eval nw=data/tile2net/nw/polygons.parquet ninth=data/tile2net/ninth/polygons.parquet
python3 tools/inject_sources.py                    # write the evidence table into index.html
```

Model weights: `satellite_2021.pth` md5 6718e1b06c57cb884dbe93e7d71f446a,
`hrnetv2_w48_imagenet_pretrained.pth` md5 1ce00d88068e5f483de64ea48693bc9a
(figshare DOIs 10.6084/m9.figshare.33315570 and .33315558). Inference ran on CPU
via `tools/tile2net/run_cpu.py`, which stubs CUDA calls and changes nothing in
the model.
