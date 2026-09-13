#!/usr/bin/env python3
"""
survey_sites.py — turn geotagged survey photos into map sites.

Reads a folder of photos (HEIC/JPEG/PNG) taken in the field, pulls the GPS
coordinates, timestamp and compass heading out of each one's EXIF, works out
which Berkeley zoning district the point falls in by testing it against the
ZONING layer already embedded in index.html, writes a web-sized copy of each
photo into photos/, and regenerates sites.json plus the SITES block inside
index.html.

Hand-written fields in sites.json — "label", "notes", "hidden" — are preserved
across runs. Everything else is derived from the photo and overwritten.

Usage:
    python3 tools/survey_sites.py                      # default folders
    python3 tools/survey_sites.py --photos ~/somewhere # other source folder
    python3 tools/survey_sites.py --dry-run            # report, write nothing

Requires: pillow, and pillow-heif for .HEIC input (pip3 install pillow-heif).
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime

from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = (".heic", ".heif", ".jpg", ".jpeg", ".png", ".tif", ".tiff")
MAX_PX = 1400          # longest side of the web copy
QUALITY = 78
KEEP_FIELDS = ("label", "notes", "hidden")   # never overwritten by a re-run

# AR 10.2 categories, mirroring the CATS object in index.html
CAT_NAME = {
    "res": "Residential district",
    "mixres": "Mixed-use residential",
    "com": "Commercial district",
    "man": "Manufacturing district",
    "other": "Parks, campus & special plan",
}


# ---------------------------------------------------------------- EXIF

def _dms(v):
    """EXIF degrees/minutes/seconds rational triple -> float degrees."""
    return float(v[0]) + float(v[1]) / 60.0 + float(v[2]) / 3600.0


def read_exif(path):
    """Return dict with lat/lon and whatever else the photo carries, or None."""
    img = Image.open(path)
    ex = img.getexif()
    gps = ex.get_ifd(0x8825)          # GPSInfo IFD
    if not gps or 2 not in gps or 4 not in gps:
        return None, img

    lat = _dms(gps[2])
    if str(gps.get(1, "N")).upper().startswith("S"):
        lat = -lat
    lon = _dms(gps[4])
    if str(gps.get(3, "E")).upper().startswith("W"):
        lon = -lon

    out = {"lat": round(lat, 7), "lon": round(lon, 7)}

    if 6 in gps:                       # GPSAltitude, metres
        try:
            alt = float(gps[6])
            if int(gps.get(5, 0)) == 1:    # 1 = below sea level
                alt = -alt
            out["alt_m"] = round(alt, 1)
        except (TypeError, ValueError):
            pass

    if 17 in gps:                      # GPSImgDirection — way the camera faced
        try:
            out["heading"] = round(float(gps[17]), 1)
        except (TypeError, ValueError):
            pass

    # DateTimeOriginal lives in the Exif sub-IFD; fall back to file DateTime
    sub = ex.get_ifd(0x8769)
    raw = sub.get(0x9003) or ex.get(0x0132)
    if raw:
        try:
            out["taken"] = datetime.strptime(
                str(raw), "%Y:%m:%d %H:%M:%S").isoformat(timespec="seconds")
        except ValueError:
            pass

    return out, img


# ------------------------------------------------------- zoning lookup

def load_zoning(index_html):
    """Pull the ZONING GeoJSON back out of index.html."""
    with open(index_html, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("var ZONING"):
                body = line.split("=", 1)[1].strip().rstrip(";")
                return json.loads(body)
    raise SystemExit("could not find `var ZONING` in " + index_html)


def _in_ring(lon, lat, ring):
    """Ray-casting point-in-polygon on a [lon, lat] ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            if lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _in_polygon(lon, lat, poly):
    """poly = [outer_ring, hole, hole, ...]"""
    if not poly or not _in_ring(lon, lat, poly[0]):
        return False
    return not any(_in_ring(lon, lat, hole) for hole in poly[1:])


def _bbox(geom):
    xs, ys = [], []
    stack = [geom["coordinates"]]
    while stack:
        node = stack.pop()
        if node and isinstance(node[0], (int, float)):
            xs.append(node[0])
            ys.append(node[1])
        else:
            stack.extend(node)
    return min(xs), min(ys), max(xs), max(ys)


def _rings(geom):
    polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
             else geom["coordinates"])
    for poly in polys:
        for ring in poly:
            yield ring


def _seg_dist_m(lon, lat, ring):
    """Shortest distance in metres from a point to a ring's edges.

    Local equirectangular approximation - accurate enough over the few hundred
    metres that matter here.
    """
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    px, py = lon * kx, lat * ky
    best = float("inf")
    for i in range(len(ring) - 1):
        ax, ay = ring[i][0] * kx, ring[i][1] * ky
        bx, by = ring[i + 1][0] * kx, ring[i + 1][1] * ky
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        qx, qy = ax + t * dx, ay + t * dy
        d = math.hypot(px - qx, py - qy)
        if d < best:
            best = d
    return best


# How far a point may sit from a district and still be attributed to it.
# Field photos are taken from the roadway, and the city's zoning polygons stop
# at the property line, so a point in the street is typically 10-25 m out.
SNAP_M = 60.0
# If a district in a DIFFERENT AR 10.2 category is within this much of the
# nearest one, the spot genuinely sits between two districts and is flagged.
AMBIG_M = 20.0


def district_for(lon, lat, zoning):
    """Locate a point against the zoning layer.

    Returns (properties, distance_m, ambiguous_properties). distance_m is 0.0
    when the point falls inside the district. ambiguous_properties is set when
    a district in a different AR 10.2 category is nearly as close - which is
    what standing in a street between two districts looks like, and the map
    should not pretend otherwise.
    """
    dists = []
    for f in zoning["features"]:
        g = f["geometry"]
        x0, y0, x1, y1 = _bbox(g)
        pad = 0.002                      # ~200 m, comfortably over SNAP_M
        if not (x0 - pad <= lon <= x1 + pad and y0 - pad <= lat <= y1 + pad):
            continue
        polys = ([g["coordinates"]] if g["type"] == "Polygon"
                 else g["coordinates"])
        if any(_in_polygon(lon, lat, p) for p in polys):
            return f["properties"], 0.0, None
        dists.append((min(_seg_dist_m(lon, lat, r) for r in _rings(g)),
                      f["properties"]))

    if not dists:
        return None, None, None

    dists.sort(key=lambda t: t[0])
    near_d, near_p = dists[0]
    if near_d > SNAP_M:
        return None, near_d, None

    other = next((p for d, p in dists
                  if p.get("c") != near_p.get("c") and d - near_d <= AMBIG_M), None)
    return near_p, near_d, other


# ------------------------------------------------------------- images

def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", os.path.splitext(name)[0].lower()).strip("-")


def write_web_copy(img, dest):
    im = ImageOps.exif_transpose(img).convert("RGB")
    im.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
    im.save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return im.size


# -------------------------------------------------------------- build

def inject(index_html, sites, dry_run=False):
    """Replace the SITES block in index.html with the current site list."""
    with open(index_html, "r", encoding="utf-8") as fh:
        html = fh.read()

    block = ("/* SITES:BEGIN — generated by tools/survey_sites.py, do not edit by hand */\n"
             "var SITES = " + json.dumps(sites, ensure_ascii=False) + ";\n"
             "/* SITES:END */")

    pattern = re.compile(
        r"/\* SITES:BEGIN.*?\*/.*?/\* SITES:END \*/", re.S)
    if not pattern.search(html):
        raise SystemExit(
            "no SITES:BEGIN/SITES:END markers in index.html — add them first")
    html = pattern.sub(lambda _: block, html, count=1)

    if not dry_run:
        with open(index_html, "w", encoding="utf-8") as fh:
            fh.write(html)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photos", default=os.path.join(os.path.dirname(REPO), "survey-photos"),
                    help="folder of geotagged field photos (default: ../survey-photos)")
    ap.add_argument("--repo", default=REPO, help="repo root (default: this script's parent)")
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    src = os.path.expanduser(args.photos)
    repo = os.path.expanduser(args.repo)
    index_html = os.path.join(repo, "index.html")
    photos_dir = os.path.join(repo, "photos")
    sites_json = os.path.join(repo, "sites.json")

    if not os.path.isdir(src):
        raise SystemExit("no such photo folder: " + src)

    # keep hand-written fields from the previous run
    previous = {}
    if os.path.exists(sites_json):
        with open(sites_json, encoding="utf-8") as fh:
            for s in json.load(fh):
                previous[s["id"]] = s

    zoning = load_zoning(index_html)
    if not args.dry_run:
        os.makedirs(photos_dir, exist_ok=True)

    sites, skipped = [], []
    names = sorted(n for n in os.listdir(src) if n.lower().endswith(EXTS))
    for name in names:
        path = os.path.join(src, name)
        if name.lower().endswith((".heic", ".heif")) and not HEIC:
            skipped.append((name, "HEIC support missing — pip3 install pillow-heif"))
            continue
        try:
            gps, img = read_exif(path)
        except Exception as e:                       # noqa: BLE001
            skipped.append((name, "unreadable: %s" % e))
            continue
        if not gps:
            skipped.append((name, "no GPS in EXIF"))
            continue

        sid = slug(name)
        rel = "photos/%s.jpg" % sid
        if not args.dry_run:
            w, h = write_web_copy(img, os.path.join(repo, rel))
        else:
            w = h = 0

        site = {"id": sid, "photo": rel, "w": w, "h": h}
        site.update(gps)

        props, dist_m, other = district_for(gps["lon"], gps["lat"], zoning)
        if props:
            site["zone"] = props.get("z")
            site["district"] = props.get("d")
            site["cat"] = props.get("c")
            # 0 = the point itself is inside the district; anything else is a
            # photo taken from the roadway, snapped to the district it abuts
            site["dist_m"] = round(dist_m, 1)
            if other:
                site["ambiguous"] = {"zone": other.get("z"),
                                     "district": other.get("d"),
                                     "cat": other.get("c")}
        else:
            site["zone"] = None
            site["district"] = "Outside the mapped zoning layer"
            site["cat"] = None
            site["dist_m"] = round(dist_m, 1) if dist_m else None

        old = previous.get(sid, {})
        for k in KEEP_FIELDS:
            if old.get(k) not in (None, ""):
                site[k] = old[k]
        site.setdefault("label", "")
        site.setdefault("notes", "")

        sites.append(site)

    sites.sort(key=lambda s: (s.get("taken") or "", s["id"]))

    if not args.dry_run:
        with open(sites_json, "w", encoding="utf-8") as fh:
            json.dump(sites, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    inject(index_html, sites, dry_run=args.dry_run)

    # ---- report
    for s in sites:
        d = s.get("dist_m")
        where = ("inside" if d == 0 else
                 ("%.0f m away" % d) if d is not None else "none near")
        amb = s.get("ambiguous")
        print("%-12s %9.5f,%11.5f  %-8s %-26s %-11s%s" % (
            s["id"], s["lat"], s["lon"], s.get("zone") or "-",
            CAT_NAME.get(s.get("cat"), "outside zoning layer"), where,
            "  also near " + str(amb["zone"]) if amb else ""))
    for name, why in skipped:
        print("skipped  %s — %s" % (name, why), file=sys.stderr)
    print("\n%d site(s)%s" % (len(sites), " (dry run — nothing written)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
