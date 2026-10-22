from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Product  # Make sure Product is imported at the top or inside the function
bp = Blueprint('shop', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/cart')
@login_required
def cart():
    return render_template('cart.html')

@bp.route('/orders')
@login_required
def orders():
    return render_template('orders.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@bp.route('/restock')
@login_required
def restock():
    return render_template('dashboard.html') # Or restock.html

@bp.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)