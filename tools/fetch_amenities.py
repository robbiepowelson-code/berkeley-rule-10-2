#!/usr/bin/env python3
"""
fetch_amenities.py - build the water and restroom layers from OpenStreetMap.

Two modes:

  python3 tools/fetch_amenities.py
      Rebuild amenities.json and the AMENITIES block in index.html from the
      snapshot committed at data/osm-amenities.psv. No network needed.

  python3 tools/fetch_amenities.py --refresh
      Re-query the Overpass API first, clip the results to Berkeley, and
      rewrite data/osm-amenities.psv, then do the above. Needs internet.

Why a committed snapshot: the map has to build and deploy without depending on
a live third-party API, and a snapshot is also what makes the data citable -
every point carries the OSM element id it came from, and the file header
records when it was retrieved.

Data: (c) OpenStreetMap contributors, ODbL 1.0.
      https://www.openstreetmap.org/copyright
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(REPO, "data", "osm-amenities.psv")
INDEX = os.path.join(REPO, "index.html")
OUT_JSON = os.path.join(REPO, "amenities.json")

COLS = ["id", "lat", "lon", "kind", "name", "operator", "access", "fee",
        "opening_hours", "wheelchair", "indoor", "bottle", "changing_table",
        "disposal", "check_date", "desc"]

# Bounding box used for the Overpass query, then clipped to the zoning layer.
BBOX = (37.8400, -122.3300, 37.9100, -122.2300)
CLIP_M = 120.0          # a point this close to a zoning polygon counts as Berkeley

# access values that mean "don't send anyone here"
EXCLUDE_ACCESS = {"private", "no"}

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = ('[out:json][timeout:90];('
         'nwr(%f,%f,%f,%f)["amenity"="drinking_water"];'
         'nwr(%f,%f,%f,%f)["amenity"="toilets"];);out center tags;'
         % (BBOX + BBOX))


# ------------------------------------------------------------ zoning clip

def _zoning():
    with open(INDEX, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("var ZONING"):
                return json.loads(line.split("=", 1)[1].strip().rstrip(";"))
    raise SystemExit("could not find `var ZONING` in index.html")


def _rings(geom):
    polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
             else geom["coordinates"])
    for poly in polys:
        for ring in poly:
            yield ring


def near_city(lon, lat, zoning, max_m=CLIP_M):
    """True if the point is within max_m of any zoning polygon.

    Street rights-of-way are not in the zoning layer, so this is the same
    practical 'inside Berkeley' test the street labels use, and it keeps
    Albany, Kensington, Emeryville and north Oakland out of the result.
    """
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    px, py = lon * kx, lat * ky
    lim = max_m * max_m
    pad = max_m / 90000.0
    for f in zoning["features"]:
        for ring in _rings(f["geometry"]):
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            if not (min(xs) - pad <= lon <= max(xs) + pad
                    and min(ys) - pad <= lat <= max(ys) + pad):
                continue
            for i in range(len(ring) - 1):
                ax, ay = ring[i][0] * kx, ring[i][1] * ky
                bx, by = ring[i + 1][0] * kx, ring[i + 1][1] * ky
                dx, dy = bx - ax, by - ay
                l2 = dx * dx + dy * dy
                t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
                qx, qy = ax + t * dx, ay + t * dy
                if (px - qx) ** 2 + (py - qy) ** 2 < lim:
                    return True
    return False


# --------------------------------------------------------------- refresh

def refresh():
    """Re-query Overpass and rewrite the snapshot."""
    try:
        import urllib.parse
        import urllib.request
    except ImportError:                                   # pragma: no cover
        raise SystemExit("python is missing urllib")

    body = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS, data=body,
        headers={"User-Agent": "berkeley-rule-10-2/1.0 (github.com/robbiepowelson-code/berkeley-rule-10-2)"})
    print("querying Overpass ...", file=sys.stderr)
    with urllib.request.urlopen(req, timeout=180) as r:
        payload = json.load(r)

    zoning = _zoning()
    keep = {"name", "operator", "access", "fee", "opening_hours", "wheelchair",
            "indoor", "bottle", "changing_table", "toilets:disposal", "check_date"}

    rows = []
    for e in payload.get("elements", []):
        tags = e.get("tags") or {}
        lat = e.get("lat", (e.get("center") or {}).get("lat"))
        lon = e.get("lon", (e.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        if not near_city(lon, lat, zoning):
            continue

        def cl(v):
            return re.sub(r"[|=;\r\n]", " ", str(v or "")).strip()

        desc = " - ".join(x for x in (tags.get("description"), tags.get("note")) if x)
        rows.append("|".join([
            e["type"][0] + str(e["id"]), "%.6f" % lat, "%.6f" % lon,
            "W" if tags.get("amenity") == "drinking_water" else "T",
            cl(tags.get("name")), cl(tags.get("operator")), cl(tags.get("access")),
            cl(tags.get("fee")), cl(tags.get("opening_hours")), cl(tags.get("wheelchair")),
            cl(tags.get("indoor")), cl(tags.get("bottle")), cl(tags.get("changing_table")),
            cl(tags.get("toilets:disposal")), cl(tags.get("check_date")), cl(desc),
        ]))
    rows.sort()

    header = [
        "# Drinking fountains and toilets in Berkeley, from OpenStreetMap.",
        "# Retrieved %s via the Overpass API; bbox %s," % (date.today().isoformat(), str(BBOX)),
        "# then clipped to points within %d m of the city's zoning layer." % CLIP_M,
        "# Source: OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
        "# Regenerate with tools/fetch_amenities.py",
        "|".join(COLS),
    ]
    with open(SNAPSHOT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(header + rows) + "\n")
    print("wrote %d rows to %s" % (len(rows), SNAPSHOT), file=sys.stderr)


# ----------------------------------------------------------------- build

def read_snapshot():
    retrieved = None
    rows = []
    with open(SNAPSHOT, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#"):
                m = re.search(r"Retrieved (\d{4}-\d\d-\d\d)", line)
                if m:
                    retrieved = m.group(1)
                continue
            if not line.strip() or line.startswith("id|"):
                continue
            parts = line.split("|")
            parts += [""] * (len(COLS) - len(parts))
            rows.append(dict(zip(COLS, parts[:len(COLS)])))
    return rows, retrieved


def build(dry_run=False):
    rows, retrieved = read_snapshot()

    out = []
    dropped = 0
    for r in rows:
        if r["access"].lower() in EXCLUDE_ACCESS:
            dropped += 1
            continue
        rec = {"id": r["id"],
               "lat": round(float(r["lat"]), 6),
               "lon": round(float(r["lon"]), 6),
               "k": r["kind"]}
        for k in ("name", "operator", "access", "fee", "opening_hours",
                  "wheelchair", "indoor", "bottle", "changing_table",
                  "disposal", "check_date", "desc"):
            if r[k]:
                rec[k] = r[k]
        out.append(rec)

    payload = {"source": "OpenStreetMap contributors",
               "licence": "ODbL 1.0",
               "licence_url": "https://www.openstreetmap.org/copyright",
               "retrieved": retrieved,
               "features": out}

    if not dry_run:
        with open(OUT_JSON, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, ensure_ascii=False)
            fh.write("\n")

    block = ("/* AMENITIES:BEGIN - generated by tools/fetch_amenities.py, do not edit by hand */\n"
             "var AMENITIES = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
             "/* AMENITIES:END */")
    with open(INDEX, encoding="utf-8") as fh:
        html = fh.read()
    pat = re.compile(r"/\* AMENITIES:BEGIN.*?\*/.*?/\* AMENITIES:END \*/", re.S)
    if not pat.search(html):
        raise SystemExit("no AMENITIES:BEGIN/END markers in index.html")
    html = pat.sub(lambda _: block, html, count=1)
    if not dry_run:
        with open(INDEX, "w", encoding="utf-8") as fh:
            fh.write(html)

    w = sum(1 for r in out if r["k"] == "W")
    t = len(out) - w
    print("%d points on the map: %d drinking water, %d toilets "
          "(%d dropped as private/no access). OSM data retrieved %s.%s"
          % (len(out), w, t, dropped, retrieved,
             " (dry run - nothing written)" if dry_run else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true",
                    help="re-query Overpass and rewrite the snapshot first")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()
    if args.refresh:
        refresh()
    build(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
