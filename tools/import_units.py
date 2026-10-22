"""Generic import for countries whose code areas follow admin units.
Usage:
  python tools/import_units.py <iso> <boundaries.geojson> [--tol 0.012] [--min-area 0.0004] [--wrap]

Reads (hand-maintained, in src/<iso>/):
  units.csv    shape,name,codes   shape = shapeName in the geojson, codes ";"-separated.
               Optional: without it, every unit takes the code of the nearest anchor
               (zones that predate today's admin units, e.g. Poland's pre-1999 voivodeships);
               seeds.csv (code,lat,lon) then adds extra towns per code for that assignment.
  anchors.csv  code,group,city,admin,lat,lon,cities
               admin = shape of the unit that holds the main city; lat/lon optional
               (default: that unit's label point); cities ";"-separated.
Writes src/<iso>/admin.json and src/<iso>/codes.csv; meta.json stays hand-edited.
--wrap shifts negative longitudes by +360 (Russia's Chukotka crosses the antimeridian)."""
import argparse, csv, json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_indonesia as simp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def label_point(rings):
    big = max(rings, key=simp.area)
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(big, big[1:] + big[:1]):
        f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if abs(a) < 1e-12: return big[0]
    return [cx / (3 * a), cy / (3 * a)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso"); ap.add_argument("geojson")
    ap.add_argument("--tol", type=float, default=0.012)
    ap.add_argument("--min-area", type=float, default=0.0004)
    ap.add_argument("--wrap", action="store_true")
    a = ap.parse_args()
    simp.TOL, simp.MIN_AREA = a.tol, a.min_area
    d = ROOT / "src" / a.iso.lower()

    feats = json.load(open(a.geojson, encoding="utf-8"))["features"]
    shapes = {}
    for f in feats:
        g = f["geometry"]
        poly = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        if a.wrap:
            poly = [[[[x + 360 if x < 0 else x, y] for x, y in r] for r in p] for p in poly]
        name, n = f["properties"]["shapeName"], 2
        key = name
        while key in shapes: key, n = f"{name} #{n}", n + 1      # same name in two regions (Polish powiats)
        shapes[key] = simp.simplify(poly)

    anchors = list(csv.DictReader(open(d / "anchors.csv", encoding="utf-8")))
    def containing(x, y):
        def inside(r):
            c = False
            for (xi, yi), (xj, yj) in zip(r, r[-1:] + r[:-1]):
                if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
            return c
        hit = [s for s, rings in shapes.items() if any(inside(r) for r in rings)]
        if hit: return hit[0]
        return min(shapes, key=lambda s: (label_point(shapes[s])[0] - x) ** 2 + (label_point(shapes[s])[1] - y) ** 2)
    for r in anchors:
        if not r.get("admin"):              # no admin given: the unit under the city
            r["admin"] = containing(float(r["lon"]), float(r["lat"]))
        if r["admin"] not in shapes: sys.exit(f"anchor {r['code']}: unknown shape {r['admin']!r}")
        if not r.get("lat"):
            r["lon"], r["lat"] = label_point(shapes[r["admin"]])
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])

    units = {}
    if (d / "units.csv").exists():
        for r in csv.DictReader(open(d / "units.csv", encoding="utf-8")):
            if r["shape"] not in shapes: sys.exit(f"units.csv: unknown shape {r['shape']!r}")
            units[r["shape"]] = (r["name"] or r["shape"], [c.strip() for c in r["codes"].split(";") if c.strip()])
        missing = set(shapes) - set(units)
        if missing: sys.exit(f"units.csv: shapes without codes: {sorted(missing)}")
    else:  # nearest anchor (or extra seed town, seeds.csv: code,lat,lon) to each unit's label point
        seeds = [{"code": r["code"], "lat": r["lat"], "lon": r["lon"]} for r in anchors]
        if (d / "seeds.csv").exists():
            seeds += [{"code": r["code"], "lat": float(r["lat"]), "lon": float(r["lon"])}
                      for r in csv.DictReader(open(d / "seeds.csv", encoding="utf-8"))]
        k = math.cos(math.radians(sum(r["lat"] for r in anchors) / len(anchors)))
        for s, rings in shapes.items():
            x, y = label_point(rings)
            best = min(seeds, key=lambda r: ((r["lon"] - x) * k) ** 2 + (r["lat"] - y) ** 2)
            units[s] = (s.split(" #")[0], [best["code"]])

    admin = {s: {"name": units[s][0], "rings": rings, "codes": units[s][1]} for s, rings in shapes.items()}
    hosted = {c for _, cs in units.values() for c in cs}
    rows = []
    for r in anchors:
        if r["code"] not in hosted: print(f"warning: {r['code']} ({r['city']}) is hosted by no unit")
        rows.append([r["code"], r["group"], r["city"], r.get("local", ""), r["admin"],
                     round(r["lat"], 3), round(r["lon"], 3), r.get("cities", "")])
    for c in sorted(hosted - {r["code"] for r in anchors}): sys.exit(f"code {c} has units but no anchor")
    (d / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(d / "codes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"]); w.writerows(rows)
    pts = sum(len(r) for x in admin.values() for r in x["rings"])
    print(f"{a.iso}: {len(rows)} codes, {len(admin)} units, {pts} points")


if __name__ == "__main__":
    main()
