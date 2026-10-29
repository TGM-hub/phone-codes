"""Italy: the 231 telephone districts (San Marino's 0549 left out), rebuilt from the comuni.
Usage:  python tools/import_italy.py <geoBoundaries ITA ADM4 geojson (comuni)> <cities1000 csv>
Needs shapely (pip install shapely) to merge the comuni of each district.
Reads src/it/main.txt (prefix|main town) and src/it/towns.txt (prefix:towns), both from the Italian
Wikipedia table "Prefissi telefonici italiani" (column Distretto and Aree locali, read 2026-10-29).
Each listed town is placed on its comune (or on the cities file when it is not a comune any more);
every comune then joins the district of the nearest listed town, a comune named in the table joins
its own district. Writes src/it/admin.json and src/it/codes.csv."""
import csv, json, math, re, sys, unicodedata
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_indonesia as simp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "src" / "it"
ALIAS = {"rossano": "corigliano rossano", "corigliano calabro": "corigliano rossano", "porretta terme": "alto reno terme",
         "bazzano": "valsamoggia", "fiera di primiero": "primiero san martino di castrozza", "valle mosso": "valdilana",
         "solbiate": "solbiate con cagno", "san marino": None,
         "reggio emilia": "reggio nell emilia", "reggio calabria": "reggio di calabria"}


def norm(s):
    s = unicodedata.normalize("NFD", s.replace("’", "'"))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c)).lower()).split())


def main(gj, cities_csv):
    main_town = dict(x.split("|", 1) for x in (D / "main.txt").read_text(encoding="utf-8").strip().split(";"))
    towns = {}
    for x in (D / "towns.txt").read_text(encoding="utf-8").strip().split(";"):
        p, t = x.split(":", 1)
        towns[p] = [s.strip() for s in t.split(",") if s.strip()]
    main_town.pop("0549", None); towns.pop("0549", None)
    feats = json.load(open(gj, encoding="utf-8"))["features"]
    comuni = []
    for f in feats:
        g = shape(f["geometry"])
        if not g.is_valid: g = g.buffer(0)
        c = g.representative_point()
        comuni.append({"name": f["properties"]["shapeName"], "key": norm(f["properties"]["shapeName"]), "geom": g, "x": c.x, "y": c.y})
    by_name = {}
    for i, c in enumerate(comuni): by_name.setdefault(c["key"], []).append(i)
    cities = {}
    for r in csv.DictReader(open(cities_csv, encoding="utf-8")):
        if r["cc"] == "IT": cities.setdefault(norm(r["name"]), []).append((float(r["lon"]), float(r["lat"])))
    k = math.cos(math.radians(42))

    def locate(name, near=None):
        key = norm(name)
        key = ALIAS.get(key, key)
        if key is None: return None, None
        cands = [(comuni[i]["x"], comuni[i]["y"], i) for i in by_name.get(key, [])] or \
                [(x, y, None) for x, y in cities.get(key, [])]
        if not cands: return None, None
        if near: cands.sort(key=lambda c: ((c[0] - near[0]) * k) ** 2 + (c[1] - near[1]) ** 2)
        return (cands[0][0], cands[0][1]), cands[0][2]

    seeds, own, rows, missing = [], {}, [], []
    for p, town in main_town.items():
        pos, idx = locate(town)
        if not pos: missing.append(f"{p} {town} (main)"); continue
        seeds.append((pos, p)); own.setdefault(idx, p)
        rows.append({"code": p, "city": town, "lon": pos[0], "lat": pos[1], "others": [t for t in towns.get(p, []) if norm(t) != norm(town)]})
        for t in towns.get(p, []):
            if norm(t) == norm(town): continue
            tp, ti = locate(t, near=pos)
            if not tp: missing.append(f"{p} {t}"); continue
            seeds.append((tp, p))
            if ti is not None: own.setdefault(ti, p)
    if [m for m in missing if "(main)" in m]: sys.exit("main towns not found: " + ", ".join(m for m in missing if "(main)" in m))
    if missing: print("towns not placed (skipped):", "; ".join(missing))
    parts = {}
    for i, c in enumerate(comuni):
        p = own.get(i) or min(seeds, key=lambda s: ((s[0][0] - c["x"]) * k) ** 2 + (s[0][1] - c["y"]) ** 2)[1]
        parts.setdefault(p, []).append(c["geom"])
    admin = {}
    for r in rows:
        g = unary_union(parts[r["code"]]).buffer(0)
        m = mapping(g)
        poly = m["coordinates"] if m["type"] == "MultiPolygon" else [m["coordinates"]]
        poly = [[[list(pt) for pt in ring] for ring in p] for p in poly]
        admin[r["code"]] = {"name": r["city"], "rings": simp.simplify(poly), "codes": [r["code"]]}
    json.dump(admin, open(D / "admin.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    with open(D / "codes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"])
        for r in sorted(rows, key=lambda r: r["code"]):
            w.writerow([r["code"], r["code"][1], r["city"], "", r["code"], round(r["lat"], 3), round(r["lon"], 3), ";".join(r["others"])])
    print(f"IT: {len(rows)} districts, {sum(len(r) for a in admin.values() for r in a['rings'])} points")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
