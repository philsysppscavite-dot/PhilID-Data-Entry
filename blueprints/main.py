from datetime import datetime, time

from flask import Blueprint, render_template
from flask_login import login_required

from extensions import db
from models import CheckLog, Resident

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    today_start = datetime.combine(datetime.utcnow().date(), time.min)

    total_residents = Resident.query.count()
    logs_today = CheckLog.query.filter(CheckLog.timestamp >= today_start).count()
    ins_today = CheckLog.query.filter(
        CheckLog.timestamp >= today_start, CheckLog.log_type == "IN"
    ).count()
    outs_today = CheckLog.query.filter(
        CheckLog.timestamp >= today_start, CheckLog.log_type == "OUT"
    ).count()

    return render_template(
        "dashboard.html",
        total_residents=total_residents,
        logs_today=logs_today,
        ins_today=ins_today,
        outs_today=outs_today,
    )


@bp.route("/scan")
@login_required
def scan():
    return render_template("scan.html")


@bp.route("/search")
@login_required
def search():
    return render_template("search.html")
