# Online Store Database (Flask + SQLAlchemy)

## Run it (first time)

```bash
python -m venv venv
venv\Scripts\activate            # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows      (Mac/Linux: cp .env.example .env), then set SECRET_KEY
python seed.py                   # creates the database + demo data (run it again after model changes)
python run.py                    # open http://127.0.0.1:5001
```

Demo logins (password `password123`): `admin@store.com`, `seller@store.com`, `customer@store.com`
Discount codes: `WELCOME10`, `FEST20`

## What is already working
- Register / login / logout, hashed passwords, roles (customer, seller, admin), `@role_required`
- Product list with search and category filter, product page
- Cart, checkout in ONE transaction (stock locked and reduced, payment saved, discount code)
- My orders, seller dashboard (basic), audit log helper `log_action()`
- Seller tools (`/seller/products`, `/seller/orders`): add / edit / delete products (a product that is in past
  orders is archived instead, so order history keeps working), move orders Placed -> Packed -> Shipped -> Delivered
  one step at a time; risky orders are held until an admin marks them safe
- Admin tools (`/admin/users`, `/admin/audit`): change user roles, read the audit log with filters
- Reports (`/reports`): order history, revenue (paid orders only), sales by category / status, top products,
  date and status filters, CSV download. Sellers see only their own products.
- Every seller/admin change is written to the audit log in the same transaction as the change

## Folder map
```
config.py            settings, read from .env (see .env.example)
run.py               starts the app
seed.py              demo data (users, products, 120 past orders, reviews)
app/__init__.py      app factory
app/models.py        ALL tables (Ravichandran owns this)
app/auth.py          register, login, roles, audit helper
app/shop.py          products, cart, checkout, orders, seller dashboard
app/seller.py        seller product management + order status
app/admin.py         admin users + audit log
app/reports.py       reports + CSV export
app/insights.py      connects the AI functions (app/ai/) to the pages
app/ai/              recommendations, restock, sentiment, risk score, smart search
tests/               pytest tests (run: python -m pytest)
app/templates/       pages (Ahana owns this)
```

## Settings (.env)
Settings live in a `.env` file in the project folder. It is in `.gitignore`, so passwords never reach GitHub.
Copy `.env.example` to `.env` and fill it in:
- `SECRET_KEY`: any long random string, e.g. `python -c "import secrets; print(secrets.token_hex(32))"`
- `DATABASE_URL`: leave it commented out to use the local SQLite file (`store.db`)

## Switching to PostgreSQL
1. Install PostgreSQL, then create a user and an empty database (in `psql` as the `postgres` user):
   ```sql
   CREATE USER store_user WITH PASSWORD 'your_password';
   CREATE DATABASE onlinestore OWNER store_user;
   ```
2. In `.env`, uncomment the PostgreSQL line and put in your password:
   `DATABASE_URL=postgresql+psycopg2://store_user:your_password@localhost:5432/onlinestore`
3. `pip install -r requirements.txt` (includes `psycopg2-binary`), then `python seed.py` and `python run.py`.

For MySQL, use `pip install PyMySQL` and the MySQL line in `.env.example` instead.

## Tests
```bash
python -m pytest
```
The tests use a fresh in-memory SQLite database, so they never touch `store.db` or PostgreSQL.

## Next TODOs (search the code for "TODO")
Ravichandran: done (see "What is already working").
Ahana: reviews UI, status timeline, Chart.js dashboard, product form, admin pages, error pages, testing.

## Contributions
### Ravichandran (backend, database, AI)
<!-- Ravichandran: write this section in your own words. -->
