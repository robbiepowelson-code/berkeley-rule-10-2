#!/usr/bin/env python3
"""
campable_sites.py - count the places a tent could stand on Berkeley's
sidewalks under Administrative Regulation 10.2's clearance rules.

Method (all geometry in metres, NAD83 / UTM 10N, EPSG:26910):

  1. sidewalk  = city Right-of-Way polygon  minus  the roadway, where the
                 roadway is every street centreline buffered to half its
                 curb-to-curb pavement width (PAV_WIDTH_RD).
  2. usable    = sidewalk minus every exclusion in tools/ar102_rules.json:
                 building-line setback, curb setback, intersection corners,
                 hydrants, bus stops, bike racks, painted curbs and any
                 field-drawn exclusions.
  3. for every block face (one side of one centreline segment) measure the
     sidewalk width from the curb line to the property line, work out the
     AR 10.2 path of travel it must keep (6 ft, or 10 ft when 14 ft or wider),
     and see how deep a strip is left for objects.
  4. if a tent fits in that strip, lay tents end to end along the face and
     keep every one that sits entirely inside `usable`.  Each kept rectangle
     is one "location".

Outputs (data/campable/):
  sites.geojson    one polygon per location, with street, side, zoning
  faces.geojson    one line per block face: width, path, depth, count, flags
  summary.json     totals by AR 10.2 category, zoning district and street

Field inputs (data/field/, all optional):
  sidewalk_widths.csv     centerlineid,side,width_ft   - measured widths
                          override the GIS estimate for that block face
  curb_zones.geojson      LineStrings along painted curbs, properties.color
  exclusions.geojson      Points (properties.radius_ft), LineStrings
                          (properties.width_ft) or Polygons to subtract:
                          driveways, entrances, ramps, parklets, BART

Usage:
  python3 tools/campable_sites.py                 # pilot bbox, tent footprint
  python3 tools/campable_sites.py --bbox W,S,E,N
  python3 tools/campable_sites.py --footprint 3x3 # AR 10.2's 9 sq ft object
  python3 tools/campable_sites.py --all-zones     # include residential faces

Needs shapely>=2 and pyproj.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

try:
    from shapely.geometry import (LineString, MultiLineString, Point, Polygon,
                                  box, mapping, shape)
    from shapely.ops import transform, unary_union
    from shapely.validation import make_valid
    from shapely import STRtree
    import pyproj
except ImportError as e:  # pragma: no cover
    raise SystemExit("needs shapely>=2 and pyproj:  pip3 install shapely pyproj  (%s)" % e)

FT = 0.3048
PILOT_BBOX = (-122.32, 37.85, -122.28, 37.882)   # West Berkeley, Gilman to Ashby

CAT_NAME = {
    "res": "Residential district",
    "mixres": "Mixed-use residential",
    "com": "Commercial district",
    "man": "Manufacturing district",
    "other": "Parks, campus & special plan",
}

# ------------------------------------------------------------------ helpers

def ft(v):
    return v * FT


def load_geojson(path, required=True):
    if not os.path.exists(path):
        if required:
            raise SystemExit("missing %s" % path)
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["features"]


def load_zoning(index_html):
    with open(index_html, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("var ZONING"):
                return json.loads(line.split("=", 1)[1].strip().rstrip(";"))["features"]
    raise SystemExit("could not find `var ZONING` in " + index_html)


def polygonal(geom):
    """Keep only the polygon parts of whatever make_valid returned."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(parts)


def lines_of(geom):
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return []


def offset(line, dist, side):
    """Parallel offset that keeps direction; shapely's right offsets reverse."""
    o = line.offset_curve(dist if side == "L" else -dist)
    if o.is_empty:
        return None
    if isinstance(o, MultiLineString):
        o = max(o.geoms, key=lambda g: g.length)
    return o


def rect_along(line, s, length, depth):
    """Rectangle length x depth centred on the point `s` metres along `line`."""
    if s - length / 2 < 0 or s + length / 2 > line.length:
        return None
    a = line.interpolate(s - length / 2)
    b = line.interpolate(s + length / 2)
    dx, dy = b.x - a.x, b.y - a.y
    n = math.hypot(dx, dy)
    if n == 0:
        return None
    nx, ny = -dy / n * depth / 2, dx / n * depth / 2
    return Polygon([(a.x + nx, a.y + ny), (b.x + nx, b.y + ny),
                    (b.x - nx, b.y - ny), (a.x - nx, a.y - ny)])


def rnd(coords, nd=5):
    return [[round(x, nd), round(y, nd)] for x, y in coords]


def inject(index_html, sites, faces, summary, area_name):
    """Rewrite the CAMPABLE block in index.html with a compact copy of the results."""
    keep = {"id": "f", "street": "st", "side": "sd", "width_ft": "w", "width_source": "ws",
            "path_ft": "p", "depth_ft": "d", "count": "n", "zone": "z", "cat": "c", "placement": "pl"}
    fc_faces = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "LineString",
                      "coordinates": rnd(transform_back(f["geometry"]).simplify(0.00002).coords)},
         "properties": {v: f["properties"][k] for k, v in keep.items()}}
        for f in faces]}
    fc_sites = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Polygon", "coordinates": [rnd(f["geometry"]["coordinates"][0], 6)]},
         "properties": {"f": f["properties"]["face"], "n": f["properties"]["n"]}}
        for f in sites]}
    payload = {"total": summary["total_locations"], "footprint_ft": summary["footprint_ft"],
               "area": area_name, "bbox": summary["bbox"], "by_category": summary["by_category"],
               "sites": fc_sites, "faces": fc_faces}
    block = ("/* CAMPABLE:BEGIN \u2014 generated by tools/campable_sites.py, do not edit by hand */\n"
             "var CAMPABLE = " + json.dumps(payload, separators=(",", ":")) + ";\n"
             "/* CAMPABLE:END */")
    with open(index_html, encoding="utf-8") as fh:
        html = fh.read()
    pat = re.compile(r"/\* CAMPABLE:BEGIN.*?\*/.*?/\* CAMPABLE:END \*/", re.S)
    if not pat.search(html):
        raise SystemExit("no CAMPABLE:BEGIN/END markers in index.html")
    html = pat.sub(lambda m: block, html, count=1)
    with open(index_html, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("injected %d locations / %d faces into index.html (%d KB block)" %
          (len(fc_sites["features"]), len(fc_faces["features"]), len(block) // 1024), file=sys.stderr)


def transform_back(geom_dict):
    return shape(geom_dict)


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", default=",".join(map(str, PILOT_BBOX)),
                    help="W,S,E,N in WGS-84 (default: West Berkeley pilot)")
    ap.add_argument("--footprint", default=None, help="SHORTxLONG in feet, overrides rules.json")
    ap.add_argument("--all-zones", action="store_true", help="count residential faces too")
    ap.add_argument("--rules", default=None)
    ap.add_argument("--out", default=None, help="output folder (default data/campable)")
    ap.add_argument("--no-inject", action="store_true", help="do not rewrite the CAMPABLE block in index.html")
    ap.add_argument("--area-name", default="West Berkeley pilot (Gilman to Ashby)")
    args = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gis = os.path.join(repo, "data", "gis")
    field = os.path.join(repo, "data", "field")
    out = args.out or os.path.join(repo, "data", "campable")
    os.makedirs(out, exist_ok=True)

    with open(args.rules or os.path.join(repo, "tools", "ar102_rules.json"), encoding="utf-8") as fh:
        R = json.load(fh)

    if args.footprint:
        short_ft, long_ft = (float(x) for x in args.footprint.lower().split("x"))
    else:
        short_ft, long_ft = R["footprint"]["tent_short_ft"], R["footprint"]["tent_long_ft"]
    short_m, long_m = ft(short_ft), ft(long_ft)

    to_m = pyproj.Transformer.from_crs(4326, 26910, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(26910, 4326, always_xy=True).transform
    W, S, E, N = (float(x) for x in args.bbox.split(","))
    bbox = transform(to_m, box(W, S, E, N))

    # ---- inputs ---------------------------------------------------------
    print("loading layers ...", file=sys.stderr)
    row_raw = polygonal(make_valid(transform(to_m, shape(load_geojson(os.path.join(gis, "row.geojson"))[0]["geometry"]))))
    property_line = row_raw.boundary                      # ROW edge = parcel line
    row = row_raw.intersection(bbox)

    defaults = R["roadway"]["default_pavement_width_ft"]
    segs = []
    for f in load_geojson(os.path.join(gis, "centerlines.geojson")):
        p = f["properties"]
        g = transform(to_m, shape(f["geometry"]))
        if not g.intersects(bbox):
            continue
        w = p.get("PAV_WIDTH_RD")
        src = "gis"
        if not w:
            w = defaults.get((p.get("STREET_TYPE") or "*").upper(), defaults["*"])
            src = "default"
        for i, ln in enumerate(lines_of(g)):
            segs.append({
                "id": "%s%s" % (p.get("CENTERLINEID") or p.get("OBJECTID"), "" if i == 0 else "-%d" % i),
                "street": " ".join(x for x in [p.get("STREET_NAME"), p.get("STREET_TYPE")] if x),
                "line": ln, "half": ft(w) / 2, "pav_ft": w, "width_source": src,
                "roadclass": p.get("ROADCLASS"),
            })
    print("  %d centreline segments" % len(segs), file=sys.stderr)

    roadway = unary_union([s["line"].buffer(s["half"], cap_style="round") for s in segs])
    sidewalk = row.difference(roadway)

    # ---- exclusions -----------------------------------------------------
    excl = []
    why = Counter()

    if R["building_setback"].get("enabled", True):
        excl.append(property_line.buffer(ft(R["building_setback"]["ft"])))
    if R["curb_setback"].get("enabled", True):
        excl.append(roadway.buffer(ft(R["curb_setback"]["ft"])))

    # intersection corners: nodes where 2+ segments meet
    if R["corner_clearance"].get("enabled", True):
        nodes = defaultdict(list)
        for s in segs:
            for pt in (s["line"].coords[0], s["line"].coords[-1]):
                nodes[(round(pt[0], 1), round(pt[1], 1))].append(s)
        corner_ft = R["corner_clearance"]["ft"]
        corners = []
        for (x, y), ss in nodes.items():
            names = {s["street"] for s in ss}
            if len(ss) >= 3 or len(names) >= 2:
                r = max(s["half"] for s in ss) + ft(corner_ft)
                corners.append(Point(x, y).buffer(r))
        if corners:
            excl.append(unary_union(corners))
        print("  %d intersections cleared" % len(corners), file=sys.stderr)

    P = R["point_obstructions"]
    for fname, key in (("hydrants.geojson", "hydrant_ft"), ("transit.geojson", "bus_stop_ft"),
                       ("bikeracks.geojson", "bike_rack_ft")):
        pts = [transform(to_m, shape(f["geometry"])) for f in load_geojson(os.path.join(gis, fname), required=False)]
        pts = [p for p in pts if p.intersects(bbox)]
        if pts:
            excl.append(unary_union([p.buffer(ft(P[key])) for p in pts]))
        print("  %-18s %4d points, %s ft clear" % (fname, len(pts), P[key]), file=sys.stderr)

    CZ = R["curb_zones"]
    for f in load_geojson(os.path.join(field, "curb_zones.geojson"), required=False):
        if (f["properties"].get("color") or "").lower() in CZ["colors_excluded"]:
            excl.append(transform(to_m, shape(f["geometry"])).buffer(ft(CZ["adjacent_ft"])))
    for f in load_geojson(os.path.join(field, "exclusions.geojson"), required=False):
        g = transform(to_m, shape(f["geometry"]))
        pr = f["properties"]
        if g.geom_type == "Point":
            g = g.buffer(ft(pr.get("radius_ft", 3)))
        elif g.geom_type in ("LineString", "MultiLineString"):
            g = g.buffer(ft(pr.get("width_ft", 3)) / 2)
        excl.append(g)

    usable = sidewalk.difference(unary_union(excl)) if excl else sidewalk
    print("  sidewalk %.1f ha, usable after exclusions %.1f ha" %
          (sidewalk.area / 1e4, usable.area / 1e4), file=sys.stderr)

    # ---- zoning ---------------------------------------------------------
    zfeat = load_zoning(os.path.join(repo, "index.html"))
    zgeoms = [make_valid(transform(to_m, shape(f["geometry"]))) for f in zfeat]
    ztree = STRtree(zgeoms)
    snap = R["zoning"]["snap_m"]

    def zone_for(pt):
        cand = ztree.query(pt.buffer(snap))
        best, bd = None, snap + 1
        for i in cand:
            d = zgeoms[i].distance(pt)
            if d < bd:
                best, bd = zfeat[i]["properties"], d
        return best, bd

    # ---- measured widths ------------------------------------------------
    measured = {}
    wcsv = os.path.join(field, "sidewalk_widths.csv")
    if os.path.exists(wcsv):
        with open(wcsv, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                measured[(r["centerlineid"].strip(), r["side"].strip().upper()[0])] = float(r["width_ft"])
        print("  %d measured block-face widths" % len(measured), file=sys.stderr)

    # ---- block faces ----------------------------------------------------
    PT = R["path_of_travel"]
    bset = ft(R["building_setback"]["ft"]) if R["building_setback"].get("enabled", True) else 0
    cset = ft(R["curb_setback"]["ft"]) if R["curb_setback"].get("enabled", True) else 0
    campable_cats = set(R["zoning"]["campable_categories"])
    positions = ["curb", "building"] if PT.get("position", "best") == "best" else [PT["position"]]

    placed = []          # kept rectangles (metres)
    placed_tree = None
    faces, sites = [], []
    tally = Counter()

    print("placing %gx%g ft footprints ..." % (short_ft, long_ft), file=sys.stderr)
    for s in segs:
        for side in ("L", "R"):
            curb = offset(s["line"], s["half"], side)
            if curb is None or curb.length < long_m:
                continue
            # sidewalk width: curb line -> property line, sampled every 3 m
            n = max(3, int(curb.length // 3))
            ds = [property_line.distance(curb.interpolate(i / (n - 1), normalized=True)) for i in range(n)]
            ds.sort()
            w_m = ds[len(ds) // 2]
            w_src = s["width_source"]
            key = (s["id"], side)
            if key in measured:
                w_m, w_src = ft(measured[key]), "measured"
            w_ft = w_m / FT
            if w_ft > 40:            # curb line is not next to a parcel (park, rail, freeway)
                why["no property line within 40 ft"] += 1
                continue
            path_ft = PT["wide_sidewalk_path_ft"] if w_ft >= PT["wide_sidewalk_threshold_ft"] else PT["narrow_sidewalk_path_ft"]
            depth_m = w_m - cset - bset - ft(path_ft)

            mid = curb.interpolate(0.5, normalized=True)
            zp, zd = zone_for(mid)
            cat = zp["c"] if zp else None
            in_zone = cat in campable_cats

            face = {
                "id": key[0] + side, "street": s["street"], "side": side,
                "pavement_ft": s["pav_ft"], "width_ft": round(w_ft, 1), "width_source": w_src,
                "path_ft": path_ft, "depth_ft": round(depth_m / FT, 1),
                "zone": zp["z"] if zp else None, "district": zp["d"] if zp else None,
                "cat": cat, "zone_dist_m": round(zd, 1) if zp else None,
                "campable_zone": in_zone, "count": 0, "placement": None,
            }
            if depth_m < short_m:
                why["strip too shallow for footprint"] += 1
            elif not (in_zone or args.all_zones):
                why["not a campable zoning category"] += 1
            else:
                best = (0, None, [])
                for pos in positions:
                    d0 = cset + short_m / 2 if pos == "curb" else w_m - bset - short_m / 2
                    line = offset(s["line"], s["half"] + d0, side)
                    if line is None:
                        continue
                    rects = []
                    k = 0
                    st = long_m / 2
                    while st + long_m / 2 <= line.length + 1e-6:
                        r = rect_along(line, st, long_m, short_m)
                        if r is not None and r.within(usable):
                            hit = placed_tree.query(r) if placed_tree is not None else []
                            if not any(placed[i].intersection(r).area > 0.05 for i in hit):
                                rects.append(r)
                        st += long_m
                    if len(rects) > best[0]:
                        best = (len(rects), pos, rects)
                if best[0] == 0:
                    why["no full footprint clears the exclusions"] += 1
                face["count"], face["placement"] = best[0], best[1]
                for i, r in enumerate(best[2]):
                    placed.append(r)
                    sites.append({"type": "Feature", "geometry": mapping(transform(to_ll, r)),
                                  "properties": {"face": face["id"], "n": i + 1, "street": s["street"],
                                                 "side": side, "zone": face["zone"], "cat": cat,
                                                 "placement": best[1], "width_source": w_src}})
                if best[2]:
                    placed_tree = STRtree(placed)
                tally[(cat, face["zone"], s["street"])] += best[0]
            faces.append({"type": "Feature", "geometry": mapping(transform(to_ll, curb)), "properties": face})

    # ---- outputs --------------------------------------------------------
    total = sum(f["properties"]["count"] for f in faces)
    by_cat = Counter()
    by_zone = Counter()
    by_street = Counter()
    for (cat, zone, street), n in tally.items():
        by_cat[cat or "none"] += n
        by_zone[zone or "none"] += n
        by_street[street] += n
    flagged = sum(1 for f in faces if f["properties"]["width_source"] == "default" and f["properties"]["count"])

    summary = {
        "bbox": [W, S, E, N], "footprint_ft": [short_ft, long_ft],
        "total_locations": total,
        "by_category": {CAT_NAME.get(k, k): v for k, v in by_cat.most_common()},
        "by_zoning_district": dict(by_zone.most_common()),
        "by_street": dict(by_street.most_common()),
        "block_faces": len(faces),
        "faces_with_locations": sum(1 for f in faces if f["properties"]["count"]),
        "faces_using_default_pavement_width": flagged,
        "faces_skipped": dict(why),
        "sidewalk_area_ha": round(sidewalk.area / 1e4, 2),
        "usable_area_ha": round(usable.area / 1e4, 2),
        "rules": R,
    }
    with open(os.path.join(out, "sites.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": sites}, fh, separators=(",", ":"))
    with open(os.path.join(out, "faces.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": faces}, fh, separators=(",", ":"))
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)

    if not args.no_inject and not args.footprint:
        inject(os.path.join(repo, "index.html"), sites, faces, summary, args.area_name)

    print("\n%d locations for a %gx%g ft footprint in the bbox" % (total, short_ft, long_ft))
    for k, v in summary["by_category"].items():
        print("  %-28s %5d" % (k, v))
    print("top streets:")
    for k, v in by_street.most_common(12):
        print("  %-28s %5d" % (k, v))
    print("block faces: %d, with locations: %d, using default pavement width: %d" %
          (len(faces), summary["faces_with_locations"], flagged))
    for k, v in why.most_common():
        print("  skipped - %s: %d" % (k, v))
    print("wrote", out)


if __name__ == "__main__":
    main()
