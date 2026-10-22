"""One-shot import of the legacy trainers (brasil-phone-code, japan-phone-code)
into src/<iso>/. Usage:  python tools/import_legacy.py <brasil index.html> <japan index.html>
The output is meant to be edited by hand afterwards; do not re-run blindly."""
import csv, json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def js_value(src, name):
    """Extract a JSON literal assigned with `const NAME = ...;`."""
    i = src.index(f"const {name} = ") + len(f"const {name} = ")
    depth, j, in_str = 0, i, False
    while True:
        ch = src[j]
        if in_str:
            if ch == "\\": j += 1
            elif ch == '"': in_str = False
        elif ch == '"': in_str = True
        elif ch in "[{": depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0: return json.loads(src[i:j + 1])
        j += 1


def slug(s):
    s = unicodedata.normalize("NFD", s)
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def write(iso, meta, codes, admin):
    d = ROOT / "src" / iso.lower()
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (d / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    with open(d / "codes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"])
        w.writerows(codes)
    print(iso, len(codes), "codes,", len(admin), "admin units")


def brazil(path):
    s = Path(path).read_text(encoding="utf-8")
    states, ddd = js_value(s, "STATES"), js_value(s, "DDD")
    admin = {uf: {"name": v["n"], "rings": v["r"]} for uf, v in states.items()}
    codes = [[c, c[0], city, "", uf, la, lo, ""] for c, (city, uf, la, lo) in ddd.items()]
    groups = [
        ("1", "São Paulo", "São Paulo", "#C9A9E0"),
        ("2", "Rio de Janeiro et Espírito Santo", "Rio de Janeiro & Espírito Santo", "#DCD39A"),
        ("3", "Minas Gerais", "Minas Gerais", "#F0A860"),
        ("4", "Paraná et Santa Catarina", "Paraná & Santa Catarina", "#5CC9C4"),
        ("5", "Rio Grande do Sul", "Rio Grande do Sul", "#8FE0BC"),
        ("6", "Centre-Ouest, Acre, Rondônia, Tocantins", "Centre-West, Acre, Rondônia, Tocantins", "#EFE04A"),
        ("7", "Bahia et Sergipe", "Bahia & Sergipe", "#F0A0DC"),
        ("8", "Nordeste (PE, AL, PB, RN, CE, PI)", "Northeast (PE, AL, PB, RN, CE, PI)", "#EE7A6A"),
        ("9", "Nord et Maranhão", "North & Maranhão", "#57D06A"),
    ]
    meta = {
        "iso": "BR", "name": {"fr": "Brésil", "en": "Brazil"},
        "display": "({code})", "system": {"fr": "DDD", "en": "DDD"},
        "group_label": {"fr": "Zone", "en": "Zone"},
        "groups": [{"id": g, "name": {"fr": fr, "en": en}, "color": col} for g, fr, en, col in groups],
        "anchors": ["11", "21", "31", "41", "51", "61", "71", "81", "85", "91", "92", "98"],
        "twins": [["74", "87"]],
        "tips": [
            {"title": "1 → 9", "codes": [],
             "fr": "Le premier chiffre donne la macro-zone, du sud-est (1 = São Paulo) vers le nord (9 = Amazonie et Maranhão). Le second chiffre situe la ville dans la zone ; x1 est presque toujours la capitale.",
             "en": "The first digit gives the macro-zone, from the southeast (1 = São Paulo) to the north (9 = Amazon and Maranhão). The second digit places the city within the zone; x1 is almost always the capital."},
            {"title": "74 / 87", "codes": ["74", "87"],
             "fr": "Juazeiro (74, Bahia) et Petrolina (87, Pernambuco) se font face de part et d'autre du São Francisco, à 3 km : les deux réponses sont acceptées.",
             "en": "Juazeiro (74, Bahia) and Petrolina (87, Pernambuco) face each other across the São Francisco, 3 km apart: both answers are accepted."},
        ],
    }
    write("BR", meta, codes, admin)


def japan(path):
    s = Path(path).read_text(encoding="utf-8")
    pref, raw = js_value(s, "PREF"), js_value(s, "CODES_RAW")
    admin = {k: {"name": v["n"], "local": v["kj"], "rings": v["r"]} for k, v in pref.items()}
    codes = []
    for code, ro, kj, prefname, la, lo in raw:
        key = slug(prefname)
        assert key in admin, prefname
        codes.append([code, code[1], ro, kj, key, la, lo, ""])
    groups = [
        ("1", "Hokkaidō et Tōhoku nord", "Hokkaidō & northern Tōhoku", "#57D06A"),
        ("2", "Tōhoku sud, Kantō nord, Shin'etsu", "Southern Tōhoku, northern Kantō, Shin'etsu", "#8FE0BC"),
        ("3", "Tokyo (23 arrondissements)", "Tokyo (23 wards)", "#EE7A6A"),
        ("4", "Kantō sud", "Southern Kantō", "#EFE04A"),
        ("5", "Tōkai et Yamanashi", "Tōkai & Yamanashi", "#F0A860"),
        ("6", "Ōsaka", "Ōsaka", "#C9A9E0"),
        ("7", "Kansai et Hokuriku", "Kansai & Hokuriku", "#F0A0DC"),
        ("8", "Chūgoku et Shikoku", "Chūgoku & Shikoku", "#5CC9C4"),
        ("9", "Kyūshū et Okinawa", "Kyūshū & Okinawa", "#9FD356"),
    ]
    tips = [
        ("03 / 06", ["03", "06"],
         "Les deux seuls indicatifs à deux chiffres du pays : Tokyo (23 arrondissements) et Ōsaka-ville. Voir « 03- » sur une devanture suffit à conclure.",
         "The only two-digit codes in the country: Tokyo (23 wards) and Ōsaka city. Seeing “03-” on a shopfront settles it."),
        ("076", ["076"],
         "Un même indicatif pour Kanazawa (Ishikawa) et Toyama, deux préfectures voisines du Hokuriku.",
         "One code for both Kanazawa (Ishikawa) and Toyama, neighbouring prefectures in Hokuriku."),
        ("088", ["088"],
         "Un même indicatif de part et d'autre du Shikoku : Tokushima au nord-est et Kōchi au sud-ouest.",
         "One code on both sides of Shikoku: Tokushima in the northeast and Kōchi in the southwest."),
        ("Bloc 07", [],
         "Censé être le Kansai, il contient aussi tout le Hokuriku (Toyama, Ishikawa, Fukui), qui est au nord. C'est la principale entorse à la logique nord-sud.",
         "Meant to be Kansai, it also holds all of Hokuriku (Toyama, Ishikawa, Fukui), further north. It is the main break in the north-to-south logic."),
        ("059 · Mie", ["059"],
         "Mie est en Kinki mais porte un indicatif du bloc 05 (Tōkai), pour des raisons de routage du réseau.",
         "Mie is in Kinki but carries a block-05 (Tōkai) code, for network routing reasons."),
        ("098 · Okinawa", ["098", "0985"],
         "Okinawa était sous administration américaine lors de l'attribution des numéros. Elle a reçu après coup un créneau réservé au Miyazaki, d'où 098 pour Naha et 0985 pour Miyazaki.",
         "Okinawa was under US administration when numbers were assigned. It later got a slot reserved for Miyazaki, hence 098 for Naha and 0985 for Miyazaki."),
        ("0776 / 0952 / 0985", ["0776", "0952", "0985"],
         "À trois chiffres ces aires se télescopent avec leurs voisines : Fukui se distingue d'Ōtsu (077), Saga de Nagasaki (095), Miyazaki d'Okinawa (098). Il faut le quatrième chiffre.",
         "At three digits these areas collide with their neighbours: Fukui vs Ōtsu (077), Saga vs Nagasaki (095), Miyazaki vs Okinawa (098). You need the fourth digit."),
    ]
    meta = {
        "iso": "JP", "name": {"fr": "Japon", "en": "Japan"},
        "display": "{code}-", "system": {"fr": "市外局番", "en": "市外局番"},
        "group_label": {"fr": "Bloc", "en": "Block"},
        "groups": [{"id": g, "name": {"fr": fr, "en": en}, "color": col} for g, fr, en, col in groups],
        "anchors": ["011", "022", "03", "045", "052", "075", "06", "078", "082", "092", "098"],
        "twins": [],
        "tips": [{"title": t, "codes": c, "fr": fr, "en": en} for t, c, fr, en in tips],
    }
    write("JP", meta, codes, admin)


if __name__ == "__main__":
    brazil(sys.argv[1])
    japan(sys.argv[2])
