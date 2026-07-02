"""Imports a masterlist / Release Tracking Sheet (RTS) spreadsheet -- like
DASMA_RTS.xlsx -- into the Resident table, pre-loading everyone who's
expected to eventually get a PhilSys ID delivered to them.

Every sheet in the workbook is processed (not just the first one). Expected
columns, case-insensitive, in any order: TRN, MUNICIPALITY, BARANGAY,
FIRST NAME, MIDDLE NAME, LAST NAME, SUFFIX. A PROVINCE column is honored if
present; otherwise the province is looked up from the reference geocode
data by matching MUNICIPALITY (e.g. "DASMARIÑAS" resolves to "CITY OF
DASMARIÑAS" / "CAVITE").

Import is additive/idempotent: rows whose TRN (id_number) already exists in
the residents table are left completely untouched (their live delivery
status is never overwritten). Only brand-new TRNs get inserted, as
'pending' with source='masterlist_import'.
"""
import difflib
import re

ID_NUMBER_RE = re.compile(r"^\d{29}$")

_HEADER_ALIASES = {
    "trn": "trn",
    "id number": "trn",
    "id_number": "trn",
    "province": "province",
    "municipality": "municipality",
    "city": "municipality",
    "city_municipality": "municipality",
    "city/municipality": "municipality",
    "barangay": "barangay",
    "first name": "first_name",
    "middle name": "middle_name",
    "last name": "last_name",
    "suffix": "suffix",
    "contact number": "contact_number",
    "contact_number": "contact_number",
    "address": "address_line",
    "address line": "address_line",
}


def _norm(v):
    return re.sub(r"\s+", " ", str(v).strip().upper()) if v not in (None, "") else ""


_ROMAN_TO_ARABIC = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"}


def _normalize_barangay_key(s):
    """Loose comparison key for a barangay name: strips '(POB.)', periods,
    and ALL spaces (so 'P.F. ESPIRITU', 'P. F ESPIRITU', and 'P.F ESPIRITU'
    all collapse to the same key), then converts a trailing Roman numeral
    to its Arabic digit ('ZAPOTE III' == 'ZAPOTE 3')."""
    s = s.upper().strip()
    s = s.replace("(POB.)", "").replace("(POB)", "")
    s = re.sub(r"[.\s]+", " ", s).strip()
    tokens = s.split(" ")
    if tokens and tokens[-1] in _ROMAN_TO_ARABIC:
        tokens[-1] = _ROMAN_TO_ARABIC[tokens[-1]]
    return "".join(tokens)


# Some cities have gone through official barangay consolidations/renumbering
# since older RTS spreadsheets were made -- several old, smaller barangays
# get merged into one current barangay, and some just get renumbered. Keyed
# by (city_municipality, normalized old barangay name) -> current official
# barangay name. Applied to BOTH the geocode lookup and the barangay value
# actually saved on the resident record, since the app's area filters/
# dropdowns are built from the current official barangay list -- residents
# left with a retired barangay name wouldn't show up in those filters.
KNOWN_BARANGAY_CORRECTIONS = {
    ("CITY OF BACOOR", "SINEGUELASAN"): "SINBANALI",
    ("CITY OF BACOOR", "BANALO"): "SINBANALI",
    ("CITY OF BACOOR", "ALIMA"): "SINBANALI",
    ("CITY OF BACOOR", "TABINGDAGAT"): "POBLACION",
    ("CITY OF BACOOR", "CAMPOSANTO"): "POBLACION",
    ("CITY OF BACOOR", "DAANGBUKID"): "POBLACION",
    ("CITY OF BACOOR", "KAINGIN"): "KAINGIN DIGMAN",
    ("CITY OF BACOOR", "DIGMAN"): "KAINGIN DIGMAN",
    ("CITY OF BACOOR", "MABOLO1"): "MABOLO",
    ("CITY OF BACOOR", "MABOLO2"): "MABOLO",
    ("CITY OF BACOOR", "MABOLO3"): "MABOLO",
    ("CITY OF BACOOR", "SALINAS3"): "SALINAS 2",
    ("CITY OF BACOOR", "SALINAS4"): "SALINAS 2",
    ("CITY OF BACOOR", "MALIKSI3"): "MALIKSI 2",
    ("CITY OF BACOOR", "ZAPOTE2"): "ZAPOTE 1",
    ("CITY OF BACOOR", "ZAPOTE4"): "ZAPOTE 2",
    ("CITY OF BACOOR", "ZAPOTE5"): "ZAPOTE 3",
    ("CITY OF BACOOR", "TALABA3"): "TALABA 1",
    ("CITY OF BACOOR", "TALABA7"): "TALABA 1",
    ("CITY OF BACOOR", "TALABA4"): "TALABA 3",
    ("CITY OF BACOOR", "TALABA5"): "TALABA 3",
    ("CITY OF BACOOR", "TALABA6"): "TALABA 3",
    ("CITY OF BACOOR", "ANIBAN3"): "ANIBAN 1",
    ("CITY OF BACOOR", "ANIBAN5"): "ANIBAN 1",
    ("CITY OF BACOOR", "ANIBAN4"): "ANIBAN 2",
    ("CITY OF BACOOR", "MAMBOG5"): "MAMBOG 2",
    ("CITY OF BACOOR", "NIOG1"): "NIOG",
    ("CITY OF BACOOR", "NIOG2"): "NIOG",
    ("CITY OF BACOOR", "NIOG3"): "NIOG",
    ("CITY OF BACOOR", "LIGAS2"): "LIGAS 1",
    ("CITY OF BACOOR", "LIGAS3"): "LIGAS 2",
    ("CITY OF BACOOR", "REAL1"): "REAL",
    ("CITY OF BACOOR", "REAL2"): "REAL",
    ("CITY OF BACOOR", "PFESPIRITU3"): "P.F. ESPIRITU 2",
    ("CITY OF BACOOR", "PFESPIRITU4"): "P.F. ESPIRITU 3",
    ("CITY OF BACOOR", "PFESPIRITU5"): "P.F. ESPIRITU 4",
    ("CITY OF BACOOR", "PFESPIRITU6"): "P.F. ESPIRITU 4",
    ("CITY OF BACOOR", "PFESPIRITU7"): "P.F. ESPIRITU 5",
    ("CITY OF BACOOR", "PFESPIRITU8"): "P.F. ESPIRITU 6",
    # A handful of one-off misspellings seen in DASMA_RTS.xlsx.
    ("CITY OF DASMARIÑAS", "SANLUIZ2"): "SAN LUIS II",
    ("CITY OF DASMARIÑAS", "SANTLUCIA"): "SANTA LUCIA",
    ("CITY OF DASMARIÑAS", "SANALUCIA"): "SANTA LUCIA",
    ("CITY OF DASMARIÑAS", "SANESTABAN"): "SAN ESTEBAN",
    ("CITY OF DASMARIÑAS", "SANMIGUEL1"): "SAN MIGUEL",
    ("CITY OF BACOOR", "MOLONO2"): "MOLINO II",
}


def _correct_barangay(city_official, barangay):
    """Applies KNOWN_BARANGAY_CORRECTIONS if this (city, barangay) is a
    known retired/misspelled name. Returns the barangay to actually save
    (falls back to the original, uppercased/cleaned value if no
    correction is known)."""
    key = (city_official, _normalize_barangay_key(barangay))
    return KNOWN_BARANGAY_CORRECTIONS.get(key, barangay)


# A couple of RTS rows have the municipality typed as a truncated/garbled
# fragment rather than the real name (e.g. just "D"). These are confirmed,
# specific one-off fixes -- not a general "starts with" guess -- so they're
# safe to apply automatically instead of leaving a real person's ID
# unassigned to any municipality.
MUNICIPALITY_ALIASES = {
    "D": "DASMARIÑAS",
}


def _fold_accents(s):
    """DASMARINAS should match DASMARIÑAS -- RTS sheets are often typed
    without diacritics. Folds common Spanish/Filipino accented letters to
    their plain equivalents for comparison purposes only."""
    return (
        s.replace("Ñ", "N")
        .replace("Á", "A").replace("É", "E").replace("Í", "I")
        .replace("Ó", "O").replace("Ú", "U")
    )


def _simplify_city(name):
    """Strips common PSGC prefixes so 'DASMARIÑAS' and 'CITY OF
    DASMARIÑAS' both normalize to the same key."""
    return re.sub(r"^(CITY OF|MUNICIPALITY OF)\s+", "", name).strip()


def build_city_province_index(db):
    """{simplified_city_name: (official_city_name, province)} from the
    GeoBarangay reference table, for resolving a bare municipality name
    (e.g. from an RTS sheet) to its official name + province. Indexes both
    the exact spelling and an accent-folded spelling (DASMARINAS as well
    as DASMARIÑAS), since RTS sheets are often typed without diacritics."""
    from models import GeoBarangay

    index = {}
    rows = db.session.query(GeoBarangay.city_municipality, GeoBarangay.province).distinct()
    for city, province in rows:
        if not city:
            continue
        city_u = city.strip().upper()
        province_u = (province or "").strip().upper()
        for key in {_simplify_city(city_u), city_u, _fold_accents(_simplify_city(city_u)), _fold_accents(city_u)}:
            index.setdefault(key, (city_u, province_u))
    return index


def build_barangay_geocode_index(db):
    """{(province, city_municipality, normalized_barangay_key): geocode}"""
    from models import GeoBarangay

    index = {}
    rows = db.session.query(GeoBarangay.province, GeoBarangay.city_municipality, GeoBarangay.barangay, GeoBarangay.geocode)
    for province, city, barangay, geocode in rows:
        if not (province and city and barangay):
            continue
        key = (province.strip().upper(), city.strip().upper(), _normalize_barangay_key(barangay))
        index[key] = geocode
    return index


def _split_base_numeral(normalized_key):
    """('PFESPIRITU', '4') from the normalized key 'PFESPIRITU4'."""
    m = re.match(r"^(.*?)(\d+)$", normalized_key)
    if m:
        return m.group(1), m.group(2)
    return normalized_key, None


def build_barangay_fuzzy_index(db):
    """{(province, city_municipality): [(base, numeral, official_barangay_name, geocode)]}
    -- a fallback used only when the normalized exact match fails. Finds
    the closest-*spelled* barangay that has the SAME trailing number
    within the SAME city (e.g. 'P.F. ESPIRTU IV' -> 'P.F. ESPIRITU 4'),
    so a spelling typo gets fixed without ever guessing across different
    barangay numbers -- that distinction matters (barangay 3 and barangay
    4 are different places; only the spelling of the text part is fuzzy)."""
    from models import GeoBarangay

    index = {}
    rows = db.session.query(GeoBarangay.province, GeoBarangay.city_municipality, GeoBarangay.barangay, GeoBarangay.geocode)
    for province, city, barangay, geocode in rows:
        if not (province and city and barangay):
            continue
        key = (province.strip().upper(), city.strip().upper())
        base, numeral = _split_base_numeral(_normalize_barangay_key(barangay))
        index.setdefault(key, []).append((base, numeral, barangay.strip().upper(), geocode))
    return index


def _fuzzy_match_barangay(province, city_official, barangay, fuzzy_index, threshold=0.72):
    """Returns (official_barangay_name, geocode) for the closest spelling
    match within the same city (and same trailing number, if the input
    has one), or (None, None) if nothing is close enough to be safe."""
    if not fuzzy_index:
        return None, None
    candidates = fuzzy_index.get((province, city_official))
    if not candidates:
        return None, None

    base, numeral = _split_base_numeral(_normalize_barangay_key(barangay))
    same_numeral = [c for c in candidates if c[1] == numeral]
    pool = same_numeral if same_numeral else candidates

    best, best_ratio = None, 0.0
    for cand_base, _cand_numeral, official_name, geocode in pool:
        ratio = difflib.SequenceMatcher(None, base, cand_base).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, (official_name, geocode)

    if best and best_ratio >= threshold:
        return best
    return None, None


def _map_headers(header_row):
    mapping = {}
    for i, cell in enumerate(header_row):
        if not cell:
            continue
        key = _HEADER_ALIASES.get(str(cell).strip().lower())
        if key:
            mapping[key] = i
    return mapping


def parse_workbook(wb, city_index, geocode_index, fuzzy_index=None):
    """Reads every sheet in the workbook. Returns (rows, stats) where rows
    is a list of dicts ready to insert as Resident records, and stats has
    counts of what happened row-by-row."""
    rows = []
    seen_trns = set()
    stats = {
        "total_scanned": 0, "invalid_trn": 0, "missing_fields": 0,
        "duplicate_in_file": 0, "unmatched_city": 0, "barangay_corrected": 0,
        "barangay_fuzzy_matched": 0, "unmatched_barangay": 0, "ready": 0,
    }

    for sheet in wb.worksheets:
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            continue
        colmap = _map_headers(header_row)
        if "trn" not in colmap:
            continue  # not a masterlist-shaped sheet, skip it

        for raw in rows_iter:
            trn_val = raw[colmap["trn"]] if colmap["trn"] < len(raw) else None
            if trn_val in (None, ""):
                continue
            stats["total_scanned"] += 1

            trn = re.sub(r"\s+", "", str(trn_val).strip())
            if not ID_NUMBER_RE.match(trn):
                stats["invalid_trn"] += 1
                continue
            if trn in seen_trns:
                stats["duplicate_in_file"] += 1
                continue

            def get(field):
                idx = colmap.get(field)
                if idx is None or idx >= len(raw) or raw[idx] is None:
                    return ""
                return _norm(raw[idx])

            first_name = get("first_name")
            last_name = get("last_name")
            municipality = get("municipality")
            barangay = get("barangay")

            if not (first_name and last_name and municipality and barangay):
                stats["missing_fields"] += 1
                continue

            province = get("province")
            city_lookup = (
                city_index.get(municipality)
                or city_index.get(_fold_accents(municipality))
                or city_index.get(MUNICIPALITY_ALIASES.get(municipality, ""))
            )
            if province and city_lookup:
                city_official = city_lookup[0]
            elif city_lookup:
                city_official, province = city_lookup
            else:
                stats["unmatched_city"] += 1
                # Still import it -- just without a resolved official
                # city/province name -- rather than silently dropping a
                # real person from the masterlist.
                city_official = municipality
                province = province or ""

            barangay_original = barangay
            barangay = _correct_barangay(city_official, barangay)
            if barangay != barangay_original:
                stats["barangay_corrected"] += 1

            geocode = geocode_index.get((province, city_official, _normalize_barangay_key(barangay)), "")

            if not geocode and city_lookup:
                fuzzy_name, fuzzy_geocode = _fuzzy_match_barangay(province, city_official, barangay, fuzzy_index)
                if fuzzy_name:
                    barangay = fuzzy_name
                    geocode = fuzzy_geocode
                    stats["barangay_fuzzy_matched"] += 1
                else:
                    stats["unmatched_barangay"] += 1

            seen_trns.add(trn)
            rows.append({
                "id_number": trn,
                "first_name": first_name,
                "middle_name": get("middle_name"),
                "last_name": last_name,
                "suffix": get("suffix"),
                "province": province,
                "city_municipality": city_official,
                "barangay": barangay,
                "geocode": geocode,
                "contact_number": get("contact_number") or None,
                "address_line": get("address_line") or None,
            })
            stats["ready"] += 1

    return rows, stats


def import_rows(db, rows):
    """Inserts only the rows whose id_number isn't already a resident.
    Never updates/overwrites an existing resident. Returns (inserted_count,
    skipped_existing_count)."""
    from models import Resident

    existing = {
        r[0] for r in db.session.query(Resident.id_number).filter(
            Resident.id_number.in_([row["id_number"] for row in rows])
        )
    } if rows else set()

    inserted = 0
    for row in rows:
        if row["id_number"] in existing:
            continue
        db.session.add(Resident(
            id_number=row["id_number"],
            first_name=row["first_name"],
            middle_name=row["middle_name"] or None,
            last_name=row["last_name"],
            suffix=row["suffix"] or None,
            province=row["province"] or "UNSPECIFIED",
            city_municipality=row["city_municipality"] or "UNSPECIFIED",
            barangay=row["barangay"],
            geocode=row["geocode"] or None,
            contact_number=row.get("contact_number"),
            address_line=row.get("address_line"),
            source="masterlist_import",
        ))
        inserted += 1

    db.session.commit()
    return inserted, len(existing)
