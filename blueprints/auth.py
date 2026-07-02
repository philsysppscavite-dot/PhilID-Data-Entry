from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User

bp = Blueprint("auth", __name__)


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("You need administrator access for that page.", "danger")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)

    return wrapped


def staff_or_admin_required(f):
    """Blocks the 'delivery' role from actions meant for office staff:
    editing/deleting a resident's master record. (Dashboard, Reports, and
    Personnel are open to everyone now -- each user just sees data scoped
    to their own activity there.)"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_delivery:
            flash("That page isn't available for delivery accounts.", "danger")
            return redirect(url_for("main.scan"))
        return f(*args, **kwargs)

    return wrapped


def default_landing_page():
    """Where to send someone right after login, based on their role."""
    if current_user.is_delivery:
        return url_for("main.scan")
    return url_for("main.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(default_landing_page())

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and user.is_active_user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.full_name}.", "success")
            next_page = request.args.get("next")
            # Don't honor a ?next= that points somewhere a delivery account
            # can't access -- fall back to their own default landing page.
            if next_page and user.is_delivery and not (
                next_page.startswith("/scan")
                or next_page.startswith("/search")
                or next_page.startswith("/masterlist")
            ):
                next_page = None
            return redirect(next_page or default_landing_page())

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=all_users)


@bp.route("/users/create", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "staff")

    if not username or not full_name or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for("auth.users"))

    if User.query.filter_by(username=username).first():
        flash("That username is already taken.", "danger")
        return redirect(url_for("auth.users"))

    user = User(username=username, full_name=full_name, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f"User '{username}' created.", "success")
    return redirect(url_for("auth.users"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't disable your own account.", "danger")
        return redirect(url_for("auth.users"))

    user.is_active_user = not user.is_active_user
    db.session.commit()
    state = "enabled" if user.is_active_user else "disabled"
    flash(f"User '{user.username}' {state}.", "info")
    return redirect(url_for("auth.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You can't delete your own account.", "danger")
        return redirect(url_for("auth.users"))

    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted.", "info")
    return redirect(url_for("auth.users"))
