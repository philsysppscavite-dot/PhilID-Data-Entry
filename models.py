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

    # flask-login expects is_active as a property/attribute
    @property
    def is_active(self):
        return self.is_active_user


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

    province = db.Column(db.String(120), nullable=False)
    city_municipality = db.Column(db.String(120), nullable=False)
    barangay = db.Column(db.String(120), nullable=False)
    geocode = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship(
        "CheckLog", backref="resident", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def full_name(self):
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return " ".join(parts)


class CheckLog(db.Model):
    """A single time-in / time-out event produced by a QR scan."""

    __tablename__ = "check_logs"

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)
    log_type = db.Column(db.String(3), nullable=False)  # IN | OUT
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    scanned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    scanned_by = db.relationship("User")
