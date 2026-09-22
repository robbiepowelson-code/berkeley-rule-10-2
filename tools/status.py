#!/usr/bin/env python3
"""
status.py - one screen that says what is working and what is not.

  python3 tools/status.py

Checks, in order: the local repo (commits waiting to push, stray git lock
files), GitHub (does origin/main have the latest commit), GitHub Pages (does
the live site serve the latest index.html, review.html, and which layers are
in it), the data files every tool needs, and the model outputs.
Each line is OK / WAIT / FAIL with the one command that fixes it.
"""
import json, os, re, subprocess, sys, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://robbiepowelson-code.github.io/berkeley-rule-10-2/"
RAW = "https://raw.githubusercontent.com/robbiepowelson-code/berkeley-rule-10-2/main/"
GREEN, YELLOW, RED, DIM, END = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
rows = []

def ok(label, detail=""):   rows.append((GREEN + " OK  " + END, label, detail))
def wait(label, detail=""): rows.append((YELLOW + "WAIT " + END, label, detail))
def fail(label, detail=""): rows.append((RED + "FAIL " + END, label, detail))

def git(*a):
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True)
    return r.stdout.strip(), r.returncode

def fetch(url, timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url + ("&" if "?" in url else "?") + "nocache=%d" % os.getpid(), headers={"Cache-Control": "no-cache"}), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)

# ---- local repo -------------------------------------------------------
locks = [f for f in ("index.lock", "HEAD.lock") if os.path.exists(os.path.join(REPO, ".git", f))]
if locks:
    fail("git lock file present", "rm .git/" + " .git/".join(locks))
else:
    ok("no stray git lock files")
head, _ = git("rev-parse", "--short", "HEAD")
subject, _ = git("log", "-1", "--format=%s")
dirty, _ = git("status", "--porcelain", "--untracked-files=no")
if dirty:
    wait("uncommitted changes", "\n        " + dirty.replace("\n", "\n        "))
else:
    ok("working tree clean", "HEAD %s  %s" % (head, subject[:60]))

# ---- github -----------------------------------------------------------
git("fetch", "-q", "origin", "main")
ahead, _ = git("rev-list", "--count", "origin/main..HEAD")
behind, _ = git("rev-list", "--count", "HEAD..origin/main")
if ahead and ahead != "0":
    fail("%s commit(s) not on GitHub yet" % ahead, "git push origin main")
elif behind and behind != "0":
    wait("GitHub is %s commit(s) ahead of this Mac" % behind, "git pull")
else:
    ok("GitHub has the latest commit")

# ---- pages ------------------------------------------------------------
st, live = fetch(SITE + "index.html")
local_html = open(os.path.join(REPO, "index.html"), encoding="utf-8").read()
def block(html, name):
    m = re.search(r"var %s = (.*?);\n/\* %s:END" % (name, name), html, re.S)
    if not m: return None
    try: return json.loads(m.group(1))
    except Exception: return "bad"
if st != 200:
    fail("live map not reachable (HTTP %s)" % st, SITE + "index.html")
else:
    same = live.strip() == local_html.strip()
    (ok if same else wait)("live map %s the local index.html" % ("matches" if same else "is older than"),
                           "" if same else "push, then wait 1-2 min for GitHub Pages; hard-reload (Cmd+Shift+R)")
    for name, what in (("SITES", "surveyed-site pins"), ("CAMPABLE", "tent layer (5x7)"), ("CAMPABLE_PINS", "alternative-footprint pins")):
        b = block(live, name)
        if b is None or b == "bad": fail("live map: %s block missing" % what)
        elif not b: wait("live map: %s is empty" % what, "run tools/campable_sites.py" + (" --footprint 7x16 --pins" if name.endswith("PINS") else "") + " and push")
        else:
            n = len(b) if isinstance(b, list) else b.get("total", "?")
            ok("live map: %s (%s)" % (what, n))
st2, rv = fetch(SITE + "review.html")
(ok if st2 == 200 and "Block-face review" in rv else fail)("live review tool", SITE + "review.html")

# ---- data -------------------------------------------------------------
need = ["data/gis/row.geojson", "data/gis/centerlines.geojson", "data/gis/transit.geojson", "data/gis/hydrants.geojson",
        "data/gis/bikeracks.geojson", "data/gis/osm-points.geojson", "data/gis/osm-ways.geojson", "data/gis/osm-buildings-1.geojson",
        "tools/ar102_rules.json", "data/campable/faces.geojson", "data/campable/sites.geojson", "data/campable/summary.json"]
missing = [p for p in need if not os.path.exists(os.path.join(REPO, p))]
if missing: fail("data files missing", ", ".join(missing))
else: ok("all data files present")
try:
    import shapely, pyproj
    ok("shapely %s / pyproj %s installed" % (shapely.__version__, pyproj.__version__))
except ImportError:
    fail("shapely/pyproj not installed", "pip3 install shapely pyproj")
sp = os.path.join(REPO, "data/campable/summary.json")
if os.path.exists(sp):
    s = json.load(open(sp))
    ok("model: %d locations for %sx%s ft on %d of %d faces" % (s["total_locations"], s["footprint_ft"][0], s["footprint_ft"][1], s["faces_with_locations"], s["block_faces"]))
field = os.path.join(REPO, "data/field")
revs = sorted(f for f in os.listdir(field) if f.startswith("review") and f.endswith(".geojson")) if os.path.isdir(field) else []
widths = os.path.join(field, "sidewalk_widths.csv")
nw = sum(1 for _ in open(widths)) - 1 if os.path.exists(widths) else 0
(ok if (revs or nw) else wait)("field data: %d tape widths, %d review export(s)" % (nw, len(revs)), "" if (revs or nw) else "review.html -> Export -> save into data/field/")
lb = block(local_html, "CAMPABLE")
if lb and os.path.exists(sp) and lb.get("total") != s["total_locations"]:
    wait("index.html tent layer (%s) differs from data/campable (%s)" % (lb.get("total"), s["total_locations"]), "python3 tools/campable_sites.py")

# ---- print ------------------------------------------------------------
print("\nWhere Rule 10.2 Applies - status\n")
for tag, label, detail in rows:
    print("  %s %s" % (tag, label))
    if detail: print("        " + DIM + detail + END)
n_fail = sum(1 for r in rows if "FAIL" in r[0]); n_wait = sum(1 for r in rows if "WAIT" in r[0])
print("\n  %s%d problem(s), %d waiting%s\n" % (RED if n_fail else (YELLOW if n_wait else GREEN), n_fail, n_wait, END))
sys.exit(1 if n_fail else 0)
