"""Mexico: LADA area codes at state level (like the US map: the answer is the state).
Usage:  python tools/import_mexico.py <libphonenumber resources/geocoding/en/52.txt> <geoBoundaries MEX ADM1 geojson>
Codes and states: Google libphonenumber geocoding data (Apache 2.0), which gives "City, ST" or the state(s)
for each 3-digit code; 33, 55, 56 and 81 added by hand. Main city per code: the libphonenumber city when
there is one, else CITY below (state capitals and major cities, English Wikipedia "Telephone numbers in
Mexico", read 2026-10-28), else the state. Writes src/mx/admin.json and src/mx/codes.csv."""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_indonesia as simp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "src" / "mx"
ST = {  # abbreviations and spellings in libphonenumber -> geoBoundaries ADM1 name
 "AGS": "Aguascalientes", "BCN": "Baja California", "BCS": "Baja California Sur", "CAMP": "Campeche", "CHIS": "Chiapas",
 "CHIH": "Chihuahua", "COAH": "Coahuila de Zaragoza", "COL": "Colima", "FD": "Distrito Federal", "DGO": "Durango",
 "GTO": "Guanajuato", "GRO": "Guerrero", "HGO": "Hidalgo", "JAL": "Jalisco", "MEX": "Mexico", "MICH": "Michoacan de Ocampo",
 "MOR": "Morelos", "NAY": "Nayarit", "NL": "Nuevo Leon", "OAX": "Oaxaca", "PUE": "Puebla", "QRO": "Queretaro de Arteaga",
 "QROO": "Quintana Roo", "SLP": "San Luis Potosi", "SIN": "Sinaloa", "SON": "Sonora", "TAB": "Tabasco", "TAMPS": "Tamaulipas",
 "TLAX": "Tlaxcala", "VER": "Veracruz de Ignacio de la Llave", "YUC": "Yucatan", "ZAC": "Zacatecas",
 "Aguascalientes": "Aguascalientes", "Baja California": "Baja California", "Baja California Sur": "Baja California Sur",
 "Campeche": "Campeche", "Chiapas": "Chiapas", "Chihuahua": "Chihuahua", "Coahuila": "Coahuila de Zaragoza",
 "Colima": "Colima", "Durango": "Durango", "Guanajuato": "Guanajuato", "Guerrero": "Guerrero", "Hidalgo": "Hidalgo",
 "Jalisco": "Jalisco", "Estado de Mexico": "Mexico", "Mexico": "Mexico", "Michoacan": "Michoacan de Ocampo",
 "Morelos": "Morelos", "Nayarit": "Nayarit", "Nuevo Leon": "Nuevo Leon", "Oaxaca": "Oaxaca", "Puebla": "Puebla",
 "Queretaro": "Queretaro de Arteaga", "Quintana Roo": "Quintana Roo", "San Luis Potosi": "San Luis Potosi",
 "Sinaloa": "Sinaloa", "Sonora": "Sonora", "Tabasco": "Tabasco", "Tamaulipas": "Tamaulipas", "Tlaxcala": "Tlaxcala",
 "Veracruz": "Veracruz de Ignacio de la Llave", "Yucatan": "Yucatan", "Zacatecas": "Zacatecas",
 # a few entries give a city instead of a state
 "Merida": "Yucatan", "Toluca": "Mexico", "Culiacan": "Sinaloa", "Morelia": "Michoacan de Ocampo",
 "Tuxtla Gutierrez": "Chiapas", "Cuernavaca": "Morelos", "Nuevo Laredo": "Tamaulipas",
}
NAME = {"Coahuila de Zaragoza": "Coahuila", "Distrito Federal": "Ciudad de México", "Mexico": "Estado de México",
        "Michoacan de Ocampo": "Michoacán", "Queretaro de Arteaga": "Querétaro", "Veracruz de Ignacio de la Llave": "Veracruz",
        "Nuevo Leon": "Nuevo León", "San Luis Potosi": "San Luis Potosí", "Yucatan": "Yucatán"}
CITY = {"55": "Ciudad de México", "56": "Ciudad de México", "81": "Monterrey", "33": "Guadalajara", "656": "Ciudad Juárez",
 "657": "Ciudad Juárez", "614": "Chihuahua", "618": "Durango", "999": "Mérida", "990": "Mérida", "220": "Puebla", "221": "Puebla",
 "222": "Puebla", "442": "Querétaro", "446": "Querétaro", "449": "Aguascalientes", "663": "Tijuana", "664": "Tijuana",
 "612": "La Paz", "624": "Los Cabos", "844": "Saltillo", "686": "Mexicali", "667": "Culiacán", "720": "Toluca", "722": "Toluca",
 "729": "Toluca", "998": "Cancún", "871": "Torreón", "744": "Acapulco", "444": "San Luis Potosí", "440": "San Luis Potosí",
 "833": "Tampico", "477": "León", "479": "León", "961": "Tuxtla Gutiérrez", "662": "Hermosillo", "633": "Agua Prieta",
 "645": "Cananea", "644": "Ciudad Obregón", "642": "Navojoa", "631": "Nogales", "229": "Veracruz", "443": "Morelia",
 "921": "Coatzacoalcos", "771": "Pachuca", "981": "Campeche", "899": "Reynosa", "868": "Matamoros", "492": "Zacatecas",
 "228": "Xalapa", "311": "Tepic", "777": "Cuernavaca", "993": "Villahermosa", "834": "Ciudad Victoria", "951": "Oaxaca",
 "747": "Chilpancingo", "983": "Chetumal", "312": "Colima", "473": "Guanajuato", "246": "Tlaxcala", "867": "Nuevo Laredo",
 "660": "Culiacán", "450": "Morelia", "960": "Tuxtla Gutiérrez"}
EXTRA = {"33": ["JAL"], "55": ["FD", "MEX"], "56": ["FD", "MEX"], "81": ["NL"],
         # big-city codes missing from libphonenumber's 3-digit lines (they sit under its 2-digit fall-backs)
         "446": ["QRO"], "663": ["BCN"], "664": ["BCN"], "440": ["SLP"], "479": ["GTO"], "961": ["CHIS"], "951": ["OAX"]}
# corrections to libphonenumber: 987 Cozumel is tagged QRO (Querétaro) but is in Quintana Roo;
# 427 is San Juan del Río, Querétaro, not "Mexico/Quintana Roo"
FIX = {"987": (["QROO"], "Cozumel"), "427": (["QRO"], "San Juan del Río")}


def main(lpn, gj):
    feats = json.load(open(gj, encoding="utf-8"))["features"]
    admin = {}
    for f in feats:
        g = f["geometry"]; poly = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        n = f["properties"]["shapeName"]
        admin[n] = {"name": NAME.get(n, n), "rings": simp.simplify(poly), "codes": []}
    codes = {c: {"states": [ST[s] for s in v], "city": None} for c, v in EXTRA.items()}
    for line in open(lpn, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        p, text = line.split("|", 1)
        code = p[2:]
        if len(code) != 3: continue
        place, _, st = text.rpartition(", ")
        if place and st in ST:
            states, city = [ST[st]], place.split("/")[0]
        else:
            parts = [x.strip() for x in text.split("/")]
            states = [ST[x] for x in parts if x in ST]
            city = next((x for x in parts if x not in ST or x in ("Merida", "Toluca", "Culiacan", "Morelia", "Tuxtla Gutierrez", "Cuernavaca", "Nuevo Laredo")), None)
            if city and ST.get(city) and city not in ("Merida", "Toluca", "Culiacan", "Morelia", "Tuxtla Gutierrez", "Cuernavaca", "Nuevo Laredo"): city = None
            if not states:
                raise SystemExit(f"no state for {code}: {text}")
        if code in FIX: states, city = [ST[x] for x in FIX[code][0]], FIX[code][1]
        codes[code] = {"states": list(dict.fromkeys(states)), "city": city}
    rows = []
    for code in sorted(codes, key=lambda c: (len(c), c)):
        v = codes[code]
        for s in v["states"]:
            if code not in admin[s]["codes"]: admin[s]["codes"].append(code)
        home = v["states"][0]
        city = CITY.get(code) or v["city"] or NAME.get(home, home)
        rings = admin[home]["rings"]; big = max(rings, key=len)
        lat = sum(p[1] for p in big) / len(big); lon = sum(p[0] for p in big) / len(big)
        others = [NAME.get(s, s) for s in v["states"][1:]]
        rows.append([code, code[0], city, "", home, round(lat, 3), round(lon, 3), ";".join(others)])
    json.dump(admin, open(D / "admin.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    with open(D / "codes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"]); w.writerows(rows)
    print(f"MX: {len(rows)} codes on {len(admin)} states")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
