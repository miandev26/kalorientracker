"""Kalorientracker - lokale Web-App.

Start:  uvicorn app.main:app --host 0.0.0.0 --port 8101
"""
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import base_foods, db

BASE_DIR = Path(__file__).parent
OFF_ONLINE = os.environ.get("OFF_ONLINE", "1") == "1"

app = FastAPI(title="Kalorientracker")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

MEALS = [
    ("fruehstueck", "Frühstück"),
    ("mittag", "Mittag"),
    ("abend", "Abend"),
    ("snack", "Snack"),
]
MEAL_LABELS = dict(MEALS)


@app.on_event("startup")
def startup():
    db.init()
    with db.connect() as con:
        # Idempotent - läuft auch dann sauber, wenn der OFF-Import
        # die Datenbank vor dem ersten App-Start schon befüllt hat.
        added = base_foods.seed(con)
        n = con.execute("SELECT COUNT(*) c FROM foods").fetchone()["c"]
        print(f"Katalog: {n} Lebensmittel ({added} neu angelegt)")


# ===============================================================
# Helfer
# ===============================================================
def today_str() -> str:
    return date.today().isoformat()


def parse_day(value: str | None) -> str:
    if not value:
        return today_str()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(400, "Ungültiges Datum")


def day_summary(con, day: str) -> dict:
    row = con.execute(
        """SELECT COALESCE(SUM(kcal),0) kcal, COALESCE(SUM(protein),0) protein,
                  COALESCE(SUM(carbs),0) carbs, COALESCE(SUM(fat),0) fat,
                  COUNT(*) n,
                  COALESCE(SUM(CASE WHEN confidence='estimated' THEN kcal END),0) est_kcal
           FROM log_entries WHERE day = ?""",
        (day,),
    ).fetchone()
    return dict(row)


def fts_query(q: str) -> str:
    """Nutzereingabe in eine sichere FTS5-Prefix-Query uebersetzen."""
    words = re.findall(r"[\wäöüßÄÖÜ]+", q, flags=re.UNICODE)
    return " ".join(f'"{w}"*' for w in words if len(w) > 1)


def search_foods(con, q: str, limit: int = 30) -> list:
    q = (q or "").strip()
    if not q:
        return con.execute(
            "SELECT * FROM foods WHERE use_count > 0 ORDER BY use_count DESC LIMIT ?",
            (limit,),
        ).fetchall()

    fq = fts_query(q)
    rows = []
    if fq:
        rows = con.execute(
            """SELECT f.* FROM foods_fts
               JOIN foods f ON f.id = foods_fts.rowid
               WHERE foods_fts MATCH ?
               ORDER BY f.suspect ASC, f.use_count DESC, bm25(foods_fts)
               LIMIT ?""",
            (fq, limit),
        ).fetchall()
    if not rows:  # Fallback fuer Teilwoerter mitten im Namen
        rows = con.execute(
            """SELECT * FROM foods WHERE name LIKE ?
               ORDER BY suspect ASC, use_count DESC LIMIT ?""",
            (f"%{q}%", limit),
        ).fetchall()
    return rows


def food_dict(f) -> dict:
    return {
        "id": f["id"], "name": f["name"], "brand": f["brand"],
        "kcal_100": f["kcal_100"], "protein_100": f["protein_100"],
        "carbs_100": f["carbs_100"], "fat_100": f["fat_100"],
        "default_g": f["default_g"] or 100, "is_liquid": f["is_liquid"],
        "suspect": f["suspect"], "source": f["source"],
    }


def with_portions(con, foods: list) -> list:
    out = []
    for f in foods:
        d = food_dict(f)
        d["portions"] = [
            {"label": p["label"], "grams": p["grams"]}
            for p in con.execute(
                "SELECT label, grams FROM portions WHERE food_id = ? ORDER BY grams",
                (f["id"],),
            )
        ]
        out.append(d)
    return out


# ===============================================================
# Seiten
# ===============================================================
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return day_view(request, today_str())


@app.get("/tag/{day}", response_class=HTMLResponse)
def day_page(request: Request, day: str):
    return day_view(request, parse_day(day))


def day_view(request: Request, day: str) -> HTMLResponse:
    with db.connect() as con:
        entries = con.execute(
            "SELECT * FROM log_entries WHERE day = ? ORDER BY logged_at", (day,)
        ).fetchall()
        summary = day_summary(con, day)
        target = float(db.get_setting(con, "kcal_target", "2200"))
        p_target = float(db.get_setting(con, "protein_target", "130"))

    by_meal = {key: [] for key, _ in MEALS}
    for e in entries:
        by_meal.setdefault(e["meal"], []).append(e)

    d = date.fromisoformat(day)
    return templates.TemplateResponse(
        "day.html",
        {
            "request": request, "day": day, "is_today": day == today_str(),
            "day_label": f"{['Mo','Di','Mi','Do','Fr','Sa','So'][d.weekday()]}, {d.strftime('%d.%m.%Y')}",
            "prev_day": (d - timedelta(days=1)).isoformat(),
            "next_day": (d + timedelta(days=1)).isoformat(),
            "meals": MEALS, "by_meal": by_meal, "summary": summary,
            "target": target, "protein_target": p_target,
            "remaining": round(target - summary["kcal"]),
            "pct": min(100, round(summary["kcal"] / target * 100)) if target else 0,
        },
    )


@app.get("/suchen", response_class=HTMLResponse)
def search_page(request: Request, q: str = "", meal: str = "", day: str = ""):
    day = parse_day(day)
    with db.connect() as con:
        results = with_portions(con, search_foods(con, q))
        recent = con.execute(
            """SELECT name, brand, amount_g, kcal, protein, carbs, fat, food_id,
                      MAX(logged_at) la, COUNT(*) n
               FROM log_entries GROUP BY name, brand, amount_g
               ORDER BY n DESC, la DESC LIMIT 12"""
        ).fetchall() if not q else []
    return templates.TemplateResponse(
        "search.html",
        {"request": request, "q": q, "results": results, "recent": recent,
         "meal": meal or current_meal(), "day": day, "meals": MEALS},
    )


@app.get("/scannen", response_class=HTMLResponse)
def scan_page(request: Request, meal: str = "", day: str = ""):
    return templates.TemplateResponse(
        "scan.html",
        {"request": request, "meal": meal or current_meal(),
         "day": parse_day(day), "meals": MEALS},
    )


@app.get("/neu", response_class=HTMLResponse)
def new_food_page(request: Request, ean: str = "", name: str = "",
                  meal: str = "", day: str = ""):
    return templates.TemplateResponse(
        "food_new.html",
        {"request": request, "ean": ean, "name": name,
         "meal": meal or current_meal(), "day": parse_day(day), "meals": MEALS},
    )


@app.post("/neu")
def new_food_save(
    name: str = Form(...), brand: str = Form(""), ean: str = Form(""),
    kcal_100: float = Form(...), protein_100: float = Form(0),
    carbs_100: float = Form(0), fat_100: float = Form(0),
    default_g: float = Form(100), is_liquid: int = Form(0),
    meal: str = Form("snack"), day: str = Form(""),
):
    day = parse_day(day)
    with db.connect() as con:
        cur = con.execute(
            """INSERT INTO foods(source, source_id, name, brand, kcal_100,
                   protein_100, carbs_100, fat_100, default_g, is_liquid)
               VALUES ('custom', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ean.strip() or None, name.strip(), brand.strip() or None, kcal_100,
             protein_100, carbs_100, fat_100, default_g, is_liquid),
        )
        con.commit()
        food_id = cur.lastrowid
    return RedirectResponse(
        f"/suchen?q={name}&meal={meal}&day={day}#food-{food_id}", status_code=303
    )


@app.get("/statistik", response_class=HTMLResponse)
def stats_page(request: Request, days: int = 30):
    days = max(7, min(days, 180))
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with db.connect() as con:
        rows = con.execute(
            """SELECT day, SUM(kcal) kcal, SUM(protein) protein,
                      SUM(carbs) carbs, SUM(fat) fat,
                      SUM(CASE WHEN confidence='estimated' THEN kcal ELSE 0 END) est
               FROM log_entries WHERE day >= ?
               GROUP BY day ORDER BY day DESC""",
            (since,),
        ).fetchall()
        by_input = con.execute(
            """SELECT input, COUNT(*) n, SUM(kcal) kcal FROM log_entries
               WHERE day >= ? GROUP BY input ORDER BY kcal DESC""",
            (since,),
        ).fetchall()
        target = float(db.get_setting(con, "kcal_target", "2200"))
    avg = round(sum(r["kcal"] for r in rows) / len(rows)) if rows else 0
    total_kcal = sum(r["kcal"] for r in rows) or 1
    return templates.TemplateResponse(
        "stats.html",
        {"request": request, "rows": rows, "days": days, "avg": avg,
         "target": target, "by_input": by_input, "total_kcal": total_kcal,
         "max_kcal": max([r["kcal"] for r in rows], default=1)},
    )


@app.get("/einstellungen", response_class=HTMLResponse)
def settings_page(request: Request):
    with db.connect() as con:
        target = db.get_setting(con, "kcal_target", "2200")
        p_target = db.get_setting(con, "protein_target", "130")
        counts = con.execute(
            "SELECT source, COUNT(*) n FROM foods GROUP BY source"
        ).fetchall()
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "target": target, "protein_target": p_target,
         "counts": counts, "off_online": OFF_ONLINE},
    )


@app.post("/einstellungen")
def settings_save(kcal_target: int = Form(...), protein_target: int = Form(...)):
    with db.connect() as con:
        db.set_setting(con, "kcal_target", kcal_target)
        db.set_setting(con, "protein_target", protein_target)
        con.commit()
    return RedirectResponse("/einstellungen", status_code=303)


def current_meal() -> str:
    h = datetime.now().hour
    if h < 10:
        return "fruehstueck"
    if h < 15:
        return "mittag"
    if h < 21:
        return "abend"
    return "snack"


# ===============================================================
# API
# ===============================================================
@app.get("/api/search")
def api_search(q: str = "", limit: int = 30):
    with db.connect() as con:
        return {"results": with_portions(con, search_foods(con, q, limit))}


@app.get("/api/barcode/{ean}")
def api_barcode(ean: str):
    ean = re.sub(r"\D", "", ean)
    if not ean:
        raise HTTPException(400, "Kein gültiger Barcode")

    with db.connect() as con:
        row = con.execute(
            "SELECT * FROM foods WHERE source_id = ? ORDER BY source='off' DESC LIMIT 1",
            (ean,),
        ).fetchone()
        if row:
            return {"found": True, "origin": "lokal",
                    "food": with_portions(con, [row])[0]}

    if OFF_ONLINE:
        food = fetch_off_online(ean)
        if food:
            with db.connect() as con:
                cur = con.execute(
                    """INSERT INTO foods(source, source_id, name, brand, kcal_100,
                           protein_100, carbs_100, fat_100, default_g, suspect)
                       VALUES('off', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(source, source_id) WHERE source_id IS NOT NULL DO NOTHING""",
                    (ean, food["name"], food["brand"], food["kcal_100"],
                     food["protein_100"], food["carbs_100"], food["fat_100"],
                     food["default_g"], food["suspect"]),
                )
                con.commit()
                row = con.execute(
                    "SELECT * FROM foods WHERE source='off' AND source_id = ?", (ean,)
                ).fetchone()
            if row:
                return {"found": True, "origin": "Open Food Facts",
                        "food": with_portions(con, [row])[0]}

    return JSONResponse({"found": False, "ean": ean}, status_code=404)


def fetch_off_online(ean: str) -> dict | None:
    """Fallback auf die OFF-API, wenn der EAN lokal fehlt."""
    try:
        import httpx
        url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
        r = httpx.get(url, timeout=6.0, params={
            "fields": "product_name,product_name_de,brands,nutriments,serving_quantity"
        }, headers={"User-Agent": "lokaler-kalorientracker/1.0"})
        if r.status_code != 200:
            return None
        p = r.json().get("product") or {}
        n = p.get("nutriments") or {}
        kcal = n.get("energy-kcal_100g")
        if kcal is None and n.get("energy_100g"):
            kcal = float(n["energy_100g"]) / 4.184
        if kcal is None:
            return None
        name = p.get("product_name_de") or p.get("product_name") or f"EAN {ean}"
        f = {
            "name": name.strip()[:120],
            "brand": (p.get("brands") or "").split(",")[0].strip() or None,
            "kcal_100": round(float(kcal), 1),
            "protein_100": float(n.get("proteins_100g") or 0),
            "carbs_100": float(n.get("carbohydrates_100g") or 0),
            "fat_100": float(n.get("fat_100g") or 0),
            "default_g": float(p.get("serving_quantity") or 100) or 100,
        }
        f["suspect"] = int(db.is_suspect(f["kcal_100"], f["protein_100"],
                                         f["carbs_100"], f["fat_100"]))
        return f
    except Exception as exc:  # Offline oder Timeout - kein Grund zum Absturz
        print(f"OFF-Abfrage fehlgeschlagen: {exc}")
        return None


@app.post("/api/log")
def api_log(
    food_id: int = Form(None), name: str = Form(None), brand: str = Form(""),
    amount_g: float = Form(...), meal: str = Form("snack"), day: str = Form(""),
    kcal: float = Form(None), protein: float = Form(0), carbs: float = Form(0),
    fat: float = Form(0), input: str = Form("search"),
    confidence: str = Form("exact"), redirect: str = Form("/"),
):
    day = parse_day(day)
    if amount_g <= 0:
        raise HTTPException(400, "Menge muss größer als 0 sein")

    with db.connect() as con:
        if food_id:
            f = con.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
            if not f:
                raise HTTPException(404, "Lebensmittel nicht gefunden")
            vals = db.scale(f, amount_g)
            name, brand = f["name"], f["brand"]
            kcal, protein = vals["kcal"], vals["protein"]
            carbs, fat = vals["carbs"], vals["fat"]
            con.execute("UPDATE foods SET use_count = use_count + 1 WHERE id = ?",
                        (food_id,))
        elif name is None or kcal is None:
            raise HTTPException(400, "Name und Kalorien fehlen")

        con.execute(
            """INSERT INTO log_entries(day, meal, name, brand, amount_g, kcal,
                   protein, carbs, fat, food_id, input, confidence)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (day, meal, name, brand or None, amount_g, kcal, protein, carbs, fat,
             food_id, input, confidence),
        )
        con.commit()
    return RedirectResponse(redirect or f"/tag/{day}", status_code=303)


@app.post("/api/log/{entry_id}/loeschen")
def api_log_delete(entry_id: int, redirect: str = Form("/")):
    with db.connect() as con:
        con.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))
        con.commit()
    return RedirectResponse(redirect or "/", status_code=303)


@app.post("/api/log/{entry_id}/wiederholen")
def api_log_repeat(entry_id: int, meal: str = Form(None), redirect: str = Form("/")):
    with db.connect() as con:
        e = con.execute("SELECT * FROM log_entries WHERE id = ?", (entry_id,)).fetchone()
        if not e:
            raise HTTPException(404, "Eintrag nicht gefunden")
        con.execute(
            """INSERT INTO log_entries(day, meal, name, brand, amount_g, kcal,
                   protein, carbs, fat, food_id, input, confidence)
               VALUES(?,?,?,?,?,?,?,?,?,?,'repeat',?)""",
            (today_str(), meal or e["meal"], e["name"], e["brand"], e["amount_g"],
             e["kcal"], e["protein"], e["carbs"], e["fat"], e["food_id"],
             e["confidence"]),
        )
        con.commit()
    return RedirectResponse(redirect or "/", status_code=303)


@app.get("/api/gestern")
def api_yesterday():
    """Eintraege von gestern - Basis fuer 'wie gestern'."""
    y = (date.today() - timedelta(days=1)).isoformat()
    with db.connect() as con:
        rows = con.execute(
            "SELECT * FROM log_entries WHERE day = ? ORDER BY logged_at", (y,)
        ).fetchall()
    return {"day": y, "entries": [dict(r) for r in rows]}


@app.get("/healthz")
def healthz():
    with db.connect() as con:
        n = con.execute("SELECT COUNT(*) c FROM foods").fetchone()["c"]
    return {"ok": True, "foods": n}
