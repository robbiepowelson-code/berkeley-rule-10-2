# Adding to the map

The map has two kinds of points you can add to: **surveyed sites**, which are
places somebody photographed, and corrections to the **water and toilet**
layers, which come from OpenStreetMap.

A pin marks where a photo was taken. It is not a claim that a spot is lawful,
safe, or available, and nothing submitted here will be presented as one. Please
don't photograph people or their belongings, and don't submit anything that
shows where a particular person is staying.

---

## Adding one site, with no tools

Open a **[new issue using the "Add a surveyed site" form][new-issue]**, fill it
in, and attach your photo. A bot turns it into a pull request within a minute or
two; a person reviews that before it reaches the live map.

[new-issue]: https://github.com/robbiepowelson-code/berkeley-rule-10-2/issues/new?template=add-site.yml

**You have to type the coordinates yourself.** GitHub strips location data out
of photos attached to issues, so the photo alone can't say where it was taken.
Getting the coordinates takes about ten seconds:

- **iPhone** — open the photo in Photos, swipe up (or tap ⓘ). The map at the
  bottom is the location; tap it, then tap the coordinates to copy them.
- **Android** — open the photo in Google Photos, tap ⓘ, and the location is
  listed with coordinates.
- **Anywhere** — find the spot on [openstreetmap.org][osm], right-click, choose
  "Show address". The coordinates appear in the search box, latitude first.

[osm]: https://www.openstreetmap.org/#map=15/37.8690/-122.2990

Latitude is about `37.87` in Berkeley. Longitude is about `-122.29` — it is
negative, and the minus sign matters. The form rejects a pair that lands outside
Berkeley, which catches the two common mistakes (swapping the numbers, dropping
the minus).

If the bot can't process your issue it will comment saying so. Editing the issue
makes it try again.

---

## Adding a batch of photos, with the full location data

If you have a folder of geotagged photos, running the script locally keeps
everything the camera recorded — GPS, timestamp, and the compass direction the
camera was facing — which the issue route loses.

You need Python 3, `git`, and two libraries:

```
pip3 install pillow pillow-heif
```

Then:

```
git clone https://github.com/robbiepowelson-code/berkeley-rule-10-2.git
cd berkeley-rule-10-2
python3 tools/survey_sites.py --photos ~/path/to/your/photos
```

That reads every photo in the folder, writes web-sized copies into `photos/`,
matches each point to its zoning district, and rewrites `sites.json` and the
`SITES` block in `index.html`. Open `index.html` in a browser to check the pins
landed where you expect, then open a pull request.

The folder you pass is remembered in `survey.config.json` (untracked), so later
runs are just `python3 tools/survey_sites.py`.

**Photos without GPS are skipped** and the script says which ones. iPhones drop
location if Location Services was off for the Camera app, and most photos that
have been through a messaging app have had it stripped.

**Writing notes.** `sites.json` has a `label` and a `notes` field for every
site, both empty until somebody fills them in. Edit them by hand — they survive
re-runs of the script. Notes are the part a map can't generate: sidewalk width,
shade, lighting, slope, noise, what's posted nearby, how exposed it is.

---

## Fixing the water and toilet layers

Those layers come from [OpenStreetMap][osmcopy], not from this project. A
fountain that's missing, moved, or long since removed should be fixed **in
OpenStreetMap** — anyone can edit it, and the fix then benefits every map that
uses the data, not just this one.

[osmcopy]: https://www.openstreetmap.org/copyright

Once OSM is right, refresh this repo's snapshot:

```
python3 tools/fetch_amenities.py --refresh
```

That re-queries the Overpass API, clips the results to Berkeley, and rewrites
`data/osm-amenities.psv`, `amenities.json`, and the `AMENITIES` block in
`index.html`. Without `--refresh` it rebuilds from the committed snapshot and
needs no network. Open a pull request with the changed files.

The snapshot is committed deliberately: the map builds and deploys without
depending on a live third-party API, and every point carries the OSM element id
it came from, so any pin can be traced back to its source.

---

## What gets merged

Reviewers check three things: the pin lands where the photo was taken, the
district the script matched looks right on the ground, and the photo shows a
place rather than a person. Notes get read for tone — this map describes
conditions, it doesn't advise anyone to do anything.
