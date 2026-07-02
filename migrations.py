"""
Lightweight, dependency-free "migrations" that run automatically every
time the app starts (see app.py -> create_app()).

This app uses a plain SQLite file rather than a full migration framework
(like Alembic), so when a column gets added to a model in models.py, an
*existing* database file on someone's computer doesn't automatically get
that column -- SQLAlchemy's db.create_all() only creates tables that don't
exist yet, it never alters existing ones. That mismatch is what caused:

    sqlite3.OperationalError: no such column: residents.contact_number

The functions below fix that safely:
  - ensure_resident_columns(): adds any columns that exist on the Resident
    model but not on the actual residents table yet. This never touches
    existing data/rows, it only adds new (empty) columns.
  - sync_geo_data(): re-imports data/geocode.csv into the GeoBarangay
    reference table whenever that CSV file changes, so replacing the CSV
    (e.g. with updated province/city/barangay data) actually takes effect
    without anyone needing to delete the database by hand.
"""
import csv
import hashlib
import os

from sqlalchemy import inspect, text

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CSV_PATH = os.path.join(BASE_DIR, "data", "geocode.csv")


def ensure_resident_columns(db):
    """Add any columns missing from the residents table, without touching
    existing rows. Safe to run on every startup. Works on both SQLite
    (local dev) and Postgres (Render) via SQLAlchemy's inspector instead
    of SQLite-only PRAGMA statements."""
    from models import Resident

    engine = db.engine
    inspector = inspect(engine)

    if not inspector.has_table("residents"):
        # Table doesn't exist yet at all (fresh install) -- db.create_all()
        # in app.py already handles that case, nothing to do here.
        return

    existing = {col["name"] for col in inspector.get_columns("residents")}

    with engine.connect() as conn:
        added = []
        for column in Resident.__table__.columns:
            if column.name in existing:
                continue

            col_type = _column_type_for(column, engine.dialect.name)
            ddl = f"ALTER TABLE residents ADD COLUMN {column.name} {col_type}"
            default_clause = _default_clause_for(column, engine.dialect.name)
            if default_clause:
                ddl += f" {default_clause}"
            conn.execute(text(ddl))
            added.append(column.name)

        if added:
            conn.commit()
            print(f"[migrations] Added missing column(s) to residents table: {', '.join(added)}")


def _column_type_for(column, dialect_name):
    from sqlalchemy import Boolean, DateTime, Integer, String

    if isinstance(column.type, Integer):
        return "INTEGER"
    if isinstance(column.type, Boolean):
        return "BOOLEAN"
    if isinstance(column.type, DateTime):
        # SQLite accepts "DATETIME" as a type affinity; Postgres does not
        # have a DATETIME type and requires TIMESTAMP instead.
        return "TIMESTAMP" if dialect_name == "postgresql" else "DATETIME"
    if isinstance(column.type, String):
        return "VARCHAR"
    return "TEXT"


def _default_clause_for(column, dialect_name):
    """Returns a ' DEFAULT ...' clause for columns with a simple scalar
    default, so existing rows are backfilled instead of left NULL when a
    new NOT NULL-ish column (e.g. Resident.source) is added to a table
    that already has data."""
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return ""
    value = default.arg
    if isinstance(value, str):
        return f"DEFAULT '{value}'"
    if isinstance(value, bool):
        if dialect_name == "postgresql":
            return f"DEFAULT {'TRUE' if value else 'FALSE'}"
        return f"DEFAULT {1 if value else 0}"
    if isinstance(value, (int, float)):
        return f"DEFAULT {value}"
    return ""


def _file_hash(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def sync_geo_data(db):
    """(Re)import data/geocode.csv into GeoBarangay whenever the CSV's
    contents have changed since the last import. Safe to run on every
    startup -- it's a no-op if nothing changed."""
    from models import AppMeta, GeoBarangay

    current_hash = _file_hash(CSV_PATH)
    if current_hash is None:
        return

    stored = db.session.get(AppMeta, "geocode_csv_hash")
    if stored is not None and stored.value == current_hash:
        return  # already up to date

    print("[migrations] geocode.csv changed, refreshing barangay/city/province reference data...")

    batch = []
    seen_geocodes = set()
    skipped = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            geocode = (row.get("geocode") or "").strip()
            if not geocode or geocode in seen_geocodes:
                skipped += 1
                continue
            seen_geocodes.add(geocode)
            batch.append(
                {
                    "region": row["region"],
                    "province": row["province"],
                    "city_municipality": row["city_municipality"],
                    "barangay": row["barangay"],
                    "geocode": geocode,
                }
            )

    # Replace the table contents wholesale so stale rows never linger.
    GeoBarangay.query.delete()
    db.session.bulk_insert_mappings(GeoBarangay, batch)

    meta = db.session.get(AppMeta, "geocode_csv_hash")
    if meta is None:
        meta = AppMeta(key="geocode_csv_hash", value=current_hash)
        db.session.add(meta)
    else:
        meta.value = current_hash

    db.session.commit()
    print(f"[migrations] Imported {len(batch)} barangay records"
          + (f" ({skipped} duplicate/blank row(s) skipped)." if skipped else "."))


MASTERLIST_CSV_PATH = os.path.join(BASE_DIR, "data", "masterlist.csv")


def sync_masterlist_data(db):
    """(Re)imports data/masterlist.csv -- the baked-in RTS/masterlist
    spreadsheet (e.g. DASMA_RTS.xlsx, all sheets) -- whenever that file's
    contents change. Unlike sync_geo_data(), this NEVER deletes or
    overwrites existing residents: it only inserts brand-new TRNs that
    aren't in the residents table yet, so nobody's live delivery status is
    ever touched by this. Safe to run on every startup."""
    from models import AppMeta, Resident

    current_hash = _file_hash(MASTERLIST_CSV_PATH)
    if current_hash is None:
        return

    stored = db.session.get(AppMeta, "masterlist_csv_hash")
    if stored is not None and stored.value == current_hash:
        return  # already imported, nothing changed

    print("[migrations] masterlist.csv changed, importing new resident records...")

    inserted = 0
    skipped_existing = 0
    with open(MASTERLIST_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    existing = {
        r[0] for r in db.session.query(Resident.id_number).filter(
            Resident.id_number.in_([row["id_number"] for row in all_rows])
        )
    } if all_rows else set()

    for row in all_rows:
        id_number = (row.get("id_number") or "").strip()
        if not id_number or id_number in existing:
            skipped_existing += 1
            continue
        db.session.add(Resident(
            id_number=id_number,
            first_name=(row.get("first_name") or "").strip(),
            middle_name=(row.get("middle_name") or "").strip() or None,
            last_name=(row.get("last_name") or "").strip(),
            suffix=(row.get("suffix") or "").strip() or None,
            province=(row.get("province") or "UNSPECIFIED").strip(),
            city_municipality=(row.get("city_municipality") or "UNSPECIFIED").strip(),
            barangay=(row.get("barangay") or "").strip(),
            geocode=(row.get("geocode") or "").strip() or None,
            source="masterlist_import",
        ))
        inserted += 1

    meta = db.session.get(AppMeta, "masterlist_csv_hash")
    if meta is None:
        meta = AppMeta(key="masterlist_csv_hash", value=current_hash)
        db.session.add(meta)
    else:
        meta.value = current_hash

    db.session.commit()
    print(f"[migrations] Masterlist import: {inserted} new resident(s) added"
          + (f", {skipped_existing} already existed (untouched)." if skipped_existing else "."))


def run_all(db):
    ensure_resident_columns(db)
    sync_geo_data(db)
    sync_masterlist_data(db)
