from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import db
from .models import AuditLog, User

bp = Blueprint("auth", __name__)


def role_required(*roles):
    """Use under @login_required:  @role_required("seller", "admin")"""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def log_action(action, entity="", entity_id=None):
    """Call this whenever an admin/seller changes something (audit log)."""
    uid = current_user.id if current_user.is_authenticated else None
    db.session.add(AuditLog(user_id=uid, action=action, entity=entity, entity_id=entity_id))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "customer")
        if role not in ("customer", "seller"):  # nobody can self-register as admin
            role = "customer"
        if not name or not email or len(password) < 6:
            flash("Fill all fields. Password needs at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            return redirect(request.args.get("next") or url_for("shop.products"))
        flash("Wrong email or password.", "danger")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
