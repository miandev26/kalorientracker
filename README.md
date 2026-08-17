# Kalorientracker

Lokale Web-App für den MiniPC. Barcode scannen, Menge eingeben, fertig.
FastAPI + SQLite, server-rendered, keine externen Abhängigkeiten zur Laufzeit.

Läuft ausschließlich im eigenen Netz. Keine Cloud, keine Anmeldung,
keine externen Abhängigkeiten zur Laufzeit.

```
Handy im LAN ──▶ MiniPC :8101 (HTTP)  ──▶ SQLite
             └─▶ MiniPC :8443 (HTTPS) ──┘   Katalog + Tagebuch
                    │
                    └─ nur hier gibt der Browser die Kamera frei

Barcode wird im Browser dekodiert (BarcodeDetector / ZXing, lokal gebündelt).
Der Server bekommt nur die fertige Ziffernfolge zu sehen.
```

## Starten

```bash
git clone <repo> kcal && cd kcal
docker compose up -d --build
```

Danach läuft die App auf `http://minipc:8101`. Für den Kamera-Scanner
kommt noch ein Zertifikat dazu, siehe nächster Abschnitt. Beim ersten Start
werden 83 Grundnahrungsmittel angelegt — Obst, Gemüse, Fleisch, Beilagen, Getränke.
Damit ist die App sofort benutzbar, auch ohne OFF-Dump.

Ohne Docker:

```bash
pip install -r requirements.txt
KCAL_DB=./data/kcal.db uvicorn app.main:app --host 0.0.0.0 --port 8101

# mit HTTPS, nachdem ./scripts/zertifikat.sh gelaufen ist
KCAL_DB=./data/kcal.db uvicorn app.main:app --host 0.0.0.0 --port 8443 \
  --ssl-certfile data/certs/cert.pem --ssl-keyfile data/certs/key.pem
```

## HTTPS — sonst bleibt die Kamera tot

Das ist der einzige unbequeme Teil, und er lässt sich nicht umgehen: Browser
geben `getUserMedia` nur in einem *Secure Context* frei. Das heißt HTTPS oder
`localhost` — sonst nichts. Ein privates Netz oder ein VPN ändern daran
nichts, weil der Browser gar nicht weiß, dass die Verbindung vertrauenswürdig
ist. Er sieht nur `http://` und sperrt die Kamera.

Deshalb läuft die App auf zwei Ports:

| Port | Protokoll | Wofür |
|---|---|---|
| 8101 | HTTP | Katalog, Logging, Statistik, manuelle Barcode-Eingabe |
| 8443 | HTTPS | zusätzlich der Kamera-Scanner |

Zertifikat erzeugen — Hostname und LAN-IP des MiniPC angeben:

```bash
./scripts/zertifikat.sh minipc.local 192.168.0.42
docker compose restart
```

Danach am Handy `https://minipc.local:8443` aufrufen.

**Mit mkcert (empfohlen).** Ist `mkcert` installiert, signiert das Skript
gegen eine eigene lokale CA. Die Datei `rootCA.pem` einmal aufs Handy
übertragen und installieren — danach ist die App dort ohne jede Warnung
erreichbar, und „Zum Homescreen hinzufügen" macht daraus eine echte App
ohne Browserleiste.

```bash
apt install mkcert     # oder von github.com/FiloSottile/mkcert
```

**Ohne mkcert.** Das Skript erzeugt ein selbstsigniertes Zertifikat. Beim
ersten Aufruf kommt eine Warnung, einmal „Erweitert" → „Trotzdem fortfahren".
Ab dann gilt der Kontext als sicher und die Kamera funktioniert. Auf iOS ist
das etwas zäher als auf Android, weshalb sich mkcert dort besonders lohnt.

**Der faule Weg für Android-Chrome.** Wer gar keine Zertifikate anfassen
will, kann unter `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
die Adresse `http://minipc:8101` eintragen. Funktioniert, ist aber ein
globaler Schalter am Browser und kein Setup, das man einem zweiten Gerät
nochmal erklären möchte.

Ohne HTTPS bleibt die App voll benutzbar — die Scanseite blendet dann einen
Link auf den HTTPS-Port ein, und die manuelle EAN-Eingabe funktioniert auch
über HTTP.

## Zugriff aufs LAN begrenzen

Standardmäßig lauscht der Container auf allen Schnittstellen. Soll die App
nur über eine bestimmte Adresse erreichbar sein, in `docker-compose.yml` die
IP davorschreiben:

```yaml
ports:
  - "192.168.0.42:8101:8101"
  - "192.168.0.42:8443:8443"
```

Ein Port-Forwarding am Router ist nicht nötig und wäre auch keine gute Idee:
die App kennt keine Anmeldung.

## Open-Food-Facts-Dump importieren

Ohne Import fragt die App bei jedem unbekannten Barcode die OFF-API an und
merkt sich das Ergebnis lokal. Das reicht für den Alltag. Wer den Katalog
komplett offline haben will:

```bash
wget -O data/off.csv.gz \
  https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz

docker compose exec kcal python scripts/import_off.py /data/off.csv.gz
```

Gefiltert wird auf AT/DE/CH und auf plausible Nährwerte. Von rund 4 Mio.
Zeilen bleiben grob 300.000–500.000 übrig, die Datenbank landet bei ein paar
hundert MB. Auf einem N100 dauert der Durchlauf etwa 10–20 Minuten — der
Dump wird gestreamt, nicht entpackt.

Nützliche Optionen:

| Option | Wirkung |
|---|---|
| `--limit 20000` | Testlauf mit den ersten N Treffern |
| `--laender at` | nur Österreich |
| `--alle-laender` | kein Länderfilter (sehr groß) |

Monatlich per Cron aktualisieren ist sinnvoll, aber kein Muss —
`ON CONFLICT DO NOTHING` verhindert Dubletten.

Daten von Open Food Facts stehen unter ODbL.

## Wie die App rechnet

**Log-Einträge sind Snapshots.** Beim Eintragen werden die Nährwerte
ausgerechnet und als absolute Zahlen gespeichert. Korrigiert jemand später
einen Katalogeintrag, bleibt die Vergangenheit unverändert. `food_id` steht
nur als Herkunftsvermerk daneben.

**Jeder Eintrag merkt sich, wie er entstanden ist.** `input` unterscheidet
`barcode` / `search` / `manual` / `repeat`, `confidence` unterscheidet
`exact` (Herstellerangabe vom Etikett) von `estimated` (Katalogwert plus
geschätzte Menge). Die Tagesansicht zeigt an, welcher Anteil der Kalorien
geschätzt ist, die Statistik schlüsselt es auf. Wenn dieser Anteil über
40 % liegt, ist die Wochenbilanz eher Stimmungsbild als Messung.

**Plausibilitätsprüfung gegen OFF-Datenmüll.** Der häufigste Crowdsourcing-
Fehler ist kJ im kcal-Feld (Faktor 4,184 zu hoch). Geprüft wird auf
`kcal > 900`, auf `Eiweiß + KH + Fett > 105 g` und darauf, ob sich die Makros
zur angegebenen Energie zusammenrechnen (Toleranz 25 %). Beim Import fliegen
solche Einträge raus, beim Live-Lookup werden sie markiert.

## Aufbau

```
app/
  main.py         Routen
  db.py           SQLite-Zugriff, Plausibilität, Umrechnung
  schema.sql      Tabellen, FTS5-Index, Trigger
  base_foods.py   Grundnahrungsmittel ohne Barcode
  templates/      Jinja2
  static/
    app.css       Optik einer Küchenwaage
    scanner.js    BarcodeDetector mit ZXing-Fallback
    vendor/       ZXing (lokal gebündelt, läuft offline)
scripts/
  import_off.py   OFF-Dump-Import
  zertifikat.sh   TLS-Zertifikat fürs LAN (mkcert oder OpenSSL)
docker/
  entrypoint.sh   startet HTTP, plus HTTPS sobald ein Zertifikat da ist
```

Beide uvicorn-Prozesse teilen sich dieselbe SQLite-Datei. Das ist unkritisch,
weil WAL aktiv ist — gleichzeitiges Lesen und Schreiben ist damit erlaubt.

## Was noch fehlt

**Rezepte.** Selbstgekochtes einmal aus Komponenten anlegen, die App rechnet
auf 100 g runter, danach loggst du es wie ein Fertigprodukt. Die Tabellen
`meals` und `meal_items` liegen im Schema schon bereit. Das ist der größte
verbliebene Reibungspunkt und der nächste sinnvolle Schritt.

**Gewichtsverlauf.** Ohne Gewichtskurve daneben sagt die Kalorienbilanz
wenig — die tatsächliche Energiebilanz liest man am Trend ab, nicht an der
Summe.

**Export.** CSV-Dump des Tagebuchs, falls die Daten mal woanders hin sollen.

Kein Foto-Modul: Ein Bild kann keine Menge messen. Die Erkennung „das ist ein
Schnitzel" ist einfach, aber zwischen 150 g und 400 g liegen 600 kcal, und
Zubereitungsfett ist unsichtbar. Ein Barcode liefert stattdessen die
Herstellerangabe. Für alles ohne Barcode sind Katalogsuche und Rezepte der
genauere Weg.
