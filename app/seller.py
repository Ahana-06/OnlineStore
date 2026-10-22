"""Seller tools: manage products (add / edit / delete) and move orders through their status.

Sellers only see and change their OWN products and the orders that contain them.
Admins can see and change everything.
Every change is written to the audit log in the same transaction as the change itself.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import db
from .ai.risk import FLAG_THRESHOLD
from .auth import log_action, role_required
from .models import ORDER_STATUSES, CartItem, Category, Order, OrderItem, Product

bp = Blueprint("seller", __name__, url_prefix="/seller")


# ------------------------------------------------------------ helpers
def _own_product_or_403(product_id):
    product = db.get_or_404(Product, product_id)
    if current_user.role != "admin" and product.seller_id != current_user.id:
        abort(403)
    return product


def _read_product_form(form):
    """Validate the product form. Returns (data, errors)."""
    errors = []
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()
    image_url = form.get("image_url", "").strip()
    category_id = form.get("category_id", type=int)
    new_category = form.get("new_category", "").strip()

    try:
        price = round(float(form.get("price", "")), 2)
        if price <= 0:
            errors.append("Price must be more than 0.")
    except ValueError:
        price = None
        errors.append("Price must be a number.")

    try:
        stock = int(form.get("stock", ""))
        if stock < 0:
            errors.append("Stock cannot be negative.")
    except ValueError:
        stock = None
        errors.append("Stock must be a whole number.")

    if not name:
        errors.append("Name is required.")
    if not new_category and not (category_id and db.session.get(Category, category_id)):
        errors.append("Pick a category or type a new one.")

    data = {"name": name, "description": description, "image_url": image_url, "price": price,
            "stock": stock, "category_id": category_id, "new_category": new_category}
    return data, errors


def _resolve_category(data):
    """Use the chosen category, or create the new one the seller typed."""
    if data["new_category"]:
        existing = Category.query.filter(Category.name.ilike(data["new_category"])).first()
        if existing:
            return existing.id
        cat = Category(name=data["new_category"].title())
        db.session.add(cat)
        db.session.flush()  # gives cat.id
        return cat.id
    return data["category_id"]


def next_status(status):
    """Placed -> Packed -> Shipped -> Delivered. Returns None once delivered."""
    if status not in ORDER_STATUSES:
        return None
    i = ORDER_STATUSES.index(status)
    return ORDER_STATUSES[i + 1] if i + 1 < len(ORDER_STATUSES) else None


def _seller_orders_query():
    query = Order.query
    if current_user.role == "seller":
        # orders that contain at least one of this seller's products
        query = query.filter(Order.items.any(OrderItem.product.has(Product.seller_id == current_user.id)))
    return query


# ------------------------------------------------------------ products
@bp.route("/products")
@role_required("seller", "admin")
def products():
    query = Product.query
    if current_user.role == "seller":
        query = query.filter_by(seller_id=current_user.id)
    show_archived = request.args.get("archived") == "1"
    if not show_archived:
        query = query.filter_by(is_active=True)
    return render_template("seller_products.html",
                           products=query.order_by(Product.name).all(),
                           show_archived=show_archived)


@bp.route("/products/new", methods=["GET", "POST"])
@role_required("seller", "admin")
def product_new():
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        data, errors = _read_product_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("product_form.html", product=None, form=data, categories=categories)

        product = Product(seller_id=current_user.id, category_id=_resolve_category(data),
                          name=data["name"], description=data["description"],
                          image_url=data["image_url"], price=data["price"], stock=data["stock"])
        db.session.add(product)
        db.session.flush()  # gives product.id for the log
        log_action("Created product", "product", product.id,
                   f"{product.name}, price {product.price:g}, stock {product.stock}")
        db.session.commit()
        flash(f"Added {product.name}.", "success")
        return redirect(url_for("seller.products"))

    return render_template("product_form.html", product=None, form={}, categories=categories)


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("seller", "admin")
def product_edit(product_id):
    product = _own_product_or_403(product_id)
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        data, errors = _read_product_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("product_form.html", product=product, form=data, categories=categories)

        new_values = {"name": data["name"], "description": data["description"],
                      "image_url": data["image_url"], "price": data["price"], "stock": data["stock"],
                      "category_id": _resolve_category(data)}
        changes = []
        for field, value in new_values.items():
            old = getattr(product, field)
            if old != value:
                # keep the log short: long text fields are just named, not copied
                changes.append(field if field in ("description", "image_url") else f"{field}: {old} -> {value}")
                setattr(product, field, value)

        if changes:
            log_action("Updated product", "product", product.id, "; ".join(changes))
            db.session.commit()
            flash(f"Saved {product.name}.", "success")
        else:
            flash("Nothing changed.", "info")
        return redirect(url_for("seller.products"))

    form = {"name": product.name, "description": product.description, "image_url": product.image_url,
            "price": product.price, "stock": product.stock, "category_id": product.category_id}
    return render_template("product_form.html", product=product, form=form, categories=categories)


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@role_required("seller", "admin")
def product_delete(product_id):
    product = _own_product_or_403(product_id)
    name = product.name
    in_orders = OrderItem.query.filter_by(product_id=product.id).first() is not None

    if in_orders:
        # past orders point at this product (foreign key), so archive instead of deleting
        product.is_active = False
        log_action("Archived product", "product", product.id, f"{name} (kept for order history)")
        msg = f"{name} is in past orders, so it was archived (hidden from the shop) instead of deleted."
    else:
        CartItem.query.filter_by(product_id=product.id).delete()
        log_action("Deleted product", "product", product.id, name)
        db.session.delete(product)
        msg = f"Deleted {name}."

    db.session.commit()
    flash(msg, "success")
    return redirect(url_for("seller.products"))


@bp.route("/products/<int:product_id>/restore", methods=["POST"])
@role_required("seller", "admin")
def product_restore(product_id):
    product = _own_product_or_403(product_id)
    product.is_active = True
    log_action("Restored product", "product", product.id, product.name)
    db.session.commit()
    flash(f"{product.name} is back in the shop.", "success")
    return redirect(url_for("seller.products"))


# ------------------------------------------------------------ order status
@bp.route("/orders")
@role_required("seller", "admin")
def orders():
    """Page: seller_orders.html (Ahana).
    Template gets: orders, status (current filter or ""), statuses, next_status (function),
    threshold (risk score at which an order is held for admin review)."""
    status = request.args.get("status", "")
    query = _seller_orders_query()
    if status in ORDER_STATUSES:
        query = query.filter(Order.status == status)
    return render_template("seller_orders.html",
                           orders=query.order_by(Order.created_at.desc()).all(),
                           status=status, statuses=ORDER_STATUSES,
                           next_status=next_status, threshold=FLAG_THRESHOLD)


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
@role_required("seller", "admin")
def update_order_status(order_id):
    """Form field: status = the next status. Orders can only move ONE step forward."""
    order = db.get_or_404(Order, order_id)

    if current_user.role == "seller":
        owns_item = any(it.product.seller_id == current_user.id for it in order.items)
        if not owns_item:
            abort(403)
        # AI risk flag: a flagged order is held until an admin marks it safe
        if (order.risk_score or 0) >= FLAG_THRESHOLD:
            flash(f"Order #{order.id} is flagged as risky and waiting for admin review.", "warning")
            return redirect(request.referrer or url_for("seller.orders"))

    new_status = request.form.get("status", "")
    expected = next_status(order.status)
    if expected is None:
        flash(f"Order #{order.id} is already {order.status}.", "info")
    elif new_status != expected:
        flash(f"Order #{order.id} can only move from {order.status} to {expected}.", "danger")
    else:
        old = order.status
        order.status = new_status
        log_action("Changed order status", "order", order.id, f"{old} -> {new_status}")
        db.session.commit()
        flash(f"Order #{order.id} is now {new_status}.", "success")

    return redirect(request.referrer or url_for("seller.orders"))
