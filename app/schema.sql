PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------
-- KATALOG (veraenderlich)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS foods (
  id          INTEGER PRIMARY KEY,
  source      TEXT NOT NULL,              -- 'off' | 'base' | 'custom'
  source_id   TEXT,                       -- EAN bei OFF, sonst NULL
  name        TEXT NOT NULL,
  brand       TEXT,
  kcal_100    REAL NOT NULL,
  protein_100 REAL DEFAULT 0,
  carbs_100   REAL DEFAULT 0,
  fat_100     REAL DEFAULT 0,
  fiber_100   REAL DEFAULT 0,
  default_g   REAL,                       -- typische Portion in g
  is_liquid   INTEGER NOT NULL DEFAULT 0, -- 1 = UI zeigt ml
  suspect     INTEGER NOT NULL DEFAULT 0, -- Plausibilitaetspruefung fehlgeschlagen
  use_count   INTEGER NOT NULL DEFAULT 0,
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_foods_src  ON foods(source, source_id)
  WHERE source_id IS NOT NULL;
CREATE INDEX        IF NOT EXISTS ix_foods_use  ON foods(use_count DESC);

-- Volltextsuche. Wird per Trigger synchron gehalten.
CREATE VIRTUAL TABLE IF NOT EXISTS foods_fts USING fts5(
  name, brand, content='foods', content_rowid='id',
  tokenize="unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS foods_ai AFTER INSERT ON foods BEGIN
  INSERT INTO foods_fts(rowid, name, brand) VALUES (new.id, new.name, new.brand);
END;
CREATE TRIGGER IF NOT EXISTS foods_ad AFTER DELETE ON foods BEGIN
  INSERT INTO foods_fts(foods_fts, rowid, name, brand)
    VALUES('delete', old.id, old.name, old.brand);
END;
CREATE TRIGGER IF NOT EXISTS foods_au AFTER UPDATE OF name, brand ON foods BEGIN
  INSERT INTO foods_fts(foods_fts, rowid, name, brand)
    VALUES('delete', old.id, old.name, old.brand);
  INSERT INTO foods_fts(rowid, name, brand) VALUES (new.id, new.name, new.brand);
END;

-- Haushaltsmasse: "1 Scheibe" = 45 g
CREATE TABLE IF NOT EXISTS portions (
  id      INTEGER PRIMARY KEY,
  food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
  label   TEXT NOT NULL,
  grams   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_portions_food ON portions(food_id);

-- ---------------------------------------------------------------
-- LOG (unveraenderlich: Naehrwerte werden eingefroren)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_entries (
  id         INTEGER PRIMARY KEY,
  day        TEXT NOT NULL,               -- 'YYYY-MM-DD', lokale Zeit
  logged_at  TEXT NOT NULL DEFAULT (datetime('now')),
  meal       TEXT NOT NULL DEFAULT 'snack',
  name       TEXT NOT NULL,
  brand      TEXT,
  amount_g   REAL NOT NULL,
  kcal       REAL NOT NULL,
  protein    REAL DEFAULT 0,
  carbs      REAL DEFAULT 0,
  fat        REAL DEFAULT 0,
  food_id    INTEGER,                     -- nur Herkunft, bewusst ohne FK-Zwang
  input      TEXT NOT NULL DEFAULT 'search', -- barcode|search|manual|repeat
  confidence TEXT NOT NULL DEFAULT 'exact'   -- exact|estimated
);
CREATE INDEX IF NOT EXISTS ix_log_day ON log_entries(day);

-- ---------------------------------------------------------------
-- EINSTELLUNGEN
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO settings(key, value) VALUES
  ('kcal_target', '2200'),
  ('protein_target', '130');
