import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)

# Модель категории
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    products = db.relationship('Product', backref='category', lazy=True)

# Модель товара
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(100), nullable=False, unique=True)
    stock = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

# Модель корзины покупок
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', backref='cart_items')

# Инициализация БД с категориями
def init_db():
    with app.app_context():
        db.create_all()
        
        # Создаем основные категории, если их нет
        if not Category.query.first():
            default_categories = [
                'Электроника', 'Одежда', 'Книги', 'Дом и сад', 
                'Спорт', 'Красота', 'Игрушки', 'Еда'
            ]
            for cat_name in default_categories:
                category = Category(name=cat_name)
                db.session.add(category)
            db.session.commit()

# Главная страница с фильтрацией по категориям
@app.route('/')
def index():
    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('q', '')
    
    query = Product.query
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if search_query:
        query = query.filter(
            (Product.name.ilike(f'%{search_query}%')) | 
            (Product.description.ilike(f'%{search_query}%'))
        )
    
    products = query.order_by(Product.name).all()
    categories = Category.query.order_by(Category.name).all()
    cart_items = Cart.query.all()
    
    return render_template('index.html', 
                         products=products, 
                         categories=categories, 
                         cart_items=cart_items,
                         selected_category_id=category_id,
                         search_query=search_query)

# Добавление товара в корзину
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if not product:
        flash('Товар не найден', 'error')
        return redirect(url_for('index'))

    if product.stock <= 0:
        flash('Товара нет в наличии', 'error')
        return redirect(url_for('index'))

    try:
        # Уменьшаем количество на складе
        product.stock -= 1
        cart_item = Cart(product_id=product_id)
        db.session.add(cart_item)
        db.session.commit()
        flash('Товар добавлен в корзину!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# Оформление заказа
@app.route('/checkout', methods=['POST'])
def checkout():
    try:
        cart_items = Cart.query.all()
        if not cart_items:
            flash('Корзина пуста', 'error')
            return redirect(url_for('index'))
        
        # Очищаем корзину
        db.session.query(Cart).delete()
        db.session.commit()
        flash('Заказ успешно оформлен!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка оформления заказа: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# Удаление товара
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        flash('Товар не найден', 'error')
        return redirect(url_for('index'))

    try:
        # Удаляем изображение
        if product.image:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Удаляем из корзины
        Cart.query.filter_by(product_id=product_id).delete()
        db.session.delete(product)
        db.session.commit()
        flash('Товар успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'error')
    
    return redirect(url_for('index'))

# Загрузка товара
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    categories = Category.query.order_by(Category.name).all()
    
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('Изображение не выбрано', 'error')
            return redirect(request.url)
        
        image_file = request.files['image']
        if image_file.filename == '':
            flash('Изображение не выбрано', 'error')
            return redirect(request.url)
        
        try:
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            
            product = Product(
                name=request.form['name'],
                description=request.form['description'],
                price=float(request.form['price']),
                image=filename,
                stock=int(request.form['stock']),
                category_id=request.form.get('category_id')
            )
            db.session.add(product)
            db.session.commit()
            flash('Товар успешно добавлен!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Ошибка загрузки: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('upload.html', categories=categories)

# Добавление новой категории
@app.route('/add_category', methods=['POST'])
def add_category():
    category_name = request.form.get('category_name', '').strip()
    if not category_name:
        flash('Введите название категории', 'error')
        return redirect(url_for('index'))
    
    try:
        if Category.query.filter_by(name=category_name).first():
            flash('Такая категория уже существует', 'error')
        else:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.commit()
            flash('Категория успешно добавлена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка добавления категории: {str(e)}', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True)
