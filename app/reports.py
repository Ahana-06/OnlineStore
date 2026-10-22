"""Reports: order history and sales numbers, with filters and a CSV download.

Sellers see only the lines for THEIR products. Admins see the whole store.
Revenue counts only orders whose payment went through (status "Paid").
Revenue is what the customer actually paid: if the order used a discount code, the discount is
shared across its lines in proportion to their price (so a seller's share is correct too).
"""
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, Response, render_template, request
from flask_login import current_user
from sqlalchemy import func

from . import db
from .auth import role_required
from .models import ORDER_STATUSES, Category, Order, OrderItem, Payment, Product, User

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _filters():
    """Read ?start=YYYY-MM-DD&end=YYYY-MM-DD&status=... (default: last 30 days)."""
    end = _parse_date(request.args.get("end")) or datetime.utcnow()
    start = _parse_date(request.args.get("start")) or (end - timedelta(days=30))
    status = request.args.get("status", "")
    if status not in ORDER_STATUSES:
        status = ""
    return start.replace(hour=0, minute=0, second=0, microsecond=0), \
        end.replace(hour=23, minute=59, second=59, microsecond=0), status


def _line_rows(start, end, status):
    """One row per order line, joined with everything the report needs (a single SQL query)."""
    # full price of ALL lines in each order (before discount), even lines a seller can't see
    full = (db.session.query(OrderItem.order_id.label("order_id"),
                             func.sum(OrderItem.qty * OrderItem.price_at_purchase).label("full_price"))
            .group_by(OrderItem.order_id).subquery())
    query = (db.session.query(Order.id, Order.created_at, Order.status, Order.total, Order.discount_code,
                              User.name, Payment.status, Product.name, Category.name,
                              OrderItem.qty, OrderItem.price_at_purchase, full.c.full_price)
             .join(OrderItem, OrderItem.order_id == Order.id)
             .join(full, full.c.order_id == Order.id)
             .join(Product, Product.id == OrderItem.product_id)
             .join(Category, Category.id == Product.category_id)
             .join(User, User.id == Order.user_id)
             .outerjoin(Payment, Payment.order_id == Order.id)
             .filter(Order.created_at >= start, Order.created_at <= end))
    if status:
        query = query.filter(Order.status == status)
    if current_user.role == "seller":
        query = query.filter(Product.seller_id == current_user.id)
    return query.order_by(Order.created_at.desc()).all()


def build_report(rows):
    """Turn the line rows into the order list + summary numbers. Pure Python, easy to test."""
    orders = {}
    by_category = defaultdict(float)
    by_product = defaultdict(lambda: [0, 0.0])   # name -> [units, revenue]
    by_status = defaultdict(int)
    revenue = 0.0
    units = 0
    failed = set()

    for (oid, created, status, total, code, customer, pay_status,
         product, category, qty, price, full_price) in rows:
        o = orders.setdefault(oid, {"id": oid, "created_at": created, "status": status, "total": total,
                                    "code": code, "customer": customer, "payment": pay_status or "None",
                                    "items": [], "subtotal": 0.0})   # subtotal = after discount
        # share of what was paid: order total / full price (1.0 when no discount was used)
        paid_share = (total or 0) / full_price if full_price else 1.0
        line = qty * price * paid_share
        o["items"].append(f"{product} x {qty}")
        o["subtotal"] += line
        if pay_status == "Paid":
            revenue += line
            units += qty
            by_category[category] += line
            by_product[product][0] += qty
            by_product[product][1] += line
        else:
            failed.add(oid)

    for o in orders.values():
        by_status[o["status"]] += 1
        o["subtotal"] = round(o["subtotal"], 2)

    paid_orders = len(orders) - len(failed)
    top = sorted(by_product.items(), key=lambda kv: -kv[1][1])[:5]
    return {
        "orders": list(orders.values()),
        "total_orders": len(orders),
        "paid_orders": paid_orders,
        "failed_orders": len(failed),
        "revenue": round(revenue, 2),
        "units": units,
        "avg_order": round(revenue / paid_orders, 2) if paid_orders else 0,
        "by_category": sorted(((c, round(v, 2)) for c, v in by_category.items()), key=lambda kv: -kv[1]),
        "by_status": [(s, by_status.get(s, 0)) for s in ORDER_STATUSES],
        "top_products": [(name, u, round(r, 2)) for name, (u, r) in top],
    }


@bp.route("/")
@role_required("seller", "admin")
def sales_report():
    start, end, status = _filters()
    report = build_report(_line_rows(start, end, status))
    return render_template("reports.html", r=report, start=start.strftime("%Y-%m-%d"),
                           end=end.strftime("%Y-%m-%d"), status=status, statuses=ORDER_STATUSES)


@bp.route("/orders.csv")
@role_required("seller", "admin")
def export_csv():
    start, end, status = _filters()
    report = build_report(_line_rows(start, end, status))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["order_id", "date", "customer", "items", "status", "payment",
                     "amount_after_discount", "order_total", "discount_code"])
    for o in report["orders"]:
        writer.writerow([o["id"], o["created_at"].strftime("%Y-%m-%d %H:%M"), o["customer"],
                         "; ".join(o["items"]), o["status"], o["payment"],
                         f"{o['subtotal']:.2f}", f"{o['total']:.2f}", o["code"] or ""])

    filename = f"orders_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})
