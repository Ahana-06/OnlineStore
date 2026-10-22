"""Fills the database with demo data so the AI features have something to show.

Run:  python seed.py        (it wipes and recreates the tables)
Logins (password for all: password123):
    admin@store.com   seller@store.com   customer@store.com
"""
import random
from datetime import datetime, timedelta

from app import create_app, db
from app.ai.risk import risk_score
from app.ai.sentiment import analyze
from app.models import (Category, Discount, Order, OrderItem, Payment, Product,
                        Review, User)

random.seed(7)

CATALOG = {
    "Footwear": [("Running Shoes", 2499), ("Canvas Sneakers", 1299), ("Leather Sandals", 899), ("Sports Socks", 199)],
    "Electronics": [("Wireless Earbuds", 1999), ("Phone Charger", 499), ("Power Bank", 1499), ("Phone Case", 349)],
    "Home": [("Steel Water Bottle", 549), ("Desk Lamp", 799), ("Cotton Bedsheet", 1199), ("Coffee Mug", 249)],
    "Fitness": [("Yoga Mat", 699), ("Dumbbell Set", 1799), ("Resistance Bands", 399), ("Gym Towel", 299)],
}

# products people tend to buy together (this is what recommendations will find)
BUNDLES = [
    ["Running Shoes", "Sports Socks"],
    ["Wireless Earbuds", "Phone Charger"],
    ["Phone Charger", "Power Bank", "Phone Case"],
    ["Yoga Mat", "Resistance Bands", "Gym Towel"],
    ["Steel Water Bottle", "Gym Towel"],
]

REVIEWS = [
    (5, "Excellent quality, totally worth it!"), (4, "Good product, fast delivery."),
    (3, "It is okay, nothing special."), (2, "Not great, stopped working quickly."),
    (1, "Terrible, waste of money."), (5, "Love it, would buy again."),
]


def main():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        def make_user(name, email, role):
            u = User(name=name, email=email, role=role)
            u.set_password("password123")
            db.session.add(u)
            return u

        admin = make_user("Admin", "admin@store.com", "admin")
        seller = make_user("Demo Seller", "seller@store.com", "seller")
        customers = [make_user("Demo Customer", "customer@store.com", "customer")]
        for i in range(1, 9):
            customers.append(make_user(f"Customer {i}", f"customer{i}@store.com", "customer"))
        db.session.flush()

        products = {}
        for cat_name, items in CATALOG.items():
            cat = Category(name=cat_name)
            db.session.add(cat)
            db.session.flush()
            for name, price in items:
                p = Product(seller_id=seller.id, category_id=cat.id, name=name, price=price,
                            stock=random.randint(8, 60), description=f"{name} - good quality.")
                db.session.add(p)
                products[name] = p
        # make two products run low so the restock page has something to show
        products["Wireless Earbuds"].stock = 4
        products["Yoga Mat"].stock = 6
        db.session.flush()

        db.session.add(Discount(code="WELCOME10", percent=10, active=True))
        db.session.add(Discount(code="FEST20", percent=20, active=True,
                                expires_at=datetime.utcnow() + timedelta(days=30)))

        # ~120 past orders over the last 8 weeks, mostly from the bundles above
        for _ in range(120):
            buyer = random.choice(customers)
            names = random.choice(BUNDLES) if random.random() < 0.7 else random.sample(list(products), random.randint(1, 3))
            when = datetime.utcnow() - timedelta(days=random.randint(0, 56), hours=random.randint(0, 23))
            order = Order(user_id=buyer.id, status=random.choice(["Placed", "Packed", "Shipped", "Delivered", "Delivered"]),
                          created_at=when)
            db.session.add(order)
            db.session.flush()
            total = 0
            for n in names:
                qty = random.randint(1, 3)
                p = products[n]
                db.session.add(OrderItem(order_id=order.id, product_id=p.id, qty=qty, price_at_purchase=p.price))
                total += p.price * qty
            order.total = total
            failed = random.random() < 0.05
            db.session.add(Payment(order_id=order.id, amount=total, method="COD",
                                   status="Failed" if failed else "Paid", created_at=when))

        # a few suspicious orders so the admin "Flagged orders" page has data
        def suspicious(buyer, product_name, qty, orders_last_hour=0, failed=0):
            p = products[product_name]
            total = p.price * qty
            score, reason = risk_score(qty, total, orders_last_hour, failed)
            o = Order(user_id=buyer.id, status="Placed", total=total, risk_score=score, risk_reason=reason)
            db.session.add(o)
            db.session.flush()
            db.session.add(OrderItem(order_id=o.id, product_id=p.id, qty=qty, price_at_purchase=p.price))
            db.session.add(Payment(order_id=o.id, amount=total, method="COD", status="Paid"))

        suspicious(customers[3], "Phone Case", 25)
        suspicious(customers[5], "Dumbbell Set", 12)
        suspicious(customers[7], "Power Bank", 2, orders_last_hour=4, failed=3)

        for p in products.values():
            for _ in range(random.randint(1, 3)):
                rating, text = random.choice(REVIEWS)
                db.session.add(Review(product_id=p.id, user_id=random.choice(customers).id,
                                      rating=rating, text=text, sentiment=analyze(text, rating)[0]))

        db.session.commit()
        print(f"Seeded: {len(products)} products, {len(customers) + 2} users, 123 orders (3 flagged).")
        print("Login with admin@store.com / seller@store.com / customer@store.com  (password123)")


if __name__ == "__main__":
    main()
