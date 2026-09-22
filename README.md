# Where Rule 10.2 Applies

An interactive map of every City of Berkeley zoning district, colored by what **Administrative Regulation 10.2** — the city's rule on personal belongings ("temporary non-commercial objects") on public sidewalks — means in each one: prohibited in residential districts, permitted with strict limits in commercial and manufacturing districts.

Over the districts sit three point layers: **surveyed sites** photographed in the field, and **drinking water** and **toilets** from OpenStreetMap.

**[Open the map →](https://robbiepowelson-code.github.io/berkeley-rule-10-2/)** · **[How it was made →](https://robbiepowelson-code.github.io/berkeley-rule-10-2/report.html)** · **[Add a site →](CONTRIBUTING.md)**

## What's here

- **`index.html`** — the map itself. Self-contained: Leaflet, the city's GIS data, and all three point layers are embedded, so it works offline.
- **`report.html`** — the method: the regulation, the data, how each layer was built, and what it can't tell you.
- **`CONTRIBUTING.md`** — how to add a site, either through an issue form or by running the script over a folder of photos.
- **`sites.json`** + **`photos/`** — the surveyed sites and their images.
- **`amenities.json`** + **`data/osm-amenities.psv`** — the water and toilet points, and the raw OpenStreetMap snapshot they are built from.
- **`data/contributed-sites.json`** — sites submitted through the issue form, which carry typed coordinates because GitHub strips EXIF from uploads.
- **`data/gis/`** — City of Berkeley right-of-way, street centerlines (with pavement width), AC Transit stops, hydrants, bike racks; and OpenStreetMap buildings, driveways, crossings, curb ramps and street furniture for the study area.
- **`data/campable/`** + **`tools/ar102_rules.json`** — the campable-locations model's output and every distance it uses.
- **`data/field/`** — ground truth: measured widths, painted curbs, and reviewer exports from `review.html`.

## The tools

```
python3 tools/survey_sites.py [--photos FOLDER]
```

Reads GPS, timestamp and compass heading from each photo's EXIF, writes web-sized copies into `photos/`, matches every point to the zoning district it falls in or abuts, merges in anything from `data/contributed-sites.json`, and rewrites `sites.json` and the `SITES` block in `index.html`. Hand-written `label` and `notes` fields survive a re-run. The folder is remembered in `survey.config.json` (untracked).

```
python3 tools/fetch_amenities.py [--refresh]
```

Rebuilds the water and toilet layers from `data/osm-amenities.psv`. With `--refresh`, re-queries the Overpass API first, clips the results to Berkeley, and rewrites the snapshot.

```
python3 tools/add_site.py --issue N --lat LAT --lon LON --photo-url URL ...
```

What the issue-form bot runs. Validates the coordinates against a Berkeley bounding box, fetches the photo, and appends to `data/contributed-sites.json`.

```
python3 tools/campable_sites.py [--bbox W,S,E,N] [--footprint 5x7] [--all-zones]
```

Counts the places a tent could stand under AR 10.2's clearance rules. Sidewalk = the city's right-of-way polygon minus the roadway (`data/gis/`); every setback and obstruction in `tools/ar102_rules.json` is subtracted (each entry says whether it comes from AR 10.2 or is an assumption); then a footprint is tiled along each block face in whatever strip is left. Writes `data/campable/` and the **Campable locations** layer in `index.html`. `--footprint 7x16 --pins` adds a second, pin-style layer for an alternative footprint without touching the tent layer. Field inputs in `data/field/` override the GIS: `sidewalk_widths.csv` (tape measurements), `curb_zones.geojson`, `exclusions.geojson`, and anything exported from the review tool.

- **`review.html`** — the block-face review tool. Walks through the model's block faces over the City's 3-inch 2020 aerials so a reviewer can confirm or correct each sidewalk width (measure tool), draw driveways, painted curbs, entrances, obstacles and no-go areas, and export a `review-<date>.geojson` for `data/field/`. Needs to be served over http (`python3 -m http.server`, or GitHub Pages) because it fetches the data files.

Both scripts need `pillow`; `pillow-heif` as well for `.HEIC` input.

## Sources

- **Zoning, streets, boundary** — City of Berkeley [Community GIS Portal](https://berkeleyca.gov/city-services/community-gis-portal), Land Use Planning map service, retrieved August 27, 2026.
- **Rule text** — [Administrative Regulation 10.2](https://berkeleyca.gov/sites/default/files/documents/Administrative%20Regulation%2010.2.pdf) (City Manager, rev. January 2025).
- **Buildings, driveways, crossings, curb ramps, street furniture** — © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, ODbL, via Overpass, retrieved September 21, 2026.
- **Aerial imagery in the review tool** — City of Berkeley 3-inch orthophoto, 2020 (`Imagery/ORTHOPHOTO_2020_3in` image service).
- **Drinking water and toilets** — © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/), retrieved September 13, 2026. Every point links back to the OSM element it came from.
- **Corroboration for city restrooms** — City of Berkeley, [Citywide Restroom Study / WASH Assessment](https://berkeleyca.gov/sites/default/files/documents/Citywide%20Restroom%20Study%20and%20Executive%20Summary%20-%202020-10-06%20-%20Final.pdf) (October 2020).
- **Basemap, when enabled** — © OpenStreetMap contributors.

## Read this before relying on it

A pin marks where a photograph was taken — not a finding that the spot is lawful, available, or usable. Water and toilet points are community-maintained records that may be locked, broken, seasonal, or gone. This is information, not legal advice, and AR 10.2 is not a camping permit — other city, state, and university rules still apply. Generated with Claude. Not affiliated with the City of Berkeley.
