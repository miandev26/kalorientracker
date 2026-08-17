#!/usr/bin/env python3
"""Open-Food-Facts-Dump in die lokale SQLite importieren.

Dump holen (ca. 3 GB gepackt, wird gestreamt - nicht entpacken nötig):

    wget -O /data/off.csv.gz \\
      https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz

Import:

    python scripts/import_off.py /data/off.csv.gz

Standardmäßig werden nur Produkte mit Bezug zu AT/DE/CH übernommen und nur
solche mit plausiblen Nährwerten. Das reduziert ~4 Mio. Zeilen auf grob
300.000-500.000 und die Datenbank auf ein paar hundert MB.

Optionen:
    --alle-laender      kein Länderfilter
    --laender at,de,ch  eigener Filter
    --limit 50000       nur die ersten N Treffer (für einen Testlauf)
"""
import argparse
import csv
import gzip
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db  # noqa: E402

csv.field_size_limit(10_000_000)

SPALTEN = {
    "code": ["code"],
    "name": ["product_name", "product_name_de", "generic_name"],
    "brands": ["brands"],
    "countries": ["countries_tags", "countries_en", "countries"],
    "kcal": ["energy-kcal_100g"],
    "kj": ["energy_100g", "energy-kj_100g"],
    "protein": ["proteins_100g"],
    "carbs": ["carbohydrates_100g"],
    "fat": ["fat_100g"],
    "fiber": ["fiber_100g"],
    "serving": ["serving_quantity"],
}


def spalten_index(kopf: list[str]) -> dict:
    pos = {name: i for i, name in enumerate(kopf)}
    idx = {}
    for schluessel, kandidaten in SPALTEN.items():
        idx[schluessel] = [pos[k] for k in kandidaten if k in pos]
    if not idx["code"] or not idx["name"]:
        raise SystemExit("Unerwartetes CSV-Format: 'code' oder 'product_name' fehlt.")
    return idx


def hole(zeile: list[str], stellen: list[int]) -> str:
    for i in stellen:
        if i < len(zeile) and zeile[i].strip():
            return zeile[i].strip()
    return ""


def zahl(wert: str):
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def oeffnen(pfad: Path):
    if pfad.suffix == ".gz":
        return gzip.open(pfad, "rt", encoding="utf-8", errors="replace", newline="")
    return open(pfad, "rt", encoding="utf-8", errors="replace", newline="")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("datei", type=Path)
    ap.add_argument("--laender", default="at,de,ch")
    ap.add_argument("--alle-laender", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=5000)
    args = ap.parse_args()

    if not args.datei.exists():
        raise SystemExit(f"Datei nicht gefunden: {args.datei}")

    filter_laender = None
    if not args.alle_laender:
        kurz = [c.strip().lower() for c in args.laender.split(",") if c.strip()]
        lang = {"at": ["austria", "österreich", "osterreich"],
                "de": ["germany", "deutschland"],
                "ch": ["switzerland", "schweiz", "suisse"]}
        filter_laender = set()
        for c in kurz:
            filter_laender.add(f"en:{c}")
            filter_laender.update(lang.get(c, [c]))

    db.init()
    con = db.connect()
    con.execute("PRAGMA synchronous = OFF")

    gelesen = uebernommen = verworfen_land = verworfen_werte = 0
    puffer = []
    start = time.time()

    with oeffnen(args.datei) as fh:
        leser = csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        idx = spalten_index(next(leser))

        for zeile in leser:
            gelesen += 1
            if gelesen % 200_000 == 0:
                print(f"  {gelesen:>9,} gelesen · {uebernommen:>7,} übernommen "
                      f"· {time.time()-start:5.0f}s", flush=True)

            code = hole(zeile, idx["code"])
            name = hole(zeile, idx["name"])
            if not code or not name or not code.isdigit():
                continue

            if filter_laender is not None:
                laender = hole(zeile, idx["countries"]).lower()
                if not any(l in laender for l in filter_laender):
                    verworfen_land += 1
                    continue

            kcal = zahl(hole(zeile, idx["kcal"]))
            if kcal is None:
                kj = zahl(hole(zeile, idx["kj"]))
                kcal = kj / 4.184 if kj else None
            if kcal is None:
                verworfen_werte += 1
                continue

            p = zahl(hole(zeile, idx["protein"])) or 0
            c = zahl(hole(zeile, idx["carbs"])) or 0
            f = zahl(hole(zeile, idx["fat"])) or 0
            if db.is_suspect(kcal, p, c, f):
                verworfen_werte += 1
                continue

            marke = (hole(zeile, idx["brands"]).split(",")[0] or None)
            portion = zahl(hole(zeile, idx["serving"])) or 100

            puffer.append((
                code, name[:120], marke[:60] if marke else None,
                round(kcal, 1), round(p, 1), round(c, 1), round(f, 1),
                zahl(hole(zeile, idx["fiber"])) or 0,
                min(max(portion, 1), 2000),
            ))
            uebernommen += 1

            if len(puffer) >= args.batch:
                schreiben(con, puffer)
                puffer.clear()
            if args.limit and uebernommen >= args.limit:
                break

    if puffer:
        schreiben(con, puffer)

    print("\nBaue Suchindex neu …", flush=True)
    con.execute("INSERT INTO foods_fts(foods_fts) VALUES('rebuild')")
    con.commit()
    con.execute("VACUUM")
    con.close()

    print(f"""
Fertig in {time.time()-start:.0f}s
  gelesen             {gelesen:>9,}
  übernommen          {uebernommen:>9,}
  verworfen (Land)    {verworfen_land:>9,}
  verworfen (Werte)   {verworfen_werte:>9,}
""")


def schreiben(con, puffer):
    con.executemany(
        """INSERT INTO foods(source, source_id, name, brand, kcal_100,
               protein_100, carbs_100, fat_100, fiber_100, default_g)
           VALUES('off', ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(source, source_id) WHERE source_id IS NOT NULL DO NOTHING""",
        puffer,
    )
    con.commit()


if __name__ == "__main__":
    main()
