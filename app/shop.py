from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Product, Category, CartItem, Order, OrderItem

bp = Blueprint('shop', __name__)

@bp.route('/')
def index():
    query = request.args.get('q', '')
    category_id = request.args.get('category', '')
    
    products_query = Product.query
    if query:
        products_query = products_query.filter(Product.name.ilike(f'%{query}%'))
    if category_id:
        products_query = products_query.filter_by(category_id=int(category_id))
        
    products = products_query.all()
    categories = Category.query.all()
    return render_template('products.html', products=products, categories=categories)

@bp.route('/add-to-cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product.id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product.id, quantity=1)
        db.session.add(cart_item)
    db.session.commit()
    flash('Added item to cart!', 'success')
    return redirect(url_for('shop.index'))

@bp.route('/cart')
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in items)
    return render_template('cart.html', items=items, total=total)

@bp.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).all()
    return render_template('my_orders.html', orders=orders)

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@bp.route('/restock')
@login_required
def restock():
    return render_template('restock.html')