import json
from flask import Flask,render_template,redirect,url_for,request,abort,flash,jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, false
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField ,IntegerField,PasswordField
from wtforms.validators import DataRequired, URL
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import paypalrestsdk
from paypalrestsdk import Payment
import os
import dotenv
from dotenv import load_dotenv
load_dotenv()


login_manager = LoginManager()

class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)
app.config['SECRET_KEY']="8BYkEfBA6O6donzWlSihBXox7C0sKR6b"
bootstrap = Bootstrap5(app)
# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
# initialize the app with the extension
db.init_app(app)
login_manager.init_app(app)

paypalrestsdk.configure({
    "mode": "sandbox",  # Use "live" for production
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_CLIENT_SECRET'),
})



@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

class Vegetables_shop(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    image: Mapped[str] = mapped_column(String(250), nullable=False)
    vegi: Mapped[str] = mapped_column(String(250), nullable=False)
    stock: Mapped[int] =  mapped_column(Integer, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

class Cart(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    image: Mapped[str] = mapped_column(String(250), nullable=False)
    vegi: Mapped[str] = mapped_column(String(250), nullable=False)
    stock: Mapped[int] =  mapped_column(Integer, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=True)



class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    cart: Mapped[str] = mapped_column(String(100),nullable=True)

with app.app_context():
        db.create_all()

class add_form(FlaskForm):
    image = StringField(" Image URL", validators=[DataRequired(), URL()])
    stock = IntegerField('stock ', validators=[DataRequired()])
    vegi = StringField(" vegetable name", validators=[DataRequired()])
    price = IntegerField("price", validators=[DataRequired()])
    submit = SubmitField("Post")

class Veg_edit_form(FlaskForm):
    image = StringField(" Image URL", validators=[DataRequired(), URL()])
    vegi = StringField('Vegetable name', validators=[DataRequired()])
    stock = IntegerField("Stock", validators=[DataRequired()])
    price = IntegerField("Price", validators=[DataRequired()])
    save = SubmitField("save changes")
    discard = SubmitField("discard changes")

class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Me Up!")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = StringField('password', validators=[DataRequired()])
    submit = SubmitField("Login in")


@app.route("/create_payment", methods=["POST"])
def create_payment():
    # Get cart items and calculate total
    cart_items = db.session.execute(db.select(Cart)).scalars().all()
    total_amount = sum(item.total for item in cart_items)

    if total_amount <= 0:
        flash("Your cart is empty")
        return redirect(url_for("cart"))

    # Create PayPal payment object
    payment = Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": url_for("payment_success", _external=True),
            "cancel_url": url_for("payment_cancel", _external=True)
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": item.vegi,
                    "price": str(item.price),
                    "currency": "USD",
                    "quantity": item.amount
                } for item in cart_items if item.amount > 0]
            },
            "amount": {
                "total": str(total_amount),
                "currency": "USD"
            },
            "description": "Purchase from Vegetable Shop"
        }]
    })

    # Create the payment
    if payment.create():
        # Payment created successfully
        for link in payment.links:
            if link.rel == "approval_url":
                # Redirect user to PayPal approval URL
                return redirect(link.href)
    else:
        flash(f"Payment creation failed: {payment.error}")
        return redirect(url_for("cart"))


@app.route("/payment_success")
def payment_success():
    payment_id = request.args.get("paymentId")
    payer_id = request.args.get("PayerID")

    payment = Payment.find(payment_id)

    # Execute payment
    if payment.execute({"payer_id": payer_id}):
        # Payment successful, clear cart
        cart_items = db.session.execute(db.select(Cart)).scalars().all()
        for item in cart_items:
            item.amount = 0
            item.total = 0

        # Update user's cart info if logged in
        if current_user.is_authenticated:
            active_user = db.get_or_404(User, current_user.id)
            user_items_dict = {}
            for item in cart_items:
                cart_dict = {
                    "id": item.id,
                    "amount": 0,
                    "total": 0
                }
                user_items_dict[f"item {item.id}"] = json.dumps(cart_dict)

            active_user.cart = json.dumps(user_items_dict)

        db.session.commit()
        flash("Payment successful! Thank you for your purchase.")
        return redirect(url_for("order_confirmation"))
    else:
        flash(f"Payment execution failed: {payment.error}")
        return redirect(url_for("cart"))


@app.route("/payment_cancel")
def payment_cancel():
    flash("Payment cancelled")
    return redirect(url_for("cart"))


@app.route("/order_confirmation")
def order_confirmation():
    return render_template("order_confirmation.html")


@app.route("/checkout")
def checkout():
    cart_items = db.session.execute(db.select(Cart)).scalars().all()
    total = sum(item.total for item in cart_items)

    if total <= 0:
        flash("Your cart is empty")
        return redirect(url_for("cart"))

    return render_template("checkout.html", cart_items=cart_items, total=total)




@app.route("/")
def home():
    result = db.session.execute(db.select(Vegetables_shop))
    Vegetables = result.scalars().all()
    cart_vegi = db.session.execute(db.select(Cart))
    result_cart = cart_vegi.scalars().all()
    total = 0
    for v in result_cart:
        total = total + v.total
    return render_template("home.html",vegetable=Vegetables,current_user=current_user,cart_vegi=result_cart,total=total)

@app.route('/signup', methods=["GET", "POST"])
def signup():
    form = RegisterForm()
    if form.validate_on_submit():

        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("signup.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            cart_vegi = db.session.execute(db.select(Cart))
            result = cart_vegi.scalars().all()
            active_user = db.get_or_404(User, current_user.id)
            cart_dict=json.loads(active_user.cart)
            print(cart_dict)
            for item in result:
                vegi=json.loads(cart_dict[f"item {item.id}"])
                print(vegi["amount"])
                item.amount=int(vegi["amount"])
                item.total=int(vegi["total"])
                db.session.commit()
            return redirect(url_for('home'))



    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    cart_vegi = db.session.execute(db.select(Cart))
    result = cart_vegi.scalars().all()
    active_user = db.get_or_404(User, current_user.id)
    user_items_dict={}
    for item in result:
        cart_dict={
            "id":item.id,
            "amount":item.amount,
            "total": item.total
        }
        cart_json = json.dumps(cart_dict)
        user_items_dict[f"item {item.id}"]=cart_json
    user_items_json=json.dumps(user_items_dict)
    active_user.cart=user_items_json
    db.session.commit()
    for item in result:
        item.amount=0
        item.total=0
        db.session.commit()
    logout_user()


    return redirect(url_for('home'))

@app.route('/cart')
def cart():
    cart_vegi =  db.session.execute(db.select(Cart))
    result=cart_vegi.scalars().all()
    print(cart_vegi)
    total=0
    for v in result:
        total=total+v.total

    if total > 0:
        show = True
    else :
        show = False
    return render_template('cart.html',cart_vegi=result,total=total, show=show)


@app.route("/product/<int:veg_id>", methods=["GET", "POST"])
def product(veg_id):
    vegi = db.get_or_404(Vegetables_shop, veg_id)
    cart_vegi = db.session.execute(db.select(Cart))
    result = db.session.execute(db.select(Vegetables_shop))
    Vegetables = result.scalars().all()
    result_cart = cart_vegi.scalars().all()
    total = 0
    for v in result_cart:
        total = total + v.total
    show = False
    if total == 0:
        show = False
    else :
        show =True
    return render_template("product.html",vegi=vegi,vegetable=Vegetables , cart_vegi=result_cart,total=total,show=show)

@app.route("/productAdd/<int:veg_id>/<page>", methods=["GET", "POST"])
def productAdd(veg_id,page):
    vegi = db.get_or_404(Cart, veg_id)
    vegi.amount = vegi.amount+1
    vegi.stock = vegi.stock
    db.session.commit()
    vegi.total=vegi.price * vegi.amount
    result = db.session.execute(db.select(Cart))
    update_stock = db.get_or_404(Vegetables_shop, veg_id)
    update_stock.stock=update_stock.stock-1
    db.session.commit()
    Vegetables = result.scalars().all()
    for v in Vegetables:
        if v.id !=vegi.id:
            v.total=v.price* v.amount
            db.session.commit()
    if page == "product":
        return redirect(url_for(page, veg_id=veg_id))
    if page == "cart":
        return redirect(url_for(page))
    if page == "home":
        return redirect(url_for(page))

@app.route("/productDel/<int:veg_id>/<page>", methods=["GET", "POST"])
def productDel(veg_id,page):
    vegi = db.get_or_404(Cart, veg_id)
    if vegi.amount > 0:
        vegi.amount=vegi.amount - 1
    vegi.total=vegi.total * vegi.amount
    db.session.commit()
    vegi.total = vegi.price * vegi.amount
    result = db.session.execute(db.select(Cart))
    update_stock = db.get_or_404(Vegetables_shop, veg_id)
    if vegi.amount > 0:
        update_stock.stock = update_stock.stock + 1
    db.session.commit()
    Vegetables = result.scalars().all()
    for v in Vegetables:
        if v.id != vegi.id:
            v.total = v.price * v.amount
            db.session.commit()
    if page=="product":
        return redirect(url_for(page, veg_id=veg_id))
    if page == "cart":
        return  redirect(url_for(page))
    if page == "home":
        return redirect(url_for(page))



@app.route("/add", methods=["GET", "POST"])
def add():
    form = add_form()
    if form.validate_on_submit():
        new_vegi = Vegetables_shop(
            image=form.image.data,
            vegi= form.vegi.data,
            stock=form.stock.data,
            price=form.price.data,
        )
        vegi = Cart(
                image=form.image.data,
                vegi=form.vegi.data,
                stock=form.stock.data,
                price=form.price.data,
                amount=0,
                total=0,
                )

        db.session.add(vegi)
        db.session.add(new_vegi)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("add.html",form=form)

@app.route("/vegetableList")
def vegetable_list():
    result = db.session.execute(db.select(Vegetables_shop))
    Vegetables= result.scalars().all()
    print(Vegetables)
    return render_template("vegetable_list.html",veg=Vegetables)

@app.route("/edit/<int:veg_id>", methods=["GET", "POST"])
def edit_vegi(veg_id):
    veg = db.get_or_404(Vegetables_shop,veg_id)
    edit_form = Veg_edit_form(
        image=veg.image,
        vegi=veg.vegi,
        stock=veg.stock,
        price = veg.price,
    )
    if edit_form.validate_on_submit():
        if edit_form.save:
            veg.image = edit_form.image.data
            veg.vegi = edit_form.vegi.data
            veg.stock = edit_form.stock.data
            veg.price = edit_form.price.data
            db.session.commit()
            return redirect(url_for("vegetable_list"))
        if edit_form.discard:
            return redirect(url_for("vegetable_list"))
    return render_template("vegi_edit.html",form=edit_form)


@app.route("/delete/<int:veg_id>", methods=["GET", "POST"])
def delete_vegi(veg_id):
    vegi_to_delete = db.get_or_404(Vegetables_shop, veg_id)
    cart_vegi_to_delete=db.get_or_404(Cart, veg_id)
    db.session.delete(cart_vegi_to_delete)
    db.session.delete(vegi_to_delete)
    db.session.commit()
    return redirect(url_for("vegetable_list"))




if __name__=="__main__":
    app.run( debug="True")