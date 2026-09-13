#!/usr/bin/env python3
"""
add_site.py - add one surveyed site submitted through the issue form.

GitHub strips EXIF from images attached to issues, so a photo that arrives
that way has no GPS left in it. The issue form therefore asks the contributor
to type the coordinates, and this script pairs those coordinates with the
uploaded photo. It appends the result to data/contributed-sites.json, which
tools/survey_sites.py merges into the map alongside the photos processed
locally from EXIF.

Usage (this is what .github/workflows/add-site.yml runs):

    python3 tools/add_site.py --issue 42 --lat 37.8649 --lon -122.2983 \
        --photo-url https://github.com/user-attachments/... \
        --label "Second & Cedar" --notes "Wide sidewalk, no posted signs"

Coordinates are validated against a Berkeley-area bounding box, so a
mistyped or swapped pair is rejected rather than quietly landing in the
Atlantic. Run with --check to validate without writing anything.
"""

import argparse
import io
import json
import os
import re
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRIBUTED = os.path.join(REPO, "data", "contributed-sites.json")
PHOTOS = os.path.join(REPO, "photos")
MAX_PX = 1400
QUALITY = 78

# Generous box around Berkeley - rejects swapped lat/lon and stray digits.
LAT_RANGE = (37.83, 37.92)
LON_RANGE = (-122.34, -122.22)
MAX_BYTES = 25 * 1024 * 1024


def coords(lat, lon):
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1]):
        raise SystemExit(
            "latitude %s is outside Berkeley (expected %.2f to %.2f). "
            "Latitude comes first and is about 37.87 here; longitude is negative."
            % (lat, LAT_RANGE[0], LAT_RANGE[1]))
    if not (LON_RANGE[0] <= lon <= LON_RANGE[1]):
        raise SystemExit(
            "longitude %s is outside Berkeley (expected %.2f to %.2f). "
            "Longitude is negative in California - check for a missing minus sign."
            % (lon, LON_RANGE[0], LON_RANGE[1]))
    return round(lat, 7), round(lon, 7)


def fetch_photo(url, dest):
    """Download an issue attachment and write a web-sized JPEG."""
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    req = urllib.request.Request(url, headers={"User-Agent": "berkeley-rule-10-2/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read(MAX_BYTES + 1)
    if len(blob) > MAX_BYTES:
        raise SystemExit("photo is larger than %d MB" % (MAX_BYTES // 1024 // 1024))

    im = ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
    im.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
    im.save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return im.size


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue", required=True, help="issue number this came from")
    ap.add_argument("--lat", required=True, type=float)
    ap.add_argument("--lon", required=True, type=float)
    ap.add_argument("--photo-url", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    lat, lon = coords(args.lat, args.lon)
    sid = "issue-%s" % re.sub(r"[^0-9a-z]+", "", str(args.issue).lower())
    if args.check:
        print("ok: %s at %.5f, %.5f" % (sid, lat, lon))
        return

    os.makedirs(PHOTOS, exist_ok=True)
    rec = {"id": sid, "lat": lat, "lon": lon,
           "label": args.label.strip(), "notes": args.notes.strip(),
           "source": "issue #%s" % args.issue}
    if args.author.strip():
        rec["contributor"] = args.author.strip()

    if args.photo_url:
        rel = "photos/%s.jpg" % sid
        w, h = fetch_photo(args.photo_url, os.path.join(REPO, rel))
        rec.update({"photo": rel, "w": w, "h": h})

    existing = []
    if os.path.exists(CONTRIBUTED):
        with open(CONTRIBUTED, encoding="utf-8") as fh:
            existing = json.load(fh)
    existing = [e for e in existing if e.get("id") != sid]      # re-submitting replaces
    existing.append(rec)
    existing.sort(key=lambda e: e["id"])

    with open(CONTRIBUTED, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("added %s (%.5f, %.5f)%s" % (sid, lat, lon, " with photo" if args.photo_url else ""))


if __name__ == "__main__":
    main()
