from datetime import datetime, time

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from blueprints.auth import staff_or_admin_required
from extensions import db
from models import CheckLog, Resident

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    """Admins see totals/activity across everyone. Non-admins (staff and
    delivery accounts alike) only see their own scanning activity -- the
    stat cards and the logs table below are scoped to what *they* scanned."""
    today_start = datetime.combine(datetime.utcnow().date(), time.min)

    scoped = not current_user.is_admin

    total_residents_query = Resident.query
    logs_query = CheckLog.query.filter(CheckLog.timestamp >= today_start)
    ins_query = CheckLog.query.filter(CheckLog.timestamp >= today_start, CheckLog.log_type == "IN")
    outs_query = CheckLog.query.filter(CheckLog.timestamp >= today_start, CheckLog.log_type == "OUT")

    if scoped:
        # "Registered residents" for a non-admin means residents they've
        # personally interacted with (scanned, checked out, or resolved).
        total_residents_query = Resident.query.filter(
            db.or_(
                Resident.logs.any(CheckLog.scanned_by_id == current_user.id),
                Resident.checked_out_by_id == current_user.id,
                Resident.delivered_by_id == current_user.id,
                Resident.returned_to_office_by_id == current_user.id,
            )
        )
        logs_query = logs_query.filter(CheckLog.scanned_by_id == current_user.id)
        ins_query = ins_query.filter(CheckLog.scanned_by_id == current_user.id)
        outs_query = outs_query.filter(CheckLog.scanned_by_id == current_user.id)

    return render_template(
        "dashboard.html",
        total_residents=total_residents_query.count(),
        logs_today=logs_query.count(),
        ins_today=ins_query.count(),
        outs_today=outs_query.count(),
        scoped=scoped,
    )


@bp.route("/scan")
@login_required
def scan():
    return render_template("scan.html")


@bp.route("/search")
@login_required
def search():
    return render_template("search.html")


@bp.route("/masterlist")
@login_required
def masterlist():
    return render_template("masterlist.html")


@bp.route("/reports")
@login_required
def reports():
    return render_template("reports.html", scoped=not current_user.is_admin)


@bp.route("/personnel")
@login_required
def personnel():
    return render_template("personnel.html", scoped=not current_user.is_admin)


@bp.route("/transmittal")
@login_required
def transmittal():
    return render_template("transmittal.html", scoped=not current_user.is_admin)
