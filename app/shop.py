from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import db
from .auth import role_required
from .models import CartItem, Category, Discount, Order, OrderItem, Payment, Product

bp = Blueprint("shop", __name__)


@bp.route("/")
@bp.route("/products")
def products():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", type=int)
    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if cat:
        query = query.filter_by(category_id=cat)
    return render_template(
        "products.html",
        products=query.order_by(Product.name).all(),
        categories=Category.query.order_by(Category.name).all(),
        q=q,
        cat=cat,
    )


@bp.route("/products/<int:product_id>")
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    # TODO (Ravichandran, AI): recommendations = recommend(product_id)
    return render_template("product_detail.html", product=product)


# ---------------------------------------------------------------- cart
@bp.route("/cart")
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(i.product.price * i.qty for i in items)
    return render_template("cart.html", items=items, total=total)


@bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def cart_add(product_id):
    product = db.get_or_404(Product, product_id)
    qty = max(1, request.form.get("qty", 1, type=int))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if item:
        item.qty += qty
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product.id, qty=qty))
    db.session.commit()
    flash(f"Added {product.name} to your cart.", "success")
    return redirect(request.referrer or url_for("shop.products"))


@bp.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def cart_remove(item_id):
    item = db.get_or_404(CartItem, item_id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("shop.cart"))


# ---------------------------------------------------------------- checkout
@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("shop.products"))

    if request.method == "GET":
        total = sum(i.product.price * i.qty for i in items)
        return render_template("checkout.html", items=items, total=total)

    # POST: everything below is ONE transaction. If anything fails, nothing is saved.
    try:
        order = Order(user_id=current_user.id, status="Placed")
        db.session.add(order)
        db.session.flush()  # gives order.id

        total = 0.0
        for it in items:
            # lock the row so two buyers cannot take the last item at the same time
            product = Product.query.filter_by(id=it.product_id).with_for_update().one()
            if product.stock < it.qty:
                raise ValueError(f"Not enough stock for {product.name} (only {product.stock} left).")
            product.stock -= it.qty
            db.session.add(
                OrderItem(order_id=order.id, product_id=product.id, qty=it.qty,
                          price_at_purchase=product.price)
            )
            total += product.price * it.qty

        code = request.form.get("code", "").strip().upper()
        if code:
            d = Discount.query.filter_by(code=code, active=True).first()
            if d and (d.expires_at is None or d.expires_at > datetime.utcnow()):
                total = round(total * (100 - d.percent) / 100, 2)
                order.discount_code = d.code
            else:
                raise ValueError("That discount code is not valid.")

        order.total = round(total, 2)
        db.session.add(Payment(order_id=order.id, amount=order.total, method="COD", status="Paid"))
        CartItem.query.filter_by(user_id=current_user.id).delete()

        # TODO (Ravichandran, AI): order.risk_score, order.risk_reason = risk_score(order)

        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("shop.cart"))

    flash(f"Order #{order.id} placed!", "success")
    return redirect(url_for("shop.my_orders"))


@bp.route("/orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders)


# ---------------------------------------------------------------- seller (starter stub)
@bp.route("/seller/dashboard")
@role_required("seller", "admin")
def seller_dashboard():
    my_products = Product.query.filter_by(seller_id=current_user.id).all()
    low_stock = [p for p in my_products if p.stock <= 5]
    # TODO (Ahana): charts. TODO (Ravichandran): JSON route for the chart data.
    return render_template("seller_dashboard.html", products=my_products, low_stock=low_stock)
