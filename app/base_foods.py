"""Grundnahrungsmittel ohne Barcode - Obst, Gemüse, Fleisch, Beilagen.

Deckt den Teil ab, den ein Scanner nie erwischt. Werte gerundet nach
USDA FoodData Central / BLS. Format:
(name, kcal, protein, carbs, fat, default_g, is_liquid, [(portionsname, gramm), ...])
"""

BASE_FOODS = [
    # --- Obst -------------------------------------------------------
    ("Apfel, roh",                52,  0.3, 13.8, 0.2, 150, 0, [("1 Stück", 150)]),
    ("Banane, roh",               89,  1.1, 22.8, 0.3, 120, 0, [("1 Stück", 120)]),
    ("Orange, roh",               47,  0.9, 11.8, 0.1, 180, 0, [("1 Stück", 180)]),
    ("Birne, roh",                57,  0.4, 15.2, 0.1, 170, 0, [("1 Stück", 170)]),
    ("Weintrauben",               69,  0.7, 18.1, 0.2, 100, 0, []),
    ("Erdbeeren",                 32,  0.7,  7.7, 0.3, 150, 0, []),
    ("Heidelbeeren",              57,  0.7, 14.5, 0.3, 100, 0, []),
    ("Kiwi",                      61,  1.1, 14.7, 0.5,  80, 0, [("1 Stück", 80)]),
    ("Mandarine",                 53,  0.8, 13.3, 0.3,  70, 0, [("1 Stück", 70)]),
    ("Wassermelone",              30,  0.6,  7.6, 0.2, 200, 0, []),
    ("Avocado",                  160,  2.0,  8.5, 14.7, 150, 0, [("1/2 Stück", 100)]),

    # --- Gemüse ----------------------------------------------------
    ("Karotte, roh",              41,  0.9,  9.6, 0.2, 80,  0, [("1 Stück", 80)]),
    ("Gurke",                     15,  0.7,  3.6, 0.1, 100, 0, []),
    ("Tomate",                    18,  0.9,  3.9, 0.2, 100, 0, [("1 Stück", 100)]),
    ("Paprika, rot",              31,  1.0,  6.0, 0.3, 150, 0, [("1 Stück", 150)]),
    ("Zwiebel",                   40,  1.1,  9.3, 0.1,  80, 0, [("1 Stück", 80)]),
    ("Kartoffel, gekocht",        87,  1.9, 20.1, 0.1, 200, 0, []),
    ("Kartoffel, roh",            77,  2.0, 17.5, 0.1, 200, 0, []),
    ("Brokkoli, gekocht",         35,  2.4,  7.2, 0.4, 150, 0, []),
    ("Karfiol, gekocht",          23,  1.8,  4.1, 0.5, 150, 0, []),
    ("Spinat, gekocht",           23,  3.0,  3.8, 0.3, 150, 0, []),
    ("Salat, grün",              15,  1.4,  2.9, 0.2,  60, 0, []),
    ("Zucchini",                  17,  1.2,  3.1, 0.3, 200, 0, []),
    ("Champignons",               22,  3.1,  3.3, 0.3, 150, 0, []),
    ("Mais, Dose",                86,  3.2, 19.0, 1.2, 150, 0, []),
    ("Erbsen, gekocht",           84,  5.4, 15.6, 0.2, 150, 0, []),
    ("Sauerkraut",                19,  0.9,  4.3, 0.1, 150, 0, []),

    # --- Fleisch & Fisch --------------------------------------------
    ("Hühnerbrust, roh",        120, 23.0,  0.0, 2.6, 150, 0, [("1 Stück", 150)]),
    ("Hühnerbrust, gebraten",   165, 31.0,  0.0, 3.6, 150, 0, []),
    ("Putenbrust, roh",          111, 24.0,  0.0, 1.4, 150, 0, []),
    ("Schweinefleisch, mager",   143, 21.0,  0.0, 6.0, 150, 0, []),
    ("Schweinsschnitzel, paniert",290, 20.0, 15.0, 17.0, 180, 0, [("1 Schnitzel", 180)]),
    ("Faschiertes, gemischt",    250, 17.0,  0.0, 20.0, 150, 0, []),
    ("Rindfleisch, mager",       150, 22.0,  0.0, 6.5, 150, 0, []),
    ("Speck",                    350, 14.0,  0.5, 32.0,  30, 0, [("1 Scheibe", 15)]),
    ("Extrawurst",               280, 12.0,  1.0, 25.0,  50, 0, [("1 Scheibe", 25)]),
    ("Lachs, roh",               208, 20.0,  0.0, 13.0, 150, 0, []),
    ("Thunfisch, Dose in Wasser", 99, 22.0,  0.0, 0.8, 120, 0, [("1 Dose", 120)]),
    ("Frankfurter / Wiener",     290, 12.0,  1.5, 26.0, 100, 0, [("1 Paar", 100)]),
    ("Leberkäse",               300, 12.0,  2.0, 27.0, 120, 0, [("1 Semmel-Portion", 120)]),

    # --- Milchprodukte & Eier ---------------------------------------
    ("Ei, gekocht",              155, 13.0,  1.1, 11.0,  60, 0, [("1 Stück", 60)]),
    ("Milch 3,5%",                64,  3.3,  4.8, 3.5, 250, 1, [("1 Glas", 250)]),
    ("Milch 1,5%",                47,  3.4,  4.9, 1.5, 250, 1, [("1 Glas", 250)]),
    ("Naturjoghurt 3,6%",         66,  3.5,  4.7, 3.6, 250, 0, [("1 Becher", 250)]),
    ("Topfen 20%",               123, 12.0,  3.2, 6.0, 250, 0, []),
    ("Hüttenkäse",              98, 11.0,  3.4, 4.3, 200, 0, []),
    ("Gouda",                    356, 25.0,  2.2, 27.0,  30, 0, [("1 Scheibe", 30)]),
    ("Emmentaler",               380, 28.0,  1.5, 29.0,  30, 0, [("1 Scheibe", 30)]),
    ("Frischkäse",              250,  6.0,  3.5, 24.0,  20, 0, []),
    ("Butter",                   740,  0.7,  0.6, 82.0,  10, 0, [("1 Messerspitze", 5)]),
    ("Schlagobers",              290,  2.4,  3.2, 30.0,  50, 1, []),

    # --- Getreide & Beilagen ----------------------------------------
    ("Reis, gekocht",            130,  2.7, 28.2, 0.3, 200, 0, []),
    ("Reis, roh",                355,  7.0, 78.0, 0.7,  75, 0, []),
    ("Nudeln, gekocht",          158,  5.8, 30.9, 0.9, 250, 0, []),
    ("Nudeln, roh",              360, 12.5, 71.0, 1.5, 100, 0, []),
    ("Semmel",                   270,  9.0, 54.0, 1.5,  50, 0, [("1 Stück", 50)]),
    ("Mischbrot",                240,  7.0, 46.0, 1.2,  50, 0, [("1 Scheibe", 50)]),
    ("Vollkornbrot",             215,  8.0, 38.0, 2.5,  50, 0, [("1 Scheibe", 50)]),
    ("Haferflocken",             370, 13.5, 59.0, 7.0,  60, 0, [("1 Portion", 60)]),
    ("Müsli, ungesüßt",       360, 10.0, 60.0, 8.0,  60, 0, []),
    ("Knödel, Semmelknödel",   180,  6.0, 27.0, 5.0, 100, 0, [("1 Stück", 100)]),
    ("Pommes frites, frittiert", 312,  3.4, 41.0, 15.0, 150, 0, []),
    ("Spätzle, gekocht",        170,  6.0, 28.0, 3.5, 200, 0, []),
    ("Linsen, gekocht",          116,  9.0, 20.0, 0.4, 150, 0, []),
    ("Kichererbsen, gekocht",    164,  8.9, 27.4, 2.6, 150, 0, []),

    # --- Fette, Nüsse, Süßes -------------------------------------
    ("Olivenöl",                884,  0.0,  0.0, 100.0, 10, 1, [("1 EL", 10)]),
    ("Rapsöl",                  884,  0.0,  0.0, 100.0, 10, 1, [("1 EL", 10)]),
    ("Walnüsse",                654, 15.0, 14.0, 65.0,  30, 0, []),
    ("Mandeln",                  579, 21.0, 22.0, 50.0,  30, 0, []),
    ("Erdnussbutter",            588, 25.0, 20.0, 50.0,  20, 0, [("1 EL", 20)]),
    ("Zucker",                   400,  0.0, 100.0, 0.0,   5, 0, [("1 TL", 5)]),
    ("Honig",                    304,  0.3, 82.0, 0.0,  20, 0, [("1 TL", 7)]),
    ("Milchschokolade",          535,  7.7, 59.0, 30.0,  25, 0, [("1 Riegel", 100)]),

    # --- Getränke --------------------------------------------------
    ("Wasser",                     0,  0.0,  0.0, 0.0, 500, 1, []),
    ("Kaffee, schwarz",            2,  0.1,  0.0, 0.0, 200, 1, [("1 Tasse", 200)]),
    ("Kaffee mit Milch",          25,  1.3,  1.9, 1.4, 200, 1, []),
    ("Orangensaft",               45,  0.7, 10.4, 0.2, 250, 1, [("1 Glas", 250)]),
    ("Apfelsaft",                 46,  0.1, 11.3, 0.1, 250, 1, [("1 Glas", 250)]),
    ("Bier, hell",                43,  0.5,  3.6, 0.0, 500, 1, [("1 Krügerl", 500), ("1 Seidl", 300)]),
    ("Weißwein",                 82,  0.1,  2.6, 0.0, 125, 1, [("1 Glas", 125)]),
    ("Rotwein",                   85,  0.1,  2.6, 0.0, 125, 1, [("1 Glas", 125)]),
    ("Cola",                      42,  0.0, 10.6, 0.0, 330, 1, [("1 Dose", 330)]),
    ("Radler",                    50,  0.3,  8.0, 0.0, 500, 1, []),
]


def seed(con) -> int:
    """Legt die Grundnahrungsmittel an. Idempotent ueber (source, source_id)."""
    added = 0
    for name, kcal, p, c, f, default_g, liquid, portions in BASE_FOODS:
        key = name.lower().replace(" ", "-").replace(",", "")
        cur = con.execute(
            """INSERT INTO foods
               (source, source_id, name, kcal_100, protein_100, carbs_100,
                fat_100, default_g, is_liquid)
               VALUES ('base', ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source, source_id) WHERE source_id IS NOT NULL DO NOTHING""",
            (key, name, kcal, p, c, f, default_g, liquid),
        )
        if cur.rowcount:
            added += 1
            food_id = cur.lastrowid
            for label, grams in portions:
                con.execute(
                    "INSERT INTO portions(food_id, label, grams) VALUES (?, ?, ?)",
                    (food_id, label, grams),
                )
    con.commit()
    return added
