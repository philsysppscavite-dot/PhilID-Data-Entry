from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from extensions import db
from models import GeoBarangay, Resident, CheckLog

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/provinces")
def provinces():
    rows = (
        db.session.query(GeoBarangay.province)
        .distinct()
        .order_by(GeoBarangay.province)
        .all()
    )
    return jsonify([r[0] for r in rows])


@bp.route("/cities")
def cities():
    province = request.args.get("province", "")
    rows = (
        db.session.query(GeoBarangay.city_municipality)
        .filter(GeoBarangay.province == province)
        .distinct()
        .order_by(GeoBarangay.city_municipality)
        .all()
    )
    return jsonify([r[0] for r in rows])


@bp.route("/barangays")
def barangays():
    province = request.args.get("province", "")
    city = request.args.get("city", "")
    rows = (
        db.session.query(GeoBarangay.barangay, GeoBarangay.geocode)
        .filter(GeoBarangay.province == province, GeoBarangay.city_municipality == city)
        .order_by(GeoBarangay.barangay)
        .all()
    )
    return jsonify([{"name": r[0], "geocode": r[1]} for r in rows])


@bp.route("/scan", methods=["POST"])
@login_required
def scan():
    """Called right after the browser decodes a QR code.

    If the id_number is already registered, this toggles IN/OUT and logs it.
    If it's new, the frontend is told to show the registration form instead.
    """
    payload = request.get_json(silent=True) or {}
    id_number = (payload.get("id_number") or "").strip()

    if not id_number:
        return jsonify({"error": "No ID data detected in the QR code."}), 400

    resident = Resident.query.filter_by(id_number=id_number).first()

    if not resident:
        return jsonify({"status": "new", "id_number": id_number}), 200

    last_log = resident.logs.order_by(CheckLog.timestamp.desc()).first()
    next_type = "OUT" if last_log and last_log.log_type == "IN" else "IN"

    log = CheckLog(resident_id=resident.id, log_type=next_type, scanned_by_id=current_user.id)
    db.session.add(log)
    db.session.commit()

    return jsonify(
        {
            "status": "logged",
            "log_type": next_type,
            "resident": {
                "id_number": resident.id_number,
                "full_name": resident.full_name,
                "barangay": resident.barangay,
                "city_municipality": resident.city_municipality,
                "province": resident.province,
            },
            "timestamp": log.timestamp.strftime("%b %d, %Y %I:%M %p"),
        }
    )


@bp.route("/register", methods=["POST"])
@login_required
def register():
    """Registers a brand-new resident (first time their ID is scanned) and
    immediately logs a time-IN entry."""
    payload = request.get_json(silent=True) or {}

    id_number = (payload.get("id_number") or "").strip()
    first_name = (payload.get("first_name") or "").strip()
    middle_name = (payload.get("middle_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    province = (payload.get("province") or "").strip()
    city_municipality = (payload.get("city_municipality") or "").strip()
    barangay = (payload.get("barangay") or "").strip()
    geocode = (payload.get("geocode") or "").strip()

    missing = [
        label
        for label, val in [
            ("ID number", id_number),
            ("First name", first_name),
            ("Last name", last_name),
            ("Province", province),
            ("City/Municipality", city_municipality),
            ("Barangay", barangay),
        ]
        if not val
    ]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    if Resident.query.filter_by(id_number=id_number).first():
        return jsonify({"error": "This ID number is already registered."}), 409

    resident = Resident(
        id_number=id_number,
        first_name=first_name,
        middle_name=middle_name or None,
        last_name=last_name,
        province=province,
        city_municipality=city_municipality,
        barangay=barangay,
        geocode=geocode or None,
    )
    db.session.add(resident)
    db.session.flush()

    log = CheckLog(resident_id=resident.id, log_type="IN", scanned_by_id=current_user.id)
    db.session.add(log)
    db.session.commit()

    return jsonify(
        {
            "status": "registered",
            "resident": {
                "id_number": resident.id_number,
                "full_name": resident.full_name,
                "barangay": resident.barangay,
                "city_municipality": resident.city_municipality,
                "province": resident.province,
            },
            "timestamp": log.timestamp.strftime("%b %d, %Y %I:%M %p"),
        }
    )


@bp.route("/search")
@login_required
def search():
    """Manual keyword search: matches ID number, first/middle/last name."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])

    like = f"%{q}%"
    residents = (
        Resident.query.filter(
            db.or_(
                Resident.id_number.ilike(like),
                Resident.first_name.ilike(like),
                Resident.middle_name.ilike(like),
                Resident.last_name.ilike(like),
            )
        )
        .order_by(Resident.last_name)
        .limit(30)
        .all()
    )

    return jsonify(
        [
            {
                "id_number": r.id_number,
                "full_name": r.full_name,
                "barangay": r.barangay,
                "city_municipality": r.city_municipality,
                "province": r.province,
            }
            for r in residents
        ]
    )


@bp.route("/resident/<id_number>")
@login_required
def resident_profile(id_number):
    """Full profile + visit history for one resident, used by both the QR
    lookup and the manual-search result list on the Search page."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    history = [
        {
            "type": log.log_type,
            "timestamp": log.timestamp.strftime("%b %d, %Y %I:%M %p"),
            "scanned_by": log.scanned_by.full_name if log.scanned_by else "-",
        }
        for log in resident.logs.order_by(CheckLog.timestamp.desc()).all()
    ]

    return jsonify(
        {
            "id_number": resident.id_number,
            "full_name": resident.full_name,
            "first_name": resident.first_name,
            "middle_name": resident.middle_name,
            "last_name": resident.last_name,
            "province": resident.province,
            "city_municipality": resident.city_municipality,
            "barangay": resident.barangay,
            "geocode": resident.geocode,
            "registered_on": resident.created_at.strftime("%b %d, %Y"),
            "total_visits": len(history),
            "history": history,
        }
    )


@bp.route("/logs")
@login_required
def logs():
    """Server-side data for the dashboard table, with optional filters."""
    query = CheckLog.query.join(Resident)

    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    log_type = request.args.get("type")
    search = request.args.get("q")
    province = request.args.get("province")
    city = request.args.get("city")
    barangay = request.args.get("barangay")

    if date_from:
        query = query.filter(CheckLog.timestamp >= datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        query = query.filter(
            CheckLog.timestamp < datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        )
    if log_type in ("IN", "OUT"):
        query = query.filter(CheckLog.log_type == log_type)
    if province:
        query = query.filter(Resident.province == province)
    if city:
        query = query.filter(Resident.city_municipality == city)
    if barangay:
        query = query.filter(Resident.barangay == barangay)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Resident.first_name.ilike(like),
                Resident.middle_name.ilike(like),
                Resident.last_name.ilike(like),
                Resident.id_number.ilike(like),
            )
        )

    query = query.order_by(CheckLog.timestamp.desc()).limit(500)

    results = []
    for log in query.all():
        results.append(
            {
                "id": log.id,
                "id_number": log.resident.id_number,
                "full_name": log.resident.full_name,
                "province": log.resident.province,
                "city_municipality": log.resident.city_municipality,
                "barangay": log.resident.barangay,
                "type": log.log_type,
                "timestamp": log.timestamp.strftime("%b %d, %Y %I:%M %p"),
                "scanned_by": log.scanned_by.full_name if log.scanned_by else "-",
            }
        )

    return jsonify(results)
