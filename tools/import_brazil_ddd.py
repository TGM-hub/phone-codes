"""Rebuild Brazil on real DDD areas: src/br/admin.json + the admin column of src/br/codes.csv.

    python tools/import_brazil_ddd.py <folder>

<folder> holds the open sources used for the Atlas card "Brésil DDD":
  ddd_areas.geojson  IBGE municipalities (tbrugz/geodata-br) merged by DDD, one feature per code ({"ddd": "11"})
  municipios.csv     kelvins/municipios-brasileiros (codigo_uf, ddd for each municipality)
Each DDD area becomes one admin unit hosting its code (meta.match = "admin"); region = the state(s) it covers.
Requires shapely (pip install shapely). Re-run build.py afterwards.
"""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path
from shapely.geometry import shape, Polygon, MultiPolygon

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "br"
UF = {11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN",
      25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC",
      43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF"}
TOL = 0.02          # simplification, degrees (~2 km): plenty for a click map, keeps data/br.json small


def rings_of(geom):
    g = geom.simplify(TOL, preserve_topology=True)
    parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    out = []
    for p in parts:
        if p.area < 0.002:          # specks (islets, slivers) are not clickable anyway
            continue
        out.append([[round(x, 3), round(y, 3)] for x, y in Polygon(p.exterior).exterior.coords[:-1]])
    return out


def main(folder):
    folder = Path(folder)
    feats = json.load(open(folder / "ddd_areas.geojson", encoding="utf-8"))["features"]
    states = defaultdict(Counter)
    with open(folder / "municipios.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            states[r["ddd"]][UF[int(r["codigo_uf"])]] += 1
    old = json.load(open(SRC / "admin.json", encoding="utf-8"))          # UF key -> {"name": state name}
    uf_name = {k: v["name"] for k, v in old.items()}
    with open(SRC / "codes.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f)); fields = list(rows[0].keys())
    eol = "\r\n" if b"\r\n" in (SRC / "codes.csv").read_bytes() else "\n"   # keep the file's line endings
    codes = {r["code"] for r in rows}
    geo = {ft["properties"]["ddd"]: shape(ft["geometry"]) for ft in feats}
    if set(geo) != codes:
        sys.exit(f"DDD mismatch: only in geojson {sorted(set(geo) - codes)}, only in codes.csv {sorted(codes - set(geo))}")
    admin = {}
    for r in sorted(rows, key=lambda r: r["code"]):
        c = r["code"]
        ufs = [u for u, _ in states[c].most_common()]
        admin[f"ddd{c}"] = {"name": r["city"], "rings": rings_of(geo[c]), "codes": [c],
                            "region": ", ".join(uf_name.get(u, u) for u in ufs)}
        r["admin"] = f"ddd{c}"
    (SRC / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    with open(SRC / "codes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator=eol); w.writeheader(); w.writerows(rows)
    meta = json.load(open(SRC / "meta.json", encoding="utf-8"))
    meta["match"] = "admin"
    (SRC / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    n = sum(len(a["rings"]) for a in admin.values()); p = sum(len(r) for a in admin.values() for r in a["rings"])
    print(f"br: {len(admin)} DDD areas, {n} rings, {p} points")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
