# tile2net sidewalk widths — sample run

A test of whether an imagery-based sidewalk detector can give an independent,
reproducible width for every block face, as a check on the GIS-derived widths
the campable model uses and on tape measurements.

## What was run

- **Tool:** [tile2net](https://github.com/VIDA-NYU/tile2net) v0.5.0 (BSD-3),
  the code behind Hosseini, Sevtsuk, Miranda, Cesar & Silva, *Mapping the walk*,
  Computers, Environment and Urban Systems 101 (2023). Reported sidewalk IoU
  82.7 % (precision 0.90, recall 0.92) on its own test set; trained on Cambridge
  MA, Washington DC and New York City, so Berkeley is out-of-sample.
- **Imagery:** Alameda County 2023 orthophoto (Pictometry/EagleView WMTS,
  tile2net source `al`), zoom 20, 256 px tiles, ≈ 0.12 m/px at this latitude.
  100 tiles, x 168081–168090, y 404999–405008. Fetched with
  `tools/tile2net/fetch_inputs.sh`.
- **Weights:** `satellite_2021.pth` (md5 6718e1b0…) and
  `hrnetv2_w48_imagenet_pretrained.pth` (md5 1ce00d88…), the checkpoints pinned
  in tile2net's manifest, from figshare. Not committed (890 MB).
- **Area:** the block bounded by Seventh St, Eighth St, Heinz Ave and Grayson St
  (bbox 37.8534, -122.2935 to 37.8552, -122.2910). The folder is named for it.
- **Hardware:** CPU only (2 cores, 7 GB). tile2net insists on CUDA, so
  `tools/tile2net/run_cpu.py` stubs the CUDA calls and runs the same model
  unchanged. Inference took 83 s.
- **Commands:**
  ```
  python3 -m tile2net generate -l "37.8534, -122.2935, 37.8552, -122.2910" -n sample -o out \
      -i "tiles/sample/20/x/y.png" -z 20
  TILE2NET_WEIGHTS_DIR=tile2net/weights python3 tools/tile2net/run_cpu.py inference \
      --city_info out/sample/tiles/sample_256_info.json --local --eval test --dump_percent 100
  python3 tools/tile2net_widths.py out/sample/polygons/sample-polygons.parquet data/tile2net/sample-7th-8th-heinz-grayson
  ```

## Files

- `polygons.parquet` — tile2net's raw output: 32 sidewalk, 8 road, 3 crosswalk polygons.
- `sidewalks.geojson`, `sidewalk_widths.csv` — the sidewalk polygons with width
  stats (median, 10th and 90th percentile along the skeleton, in feet).
- `face_compare.csv` — GIS width vs tile2net width for the 12 block faces fully
  inside the run.
- `segmentation_*.jpg` — aerial tile beside the model's segmentation (blue
  sidewalk, green road, red crosswalk) for eyeballing.

## What the sample showed

| face | street | side | GIS width (ft) | tile2net (ft) |
|---|---|---|---|---|
| 4056L | Heinz Ave | L | 7.9 | 8.8 |
| 4056R | Heinz Ave | R | 15.8 | 9.0 |
| 4131L | Heinz Ave | L | 4.9 | 4.4 |
| 4131R | Heinz Ave | R | 1.9 | 9.0 |
| 5116L | Grayson St | L | 3.2 | 13.5 |
| 5116R | Grayson St | R | 17.9 | 9.8 |
| 6765L | Seventh St | L | 13.0 | 9.8 |
| 6765R | Seventh St | R | 2.3 | 10.6 |
| 6767L | Seventh St | L | 11.9 | 9.4 |
| 6767R | Seventh St | R | 10.8 | 10.3 |
| 6790L | Eighth St | L | 13.2 | 9.4 |
| 6790R | Eighth St | R | 11.3 | 10.4 |

Two things stand out.

1. **The GIS widths split the two sides of a street implausibly.** Grayson comes
   out 3.2 ft on one side and 17.9 ft on the other; Seventh 2.3 ft and 13.0 ft.
   The GIS method is right-of-way minus pavement, divided between the sides by
   where the centerline sits, and the centerline is not always centred. The
   *sum* of the two sides is about right; the split is not. tile2net sees
   roughly 9–10 ft on both sides, which is what a standard West Berkeley
   industrial-street sidewalk looks like.
2. **tile2net's widths are tight and plausible but unverified.** Median widths
   cluster at 9–10.5 ft with a 10th percentile around 7 ft (poles, tree wells,
   driveways) and a few flares at driveway aprons. The model's known weak spots
   — tree canopy and deep shadow — do show: the long Heinz face 4131L is read
   at 4.4 ft under trees. None of these faces has a tape measurement yet.

So on this block the imagery widths and the GIS widths agree on the conclusion
(no 5×7 ft tent fits anywhere with a 6 ft path kept clear) but disagree on the
numbers, and the imagery looks like the better source for the *split* between
sides. That is a reason to run tile2net over the whole corridor and to tape a
sample of faces to calibrate it, not a reason to trust it on its own.

## Caveats

- The detector was not trained on Berkeley; its paper recommends retraining for
  new regions. Treat its widths as a screen with an error of roughly ±1 ft
  until the tape comparison says otherwise.
- Widths are polygon widths; they include tree wells, poles and street
  furniture that sit inside the sidewalk polygon. The clear path is narrower.
- The 2023 imagery postdates the City's 2020 orthophoto but a sidewalk can
  still have been rebuilt since.
