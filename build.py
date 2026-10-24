"""Build data/<iso>.json and data/countries.json from src/<iso>/.
Standard library only.  Usage:  python build.py
Blocking errors stop the build; warnings are printed and the build goes on."""
import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC, OUT = ROOT / "src", ROOT / "data"
errors, warnings = [], []


def err(iso, msg): errors.append(f"[{iso}] {msg}")
def warn(iso, msg): warnings.append(f"[{iso}] {msg}")


def bbox(rings):
    xs = [p[0] for r in rings for p in r]; ys = [p[1] for r in rings for p in r]
    return [min(xs), min(ys), max(xs), max(ys)]


def label_point(rings):
    """Centroid of the largest ring (good enough for a label)."""
    def area_c(r):
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
            f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
        return a / 2, cx, cy
    best = max(rings, key=lambda r: abs(area_c(r)[0]))
    a, cx, cy = area_c(best)
    if abs(a) < 1e-9: return [round(best[0][0], 2), round(best[0][1], 2)]
    return [round(cx / (6 * a), 2), round(cy / (6 * a), 2)]


def bi(iso, obj, field):
    v = obj.get(field)
    if not (isinstance(v, dict) and v.get("fr") and v.get("en")):
        err(iso, f"{field}: needs both 'fr' and 'en'")


def build_country(d):
    iso = d.name.upper()
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    admin_src = json.loads((d / "admin.json").read_text(encoding="utf-8"))
    with open(d / "codes.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if meta.get("iso") != iso: err(iso, f"meta.iso is {meta.get('iso')!r}, folder says {iso}")
    for fld in ("name", "system", "group_label"): bi(iso, meta, fld)
    if "{code}" not in meta.get("display", ""): err(iso, "display must contain {code}")
    group_ids = [g["id"] for g in meta.get("groups", [])]
    if len(group_ids) != len(set(group_ids)): err(iso, "duplicate group id")
    for g in meta.get("groups", []): bi(iso, g, "name")

    codes, seen = [], Counter()
    for n, r in enumerate(rows, 2):
        where = f"codes.csv line {n}"
        code = r["code"].strip()
        if not code.isdigit(): err(iso, f"{where}: code {code!r} is not numeric"); continue
        if r["group"] not in group_ids: err(iso, f"{where}: unknown group {r['group']!r}")
        if r["admin"] not in admin_src: err(iso, f"{where}: unknown admin {r['admin']!r}")
        try: lat, lon = float(r["lat"]), float(r["lon"])
        except ValueError: err(iso, f"{where}: bad lat/lon"); continue
        seen[(code, r["city"])] += 1
        c = {"code": code, "group": r["group"], "city": r["city"], "admin": r["admin"],
             "lat": round(lat, 3), "lon": round(lon, 3)}
        if r.get("local"): c["local"] = r["local"]
        cities = [x.strip() for x in (r.get("cities") or "").split(";") if x.strip()]
        if cities: c["cities"] = cities
        codes.append(c)
    for (code, city), k in seen.items():
        if k > 1: err(iso, f"duplicate row {code} {city}")

    known = {c["code"] for c in codes}
    for a in meta.get("anchors", []):
        if a not in known: err(iso, f"anchor {a} is not a code")
    for pair in meta.get("twins", []):
        for a in pair:
            if a not in known: err(iso, f"twin {a} is not a code")
    for t in meta.get("tips", []):
        bi(iso, {"t": {"fr": t.get("fr"), "en": t.get("en")}}, "t")
        for a in t.get("codes", []):
            if a not in known: err(iso, f"tip '{t.get('title')}' cites unknown code {a}")

    match = meta.get("match", "nearest")
    if match not in ("nearest", "admin"): err(iso, f"match must be 'nearest' or 'admin', not {match!r}")
    group_of = {c["code"]: c["group"] for c in codes}

    # admin units: membership derived from the codes they host (codes.csv admin
    # column, plus the admin's own 'codes' list), plus explicit 'groups'
    by_admin = {}
    for c in codes: by_admin.setdefault(c["admin"], Counter())[c["group"]] += 1
    hosted = Counter()
    admin = {}
    for key, a in admin_src.items():
        rings = [[[round(x, 3), round(y, 3)] for x, y in r] for r in a["rings"]]
        groups = Counter(by_admin.get(key, {}))
        for code in a.get("codes", []):
            if code not in group_of: err(iso, f"admin {key} lists unknown code {code}"); continue
            groups[group_of[code]] += 1; hosted[code] += 1
        for g in a.get("groups", []):
            if g not in group_ids: err(iso, f"admin {key}: unknown group {g}")
            groups[g] += 0
        if not groups: warn(iso, f"admin {key} belongs to no group (drawn, never correct)")
        u = {"name": a["name"], "rings": rings, "bbox": bbox(rings), "label": label_point(rings),
             "groups": [g for g, _ in groups.most_common()] if groups else list(groups)}
        for k in ("local", "region"):
            if a.get(k): u[k] = a[k]
        if a.get("codes"): u["codes"] = a["codes"]
        admin[key] = u
    # optional local-script names (Cyrillic, Greek, Hangul, Thai), shown after the answer:
    # src/<iso>/local.csv  kind,key,local   kind = code (key = code) or admin (key = admin key or name)
    lp = d / "local.csv"
    if lp.exists():
        by_name = {u["name"]: k for k, u in admin.items()}
        seen_c, seen_a = set(), set()
        with open(lp, encoding="utf-8") as f:
            for n, r in enumerate(csv.DictReader(f), 2):
                kind, key, loc = r["kind"].strip(), r["key"].strip(), r["local"].strip()
                if kind == "code":
                    hit = [c for c in codes if c["code"] == key]
                    if not hit: err(iso, f"local.csv line {n}: unknown code {key}")
                    for c in hit: c["local"] = loc
                    seen_c.add(key)
                elif kind == "admin":
                    k = key if key in admin else by_name.get(key)
                    if not k: err(iso, f"local.csv line {n}: unknown admin {key!r}"); continue
                    admin[k]["local"] = loc; seen_a.add(k)
                else: err(iso, f"local.csv line {n}: kind must be code or admin")
        for code in sorted(known - seen_c): warn(iso, f"local.csv: no local name for code {code}")
        for k in sorted(set(admin) - seen_a): warn(iso, f"local.csv: no local name for admin {k}")
    if "real" in meta:
        rl = meta["real"]
        if "{code}" not in rl.get("fmt", "") or "{n}" not in rl.get("fmt", ""): err(iso, "real.fmt needs {code} and {n}")
        if not isinstance(rl.get("total"), int): err(iso, "real.total must be an integer")
    if match == "admin":
        for code in sorted(known - set(hosted)): err(iso, f"code {code} is hosted by no admin unit (match=admin)")

    groups = []
    for g in meta["groups"]:
        members = [k for k, u in admin.items() if g["id"] in u["groups"]]
        if not members: err(iso, f"group {g['id']} has no admin unit"); continue
        boxes = [admin[k]["bbox"] for k in members]
        groups.append({**g, "admins": members,
                       "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                                max(b[2] for b in boxes), max(b[3] for b in boxes)],
                       "n": sum(1 for c in codes if c["group"] == g["id"])})

    # optional middle level: the first sub_len characters of the code
    subs = []
    n = meta.get("sub_len")
    if n:
        bi(iso, meta, "sub_label")
        for sid in sorted({c["code"][:n] for c in codes}):
            members = [c for c in codes if c["code"][:n] == sid]
            gs = {c["group"] for c in members}
            if len(gs) > 1: err(iso, f"sub-block {sid} spans several groups {sorted(gs)}")
            mcodes = {c["code"] for c in members}
            units = [u for u in admin.values() if mcodes & set(u.get("codes", []))] if match == "admin" else []
            if units:
                b = [min(u["bbox"][0] for u in units), min(u["bbox"][1] for u in units),
                     max(u["bbox"][2] for u in units), max(u["bbox"][3] for u in units)]
            else:
                b = [min(c["lon"] for c in members) - .4, min(c["lat"] for c in members) - .4,
                     max(c["lon"] for c in members) + .4, max(c["lat"] for c in members) + .4]
            regions = Counter(u.get("region") or u["name"] for u in units) if units else \
                Counter(admin[c["admin"]].get("region") or admin[c["admin"]]["name"] for c in members)
            rep = next((c for c in members if c["code"] == sid), None) or \
                next((c for c in members if c["code"] in meta.get("anchors", [])), members[0])
            subs.append({"id": sid, "group": members[0]["group"], "bbox": b, "rep": rep["code"],
                         "regions": [r for r, _ in regions.most_common(3)]})
        for c in codes: c["sub"] = c["code"][:n]

    if not any(c.get("cities") for c in codes): warn(iso, "no 'cities' filled yet")
    out = {**meta, "match": match, "groups": groups, "subs": subs, "codes": codes, "admin": admin, "bbox": bbox(
        [r for u in admin.values() for r in u["rings"]])}
    summary = {"iso": iso, "name": meta["name"], "system": meta["system"], "aliases": meta.get("aliases", []),
               "codes": len(known), "groups": len(groups)}
    return out, summary


def main():
    OUT.mkdir(exist_ok=True)
    built, index = {}, []
    for d in sorted(p for p in SRC.iterdir() if p.is_dir()):
        try:
            out, summary = build_country(d)
            built[d.name] = out; index.append(summary)
        except (OSError, KeyError, json.JSONDecodeError) as e:
            err(d.name.upper(), f"cannot read sources: {e!r}")
    for w in warnings: print("warning:", w)
    if errors:
        for e in errors: print("ERROR:", e)
        sys.exit(1)
    for name, out in built.items():
        p = OUT / f"{name}.json"
        p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size // 1024} KB")
    index.sort(key=lambda s: s["name"]["en"])
    (OUT / "countries.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"data/countries.json  {len(index)} countries")


if __name__ == "__main__":
    main()
