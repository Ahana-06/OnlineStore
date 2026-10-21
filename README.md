# Online Store Database (Flask + SQLAlchemy)

## Run it (first time)

```bash
python -m venv venv
venv\Scripts\activate            # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python seed.py                   # creates the database + demo data
python run.py                    # open http://127.0.0.1:5000
```

Demo logins (password `password123`): `admin@store.com`, `seller@store.com`, `customer@store.com`
Discount codes: `WELCOME10`, `FEST20`

## What is already working
- Register / login / logout, hashed passwords, roles (customer, seller, admin), `@role_required`
- Product list with search and category filter, product page
- Cart, checkout in ONE transaction (stock locked and reduced, payment saved, discount code)
- My orders, seller dashboard (basic), audit log helper `log_action()`

## Folder map
```
config.py            database URL (SQLite now; set DATABASE_URL for MySQL/PostgreSQL)
run.py               starts the app
seed.py              demo data (users, products, 120 past orders, reviews)
app/__init__.py      app factory
app/models.py        ALL tables (Ravichandran owns this)
app/auth.py          register, login, roles, audit helper
app/shop.py          products, cart, checkout, orders, seller dashboard
app/templates/       pages (Ahana owns this)
```

## Switching to PostgreSQL / MySQL
```bash
pip install psycopg2-binary            # or PyMySQL
set DATABASE_URL=postgresql+psycopg2://user:password@localhost/onlinestore
python seed.py
```
(create the empty database first, e.g. `CREATE DATABASE onlinestore;`)

## Next TODOs (search the code for "TODO")
Ravichandran: ai/ folder (recommend, restock_days, sentiment, risk_score), order status route,
seller product CRUD, reports, admin pages, audit log calls, NL search.
Ahana: reviews UI, status timeline, Chart.js dashboard, product form, admin pages, error pages, testing.
