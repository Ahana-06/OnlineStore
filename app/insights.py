"""Connects the AI functions (app/ai/) to the database and the pages."""
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .ai.recommend import recommend
from .ai.restock import days_left, restock_status
from .ai.risk import FLAG_THRESHOLD, risk_score
from .ai.sentiment import analyze
from .auth import log_action, role_required
from .models import Order, OrderItem, Payment, Product, Review

bp = Blueprint("insights", __name__)

RESTOCK_WINDOW_DAYS = 28


# ------------------------------------------------------------ recommendations
def get_recommendations(product_id, top_n=3):
    baskets = defaultdict(set)
    for order_id, pid in db.session.query(OrderItem.order_id, OrderItem.product_id).all():
        baskets[order_id].add(pid)

    results = []
    for pid, count in recommend(list(baskets.values()), product_id, top_n):
        product = db.session.get(Product, pid)
        if product:
            plural = "s" if count != 1 else ""
            results.append({"product": product, "count": count,
                            "reason": f"Bought together in {count} order{plural}"})
    return results


# ------------------------------------------------------------ reviews + sentiment
def review_summary(reviews):
    summary = {"positive": 0, "neutral": 0, "negative": 0, "avg_rating": None}
    for r in reviews:
        summary[r.sentiment or "neutral"] += 1
    if reviews:
        summary["avg_rating"] = round(sum(r.rating for r in reviews) / len(reviews), 1)
    return summary


@bp.route("/products/<int:product_id>/review", methods=["POST"])
@login_required
def add_review(product_id):
    product = db.get_or_404(Product, product_id)
    rating = request.form.get("rating", type=int)
    text = request.form.get("text", "").strip()
    if rating not in (1, 2, 3, 4, 5):
        flash("Please choose a rating from 1 to 5.", "danger")
    elif not text:
        flash("Please write a short review.", "danger")
    else:
        label, _score = analyze(text, rating)  # AI: sentiment of the review text
        db.session.add(Review(product_id=product.id, user_id=current_user.id,
                              rating=rating, text=text, sentiment=label))
        db.session.commit()
        flash("Thanks for your review!", "success")
    return redirect(url_for("shop.product_detail", product_id=product.id))


# ------------------------------------------------------------ risky orders
def assess_order(order, max_line_qty, total):
    """Called from checkout. Returns (score, reason)."""
    now = datetime.utcnow()
    orders_last_hour = Order.query.filter(
        Order.user_id == order.user_id, Order.id != order.id,
        Order.created_at >= now - timedelta(hours=1)).count() + 1  # +1 = this order
    failed = (db.session.query(func.count(Payment.id))
              .join(Order, Order.id == Payment.order_id)
              .filter(Order.user_id == order.user_id, Payment.status == "Failed",
                      Payment.created_at >= now - timedelta(days=1)).scalar() or 0)
    return risk_score(max_line_qty, total, orders_last_hour, failed)


@bp.route("/admin/flagged")
@role_required("admin")
def flagged_orders():
    orders = (Order.query.filter(Order.risk_score >= FLAG_THRESHOLD)
              .order_by(Order.created_at.desc()).all())
    return render_template("admin_flagged.html", orders=orders, threshold=FLAG_THRESHOLD)


@bp.route("/admin/flagged/<int:order_id>/clear", methods=["POST"])
@role_required("admin")
def clear_flag(order_id):
    order = db.get_or_404(Order, order_id)
    order.risk_score = 0
    order.risk_reason = ""
    log_action("Cleared risk flag", "order", order.id)
    db.session.commit()
    flash(f"Order #{order.id} marked as safe.", "success")
    return redirect(url_for("insights.flagged_orders"))


# ------------------------------------------------------------ restock prediction
@bp.route("/seller/restock")
@role_required("seller", "admin")
def restock():
    since = datetime.utcnow() - timedelta(days=RESTOCK_WINDOW_DAYS)
    sold = dict(
        db.session.query(OrderItem.product_id, func.sum(OrderItem.qty))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= since)
        .group_by(OrderItem.product_id).all()
    )
    query = Product.query
    if current_user.role == "seller":
        query = query.filter_by(seller_id=current_user.id)

    rows = []
    for p in query.all():
        units = int(sold.get(p.id) or 0)
        days = days_left(p.stock, units, RESTOCK_WINDOW_DAYS)
        rows.append({"product": p, "units": units, "days": days, "status": restock_status(days)})
    rows.sort(key=lambda r: (r["days"] is None, r["days"] if r["days"] is not None else 0))
    return render_template("restock.html", rows=rows, window=RESTOCK_WINDOW_DAYS)
