import os
import re
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from blueprints.auth import staff_or_admin_required, admin_required
from extensions import db
from models import GeoBarangay, Resident, CheckLog, DeliveryLog, User
import drive_storage
import geocode_helper

bp = Blueprint("api", __name__, url_prefix="/api")

# Every PhilSys ID QR code encodes a 29-digit Transaction Reference Number
# (TRN). Anything shorter/longer or containing non-digits isn't a valid
# PhilSys ID and must be rejected before it ever reaches the database.
ID_NUMBER_RE = re.compile(r"^\d{29}$")


def _valid_id_number(value):
    return bool(value) and bool(ID_NUMBER_RE.match(value))


def _upper(value):
    """Normalizes free-text data-entry fields to ALL CAPS, matching the
    masterlist/reference data convention."""
    return (value or "").strip().upper()


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

    if not _valid_id_number(id_number):
        return jsonify({
            "error": "Invalid QR code. A PhilSys ID number must be exactly 29 digits."
        }), 400

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
            "scanned_by": current_user.full_name,
        }
    )


@bp.route("/register", methods=["POST"])
@login_required
def register():
    """Registers a brand-new resident (first time their ID is scanned) and
    immediately logs a time-IN entry."""
    payload = request.get_json(silent=True) or {}

    id_number = (payload.get("id_number") or "").strip()
    first_name = _upper(payload.get("first_name"))
    middle_name = _upper(payload.get("middle_name"))
    last_name = _upper(payload.get("last_name"))
    suffix = _upper(payload.get("suffix"))
    province = _upper(payload.get("province"))
    city_municipality = _upper(payload.get("city_municipality"))
    barangay = _upper(payload.get("barangay"))
    geocode = (payload.get("geocode") or "").strip()
    contact_number = (payload.get("contact_number") or "").strip()
    address_line = _upper(payload.get("address_line"))

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

    if not _valid_id_number(id_number):
        return jsonify({
            "error": "Invalid ID number. A PhilSys ID number must be exactly 29 digits."
        }), 400

    if Resident.query.filter_by(id_number=id_number).first():
        return jsonify({"error": "This ID number is already registered."}), 409

    resident = Resident(
        id_number=id_number,
        first_name=first_name,
        middle_name=middle_name or None,
        last_name=last_name,
        suffix=suffix or None,
        province=province,
        city_municipality=city_municipality,
        barangay=barangay,
        geocode=geocode or None,
        contact_number=contact_number or None,
        address_line=address_line or None,
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
            "scanned_by": current_user.full_name,
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
                Resident.suffix.ilike(like),
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

    delivery_history = [
        {
            "event": ev.event,
            "timestamp": ev.timestamp.strftime("%b %d, %Y %I:%M %p"),
            "by": ev.by_user.full_name if ev.by_user else "-",
            "remarks": ev.remarks,
            "photo_url": ev.photo_url,
            "gps_matched": ev.gps_matched,
            "gps_reference": ev.gps_reference,
            "gps_distance_m": ev.gps_distance_m,
        }
        for ev in resident.delivery_logs.order_by(DeliveryLog.timestamp.desc()).all()
    ]

    return jsonify(
        {
            "id_number": resident.id_number,
            "full_name": resident.full_name,
            "first_name": resident.first_name,
            "middle_name": resident.middle_name,
            "last_name": resident.last_name,
            "suffix": resident.suffix,
            "province": resident.province,
            "city_municipality": resident.city_municipality,
            "barangay": resident.barangay,
            "geocode": resident.geocode,
            "contact_number": resident.contact_number,
            "address_line": resident.address_line,
            "registered_on": resident.created_at.strftime("%b %d, %Y"),
            "total_visits": len(history),
            "history": history,
            "delivery_status": resident.delivery_status,
            "checked_out_at": resident.checked_out_at.strftime("%b %d, %Y %I:%M %p") if resident.checked_out_at else None,
            "checked_out_by": resident.checked_out_by.full_name if resident.checked_out_by else None,
            "delivered_at": resident.delivered_at.strftime("%b %d, %Y %I:%M %p") if resident.delivered_at else None,
            "returned_at": resident.returned_at.strftime("%b %d, %Y %I:%M %p") if resident.returned_at else None,
            "delivered_by": resident.delivered_by.full_name if resident.delivered_by else None,
            "returned_to_office_at": resident.returned_to_office_at.strftime("%b %d, %Y %I:%M %p") if resident.returned_to_office_at else None,
            "returned_to_office_by": resident.returned_to_office_by.full_name if resident.returned_to_office_by else None,
            "delivery_photo_url": resident.delivery_photo_url,
            "delivery_remarks": resident.delivery_remarks,
            "delivery_lat": resident.delivery_lat,
            "delivery_lng": resident.delivery_lng,
            "delivery_gps_matched": resident.delivery_gps_matched,
            "delivery_gps_distance_m": resident.delivery_gps_distance_m,
            "delivery_gps_reference": resident.delivery_gps_reference,
            "delivery_history": delivery_history,
        }
    )


@bp.route("/resident/<id_number>", methods=["PUT"])
@login_required
@staff_or_admin_required
def update_resident(id_number):
    """Edits a resident's registered details (name, address, contact).
    The ID number itself is never editable here -- it's the physical
    PhilSys ID tied to the printed QR code."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    payload = request.get_json(silent=True) or {}

    first_name = _upper(payload.get("first_name"))
    middle_name = _upper(payload.get("middle_name"))
    last_name = _upper(payload.get("last_name"))
    suffix = _upper(payload.get("suffix"))
    province = _upper(payload.get("province"))
    city_municipality = _upper(payload.get("city_municipality"))
    barangay = _upper(payload.get("barangay"))
    geocode = (payload.get("geocode") or "").strip()
    contact_number = (payload.get("contact_number") or "").strip()
    address_line = _upper(payload.get("address_line"))

    missing = [
        label
        for label, val in [
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

    resident.first_name = first_name
    resident.middle_name = middle_name or None
    resident.last_name = last_name
    resident.suffix = suffix or None
    resident.province = province
    resident.city_municipality = city_municipality
    resident.barangay = barangay
    resident.geocode = geocode or resident.geocode
    resident.contact_number = contact_number or None
    resident.address_line = address_line or None
    db.session.commit()

    return jsonify({"status": "updated", "id_number": resident.id_number, "full_name": resident.full_name})


@bp.route("/resident/<id_number>", methods=["DELETE"])
@login_required
@staff_or_admin_required
def delete_resident(id_number):
    """Permanently removes a resident and all their visit/delivery
    history (cascade-deleted). Also cleans up any proof-of-delivery
    photo files tied to them."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    if resident.delivery_photo:
        old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], resident.delivery_photo)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    if resident.delivery_photo_drive_id:
        drive_storage.delete_photo(current_app.config, resident.delivery_photo_drive_id)

    db.session.delete(resident)
    db.session.commit()

    return jsonify({"status": "deleted", "id_number": id_number})


def _allowed_photo(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_PHOTO_EXTENSIONS"]


def _save_delivery_photo(resident, photo):
    """Uploads a proof photo (Drive, falling back to local disk), removing
    whatever photo was previously attached to this resident. Returns
    (local_filename_or_None, drive_file_id_or_None)."""
    ext = photo.filename.rsplit(".", 1)[-1].lower()
    filename = secure_filename(f"{resident.id_number}_{uuid.uuid4().hex}.{ext}")

    drive_file_id = drive_storage.upload_photo(current_app.config, photo, filename)

    local_filename = None
    if not drive_file_id:
        photo.stream.seek(0)
        photo.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
        local_filename = filename

    if resident.delivery_photo:
        old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], resident.delivery_photo)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    if resident.delivery_photo_drive_id:
        drive_storage.delete_photo(current_app.config, resident.delivery_photo_drive_id)

    return local_filename, drive_file_id


def _parse_latlng():
    try:
        lat = float(request.form.get("lat"))
        lng = float(request.form.get("lng"))
        return lat, lng
    except (TypeError, ValueError):
        return None, None


@bp.route("/delivery/<id_number>/checkout", methods=["POST"])
@login_required
def checkout_delivery(id_number):
    """Scan OUT: rider takes the physical ID with them for delivery. Must
    be resolved (delivered or returned) before it can be checked out again."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    if resident.delivery_status == "out_for_delivery":
        return jsonify({"error": "This ID is already checked out for delivery. Resolve it first."}), 409

    resident.delivery_status = "out_for_delivery"
    resident.checked_out_at = datetime.utcnow()
    resident.checked_out_by_id = current_user.id

    db.session.add(DeliveryLog(
        resident_id=resident.id,
        event="checked_out",
        by_user_id=current_user.id,
    ))
    db.session.commit()

    return jsonify(
        {
            "status": "out_for_delivery",
            "checked_out_at": resident.checked_out_at.strftime("%b %d, %Y %I:%M %p"),
            "checked_out_by": current_user.full_name,
        }
    )


@bp.route("/delivery/<id_number>/resolve", methods=["POST"])
@login_required
def resolve_delivery(id_number):
    """Scan back IN: resolves a checked-out ID as either delivered or
    returned/not-delivered. Always requires GPS + a photo; a reason
    (remarks) is required when the outcome is 'returned'."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    if resident.delivery_status != "out_for_delivery":
        return jsonify({"error": "This ID hasn't been checked out for delivery yet. Scan it OUT first."}), 409

    outcome = (request.form.get("outcome") or "").strip()
    if outcome not in ("delivered", "returned"):
        return jsonify({"error": "Outcome must be 'delivered' or 'returned'."}), 400

    remarks = (request.form.get("remarks") or "").strip()
    if outcome == "returned" and not remarks:
        return jsonify({"error": "A reason is required when the ID was not delivered."}), 400

    photo = request.files.get("photo")
    if not photo or not photo.filename:
        return jsonify({"error": "A photo (with the resident/location) is required."}), 400
    if not _allowed_photo(photo.filename):
        return jsonify({"error": "Photo must be a JPG, PNG, or WEBP image."}), 400

    lat, lng = _parse_latlng()
    if lat is None or lng is None:
        return jsonify({"error": "GPS location is required. Please allow location access and try again."}), 400

    gps = geocode_helper.verify_delivery_location(resident, lat, lng, current_app.config)

    if (
        outcome == "delivered"
        and gps["checked"]
        and gps["matched"] is False
        and current_app.config.get("DELIVERY_GPS_HARD_BLOCK")
    ):
        return jsonify({
            "error": (
                "GPS location doesn't match the resident's address/barangay "
                f"({gps['message']}). Move closer to the address and try again, "
                "or mark this as 'returned' with a reason instead."
            ),
            "gps": gps,
        }), 409

    local_filename, drive_file_id = _save_delivery_photo(resident, photo)

    now = datetime.utcnow()
    resident.delivery_status = outcome
    resident.delivered_by_id = current_user.id
    resident.delivery_photo = local_filename
    resident.delivery_photo_drive_id = drive_file_id
    resident.delivery_remarks = remarks or None
    resident.delivery_lat = lat
    resident.delivery_lng = lng
    resident.delivery_gps_matched = gps["matched"]
    resident.delivery_gps_distance_m = gps["distance_m"]
    resident.delivery_gps_reference = gps["reference"]

    if outcome == "delivered":
        resident.delivered_at = now
        resident.returned_at = None
    else:
        resident.returned_at = now
        resident.delivered_at = None

    db.session.add(DeliveryLog(
        resident_id=resident.id,
        event=outcome,
        by_user_id=current_user.id,
        lat=lat,
        lng=lng,
        gps_matched=gps["matched"],
        gps_distance_m=gps["distance_m"],
        gps_reference=gps["reference"],
        remarks=remarks or None,
        photo=local_filename,
        photo_drive_id=drive_file_id,
    ))
    db.session.commit()

    return jsonify(
        {
            "status": outcome,
            "delivered_at": resident.delivered_at.strftime("%b %d, %Y %I:%M %p") if resident.delivered_at else None,
            "returned_at": resident.returned_at.strftime("%b %d, %Y %I:%M %p") if resident.returned_at else None,
            "delivered_by": current_user.full_name,
            "delivery_photo_url": resident.delivery_photo_url,
            "delivery_photo_source": resident.delivery_photo_source,
            "delivery_remarks": resident.delivery_remarks,
            "gps": gps,
        }
    )


@bp.route("/delivery/<id_number>/return-to-office", methods=["POST"])
@login_required
def return_to_office(id_number):
    """Scan the physical ID back in at the office once a delivery attempt
    came back marked 'returned' (not delivered). This is the tally-and-
    confirm step -- it doesn't require GPS/photo, just a scan/lookup and a
    confirm click, and flips the status to 'returned_to_office'."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    if resident.delivery_status != "returned":
        return jsonify({"error": "This ID isn't marked as returned/not-delivered."}), 409

    resident.delivery_status = "returned_to_office"
    resident.returned_to_office_at = datetime.utcnow()
    resident.returned_to_office_by_id = current_user.id

    db.session.add(DeliveryLog(
        resident_id=resident.id,
        event="returned_to_office",
        by_user_id=current_user.id,
    ))
    db.session.commit()

    return jsonify(
        {
            "status": "returned_to_office",
            "returned_to_office_at": resident.returned_to_office_at.strftime("%b %d, %Y %I:%M %p"),
            "returned_to_office_by": current_user.full_name,
        }
    )


@bp.route("/delivery/<id_number>/undo", methods=["POST"])
@login_required
def undo_delivery(id_number):
    """Reverts a resident's ID back to pending (correcting a mistaken scan)."""
    resident = Resident.query.filter_by(id_number=id_number).first()
    if not resident:
        return jsonify({"error": "No resident found with that ID number."}), 404

    resident.delivery_status = "pending"
    resident.checked_out_at = None
    resident.checked_out_by_id = None
    resident.delivered_at = None
    resident.returned_at = None
    resident.delivered_by_id = None
    resident.returned_to_office_at = None
    resident.returned_to_office_by_id = None
    resident.delivery_remarks = None
    resident.delivery_lat = None
    resident.delivery_lng = None
    resident.delivery_gps_matched = None
    resident.delivery_gps_distance_m = None
    resident.delivery_gps_reference = None
    # Keep the photo file itself (local or Drive) for audit purposes, just
    # detach it from the record.
    resident.delivery_photo = None
    resident.delivery_photo_drive_id = None
    db.session.commit()
    return jsonify({"status": "pending"})


@bp.route("/masterlist")
@login_required
def masterlist():
    """Printable/exportable list of residents for delivery personnel, with
    optional filters by province/city/barangay/delivery status. This is the
    shared reference list (who still needs their ID), so it's not scoped to
    one user the way the reports below are."""
    province = request.args.get("province")
    city = request.args.get("city")
    barangay = request.args.get("barangay")
    status = request.args.get("status")  # pending | out_for_delivery | delivered | returned | returned_to_office

    query = Resident.query
    if province:
        query = query.filter(Resident.province == province)
    if city:
        query = query.filter(Resident.city_municipality == city)
    if barangay:
        query = query.filter(Resident.barangay == barangay)
    if status in ("pending", "out_for_delivery", "delivered", "returned", "returned_to_office"):
        query = query.filter(Resident.delivery_status == status)

    residents = query.order_by(
        Resident.province, Resident.city_municipality, Resident.barangay, Resident.last_name
    ).all()

    return jsonify(
        [
            {
                "id_number": r.id_number,
                "full_name": r.full_name,
                "contact_number": r.contact_number,
                "address_line": r.address_line,
                "barangay": r.barangay,
                "city_municipality": r.city_municipality,
                "province": r.province,
                "delivery_status": r.delivery_status,
            }
            for r in residents
        ]
    )


def _scope_to_own_deliveries(query):
    """Restricts a Resident query to records the current user personally
    handled: checked out, delivered/returned, or received back at the
    office. Used everywhere a non-admin should only see 'their own'
    assigned deliveries and statuses."""
    return query.filter(
        db.or_(
            Resident.checked_out_by_id == current_user.id,
            Resident.delivered_by_id == current_user.id,
            Resident.returned_to_office_by_id == current_user.id,
        )
    )


@bp.route("/delivery-report")
@login_required
def delivery_report():
    """Data for the ID-delivery reporting page, with photo documentation.
    Admins see every resident; everyone else only sees the ones assigned
    to / handled by them."""
    province = request.args.get("province")
    city = request.args.get("city")
    barangay = request.args.get("barangay")
    status = request.args.get("status")  # pending | out_for_delivery | delivered | returned | returned_to_office
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    scoped = not current_user.is_admin

    base_query = Resident.query
    summary_query = Resident.query
    if scoped:
        base_query = _scope_to_own_deliveries(base_query)
        summary_query = _scope_to_own_deliveries(summary_query)

    query = base_query
    if province:
        query = query.filter(Resident.province == province)
    if city:
        query = query.filter(Resident.city_municipality == city)
    if barangay:
        query = query.filter(Resident.barangay == barangay)
    if status in ("pending", "out_for_delivery", "delivered", "returned", "returned_to_office"):
        query = query.filter(Resident.delivery_status == status)
    if date_from:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        query = query.filter(
            db.or_(Resident.delivered_at >= start, Resident.returned_at >= start)
        )
    if date_to:
        end = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        query = query.filter(
            db.or_(Resident.delivered_at < end, Resident.returned_at < end)
        )

    total = summary_query.count()
    delivered_count = summary_query.filter(Resident.delivery_status == "delivered").count()
    returned_count = summary_query.filter(Resident.delivery_status == "returned").count()
    returned_to_office_count = summary_query.filter(Resident.delivery_status == "returned_to_office").count()
    out_count = summary_query.filter(Resident.delivery_status == "out_for_delivery").count()
    pending_count = total - delivered_count - returned_count - returned_to_office_count - out_count

    residents = query.order_by(Resident.delivery_status.asc(), Resident.last_name).all()

    return jsonify(
        {
            "summary": {
                "total": total,
                "delivered": delivered_count,
                "returned": returned_count,
                "returned_to_office": returned_to_office_count,
                "out_for_delivery": out_count,
                "pending": pending_count,
            },
            "results": [
                {
                    "id_number": r.id_number,
                    "full_name": r.full_name,
                    "barangay": r.barangay,
                    "city_municipality": r.city_municipality,
                    "province": r.province,
                    "delivery_status": r.delivery_status,
                    "checked_out_at": r.checked_out_at.strftime("%b %d, %Y %I:%M %p") if r.checked_out_at else None,
                    "checked_out_by": r.checked_out_by.full_name if r.checked_out_by else None,
                    "delivered_at": r.delivered_at.strftime("%b %d, %Y %I:%M %p") if r.delivered_at else None,
                    "returned_at": r.returned_at.strftime("%b %d, %Y %I:%M %p") if r.returned_at else None,
                    "delivered_by": r.delivered_by.full_name if r.delivered_by else None,
                    "returned_to_office_at": r.returned_to_office_at.strftime("%b %d, %Y %I:%M %p") if r.returned_to_office_at else None,
                    "returned_to_office_by": r.returned_to_office_by.full_name if r.returned_to_office_by else None,
                    "delivery_photo_url": r.delivery_photo_url,
                    "delivery_remarks": r.delivery_remarks,
                    "delivery_gps_matched": r.delivery_gps_matched,
                    "delivery_gps_reference": r.delivery_gps_reference,
                    "delivery_gps_distance_m": r.delivery_gps_distance_m,
                }
                for r in residents
            ],
        }
    )


@bp.route("/personnel-report")
@login_required
def personnel_report():
    """Per-delivery-personnel totals: delivered, pending (currently out,
    unresolved), returned/not-delivered, and returned-to-office tallies.
    Admins see every rider's row; a non-admin only sees their own row (if
    they've checked anything out) -- they can't see how other users are
    performing."""
    if current_user.is_admin:
        personnel = User.query.filter_by(role="delivery").order_by(User.full_name).all()
    else:
        personnel = [current_user]

    results = []
    for user in personnel:
        checked_out_total = Resident.query.filter(Resident.checked_out_by_id == user.id).count()
        currently_out = Resident.query.filter(
            Resident.checked_out_by_id == user.id, Resident.delivery_status == "out_for_delivery"
        ).count()
        delivered_total = Resident.query.filter(
            Resident.delivered_by_id == user.id, Resident.delivery_status == "delivered"
        ).count()
        returned_total = Resident.query.filter(
            Resident.delivered_by_id == user.id, Resident.delivery_status.in_(("returned", "returned_to_office"))
        ).count()
        returned_to_office_total = Resident.query.filter(
            Resident.returned_to_office_by_id == user.id
        ).count()

        results.append(
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "is_active": user.is_active_user,
                "checked_out_total": checked_out_total,
                "pending": currently_out,
                "delivered_total": delivered_total,
                "returned_total": returned_total,
                "returned_to_office_total": returned_to_office_total,
            }
        )

    overall = {
        "total_personnel": len(personnel),
        "total_delivered": sum(r["delivered_total"] for r in results),
        "total_pending": sum(r["pending"] for r in results),
        "total_returned": sum(r["returned_total"] for r in results),
        "total_returned_to_office": sum(r["returned_to_office_total"] for r in results),
    }

    return jsonify({"summary": overall, "personnel": results})


@bp.route("/masterlist/import", methods=["POST"])
@login_required
@admin_required
def import_masterlist():
    """Admin-only: upload a masterlist/RTS spreadsheet (.xlsx) to pre-load
    residents. Every sheet in the workbook is processed. Existing residents
    (matched by TRN/id_number) are never touched -- only brand-new TRNs get
    added, as 'pending'."""
    import masterlist_helper

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "Choose an .xlsx file to import."}), 400
    if not file.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Only .xlsx files are supported."}), 400

    try:
        import openpyxl
        wb = openpyxl.load_workbook(file, data_only=True, read_only=True)
    except Exception:
        return jsonify({"error": "Couldn't read that file. Make sure it's a valid .xlsx workbook."}), 400

    city_index = masterlist_helper.build_city_province_index(db)
    geocode_index = masterlist_helper.build_barangay_geocode_index(db)
    fuzzy_index = masterlist_helper.build_barangay_fuzzy_index(db)
    rows, stats = masterlist_helper.parse_workbook(wb, city_index, geocode_index, fuzzy_index)
    inserted, skipped_existing = masterlist_helper.import_rows(db, rows)

    return jsonify({
        "status": "imported",
        "sheets_processed": len(wb.sheetnames),
        "inserted": inserted,
        "already_existed": skipped_existing,
        "invalid_trn": stats["invalid_trn"],
        "missing_fields": stats["missing_fields"],
        "duplicate_in_file": stats["duplicate_in_file"],
        "unmatched_city": stats["unmatched_city"],
        "barangay_corrected": stats["barangay_corrected"],
        "barangay_fuzzy_matched": stats["barangay_fuzzy_matched"],
        "unmatched_barangay": stats["unmatched_barangay"],
    })


@bp.route("/personnel-list")
@login_required
def personnel_list():
    """Lightweight list of user accounts, for populating the 'personnel'
    picker on the Transmittal page. Admins can pick anyone; non-admins
    don't need this (they can only transmit for themselves)."""
    if not current_user.is_admin:
        return jsonify([{
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name,
            "role": current_user.role,
        }])

    users = User.query.filter(User.role.in_(("delivery", "staff"))).order_by(User.full_name).all()
    return jsonify([
        {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role}
        for u in users
    ])


@bp.route("/transmittal")
@login_required
def transmittal():
    """Printable transmittal of IDs assigned to one delivery personnel/user
    -- i.e. the ones they checked out. Defaults to only what's currently
    'out_for_delivery', but any status can be requested (e.g. to reprint a
    transmittal for a batch that's since been delivered/returned).

    Non-admins can only pull their own transmittal; the personnel_id
    parameter is ignored/overridden for them.
    """
    status = request.args.get("status", "out_for_delivery")

    if current_user.is_admin:
        personnel_id = request.args.get("personnel_id", type=int)
        if not personnel_id:
            return jsonify({"error": "Select a delivery personnel/user first."}), 400
        personnel = User.query.get(personnel_id)
        if not personnel:
            return jsonify({"error": "That user account no longer exists."}), 404
    else:
        personnel = current_user

    query = Resident.query.filter(Resident.checked_out_by_id == personnel.id)
    if status in ("pending", "out_for_delivery", "delivered", "returned", "returned_to_office"):
        query = query.filter(Resident.delivery_status == status)

    residents = query.order_by(
        Resident.province, Resident.city_municipality, Resident.barangay, Resident.last_name
    ).all()

    return jsonify(
        {
            "personnel": {
                "id": personnel.id,
                "username": personnel.username,
                "full_name": personnel.full_name,
                "role": personnel.role,
            },
            "status": status,
            "generated_at": datetime.utcnow().strftime("%b %d, %Y %I:%M %p"),
            "results": [
                {
                    "id_number": r.id_number,
                    "full_name": r.full_name,
                    "address_line": r.address_line,
                    "barangay": r.barangay,
                    "city_municipality": r.city_municipality,
                    "province": r.province,
                    "contact_number": r.contact_number,
                    "delivery_status": r.delivery_status,
                    "checked_out_at": r.checked_out_at.strftime("%b %d, %Y %I:%M %p") if r.checked_out_at else None,
                }
                for r in residents
            ],
        }
    )


@bp.route("/logs")
@login_required
def logs():
    """Server-side data for the dashboard table, with optional filters.
    Admins see every scan; non-admins only see scans they personally made."""
    query = CheckLog.query.join(Resident)

    if not current_user.is_admin:
        query = query.filter(CheckLog.scanned_by_id == current_user.id)

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
                Resident.suffix.ilike(like),
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
