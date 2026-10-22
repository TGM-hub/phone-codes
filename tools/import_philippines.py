"""Build src/ph/ from the geoBoundaries PHL ADM2 (provinces) file.
Usage:  python tools/import_philippines.py <geoBoundaries-PHL-ADM2_simplified.geojson>
Download: https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/PHL/ADM2/geoBoundaries-PHL-ADM2_simplified.geojson
Codes per province from Wikipedia, "Telephone numbers in the Philippines" (read 2026-10-21).
Provinces marked GUESS are not in that page's table; they get the code of the
province they were split from. Overwrites codes.csv and admin.json, keeps meta.json."""
import csv, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_indonesia import simplify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

PROVINCE_CODES = {
    "NCR, City of Manila, First District": "02", "NCR, Second District": "02", "NCR, Third District": "02",
    "NCR, Fourth District": "02", "Rizal": "02",
    "Cebu": "032", "Iloilo": "033", "Guimaras": "033", "Negros Occidental": "034",
    "Negros Oriental": "035", "Siquijor": "035", "Antique": "036", "Aklan": "036", "Capiz": "036", "Bohol": "038",
    "Quezon": "042", "Marinduque": "042", "Aurora": "042", "Romblon": "042",
    "Batangas": "043", "Oriental Mindoro": "043", "Occidental Mindoro": "043",
    "Bulacan": "044", "Nueva Ecija": "044", "Pampanga": "045", "Tarlac": "045", "Cavite": "046",
    "Bataan": "047", "Zambales": "047", "Palawan": "048", "Laguna": "049",
    "Albay": "052", "Catanduanes": "052", "Leyte": "053", "Biliran": "053", "Southern Leyte": "053",
    "Camarines Norte": "054", "Camarines Sur": "054", "Samar": "055", "Eastern Samar": "055",
    "Northern Samar": "055", "Masbate": "056", "Sorsogon": "056",
    "Zamboanga del Sur": "062", "Basilan": "062", "Zamboanga Sibugay": "062", "City of Isabela": "062",
    "Lanao del Norte": "063", "Lanao del Sur": "063",
    "Cotabato": "064", "Maguindanao": "064", "Sultan Kudarat": "064", "Cotabato City": "064",
    "Zamboanga del Norte": "065", "Sulu": "068", "Tawi-Tawi": "068",
    "La Union": "072", "Abra": "074", "Apayao": "074", "Benguet": "074", "Ifugao": "074", "Kalinga": "074",
    "Mountain Province": "074", "Pangasinan": "075", "Ilocos Norte": "077", "Ilocos Sur": "077",
    "Batanes": "078", "Cagayan": "078", "Isabela": "078", "Nueva Vizcaya": "078", "Quirino": "078",
    "Davao del Sur": "082", "Davao Occidental": "082",          # GUESS: split from Davao del Sur (2013)
    "South Cotabato": "083", "Sarangani": "083",
    "Davao del Norte": "084", "Compostela Valley": "084",        # GUESS: Davao de Oro, split from Davao del Norte
    "Agusan del Norte": "085", "Agusan del Sur": "085",
    "Surigao del Norte": "086", "Surigao del Sur": "086", "Dinagat Islands": "086",  # GUESS: from Surigao del Norte
    "Davao Oriental": "087",
    "Bukidnon": "088", "Misamis Oriental": "088", "Misamis Occidental": "088", "Camiguin": "088",
}
DISPLAY = {"NCR, City of Manila, First District": "Manila", "NCR, Second District": "Metro Manila (2nd district)",
           "NCR, Third District": "Metro Manila (3rd district)", "NCR, Fourth District": "Metro Manila (4th district)",
           "Compostela Valley": "Davao de Oro", "City of Isabela": "Isabela City"}

# code -> main city, lat, lon, other places (destinations in the Wikipedia table)
CODES = {
    "02":  ("Manila", 14.599, 120.984, "Quezon City;Makati;Antipolo"),
    "032": ("Cebu City", 10.316, 123.891, "Mandaue;Lapu-Lapu;Toledo"),
    "033": ("Iloilo City", 10.720, 122.562, "Passi;Miagao;Guimaras"),
    "034": ("Bacolod", 10.676, 122.951, "Silay;Kabankalan;San Carlos"),
    "035": ("Dumaguete", 9.307, 123.308, "Bais;Bayawan;Siquijor"),
    "036": ("Roxas", 11.585, 122.751, "Kalibo;Boracay;San Jose de Buenavista"),
    "038": ("Tagbilaran", 9.648, 123.855, "Ubay;Talibon;Jagna"),
    "042": ("Lucena", 13.931, 121.617, "Tayabas;Gumaca;Boac"),
    "043": ("Batangas City", 13.757, 121.058, "Lipa;Calapan;San Jose"),
    "044": ("Malolos", 14.844, 120.811, "Meycauayan;Cabanatuan;Gapan"),
    "045": ("San Fernando", 15.034, 120.684, "Angeles;Tarlac City;Mabalacat"),
    "046": ("Dasmariñas", 14.329, 120.937, "Imus;Tagaytay;Trece Martires"),
    "047": ("Olongapo", 14.829, 120.283, "Balanga;Iba;Subic"),
    "048": ("Puerto Princesa", 9.740, 118.735, ""),
    "049": ("Calamba", 14.212, 121.165, "Santa Rosa;San Pablo;Los Baños"),
    "052": ("Legazpi", 13.139, 123.744, "Tabaco;Ligao;Virac"),
    "053": ("Tacloban", 11.244, 125.004, "Ormoc;Palo;Naval"),
    "054": ("Naga", 13.621, 123.195, "Iriga;Daet;Pili"),
    "055": ("Calbayog", 12.067, 124.600, "Catbalogan;Borongan;Catarman"),
    "056": ("Sorsogon City", 12.971, 124.006, "Masbate City;Bulan;Gubat"),
    "062": ("Zamboanga City", 6.910, 122.073, "Pagadian;Ipil;Isabela City"),
    "063": ("Iligan", 8.228, 124.245, "Marawi;Tubod;Kapatagan"),
    "064": ("Cotabato City", 7.223, 124.246, "Kidapawan;Tacurong;Isulan"),
    "065": ("Dipolog", 8.589, 123.341, "Dapitan"),
    "068": ("Jolo", 6.053, 121.002, "Bongao"),
    "072": ("San Fernando", 16.616, 120.317, "Agoo;Bauang"),
    "074": ("Baguio", 16.402, 120.596, "La Trinidad;Bontoc;Tabuk"),
    "075": ("Dagupan", 16.043, 120.334, "Lingayen;Urdaneta;Alaminos"),
    "077": ("Laoag", 18.198, 120.593, "Vigan;Batac;Candon"),
    "078": ("Tuguegarao", 17.613, 121.727, "Santiago;Ilagan;Bayombong"),
    "082": ("Davao City", 7.073, 125.613, "Digos"),
    "083": ("General Santos", 6.113, 125.172, "Koronadal;Polomolok"),
    "084": ("Tagum", 7.448, 125.808, "Panabo"),
    "085": ("Butuan", 8.948, 125.544, "Cabadbaran;Bayugan"),
    "086": ("Surigao City", 9.787, 125.491, "Bislig;Tandag"),
    "087": ("Mati", 6.955, 126.217, ""),
    "088": ("Cagayan de Oro", 8.454, 124.632, "Malaybalay;Ozamiz;Oroquieta"),
}


def main(src):
    feats = json.load(open(src, encoding="utf-8"))["features"]
    admin, hosts = {}, {}
    for f in feats:
        name = f["properties"]["shapeName"]
        code = PROVINCE_CODES.get(name)
        if code is None: sys.exit(f"no code for province {name!r}")
        g = f["geometry"]
        poly = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        key = name.lower().replace(", ", "-").replace(" ", "-")
        admin[key] = {"name": DISPLAY.get(name, name), "rings": simplify(poly), "codes": [code]}
        hosts.setdefault(code, []).append(key)
    missing = set(PROVINCE_CODES) - {f["properties"]["shapeName"] for f in feats}
    if missing: print("warning: provinces not in the file:", sorted(missing))
    rows = []
    for code, (city, lat, lon, others) in CODES.items():
        if code not in hosts: sys.exit(f"code {code} has no province")
        # main admin: the province whose bbox holds the city, else the first
        main = next((k for k in hosts[code] if any(
            min(p[0] for p in r) <= lon <= max(p[0] for p in r) and min(p[1] for p in r) <= lat <= max(p[1] for p in r)
            for r in admin[k]["rings"])), hosts[code][0])
        rows.append([code, code[1], city, "", main, lat, lon, others])
    d = ROOT / "src" / "ph"; d.mkdir(parents=True, exist_ok=True)
    (d / "admin.json").write_text(json.dumps(admin, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(d / "codes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"]); w.writerows(rows)
    print(f"PH: {len(rows)} codes, {len(admin)} provinces, {sum(len(r) for a in admin.values() for r in a['rings'])} points")


if __name__ == "__main__":
    main(sys.argv[1])
