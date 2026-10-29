"""France: 0Z AB codes (the two digits after the zone) on départements.
Usage:  python tools/import_france.py
Reads src/fr/ab.csv (dept,zone,ab: AB values of the département's zone, "3:85" for another zone)
and src/fr/admin.json (département outlines, kept); rewrites the units' codes and src/fr/codes.csv.
Source: English Wikipedia, "Local telephone area codes in France" (read 2026-10-28), table by
département, checked against the table by code (four codes added from it: 01 47 Val-de-Marne,
02 28 Vendée, 03 92 Bas-Rhin, 04 96 Bouches-du-Rhône). Telemarketing and overseas codes left out.
Since 2023 a new number no longer has to match its area; the codes still read as their old areas."""
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "src" / "fr"

# codes from before 1996, read as one city (or a pair); the later ones are regional blocks
CITY = {
 "0140": "Paris", "0144": "Paris", "0153": "Paris", "0145": "Paris", "0147": "Paris", "0149": "Paris",
 "0130": "Yvelines · Val-d'Oise", "0134": "Yvelines · Val-d'Oise", "0139": "Yvelines · Val-d'Oise",
 "0160": "Seine-et-Marne · Essonne", "0164": "Seine-et-Marne · Essonne", "0169": "Essonne · Seine-et-Marne",
 "0231": "Caen", "0232": "Évreux", "0233": "Cherbourg · Alençon", "0235": "Rouen", "0237": "Chartres",
 "0238": "Orléans", "0240": "Nantes", "0241": "Angers", "0243": "Le Mans · Laval", "0247": "Tours",
 "0248": "Bourges", "0251": "La Roche-sur-Yon", "0254": "Blois · Châteauroux", "0296": "Saint-Brieuc",
 "0297": "Vannes", "0298": "Brest · Quimper", "0299": "Rennes",
 "0320": "Lille", "0321": "Arras · Calais", "0322": "Amiens", "0323": "Laon · Saint-Quentin",
 "0324": "Charleville-Mézières", "0325": "Troyes · Chaumont", "0326": "Reims", "0327": "Valenciennes",
 "0328": "Dunkerque", "0329": "Épinal · Verdun", "0344": "Beauvais", "0380": "Dijon", "0381": "Besançon",
 "0382": "Thionville", "0383": "Nancy", "0384": "Lons-le-Saunier · Vesoul · Belfort", "0385": "Mâcon · Chalon",
 "0386": "Auxerre · Nevers", "0387": "Metz", "0388": "Strasbourg", "0389": "Mulhouse · Colmar",
 "0442": "Aix-en-Provence", "0450": "Annecy", "0466": "Nîmes", "0467": "Montpellier",
 "0468": "Perpignan · Carcassonne", "0470": "Moulins · Vichy", "0471": "Le Puy · Aurillac", "0472": "Lyon",
 "0473": "Clermont-Ferrand", "0474": "Bourg-en-Bresse", "0475": "Valence", "0476": "Grenoble",
 "0477": "Saint-Étienne", "0478": "Lyon", "0479": "Chambéry", "0490": "Avignon", "0491": "Marseille",
 "0492": "Gap · Digne", "0493": "Nice", "0494": "Toulon", "0495": "Ajaccio · Bastia", "0496": "Marseille",
 "0534": "Toulouse", "0545": "Angoulême", "0546": "La Rochelle", "0549": "Poitiers · Niort",
 "0553": "Périgueux · Agen", "0555": "Limoges", "0556": "Bordeaux", "0557": "Libourne · Blaye",
 "0558": "Mont-de-Marsan", "0559": "Pau · Bayonne", "0561": "Toulouse", "0562": "Tarbes · Auch",
 "0563": "Albi · Montauban", "0565": "Rodez · Cahors",
}
# the département that holds the named city (default: the first host)
HOME = {"0233": "Manche", "0243": "Sarthe", "0254": "Loir-et-Cher", "0298": "Finistère", "0321": "Pas-de-Calais",
        "0323": "Aisne", "0325": "Aube", "0329": "Vosges", "0382": "Moselle", "0384": "Jura", "0385": "Saône-et-Loire",
        "0386": "Yonne", "0389": "Haut-Rhin", "0468": "Pyrénées-Orientales", "0470": "Allier", "0471": "Haute-Loire",
        "0474": "Ain", "0475": "Drôme", "0490": "Vaucluse", "0492": "Hautes-Alpes", "0495": "Corse-du-Sud",
        "0549": "Vienne", "0553": "Dordogne", "0559": "Pyrénées-Atlantiques", "0562": "Hautes-Pyrénées",
        "0563": "Tarn", "0565": "Aveyron", "0472": "Rhône", "0478": "Rhône", "0442": "Bouches-du-Rhône",
        "0491": "Bouches-du-Rhône", "0496": "Bouches-du-Rhône", "0476": "Isère", "0450": "Haute-Savoie",
        "0479": "Savoie", "0467": "Hérault", "0466": "Gard", "0557": "Gironde", "0237": "Eure-et-Loir",
        "0232": "Eure", "0231": "Calvados", "0235": "Seine-Maritime", "0238": "Loiret", "0240": "Loire-Atlantique",
        "0241": "Maine-et-Loire", "0247": "Indre-et-Loire", "0248": "Cher", "0251": "Vendée", "0320": "Nord",
        "0327": "Nord", "0328": "Nord", "0326": "Marne", "0383": "Meurthe-et-Moselle", "0387": "Moselle",
        "0388": "Bas-Rhin", "0380": "Côte-d'Or", "0381": "Doubs", "0473": "Puy-de-Dôme", "0477": "Loire",
        "0493": "Alpes-Maritimes", "0494": "Var", "0534": "Haute-Garonne", "0561": "Haute-Garonne",
        "0556": "Gironde", "0555": "Haute-Vienne", "0130": "Yvelines", "0134": "Yvelines", "0139": "Yvelines",
        "0160": "Seine-et-Marne", "0164": "Seine-et-Marne", "0169": "Essonne"}
# regional blocks (mostly after 1996) read as the old region they cover
REGION = [
 ({"Calvados", "Manche", "Orne"}, "Basse-Normandie"), ({"Eure", "Seine-Maritime"}, "Haute-Normandie"),
 ({"Côtes d'Armor", "Finistère", "Ille-et-Vilaine", "Morbihan"}, "Bretagne"),
 ({"Loire-Atlantique", "Maine-et-Loire", "Mayenne", "Sarthe", "Vendée"}, "Pays de la Loire"),
 ({"Cher", "Eure-et-Loir", "Indre", "Indre-et-Loire", "Loir-et-Cher", "Loiret"}, "Centre"),
 ({"Nord", "Pas-de-Calais"}, "Nord-Pas-de-Calais"), ({"Aisne", "Oise", "Somme"}, "Picardie"),
 ({"Ardennes", "Aube", "Marne", "Haute-Marne"}, "Champagne-Ardenne"),
 ({"Meurthe-et-Moselle", "Meuse", "Moselle", "Vosges"}, "Lorraine"), ({"Bas-Rhin", "Haut-Rhin"}, "Alsace"),
 ({"Doubs", "Jura", "Haute-Saône", "Territoire de Belfort"}, "Franche-Comté"),
 ({"Côte-d'Or", "Nièvre", "Saône-et-Loire", "Yonne"}, "Bourgogne"),
 ({"Allier", "Cantal", "Haute-Loire", "Puy-de-Dôme"}, "Auvergne"),
 ({"Aude", "Gard", "Hérault", "Lozère", "Pyrénées-Orientales"}, "Languedoc-Roussillon"),
 ({"Alpes-de-Haute-Provence", "Hautes-Alpes", "Bouches-du-Rhône", "Vaucluse"}, "Provence"),
 ({"Alpes-Maritimes", "Var"}, "Côte d'Azur"), ({"Alpes-Maritimes", "Bouches-du-Rhône", "Var"}, "Provence-Côte d'Azur"),
 ({"Corse-du-Sud", "Haute-Corse"}, "Corse"), ({"Isère", "Savoie", "Haute-Savoie"}, "Alpes du Nord"),
 ({"Ain", "Ardèche", "Drôme", "Loire", "Rhône"}, "Rhône-Alpes ouest"),
 ({"Ain", "Allier", "Ardèche", "Drôme", "Loire", "Rhône"}, "Rhône-Alpes ouest + Allier"),
 ({"Dordogne", "Gironde", "Landes", "Lot-et-Garonne", "Pyrénées-Atlantiques"}, "Aquitaine"),
 ({"Ariège", "Aveyron", "Haute-Garonne", "Gers", "Lot", "Hautes-Pyrénées", "Tarn", "Tarn-et-Garonne"}, "Midi-Pyrénées"),
 ({"Charente", "Charente-Maritime", "Deux-Sèvres", "Vienne"}, "Poitou-Charentes"),
 ({"Corrèze", "Creuse", "Haute-Vienne"}, "Limousin"),
]


def main():
    admin = json.load(open(D / "admin.json", encoding="utf-8"))
    key = {a["name"].strip(): k for k, a in admin.items()}
    key.update({k.strip(): k for k in admin})
    hosts = {}
    for r in csv.DictReader(open(D / "ab.csv", encoding="utf-8")):
        k = key[r["dept"]]
        codes = []
        for part in r["ab"].split(";"):
            z, abs_ = (part.split(":") if ":" in part else (r["zone"], part))
            codes += [f"0{z}{ab}" for ab in abs_.split()]
        admin[k]["codes"] = sorted(set(codes))
        for c in codes: hosts.setdefault(c, []).append(admin[k]["name"].strip())
    missing = [a["name"] for a in admin.values() if not a.get("codes")]
    if missing: raise SystemExit(f"départements without codes: {missing}")
    rows = []
    for code in sorted(hosts):
        names = sorted(set(hosts[code]))
        city = CITY.get(code)
        if not city:
            city = next((n for s, n in REGION if s == set(names)), None) or (names[0] if len(names) == 1 else " · ".join(names))
        home = HOME.get(code) if HOME.get(code) in names else city if city in names else names[0]
        a = admin[key[home]]
        rows.append([code, code[1], city, "", key[home], "", "", "; ".join(names) if len(names) > 1 else ""])
    # lat/lon: the home département's label point (written by build.py's label rule)
    for r in rows:
        rings = admin[r[4]]["rings"]
        big = max(rings, key=lambda ring: len(ring))
        xs = [p[0] for p in big]; ys = [p[1] for p in big]
        r[5], r[6] = round(sum(ys) / len(ys), 3), round(sum(xs) / len(xs), 3)
    json.dump(admin, open(D / "admin.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    with open(D / "codes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["code", "group", "city", "local", "admin", "lat", "lon", "cities"]); w.writerows(rows)
    print(f"FR: {len(rows)} codes on {len(admin)} départements")


if __name__ == "__main__":
    main()
