"""Admin tools: list users, change roles, read the audit log."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from . import db
from .auth import log_action, role_required
from .models import AuditLog, Order, Product, User

bp = Blueprint("admin", __name__, url_prefix="/admin")

ROLES = ("customer", "seller", "admin")


@bp.route("/users")
@role_required("admin")
def users():
    role = request.args.get("role", "")
    query = User.query
    if role in ROLES:
        query = query.filter_by(role=role)

    # one query each for order counts and product counts, instead of one per user
    order_counts = dict(db.session.query(Order.user_id, func.count(Order.id)).group_by(Order.user_id).all())
    product_counts = dict(db.session.query(Product.seller_id, func.count(Product.id))
                          .group_by(Product.seller_id).all())
    return render_template("admin_users.html", users=query.order_by(User.created_at).all(),
                           roles=ROLES, role=role,
                           order_counts=order_counts, product_counts=product_counts)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def change_role(user_id):
    user = db.get_or_404(User, user_id)
    new_role = request.form.get("role", "")

    if new_role not in ROLES:
        flash("Unknown role.", "danger")
    elif user.id == current_user.id:
        flash("You can't change your own role (you could lock yourself out).", "warning")
    elif user.role == "admin" and new_role != "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("This is the last admin, so the role can't be removed.", "warning")
    elif new_role == user.role:
        flash(f"{user.name} is already a {new_role}.", "info")
    else:
        old = user.role
        user.role = new_role
        log_action("Changed role", "user", user.id, f"{user.email}: {old} -> {new_role}")
        db.session.commit()
        flash(f"{user.name} is now a {new_role}.", "success")

    return redirect(request.referrer or url_for("admin.users"))


@bp.route("/audit")
@role_required("admin")
def audit_log():
    entity = request.args.get("entity", "")
    user_id = request.args.get("user_id", type=int)

    query = AuditLog.query
    if entity:
        query = query.filter_by(entity=entity)
    if user_id:
        query = query.filter_by(user_id=user_id)

    entities = [e for (e,) in db.session.query(AuditLog.entity).distinct().order_by(AuditLog.entity) if e]
    staff = User.query.filter(User.role.in_(("seller", "admin"))).order_by(User.name).all()
    return render_template("admin_audit.html",
                           logs=query.order_by(AuditLog.created_at.desc()).limit(300).all(),
                           entities=entities, staff=staff, entity=entity, user_id=user_id)
