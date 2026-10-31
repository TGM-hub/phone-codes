"""Rebuild Japan on real area-code zones: src/jp/admin.json + the admin column of src/jp/codes.csv.

    python tools/import_japan_codes.py <folder>

<folder> holds:
  shigai.txt               MIC 市外局番の一覧 as text:  pdftotext -layout 000141817.pdf shigai.txt
                           (https://www.soumu.go.jp/main_sosiki/joho_tsusin/top/tel_number/shigai_list.html)
  N03-21_210101.json       municipalities (wards for designated cities), MLIT 国土数値情報 N03 simplified by
                           SmartNews Media Research Institute (github.com/smartnews-smri/japan-topography, topojson/s0010)

How: each 番号区画 row (zone, municipalities, area code) is matched to N03 units; every unit gets the trainer prefix of
its area code (first two digits, three for 0776 0852 0857 0952 0985; 03, 06; code 04 is 042 in Tokorozawa's zone and
047 elsewhere). A unit split between zones (大字 level) goes to the code that covers most of it (any "…を除く" remainder
beats the "…に限る" parts). One admin unit per (prefix, prefecture), hosting that prefix's code; prefixes the trainer
does not ask (Shimane / Tottori 085x outside 0852 and 0857) stay as drawn, never-correct units of their block.
Requires shapely. Re-run build.py afterwards.
"""
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "jp"
TOL = 0.01
SPECIAL = {"776", "852", "857", "952", "985"}
PREFS = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都",
         "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府",
         "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県",
         "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"]


# ---------------------------------------------------------------- MIC table
def read_rows(txt):
    row = re.compile(r"^\s{0,4}(\d+(?:-\d+)?)\s{2,}(\S.*?)\s+(\d{1,5})\s+(BCDE|CDE|DE|E)\s*$")
    rows, cur = [], None
    for line in txt.split("\n"):
        m = row.match(line)
        if m:
            cur = {"zone": m.group(1), "text": m.group(2).strip(), "code": m.group(3)}; rows.append(cur)
        elif cur and re.match(r"^\s{6,}\S", line):
            cur["text"] += line.strip()
    return rows


def prefix(code, zone):
    if code in ("3", "6"): return code
    if code == "4": return "42" if zone == "227" else "47"          # 04-29xx Tokorozawa, 04-7xxx Kashiwa / Kamogawa
    return code[:3] if code[:3] in SPECIAL else code[:2]


def split_top(s):
    out, depth, cur, i = [], 0, "", 0
    while i < len(s):
        ch = s[i]
        if ch == "（": depth += 1
        elif ch == "）": depth -= 1
        if depth == 0 and (ch == "、" or s.startswith("及び", i)):
            out.append(cur); cur = ""; i += 2 if s.startswith("及び", i) else 1; continue
        cur += ch; i += 1
    out.append(cur)
    return [x.strip() for x in out if x.strip()]


def head_paren(e):
    if "（" not in e: return e, None
    i, depth = e.index("（"), 0
    for j in range(i, len(e)):
        if e[j] == "（": depth += 1
        elif e[j] == "）":
            depth -= 1
            if depth == 0: return e[:i] + e[j + 1:], e[i + 1:j]
    return e[:i], e[i + 1:]


class Units:
    def __init__(self, props):
        norm = lambda v: v.replace("ヶ", "ケ") if isinstance(v, str) else v       # N03 mixes ヶ and ケ
        self.u = [{k: norm(v) for k, v in p.items()} for p in props]
        self.by_pref = defaultdict(list)
        for i, p in enumerate(self.u): self.by_pref[p["N03_001"]].append(i)

    def lookup(self, pref, name):
        best, rest, size = [], None, -1
        for i in self.by_pref[pref]:
            g, n = self.u[i].get("N03_003") or "", self.u[i].get("N03_004") or ""
            for full in ([g + n, n] if g else [n]):
                if full and name.startswith(full):
                    if len(full) > size: best, rest, size = [i], name[len(full):], len(full)
                    elif len(full) == size: best.append(i)
            if g and name == g and len(g) > size and g[-1] in "郡市":
                best, rest, size = [k for k in self.by_pref[pref] if (self.u[k].get("N03_003") or "") == g], "", len(g)
        return best, rest


def resolve(rows, units):
    score, misses = defaultdict(lambda: defaultdict(float)), []
    for r in rows:
        text = re.sub(r"（ただし、.*$", "", r["text"])
        text = re.sub(r"（市外局番を除く電気通信番号による発信については[^（）]*）", "", text)   # dialling note, not a boundary
        text = text.replace("ヶ", "ケ").replace("篠山市", "丹波篠山市")                       # N03 spelling, 2019 renaming
        code, pref = prefix(r["code"], r["zone"]), None
        for e in split_top(text):
            for pf in PREFS:
                if e.startswith(pf): pref, e = pf, e[len(pf):]; break
            if pref == "東京都" and e.startswith("23区"):
                for i in units.by_pref["東京都"]:
                    if not units.u[i].get("N03_003") and (units.u[i].get("N03_004") or "").endswith("区"): score[i][code] += 1
                continue
            base, inner = head_paren(e)
            ids, rest = units.lookup(pref, base)
            if not ids: misses.append((r["zone"], pref, e)); continue
            partial = bool(rest)
            if inner is None:
                for i in ids: score[i][code] += 0.4 if partial else 1
            elif inner.endswith("に限る。"):
                if len(ids) > 1 and not partial:          # 郡 / designated city: only the listed members
                    for nm in split_top(inner[:-4]):
                        b2, in2 = head_paren(nm)
                        sub, rest2 = units.lookup(pref, base + b2)
                        if sub and sub != ids:
                            for i in sub: score[i][code] += 0.4 if (in2 or rest2) else 1
                        else:
                            for i in ids: score[i][code] += 0.2
                else:
                    for i in ids: score[i][code] += 0.3
            elif inner.endswith("を除く。"):
                full, part = set(), set()
                if len(ids) > 1:
                    for nm in split_top(inner[:-4]):
                        b2, in2 = head_paren(nm)
                        sub, rest2 = units.lookup(pref, base + b2)
                        if sub and sub != ids: (part if (in2 or rest2) else full).update(sub)
                for i in ids:
                    if i not in full: score[i][code] += 0.7 if (i in part or len(ids) == 1 or partial) else 1
            else:
                misses.append((r["zone"], pref, e))
    return score, misses


# ---------------------------------------------------------------- TopoJSON
def decode(topo):
    sx, sy = topo["transform"]["scale"]; tx, ty = topo["transform"]["translate"]
    arcs = []
    for a in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    def ring(idx):
        pts = []
        for k in idx:
            seg = arcs[k] if k >= 0 else arcs[~k][::-1]
            pts += seg if not pts else seg[1:]
        return pts
    out = []
    for g in next(iter(topo["objects"].values()))["geometries"]:
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        shapes = [Polygon(ring(p[0]), [ring(h) for h in p[1:]]).buffer(0) for p in polys]
        out.append((g["properties"], unary_union(shapes)))
    return out


def rings_of(geom):
    g = geom.buffer(0).simplify(TOL, preserve_topology=True)
    parts = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    return [[[round(x, 3), round(y, 3)] for x, y in Polygon(p.exterior).exterior.coords[:-1]]
            for p in parts if p.area >= 0.0004]


def main(folder):
    folder = Path(folder)
    rows = read_rows((folder / "shigai.txt").read_text(encoding="utf-8"))
    geo = decode(json.loads((folder / "N03-21_210101.json").read_text(encoding="utf-8")))
    units = Units([p for p, _ in geo])
    score, misses = resolve(rows, units)
    if misses:
        sys.exit("unmatched MIC entries:\n" + "\n".join(map(str, misses)))
    old = json.loads((SRC / "admin.json").read_text(encoding="utf-8"))
    key_of_pref = {a["local"]: k for k, a in old.items()}
    with open(SRC / "codes.csv", encoding="utf-8", newline="") as f:
        rows_c = list(csv.DictReader(f)); fields = list(rows_c[0].keys())
    eol = "\r\n" if b"\r\n" in (SRC / "codes.csv").read_bytes() else "\n"
    asked = {c["code"].lstrip("0") for c in rows_c}
    group_of = {c["code"].lstrip("0"): c["group"] for c in rows_c}
    parts = defaultdict(list)
    for i, sc in score.items():
        p = max(sc.items(), key=lambda kv: kv[1])[0]
        parts[(p, units.u[i]["N03_001"])].append(geo[i][1])
    admin = {}
    for (p, pref), geoms in sorted(parts.items()):
        key = f"p{p}-{key_of_pref[pref]}"
        a = {"name": old[key_of_pref[pref]]["name"], "local": pref, "rings": rings_of(unary_union(geoms)), "region": "0" + p}
        if p in asked: a["codes"] = ["0" + p]
        else: a["groups"] = [p[0]]            # block colour, never a right answer
        admin[key] = a
    for r in rows_c:
        p, pref = r["code"].lstrip("0"), old[r["admin"]]["local"] if r["admin"] in old else None
        key = f"p{p}-{r['admin']}" if r["admin"] in old else r["admin"]
        if key not in admin:
            sys.exit(f"{r['code']} {r['city']}: no zone {key} (city outside its own code's area?)")
        r["admin"] = key
    (SRC / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    with open(SRC / "codes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator=eol); w.writeheader(); w.writerows(rows_c)
    meta = json.loads((SRC / "meta.json").read_text(encoding="utf-8"))
    meta["match"] = "admin"
    (SRC / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    split = sum(1 for sc in score.values() if len(sc) > 1)
    print(f"jp: {len(rows)} MIC zones, {len(score)} municipalities/wards ({split} split between prefixes), {len(admin)} zones")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
