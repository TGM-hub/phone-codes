"""Countries built from Google's libphonenumber geocoding data (Apache 2.0):
resources/geocoding/en/<cc>.txt lists "<cc><area code>|City, Province".
Usage:
  python tools/import_lpn.py <ISO> <lpn file> <boundaries ADM2 geojson> <cities csv> [--tol 0.012] [--min-area 0.0004]
<cities csv> = lat,lon,name,admin1,admin2,cc (GeoNames cities1000, as shipped in the reverse_geocoder package).
Fixes per country are in FIX below (src/<iso>/places.csv, optional: code,lat,lon overrides a town's position).
Each admin unit takes the code(s) of the nearest code town (several when towns share a place),
plus every code whose town lies inside it. Writes src/<iso>/admin.json and codes.csv; meta.json is hand-edited."""
import csv, json, math, re, sys, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_indonesia as simp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CC = {"AR": "54", "MX": "52", "IT": "39", "PT": "351", "BG": "359"}
NO_PROV = {"BG"}          # BG: the text after the comma is an abbreviated province, ignored
GROUP_LEN = {"PT": 2}     # PT: every code starts with 2, the block is the first two digits
CITY_FIX = {"PT": {"21": "Lisboa", "252": "Vila Nova de Famalicão", "256": "São João da Madeira", "279": "Torre de Moncorvo"}}
SKIP = {"PT": {"291", "292", "295", "296"}}   # Madeira and the Azores: off the mainland map
PROV_STRICT = {}
REGION_NAMES = {}
AR_MERGE = {"2643": "264", "2644": "264", "2645": "264", "3433": "343", "3434": "343", "3853": "385",
            "3872": "387", "3874": "387", "3875": "387", "3883": "388", "3884": "388", "2974": "297", "2975": "297",
            "2976": "297", "2984": "298", "2985": "298", "3534": "353", "3535": "353", "3536": "353",
            "2204": "220", "2205": "220"}         # per country: province abbreviation -> name          # a town of the same name in another province is never taken


def norm(s):
    s = unicodedata.normalize("NFD", s)
    return re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in s if not unicodedata.combining(c)).lower()).split()


def code_of(iso, raw):
    """libphonenumber prefix -> area code as dialled nationally (None = skip)"""
    if iso == "AR":
        if raw == "1": return "11"
        if raw == "28": return "280"
        # libphonenumber splits some 3-digit codes by exchange: 2643/2644/2645 are all 264 San Juan
        return AR_MERGE.get(raw[:4], raw[:4])
    if raw in SKIP.get(iso, ()): return None
    if iso == "BG":                          # main towns only (codes of 1-3 digits); Silistra's 86x are one code
        if len(raw) > 3: return None
        return "86" if raw.startswith("86") else raw
    if iso == "MX":
        if len(raw) == 2: return raw if raw in ("33", "55", "81") else None   # other 2-digit lines are fall-backs
        return raw
    return raw


def label_point(rings):
    big = max(rings, key=simp.area)
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(big, big[1:] + big[:1]):
        f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if abs(a) < 1e-12: return big[0]
    return [cx / (3 * a), cy / (3 * a)]


def inside(x, y, ring):
    c = False
    for (xi, yi), (xj, yj) in zip(ring, ring[-1:] + ring[:-1]):
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
    return c


def main():
    a = sys.argv[1:]
    iso, lpn, gj, cities_csv = a[0].upper(), a[1], a[2], a[3]
    if "--tol" in a: simp.TOL = float(a[a.index("--tol") + 1])
    if "--min-area" in a: simp.MIN_AREA = float(a[a.index("--min-area") + 1])
    d = ROOT / "src" / iso.lower()
    cc = CC[iso]

    # 1. codes and their places
    codes = {}
    for line in open(lpn, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        p, text = line.split("|", 1)
        code = code_of(iso, p[len(cc):])
        if not code: continue
        place, _, prov = text.rpartition(", ")
        if not place: place, prov = text, ""
        if iso in NO_PROV: place, prov = (place or text), ""
        codes.setdefault(code, []).append((place, prov))

    # 2. town positions from the cities file, matched on name (and province when it helps)
    towns = [r for r in csv.DictReader(open(cities_csv, encoding="utf-8")) if r["cc"] == iso]
    by_name = {}
    for r in towns: by_name.setdefault(" ".join(norm(r["name"])), []).append(r)
    fix = {}
    if (d / "places.csv").exists():
        fix = {r["code"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(d / "places.csv", encoding="utf-8"))}
    rows, missing = [], []
    for code in sorted(codes, key=lambda c: (len(c), c)):
        place, prov = codes[code][0]
        names = [re.sub(r"\(.*?\)", "", n).strip() for n in re.split(r"/", place)]
        pos = fix.get(code)
        for n in names:
            if pos: break
            cand = by_name.get(" ".join(norm(n)), [])
            if prov:
                pv = set(norm(prov))
                best = [r for r in cand if pv & set(norm(r["admin1"]))]
                cand = best if best or not PROV_STRICT.get(iso, True) else []
            if not cand and prov:               # looser: same province, one name contains the other
                q, pv = " ".join(norm(n)), set(norm(prov))
                cand = [r for r in towns if pv & set(norm(r["admin1"])) and len(q) > 3
                        and (f" {q} " in f" {' '.join(norm(r['name']))} " or f" {' '.join(norm(r['name']))} " in f" {q} ")]
                cand.sort(key=lambda r: abs(len(r["name"]) - len(n)))
            if cand: pos = (float(cand[0]["lat"]), float(cand[0]["lon"]))
        if not pos: missing.append(f"{code}|{place}, {prov}"); continue
        city = CITY_FIX.get(iso, {}).get(code, names[0])
        others = sorted({n for pl, _ in codes[code] for n in re.split(r"/", pl) if n.strip() and n.strip() != city})
        rows.append({"code": code, "city": city, "prov": prov, "lat": pos[0], "lon": pos[1], "cities": ";".join(others)})
    if missing:
        print("no position (add them to places.csv):"); [print("  " + m) for m in missing]
        sys.exit(1)

    # 3. admin units
    feats = json.load(open(gj, encoding="utf-8"))["features"]
    shapes = {}
    for f in feats:
        g = f["geometry"]
        poly = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        name, n = f["properties"]["shapeName"], 2
        key = name
        while key in shapes: key, n = f"{name} #{n}", n + 1
        shapes[key] = simp.simplify(poly)
    k = math.cos(math.radians(sum(r["lat"] for r in rows) / len(rows)))
    place_of = {}
    for r in rows: place_of.setdefault((round(r["lat"], 3), round(r["lon"], 3)), []).append(r["code"])
    seeds = [(lat, lon, cs) for (lat, lon), cs in place_of.items()]
    admin = {}
    for s, rings in shapes.items():
        x, y = label_point(rings)
        lat, lon, cs = min(seeds, key=lambda t: ((t[1] - x) * k) ** 2 + (t[0] - y) ** 2)
        admin[s] = {"name": s.split(" #")[0], "rings": rings, "codes": list(cs)}
    for r in rows:                          # a code always covers the unit around its own town
        hit = [s for s, rings in shapes.items() if any(inside(r["lon"], r["lat"], ring) for ring in rings)]
        unit = hit[0] if hit else min(shapes, key=lambda s: ((label_point(shapes[s])[0] - r["lon"]) * k) ** 2 + (label_point(shapes[s])[1] - r["lat"]) ** 2)
        if r["code"] not in admin[unit]["codes"]: admin[unit]["codes"].append(r["code"])
        r["admin"] = unit
    for s_, u in admin.items():              # region shown in the fiches: the province of the unit's code town
        town = next((r for r in rows if r["code"] == u["codes"][0]), None)
        if town and town["prov"]: u["region"] = REGION_NAMES.get(iso, {}).get(town["prov"], town["prov"])
    (d / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(d / "codes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"])
        for r in rows: w.writerow([r["code"], r["code"].lstrip("0")[:GROUP_LEN.get(iso, 1)], r["city"], "", r["admin"], round(r["lat"], 3), round(r["lon"], 3), r["cities"]])
    twins = [cs for cs in place_of.values() if len(cs) > 1]
    print(f"{iso}: {len(rows)} codes, {len(admin)} units, twins (same town): {twins}")


if __name__ == "__main__":
    main()
