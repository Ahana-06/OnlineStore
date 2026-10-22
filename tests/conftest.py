"""Shared test setup: a fresh in-memory SQLite database for every test."""
from datetime import datetime, timedelta

import pytest

from app import create_app, db
from app.models import Category, Order, OrderItem, Payment, Product, User
from config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite://"   # in memory, gone after each test


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(name, email, role, age_days=90):
    u = User(name=name, email=email, role=role, created_at=datetime.utcnow() - timedelta(days=age_days))
    u.set_password("password123")
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture
def data(app):
    """Two sellers, an admin, a customer, and a few products."""
    admin = make_user("Admin", "admin@test.com", "admin")
    seller = make_user("Seller One", "seller@test.com", "seller")
    seller2 = make_user("Seller Two", "seller2@test.com", "seller")
    customer = make_user("Customer", "customer@test.com", "customer")
    shoes = Category(name="Footwear")
    tech = Category(name="Electronics")
    db.session.add_all([shoes, tech])
    db.session.flush()
    p_shoe = Product(seller_id=seller.id, category_id=shoes.id, name="Running Shoes", price=2500, stock=10)
    p_sock = Product(seller_id=seller.id, category_id=shoes.id, name="Sports Socks", price=200, stock=50)
    p_buds = Product(seller_id=seller2.id, category_id=tech.id, name="Wireless Earbuds", price=2000, stock=10)
    db.session.add_all([p_shoe, p_sock, p_buds])
    db.session.commit()
    return {"admin": admin, "seller": seller, "seller2": seller2, "customer": customer,
            "shoes": shoes, "tech": tech, "shoe": p_shoe, "sock": p_sock, "buds": p_buds}


def make_order(user, lines, status="Placed", payment="Paid", risk=0, created_at=None):
    """lines: [(product, qty), ...]"""
    order = Order(user_id=user.id, status=status, risk_score=risk,
                  created_at=created_at or datetime.utcnow())
    db.session.add(order)
    db.session.flush()
    total = 0
    for product, qty in lines:
        db.session.add(OrderItem(order_id=order.id, product_id=product.id, qty=qty,
                                 price_at_purchase=product.price))
        total += product.price * qty
    order.total = total
    db.session.add(Payment(order_id=order.id, amount=total, method="COD", status=payment))
    db.session.commit()
    return order


def login(client, email):
    return client.post("/login", data={"email": email, "password": "password123"})
