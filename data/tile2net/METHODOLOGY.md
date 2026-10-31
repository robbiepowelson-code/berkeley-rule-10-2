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

Applied to the 1,038 tent locations in commercial and manufacturing districts (before the width re-run in 4b):

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

## 4b. Width along the block, not per block: the clear-walk profile

A tape measurement at 1409 Fourth St (east side, face 6649L) on 30 October
2026 read **4 ft** of clear concrete walk. The GIS estimate for that face was
8.0 ft and the tile2net polygon 10.4 ft. The aerial shows why: the polygon
spans curb to property line and so includes the row of tree wells; the usable
walk is the strip between the tree wells and the fence. Two consequences
were built in (`tools/clear_width.py`):

1. **Width is now read every metre along each face**, on a cross-section
   perpendicular to the curb line, as the longest contiguous run of paved
   pixels (low colour saturation, not dark) inside the detected sidewalk
   polygon. Planting strips, tree wells, dirt and parked cars break the run;
   sections within 4 m of an OSM driveway or a detected crosswalk are
   excluded as driveway aprons. Adjacent sections are smoothed with a 5 m
   rolling median and merged into runs, drawn on the map as the "Clear walk
   width" layer so the width is seen to change along the block.
2. **The governing width is the pinch point, and the aerial cannot see it
   under a tree.** At a street tree the canopy hides both the tree well and
   the walk beside it. So the rule is: a tape measurement governs; otherwise,
   on faces with essentially no canopy (under 10 % of sections hidden), the
   median clear width between obstructions from the aerial; otherwise no
   imagery number, and the face is flagged *tape needed: street trees hide
   the pinch point*. In the two imagery areas this gives 151 faces an
   imagery width (median 6.0 ft in `nw`, 7.1 ft in `ninth`) and flags 213 for
   tape. The tent model takes widths in the order tape > reviewer >
   imagery > OSM building face > GIS.

Calibration so far (n = 2): Fourth St 6649L tape 4.0 ft vs imagery
between-obstruction median 7.5 ft (the 4 ft is at the tree wells, which the
imagery cannot read — hence the rule above); Camelia St 1084R tape 12.0 ft vs
imagery 7.5 ft (the detector outlines less than the tape covered; that face
has 34 % canopy). Neither is a width error of the method as adopted, because
both faces are governed by their tape values, but they show the two ways the
aerial can be wrong and why the n ≥ 30 tape sample is still required before
any imagery width is presented as a measurement rather than a screen.

Effect on the count: re-running the model with the imagery widths and the
Fourth St tape moved the pilot total from 1,081 to **991** tent locations
(Ninth St 227 → 166, Carleton 159 → 144, Gilman 47 → 39, San Pablo 91 → 85).

## 4c. Calibrating the GIS width with tape, corridor-wide

By 30 October 2026 five block faces had been taped for clear walk width
(tree wells, planting strips and driveways subtracted) and three more
observed to have no sidewalk at all (`data/field/sidewalk_widths.csv`):

| face | street | GIS strip (ft) | clear walk (ft) | ratio |
|---|---|---|---|---|
| 1084R | Camelia St, north | 11.8 | 12.0 | 1.02 |
| 6649L | Fourth St, east (1409) | 8.0 | 4.0 | 0.50 |
| 551L | Cedar St, north, First–Second | 9.4 | 6.0 | 0.64 |
| 357L | Delaware St, north, Sixth–Seventh | 13.9 | 6.0 | 0.43 |
| 357R | Delaware St, south, Sixth–Seventh | 16.4 | 6.0 | 0.37 |
| 551R | Cedar St, south, First–Second | 15.5 | 0 — all landscaped | — |
| 1465L | Eastshore Hwy, I-80 side | 36.6 | 0 — grass embankment (Street View) | — |
| 1211L | Harrison St, north | 9.1 | 0 — asphalt apron, no curb (Street View) | — |

The GIS strip is curb to property line; the walk is what is left after the
landscaped and furnishing zone. Across the taped faces the walk is on average
**0.59 × the GIS strip (sd 0.26, n = 5)**. `tools/calibrate_gis.py` computes
this factor from the tape file each time it is run, and the tent model now
applies it to every face that has neither a tape nor an imagery clear width
(`width_source = gis-calibrated`, stated in the popup as interim). Faces
taped or observed at 0 ft are treated as no sidewalk.

The factor is deliberately crude — its spread is as large as its value is
precise — and it exists to stop the raw GIS strip being presented as a
sidewalk width anywhere in the corridor while the imagery run and the tape
sample catch up. Its effect is large because the GIS strip was wrong by a
lot: the pilot total fell from 991 to **90 locations on 8 block faces**:

| face | street | width (ft) | source | locations |
|---|---|---|---|---|
| 5671R | San Pablo Ave | 22.3 | GIS × 0.59 | 20 |
| 1409L | Eastshore Hwy | 21.7 | GIS × 0.59 | 20 |
| 3652L / 3652R | University Ave overpass | 23.0 / 23.3 | GIS × 0.59 | 8 / 6 |
| 433L | Gilman St | 20.3 | 2023 imagery | 13 |
| 3635L | Ashby Ave | 23.4 | GIS × 0.59 | 11 |
| 180R | I-80 east off-ramp at University | 21.0 | GIS × 0.59 | 10 |
| 6770R | Seventh St | 19.6 | GIS × 0.59 | 2 |

Every one of these is an unusually wide strip (a freeway frontage, an
overpass, an arterial), which is exactly where the "half the strip" rule is
least likely to hold; `data/field/candidates_2026-10-30.csv` lists them with
Street View links as the field-verification list. This is consistent with the
field survey's finding that the corridor has fewer than fifteen usable
locations, and it is the list to take a tape to.

## 4d. Testing against the Berkeley Homeless Union survey (52 measurements)

On 21 September 2026 the Berkeley Homeless Union sent its volunteer tape
survey (`data/field/bhu_sidewalk_measurements_2026-09.tsv`): 52 block faces
with a mid-block map pin, "clear path of travel", "total width of sidewalk"
and "available space remaining". 43 rows fall in West Berkeley, 9 in South
Berkeley outside the pilot. Each pin was matched to the nearest block face
(`tools/bhu_survey_eval.py`; pins within 3 m of equidistant between the two
sides are flagged side-ambiguous).

**The two surveys measure different things.** The BHU "total width" tracks
the curb-to-property strip — it agrees with the raw GIS strip (mean error
+1.5 ft) and with the tile2net polygon (−1.3 ft) — while the October tapes
in `sidewalk_widths.csv` are the clear paved walk with tree wells and
landscaping excluded (about 0.59 × the strip). Camelia St's 12 ft of
September is a strip figure. Both are legitimate; the model needs the clear
walk, because a tent cannot stand in a tree well, so the BHU totals enter it
as **measured strip widths** (`data/field/strip_widths.csv`, 41 faces),
replacing the GIS estimate there, with the clear-walk factor applied on top
(`width_source = strip-tape-calibrated`).

How well each estimate of the strip matches the BHU tapes, West Berkeley:

| estimate | n | mean error | mean abs. error | within 2 ft |
|---|---|---|---|---|
| tile2net polygon width (2023 aerial) | 21 | −1.3 ft | 3.5 ft | 33 % |
| raw GIS strip (right-of-way − pavement) | 38 | +1.5 ft | 4.3 ft | 24 % |

Neither is good enough on its own at the block-face level — a ±4 ft typical
error on a 10 ft strip — which is the quantitative case for measuring rather
than estimating, and for the per-metre clear-walk profile. The profile's
median on tree-lined faces (Eighth St) read 1–6 ft against BHU totals of
10 ft: those faces are the ones the method already flags "tape needed",
and the comparison confirms the flag is right. The run also exposed a defect
in the first version of `clear_width.py`: it started each cross-section at
the GIS curb line, which on Eighth St sits several feet inside the sidewalk;
the section now spans 6 m on the road side as well, so it finds the walk
wherever the curb actually is.

**South Berkeley as a calibration area.** The full August form export has
99 rows, 76 of them on residential streets between Oregon and Blake, Shattuck
and Sacramento, each with the side of the street and obstacle notes. The
model's inputs were extended to that box (City centerlines, transit stops
and bike racks; OpenStreetMap buildings, driveways and street trees;
`data/campable_south/`) so those rows could be matched to block faces too.
They separate three quantities that the West Berkeley rows could not:

| quantity | measured by | typical share of the GIS strip |
|---|---|---|
| curb-to-property strip | City GIS (right-of-way minus pavement) | 1.00 (over-reads: +4.0 ft mean in South Berkeley, +1.3 ft in West) |
| paved sidewalk, tree wells included | BHU "total width" | 0.84 West Berkeley (n=49, IQR 0.75–1.06); 0.73 South Berkeley (n=74, IQR 0.55–0.86) |
| clear walk, tree wells and landscaping out | October tapes | 0.59 (n=5, sd 0.26) |

West Berkeley's industrial sidewalks run from the curb face to the building,
so paved ≈ strip there; residential South Berkeley has a planting strip
between curb and walk, so paved is three-quarters of the strip. Tree wells
were noted on 53 of the 76 South Berkeley rows and the BHU totals are the
same with and without them (median 10.0 ft both), confirming the survey
measured across the tree-well zone. The model's clear-walk factor (0.59) is
therefore applied to the strip, or to the BHU paved width where one exists;
on a residential face with a planting strip that double-counts the
reduction and is conservative, which is acceptable because those faces are
calibration only and are not counted under AR 10.2.

After adding the strip widths the pilot count is **97 locations on 9 block
faces** (Gilman 20, Eastshore 20, San Pablo 20, University overpass 14,
Ashby 11, I-80 off-ramp 10, Seventh 2) — the same short list, to be walked.

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
python3 tools/clear_width.py nw ninth              # clear-walk width profile every metre (needs the tiles)
python3 tools/calibrate_gis.py                     # tape/GIS factor -> data/field/gis_calibration.json
python3 tools/bhu_survey_eval.py                   # BHU survey vs every source; writes data/field/strip_widths.csv
python3 tools/campable_sites.py                    # tent model: tape > reviewer > imagery > GIS x factor
python3 tools/inject_sources.py                    # write the evidence table into index.html
```

Model weights: `satellite_2021.pth` md5 6718e1b06c57cb884dbe93e7d71f446a,
`hrnetv2_w48_imagenet_pretrained.pth` md5 1ce00d88068e5f483de64ea48693bc9a
(figshare DOIs 10.6084/m9.figshare.33315570 and .33315558). Inference ran on CPU
via `tools/tile2net/run_cpu.py`, which stubs CUDA calls and changes nothing in
the model.
