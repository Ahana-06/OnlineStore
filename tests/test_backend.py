"""Tests for the seller, admin, reports and checkout routes (in-memory SQLite)."""
from datetime import datetime, timedelta

from app import db
from app.models import AuditLog, CartItem, Order, Product, User
from app.reports import build_report

from .conftest import login, make_order


def last_log():
    return AuditLog.query.order_by(AuditLog.id.desc()).first()


# ------------------------------------------------------------ access control
def test_customer_cannot_open_staff_pages(client, data):
    login(client, "customer@test.com")
    for url in ["/seller/products", "/seller/orders", "/reports/", "/admin/users", "/admin/audit"]:
        assert client.get(url).status_code == 403, url


def test_seller_cannot_open_admin_pages(client, data):
    login(client, "seller@test.com")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/audit").status_code == 403


def test_all_staff_pages_render_for_admin(client, data):
    make_order(data["customer"], [(data["shoe"], 1)])
    login(client, "admin@test.com")
    for url in ["/", "/seller/products", "/seller/products/new", "/seller/orders", "/reports/",
                "/reports/orders.csv", "/admin/users", "/admin/audit", "/admin/flagged", "/seller/restock",
                f"/seller/products/{data['shoe'].id}/edit"]:
        assert client.get(url).status_code == 200, url


# ------------------------------------------------------------ products
def test_seller_adds_product_and_it_is_logged(client, data):
    login(client, "seller@test.com")
    r = client.post("/seller/products/new", data={
        "name": "Trail Shoes", "price": "3199", "stock": "7", "category_id": data["shoes"].id})
    assert r.status_code == 302
    p = Product.query.filter_by(name="Trail Shoes").one()
    assert p.seller_id == data["seller"].id and p.price == 3199 and p.stock == 7
    log = last_log()
    assert log.action == "Created product" and log.entity_id == p.id and log.user_id == data["seller"].id


def test_new_category_typed_by_seller_is_created_once(client, data):
    login(client, "seller@test.com")
    for name in ("Pen", "Pencil"):
        client.post("/seller/products/new", data={"name": name, "price": "10", "stock": "1",
                                                  "new_category": "stationery"})
    pen, pencil = Product.query.filter_by(name="Pen").one(), Product.query.filter_by(name="Pencil").one()
    assert pen.category_id == pencil.category_id
    assert pen.category.name == "Stationery"


def test_bad_product_form_saves_nothing(client, data):
    login(client, "seller@test.com")
    before = Product.query.count()
    r = client.post("/seller/products/new", data={"name": "", "price": "-5", "stock": "x"})
    assert r.status_code == 200          # form shown again with errors
    assert b"Price must be more than 0" in r.data and b"Stock must be a whole number" in r.data
    assert Product.query.count() == before


def test_edit_logs_old_and_new_values(client, data):
    login(client, "seller@test.com")
    shoe = data["shoe"]
    client.post(f"/seller/products/{shoe.id}/edit", data={
        "name": shoe.name, "price": "2299", "stock": "10", "category_id": shoe.category_id})
    assert db.session.get(Product, shoe.id).price == 2299
    assert "price: 2500.0 -> 2299.0" in last_log().details


def test_seller_cannot_touch_another_sellers_product(client, data):
    login(client, "seller@test.com")
    buds = data["buds"]
    assert client.get(f"/seller/products/{buds.id}/edit").status_code == 403
    assert client.post(f"/seller/products/{buds.id}/delete").status_code == 403
    assert db.session.get(Product, buds.id) is not None


def test_delete_unsold_product_removes_it(client, data):
    sock_id = data["sock"].id
    db.session.add(CartItem(user_id=data["customer"].id, product_id=sock_id, qty=1))
    db.session.commit()
    login(client, "seller@test.com")
    client.post(f"/seller/products/{sock_id}/delete")
    assert db.session.get(Product, sock_id) is None
    assert CartItem.query.filter_by(product_id=sock_id).count() == 0
    assert last_log().action == "Deleted product"


def test_delete_sold_product_archives_it(client, data):
    shoe_id = data["shoe"].id
    make_order(data["customer"], [(data["shoe"], 1)])
    login(client, "seller@test.com")
    client.post(f"/seller/products/{shoe_id}/delete", follow_redirects=True)  # also shows the flash
    shoe = db.session.get(Product, shoe_id)
    assert shoe is not None and shoe.is_active is False
    assert last_log().action == "Archived product"

    # hidden from the shop and the cart
    assert b"Running Shoes" not in client.get("/").data
    client.post(f"/cart/add/{shoe_id}")
    assert CartItem.query.filter_by(product_id=shoe_id).count() == 0

    # restore brings it back
    client.post(f"/seller/products/{shoe_id}/restore")
    assert db.session.get(Product, shoe_id).is_active is True


def test_checkout_rejects_archived_product_in_cart(client, data):
    shoe = data["shoe"]
    db.session.add(CartItem(user_id=data["customer"].id, product_id=shoe.id, qty=1))
    shoe.is_active = False
    db.session.commit()
    login(client, "customer@test.com")
    client.post("/checkout")
    assert Order.query.count() == 0
    assert db.session.get(Product, shoe.id).stock == 10    # stock untouched (rolled back)


# ------------------------------------------------------------ order status
def test_status_moves_one_step_at_a_time(client, data):
    order = make_order(data["customer"], [(data["shoe"], 1)])
    login(client, "seller@test.com")
    url = f"/seller/orders/{order.id}/status"

    client.post(url, data={"status": "Shipped"})          # skipping Packed is refused
    assert db.session.get(Order, order.id).status == "Placed"

    for expected in ["Packed", "Shipped", "Delivered"]:
        client.post(url, data={"status": expected})
        assert db.session.get(Order, order.id).status == expected

    client.post(url, data={"status": "Placed"})           # nothing after Delivered
    assert db.session.get(Order, order.id).status == "Delivered"
    assert AuditLog.query.filter_by(action="Changed order status", entity_id=order.id).count() == 3


def test_seller_cannot_move_orders_without_their_products(client, data):
    order = make_order(data["customer"], [(data["buds"], 1)])   # seller2's product
    login(client, "seller@test.com")
    assert client.post(f"/seller/orders/{order.id}/status", data={"status": "Packed"}).status_code == 403
    assert b"#%d" % order.id not in client.get("/seller/orders").data


def test_flagged_order_is_held_for_seller_but_not_admin(client, data):
    order = make_order(data["customer"], [(data["shoe"], 12)], risk=60)
    login(client, "seller@test.com")
    client.post(f"/seller/orders/{order.id}/status", data={"status": "Packed"})
    assert db.session.get(Order, order.id).status == "Placed"

    client.get("/logout")
    login(client, "admin@test.com")
    client.post(f"/seller/orders/{order.id}/status", data={"status": "Packed"})
    assert db.session.get(Order, order.id).status == "Packed"


# ------------------------------------------------------------ admin
def test_admin_changes_role_and_it_is_logged(client, data):
    login(client, "admin@test.com")
    cid = data["customer"].id
    client.post(f"/admin/users/{cid}/role", data={"role": "seller"})
    assert db.session.get(User, cid).role == "seller"
    assert last_log().details == "customer@test.com: customer -> seller"


def test_admin_cannot_change_own_role_or_set_unknown_role(client, data):
    login(client, "admin@test.com")
    client.post(f"/admin/users/{data['admin'].id}/role", data={"role": "customer"})
    assert db.session.get(User, data["admin"].id).role == "admin"
    client.post(f"/admin/users/{data['customer'].id}/role", data={"role": "superuser"})
    assert db.session.get(User, data["customer"].id).role == "customer"


def test_audit_log_filter(client, data):
    login(client, "admin@test.com")
    client.post(f"/admin/users/{data['customer'].id}/role", data={"role": "seller"})
    page = client.get("/admin/audit?entity=user").data
    assert b"Changed role" in page
    assert b"Changed role" not in client.get("/admin/audit?entity=product").data


# ------------------------------------------------------------ reports
def test_build_report_counts_paid_revenue_only():
    now = datetime.utcnow()
    rows = [
        # order, date, status, total, code, customer, payment, product, category, qty, price, full price
        (1, now, "Placed", 500, None, "A", "Paid", "Socks", "Footwear", 2, 100, 500),
        (1, now, "Placed", 500, None, "A", "Paid", "Mug", "Home", 1, 300, 500),
        (2, now, "Shipped", 1000, None, "B", "Failed", "Lamp", "Home", 1, 1000, 1000),
    ]
    r = build_report(rows)
    assert r["total_orders"] == 2 and r["paid_orders"] == 1 and r["failed_orders"] == 1
    assert r["revenue"] == 500 and r["units"] == 3 and r["avg_order"] == 500
    assert r["by_category"] == [("Home", 300), ("Footwear", 200)]
    assert dict(r["by_status"]) == {"Placed": 1, "Packed": 0, "Shipped": 1, "Delivered": 0}
    assert r["top_products"][0] == ("Mug", 1, 300)


def test_build_report_uses_discounted_amounts():
    now = datetime.utcnow()
    rows = [  # one order, full price 1000, paid 800 after a 20% code
        (1, now, "Placed", 800, "FEST20", "A", "Paid", "Lamp", "Home", 1, 600, 1000),
        (1, now, "Placed", 800, "FEST20", "A", "Paid", "Mug", "Home", 2, 200, 1000),
    ]
    r = build_report(rows)
    assert r["revenue"] == 800 and r["avg_order"] == 800
    assert r["top_products"] == [("Lamp", 1, 480), ("Mug", 2, 320)]
    assert r["orders"][0]["subtotal"] == 800


def test_discounted_order_in_store_report(client, data):
    # Rs 2500 order with 10% off -> customer paid 2250
    order = make_order(data["customer"], [(data["shoe"], 1)])
    order.total, order.discount_code = 2250, "WELCOME10"
    db.session.commit()
    login(client, "admin@test.com")
    page = client.get("/reports/").data
    assert "₹2,250".encode() in page and "₹2,500".encode() not in page


def test_seller_gets_their_share_of_a_discounted_mixed_order(client, data):
    # shoe 2500 (seller one) + earbuds 2000 (seller two) = 4500, 20% off -> paid 3600
    order = make_order(data["customer"], [(data["shoe"], 1), (data["buds"], 1)])
    order.total, order.discount_code = 3600, "FEST20"
    db.session.commit()
    login(client, "seller@test.com")
    page = client.get("/reports/").data
    assert "₹2,000".encode() in page                     # 2500 x 0.8 = seller one's share
    client.get("/logout")
    login(client, "seller2@test.com")
    assert "₹1,600".encode() in client.get("/reports/").data   # 2000 x 0.8


def test_seller_report_only_shows_their_lines(client, data):
    make_order(data["customer"], [(data["shoe"], 1), (data["buds"], 1)])   # mixed sellers
    login(client, "seller@test.com")
    page = client.get("/reports/").data
    assert b"Running Shoes" in page and b"Wireless Earbuds" not in page
    assert "₹2,500".encode() in page                     # only seller one's revenue


def test_report_date_and_status_filters(client, data):
    make_order(data["customer"], [(data["shoe"], 1)], created_at=datetime.utcnow() - timedelta(days=60))
    make_order(data["customer"], [(data["sock"], 1)], status="Delivered")
    login(client, "admin@test.com")
    page = client.get("/reports/").data                   # default: last 30 days
    assert b"Sports Socks" in page and b"Running Shoes" not in page
    assert b"Sports Socks" not in client.get("/reports/?status=Placed").data


def test_csv_export(client, data):
    make_order(data["customer"], [(data["shoe"], 2)])
    login(client, "admin@test.com")
    r = client.get("/reports/orders.csv")
    assert r.mimetype == "text/csv"
    assert "attachment" in r.headers["Content-Disposition"]
    lines = r.data.decode().strip().splitlines()
    assert lines[0].startswith("order_id,date,customer,items")
    assert "amount_after_discount" in lines[0]
    assert "Running Shoes x 2" in lines[1] and "5000.00" in lines[1]


# ------------------------------------------------------------ checkout + new-account risk rule
def test_checkout_from_new_account_with_big_order_gets_risk_points(client, data):
    client.post("/register", data={"name": "New", "email": "new@test.com", "password": "password123"})
    login(client, "new@test.com")
    client.post(f"/cart/add/{data['shoe'].id}", data={"qty": 2})   # Rs 5000
    client.post("/checkout")
    order = Order.query.one()
    assert order.total == 5000
    assert order.risk_score == 25 and "New account" in order.risk_reason
    assert db.session.get(Product, data["shoe"].id).stock == 8


def test_checkout_from_old_account_is_not_scored(client, data):
    login(client, "customer@test.com")
    client.post(f"/cart/add/{data['shoe'].id}", data={"qty": 2})
    client.post("/checkout")
    assert Order.query.one().risk_score == 0
