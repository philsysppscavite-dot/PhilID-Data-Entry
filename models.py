from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(UserMixin, db.Model):
    """System / staff accounts that can log into the dashboard."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")  # admin | staff
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_delivery(self):
        return self.role == "delivery"

    # flask-login expects is_active as a property/attribute
    @property
    def is_active(self):
        return self.is_active_user


class AppMeta(db.Model):
    """Small key/value store for internal bookkeeping (e.g. which version
    of the geocode reference data has been imported)."""

    __tablename__ = "app_meta"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(255), nullable=True)


class GeoBarangay(db.Model):
    """Reference data: province / city-municipality / barangay, from PSGC."""

    __tablename__ = "geo_barangay"

    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(120), index=True)
    province = db.Column(db.String(120), index=True)
    city_municipality = db.Column(db.String(120), index=True)
    barangay = db.Column(db.String(120), index=True)
    geocode = db.Column(db.String(20), unique=True, index=True)


class Resident(db.Model):
    """A person whose ID has been registered/scanned into the system."""

    __tablename__ = "residents"

    id = db.Column(db.Integer, primary_key=True)
    id_number = db.Column(db.String(100), unique=True, nullable=False, index=True)

    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=False)
    suffix = db.Column(db.String(20), nullable=True)  # Jr., Sr., III, etc.

    province = db.Column(db.String(120), nullable=False)
    city_municipality = db.Column(db.String(120), nullable=False)
    barangay = db.Column(db.String(120), nullable=False)
    geocode = db.Column(db.String(20), nullable=True)

    contact_number = db.Column(db.String(30), nullable=True)
    address_line = db.Column(db.String(255), nullable=True)  # house no./street, optional detail

    # ---- ID delivery tracking ----
    # pending -> out_for_delivery -> (delivered | returned) -> [out_for_delivery again, if re-attempted]
    delivery_status = db.Column(db.String(20), nullable=False, default="pending")

    # Scan OUT: rider takes the physical ID with them for delivery.
    checked_out_at = db.Column(db.DateTime, nullable=True)
    checked_out_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Resolution (scan back in, against the outcome): either delivered, or
    # returned/not delivered. Whoever resolves it is recorded in
    # delivered_by_id/delivered_by regardless of which outcome it was.
    delivered_at = db.Column(db.DateTime, nullable=True)  # set only when outcome = delivered
    returned_at = db.Column(db.DateTime, nullable=True)  # set only when outcome = returned
    delivered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Once an outcome of "returned" (not delivered) has been scanned back in
    # at the office, this records that hand-in and flips delivery_status to
    # "returned_to_office".
    returned_to_office_at = db.Column(db.DateTime, nullable=True)
    returned_to_office_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    delivery_photo = db.Column(db.String(255), nullable=True)  # local fallback: filename under static/uploads/delivery
    delivery_photo_drive_id = db.Column(db.String(100), nullable=True)  # Google Drive file ID, if uploaded there
    delivery_remarks = db.Column(db.String(255), nullable=True)  # notes if delivered, REQUIRED reason if returned

    # GPS captured at the moment of resolution, checked against the
    # resident's address/barangay (see geocode_helper.py).
    delivery_lat = db.Column(db.Float, nullable=True)
    delivery_lng = db.Column(db.Float, nullable=True)
    delivery_gps_matched = db.Column(db.Boolean, nullable=True)  # None = not verified
    delivery_gps_distance_m = db.Column(db.Float, nullable=True)
    delivery_gps_reference = db.Column(db.String(20), nullable=True)  # address | barangay | unverified

    # Where this record came from: 'manual' = registered at the scan station
    # the first time this ID was scanned; 'masterlist_import' = bulk-loaded
    # ahead of time from an RTS/masterlist spreadsheet (e.g. DASMA_RTS.xlsx).
    source = db.Column(db.String(20), nullable=False, default="manual")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship(
        "CheckLog", backref="resident", lazy="dynamic", cascade="all, delete-orphan"
    )
    delivery_logs = db.relationship(
        "DeliveryLog", backref="resident", lazy="dynamic", cascade="all, delete-orphan"
    )
    delivered_by = db.relationship("User", foreign_keys=[delivered_by_id])
    checked_out_by = db.relationship("User", foreign_keys=[checked_out_by_id])
    returned_to_office_by = db.relationship("User", foreign_keys=[returned_to_office_by_id])

    @property
    def full_name(self):
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts)

    @property
    def is_delivered(self):
        return self.delivery_status == "delivered"

    @property
    def is_out_for_delivery(self):
        return self.delivery_status == "out_for_delivery"

    @property
    def is_returned(self):
        return self.delivery_status == "returned"

    @property
    def is_returned_to_office(self):
        return self.delivery_status == "returned_to_office"

    @property
    def delivery_photo_url(self):
        if self.delivery_photo_drive_id:
            from drive_storage import thumbnail_url
            return thumbnail_url(self.delivery_photo_drive_id, size=1000)
        if self.delivery_photo:
            return f"/static/uploads/delivery/{self.delivery_photo}"
        return None

    @property
    def delivery_photo_source(self):
        if self.delivery_photo_drive_id:
            return "drive"
        if self.delivery_photo:
            return "local"
        return None


class DeliveryLog(db.Model):
    """Full audit trail of ID-delivery events: every scan OUT (checkout)
    and every resolution (delivered/returned), including re-attempts."""

    __tablename__ = "delivery_logs"

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)
    event = db.Column(db.String(20), nullable=False)  # checked_out | delivered | returned | returned_to_office
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    gps_matched = db.Column(db.Boolean, nullable=True)
    gps_distance_m = db.Column(db.Float, nullable=True)
    gps_reference = db.Column(db.String(20), nullable=True)

    remarks = db.Column(db.String(255), nullable=True)
    photo = db.Column(db.String(255), nullable=True)
    photo_drive_id = db.Column(db.String(100), nullable=True)

    by_user = db.relationship("User")

    @property
    def photo_url(self):
        if self.photo_drive_id:
            from drive_storage import thumbnail_url
            return thumbnail_url(self.photo_drive_id, size=1000)
        if self.photo:
            return f"/static/uploads/delivery/{self.photo}"
        return None


class CheckLog(db.Model):
    """A single time-in / time-out event produced by a QR scan."""

    __tablename__ = "check_logs"

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)
    log_type = db.Column(db.String(3), nullable=False)  # IN | OUT
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    scanned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    scanned_by = db.relationship("User")
