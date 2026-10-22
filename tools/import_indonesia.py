"""Build src/id/ from a local clone of TGM-hub/indonesia-kabupaten.
Usage:  python tools/import_indonesia.py <path to indonesia-kabupaten>
Admin units are the 514 kabupaten/kota (ADM2), so answers are judged on the
real code areas, not on nearest-city cells. Units with no known code inherit
their province's block so the map has no holes (they are never a correct code).
Re-runnable: it overwrites src/id/codes.csv and src/id/admin.json, and keeps
src/id/meta.json (hand-edited) if it already exists."""
import csv, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOL = 0.012            # Douglas-Peucker tolerance, degrees
MIN_AREA = 0.0004      # drop islets below ~2 km x 2 km, except a unit's largest ring
CITY = {"021": "Jakarta"}   # hand overrides of the main city name


def dp(pts, tol):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1e-12
    i, dmax = 0, -1
    for k in range(1, len(pts) - 1):
        d = abs(dy * pts[k][0] - dx * pts[k][1] + b[0] * a[1] - b[1] * a[0]) / n
        if d > dmax: i, dmax = k, d
    if dmax <= tol: return [a, b]
    return dp(pts[:i + 1], tol)[:-1] + dp(pts[i:], tol)


def area(r):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]))) / 2


def simplify(poly):
    rings = [r for p in poly for r in p[:1]]            # outer rings only
    rings = [r[:-1] if r[0] == r[-1] else r for r in rings]
    big = max(rings, key=area)
    out = []
    for r in rings:
        if r is not big and area(r) < MIN_AREA: continue
        # a closed ring has no baseline: split it at the vertex farthest from the first
        far = max(range(len(r)), key=lambda k: (r[k][0] - r[0][0]) ** 2 + (r[k][1] - r[0][1]) ** 2)
        s = dp(r[:far + 1], TOL)[:-1] + dp(r[far:] + [r[0]], TOL)[:-1]
        if len(s) < 3: s = r if len(r) <= 8 else r[::max(1, len(r) // 8)]
        out.append([[round(x, 3), round(y, 3)] for x, y in s])
    return out


def main(repo):
    repo = Path(repo)
    rows = list(csv.DictReader(open(repo / "data" / "kabupaten.csv", encoding="utf-8")))
    shapes = json.load(open(repo / "data" / "shapes.json", encoding="utf-8"))

    admin, members = {}, defaultdict(list)
    prov_groups = defaultdict(Counter)
    for r in rows:
        name = ("Kota " if r["type"] == "kota" else "") + r["name"]
        codes = [p.strip() for p in r["phone"].split(";") if p.strip()]
        rings = simplify(shapes[r["code"]]["poly"])
        a = area_total = sum(area(x) for x in rings)
        admin[r["code"]] = {"name": name, "region": r["province"], "rings": rings, "codes": codes}
        for c in codes:
            members[c].append((r, shapes[r["code"]]["pt"], a))
            prov_groups[r["province"]][c[1]] += 1
    for k, a in admin.items():
        if not a["codes"]:
            a["groups"] = [prov_groups[a["region"]].most_common(1)[0][0]]

    out = []
    for code in sorted(members, key=lambda c: (c[1], c)):
        m = members[code]
        kota = [x for x in m if x[0]["type"] == "kota"]
        main_unit = (kota or sorted(m, key=lambda x: -x[2]))[0][0]
        city = main_unit["name"]          # kabupaten name (Garut), not its seat (Tarogong Kidul)
        w = sum(x[2] for x in m) or 1
        lon = sum(x[1][0] * x[2] for x in m) / w
        lat = sum(x[1][1] * x[2] for x in m) / w
        if kota: lon, lat = kota[0][1]                 # anchor on the city when there is one
        city = CITY.get(code, city)
        others = []
        for x in m:
            n = x[0]["name"]
            if n and n != city and n not in others: others.append(n)
        out.append([code, code[1], city, "", main_unit["code"], round(lat, 3), round(lon, 3), ";".join(others[:3])])

    d = ROOT / "src" / "id"; d.mkdir(parents=True, exist_ok=True)
    (d / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(d / "codes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"]); w.writerows(out)
    pts = sum(len(r) for a in admin.values() for r in a["rings"])
    print(f"ID: {len(out)} codes, {len(admin)} units, {pts} points")


if __name__ == "__main__":
    main(sys.argv[1])
