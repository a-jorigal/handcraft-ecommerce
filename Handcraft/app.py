from flask import Flask,request,render_template,redirect,url_for,flash,session
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import time
from flask_mail import Mail, Message


app=Flask(__name__)
app.secret_key="your_secret_key"
app.config["MYSQL_HOST"]='localhost'
app.config["MYSQL_USER"]='root'
app.config["MYSQL_PASSWORD"]=''
app.config["MYSQL_DB"]="handcraft"

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'
app.config['MAIL_USE_TLS'] = True

mail = Mail(app)
#----------- (First Render Registration Page)----------------------------------
mysql=MySQL(app)
@app.route("/")
def register_template():
    return render_template("register.html")
#--------------------(Insert Registerd user To the database )-------------------------
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        nm=request.form["name"]
        email=request.form["email"]
        password=request.form["password"]
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        account = cur.fetchone()

        if account:
            flash("Account already exists! Please log in.", "warning")
            return redirect(url_for("login"))
        else:
            cur.execute("INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)", (nm, email,hashed_password))
            mysql.connection.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")
#----------------------------(Redirects to login page and Validate )---------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['loggedin'] = True
            session['user_id'] = user['id'] 
            session['username'] = user['full_name']
            session["email"] = user["email"]
             

            if email == 'admin_mail_id':  
                session['role'] = 'admin'
                flash("Welcome Admin!", "success")
                return redirect(url_for('admin'))
            else:
                session['role'] = 'user'
                flash("Login successful!", "success")
                return redirect(url_for('index'))
        else:
            flash("Invalid email or password!", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

#---------------------------------------(Redirect the Index Page )---------------------------------
@app.route("/index")
def index():
    if "loggedin" in session and session.get('role') == 'user':

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("SELECT * FROM product LIMIT 4")
        products = cur.fetchall()

        cur.close()

        return render_template("index.html",
                               username=session['username'],
                               products=products)

    return redirect(url_for("login"))
#---------------------------------------(New Pages Routes)---------------------------------
@app.route("/products")
def products():
    if "loggedin" in session and session.get('role')=='user':
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("""
            SELECT p.*, 
                   AVG(o.rating) AS avg_rating,
                   COUNT(o.rating) AS total_reviews
            FROM product p
            LEFT JOIN orders o 
                ON p.product_name = o.product_name AND o.rating IS NOT NULL
            GROUP BY p.id
        """)
        cur.execute("SELECT * FROM product")
        products_list = cur.fetchall()
        for p in products_list:
            cur.execute("""
                SELECT rating, comment 
                FROM orders 
                WHERE product_name=%s AND comment IS NOT NULL
                ORDER BY order_id DESC
                LIMIT 3
            """, (p['product_name'],))

            p['reviews'] = cur.fetchall()

        return render_template("products.html", username=session['username'], products=products_list)
    return redirect(url_for("login"))
#----------------------------------(About Us Page)------------------------------------------

@app.route("/aboutus")
def aboutus():
    if "loggedin" in session and session.get('role')=='user':
        return render_template("aboutus.html", username=session['username'])
    return redirect(url_for("login"))
#-------------------------------------(Contact us page)-----------------------------------------
@app.route("/contact")
def contact():
    if "loggedin" in session and session.get('role')=='user':
        return render_template("contact.html", username=session['username'])
    return redirect(url_for("login"))
#--------------------------------------(This is Admin Route)--------------------------------------
@app.route('/admin')
def admin():
    if 'loggedin' in session and session.get('role') == 'admin':

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("SELECT * FROM product")
        products = cur.fetchall()

    
        filter_type = request.args.get('filter', 'month')

        if filter_type == "day":
            condition = "DATE(order_date) = CURDATE()"
        elif filter_type == "week":
            condition = "order_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif filter_type == "year":
            condition = "YEAR(order_date) = YEAR(CURDATE())"
        else:
            condition = "MONTH(order_date) = MONTH(CURDATE())"

        cur.execute(f"""
            SELECT DATE_FORMAT(order_date, '%d-%m') as date,
            SUM(price * quantity) as total
            FROM orders
            WHERE {condition}
            GROUP BY DATE(order_date)
            ORDER BY DATE(order_date)
        """)
        chart_data = cur.fetchall()

        cur.execute(f"""
            SELECT product_name, SUM(quantity) as total
            FROM orders
            WHERE {condition}
            GROUP BY product_name
        """)
        pie_data = cur.fetchall()

    #   -------------Total Products-----------
        cur.execute("SELECT COUNT(*) AS total_products FROM product")
        total_products = cur.fetchone()['total_products']

    #   ------------Total Users--------------
        cur.execute("SELECT COUNT(*) AS total_users FROM users")
        total_users = cur.fetchone()['total_users']

    #   -------------Total Orders--------------
        cur.execute("SELECT COUNT(*) AS total_orders FROM orders")
        total_orders = cur.fetchone()['total_orders']

    #   --------------Total Sales----------------
        cur.execute("SELECT SUM(price * quantity) AS total_sales FROM orders")
        total_sales = cur.fetchone()['total_sales'] or 0

        # Out of Stock Products
        cur.execute("SELECT COUNT(*) AS out_of_stock FROM product WHERE qty=0")
        out_of_stock = cur.fetchone()['out_of_stock']

        cur.close()

        return render_template(
            'admin.html',
            products=products,
            chart_data=chart_data,
            pie_data=pie_data,
            filter_type=filter_type,

          
            total_products=total_products,
            total_users=total_users,
            total_orders=total_orders,
            total_sales=total_sales,
            out_of_stock=out_of_stock
        )

    else:
        return redirect(url_for('login'))
#--------------------------------------(Logout route)----------------------------------------------
@app.route("/logout")
def logout():
    session.pop("loggedin", None)
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))
#-------------------------------------(upload the image in folder)---------------

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
#------------------------------------(Add_Products)-------------------------------------------------------
@app.route("/add_product", methods=["POST"])
def add_product():
    if'loggedin' in session and session.get('role')=='admin':
        name=request.form["product_name"]
        category=request.form["category"]
        price=request.form["price"]
        qty=request.form["qty"]
        description=request.form["description"]
        image=request.files["image"]

        if image and  allowed_file(image.filename):
            filename=secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))
        else:
            filename='default.png'
        cur=mysql.connection.cursor()
        cur.execute("INSERT INTO product(product_name,category,price,qty,description,image_name) VALUES(%s,%s,%s,%s,%s,%s)",(name,category,price,qty,description,filename))
        mysql.connection.commit()
        flash("Product added Successfully")
        return redirect(url_for("admin"))
    return redirect(url_for("login"))
#----------------------------------------(Edit Product)------------------------------------------
@app.route("/edit_product", methods=["POST"])
def edit_product():
    if 'loggedin' in session and session.get('role') == 'admin':
        pid = request.form["id"]
        name = request.form["product_name"]
        category = request.form["category"]
        price = request.form["price"]
        qty = request.form["qty"]
        description = request.form["description"]
        image = request.files["image"]

        cur = mysql.connection.cursor()

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            cur.execute("""
                UPDATE product
                SET product_name=%s, category=%s, price=%s, qty=%s, description=%s, image_name=%s
                WHERE id=%s
            """, (name, category, price, qty, description, filename, pid))
        else:
            cur.execute("""
                UPDATE product
                SET product_name=%s, category=%s, price=%s, qty=%s, description=%s
                WHERE id=%s
            """, (name, category, price, qty, description, pid))

        mysql.connection.commit()
        cur.close()
        flash("Product updated successfully!", "success")
        return redirect(url_for('admin'))

    flash("Unauthorized access!", "danger")
    return redirect(url_for('login'))
#----------------------------------------(Delete Product)------------------------------------------
@app.route("/delete_product/<int:id>", methods=["POST", "GET"])
def delete_product(id):
    if 'loggedin' in session and session.get('role') == 'admin':
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM product WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()
        flash("Product deleted successfully!", "success")
        return redirect(url_for('admin'))
    else:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))
#----------------------------------(customers)-------------------------------------------------
@app.route("/customers")
def customers():
    if'loggedin' in session and session.get('role')=='admin':
        cur=mysql.connection.cursor()
        cur.execute(" SELECT id ,full_name,email FROM users ")
        customers=cur.fetchall()
        cur.close()
        return render_template("customers.html",customers=customers)
    else:
        return redirect(url_for("login"))
#-----------------------------(Buy now)-----------------------------------------
@app.route("/buy_now/<int:product_id>")
def buy_now(product_id):

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM product WHERE id=%s",(product_id,))
    product = cur.fetchone()

    return render_template("checkout.html", product=product)

#---------------------------(Place Order)----------------------------------------
@app.route("/place_order", methods=["POST"])
def place_order():

    user_id = session["user_id"]

    fullname = request.form["fullname"]
    flash(" Unauthorised access !","danger")
    address = request.form["address"]
    city = request.form["city"]
    pincode = request.form["pincode"]
    state = request.form["state"]
    payment_method = request.form.get("payment_method")
    payment_id = request.form.get("payment_id")


    if payment_method == "online":
     order_status = "Paid" if payment_id else "Pending"
    else:
     order_status = "Pending"

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT Email FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    user_email = user["Email"]

    # ---------------- BUY NOW ----------------
    if "product_id" in request.form:

        product_id = request.form["product_id"]
        quantity =int( request.form["quantity"])

        cur.execute("SELECT * FROM product WHERE id=%s",(product_id,))
        product = cur.fetchone()

        product_name = product["product_name"]
        product_image = product["image_name"]
        price = product["price"]

        total_price = int(price) * int(quantity)
         
        cur.execute("""INSERT INTO orders(user_id, product_name,product_image, price, quantity, order_date, order_status, payment_method, fullname, address, city, pincode, state)VALUES (%s, %s,%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)""", (
        user_id,product_name,product_image,price,quantity,order_status,payment_method,fullname,address,city,pincode,state))
        mysql.connection.commit()

        order_id = cur.lastrowid

        if payment_method == "online":
          cur.execute("""INSERT INTO payments(user_id, order_id, payment_id, amount, payment_method, payment_status)VALUES (%s, %s, %s, %s, %s, %s)""", (user_id,order_id,payment_id,total_price,payment_method,"Success" if payment_id else "Pending"))

        mysql.connection.commit()

        msg = Message(
       'Order Confirmation - ArtisanCrafts',
        sender=app.config['MAIL_USERNAME'],
        recipients=[user_email]
        )

        msg.body = f"""Hello {fullname}, Your order has been placed successfully!

        Product: {product_name}
        Quantity: {quantity}
        Total Price: ₹{total_price}

        Thank you for shopping with us!

         - ArtisanCrafts
        """

        mail.send(msg)

        cur.close()

        return redirect(url_for("invoice_single", order_id=order_id))


    # ---------------- CART CHECKOUT ----------------
    else:

        cur.execute("""
        SELECT cart.product_id, cart.quantity,
               product.product_name, product.image_name, product.price
        FROM cart
        JOIN product ON cart.product_id = product.id
        WHERE cart.user_id=%s
        """,(user_id,))
        payment_method = request.form.get("payment_method")
        payment_id = request.form.get("payment_id")


        if payment_method == "online":
          order_status = "Paid" if payment_id else "Pending"
        else:
          order_status = "Pending"

        cart_items = cur.fetchall()
        last_order_id=None
        for item in cart_items:
            product_id = item["product_id"]
            product_name = item["product_name"]
            product_image = item["image_name"]
            price = float(item["price"])
            quantity = int(item["quantity"])

            total_price = item["price"] * item["quantity"]

            cur.execute("""INSERT INTO orders(user_id, product_name,product_image, price, quantity, order_date, order_status, payment_method, fullname, address, city, pincode, state)VALUES (%s, %s,%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)""", (
            user_id,product_name,product_image,price,quantity,order_status,payment_method,fullname,address,city,pincode,state))
            mysql.connection.commit()

            order_id = cur.lastrowid
            last_order_id=order_id
            
            if payment_method == "online":
              cur.execute("""INSERT INTO payments(user_id, order_id, payment_id, amount, payment_method, payment_status)VALUES (%s, %s, %s, %s, %s, %s)""", (user_id,order_id,payment_id,total_price,payment_method,"Success" if payment_id else "Pending"))

              mysql.connection.commit()

        cur.execute("DELETE FROM cart WHERE user_id=%s",(user_id,))

        mysql.connection.commit()
       
        cur.execute("SELECT Email FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()
        user_email = user["Email"]

        
        email_body = f"Hello {fullname},\n\nYour order has been placed successfully!\n\n"

        grand_total = 0

        for item in cart_items:
          product_name = item["product_name"]
          quantity = int(item["quantity"])
          price = float(item["price"])

          total_price = price * quantity
          grand_total += total_price

          email_body += f"Product: {product_name}\n"
          email_body += f"Quantity: {quantity}\n"
          email_body += f"Price: ₹{total_price}\n\n"


        email_body += f"Total Amount: ₹{grand_total}\n\n"
        email_body += "Thank you for shopping with us!\n\n- ArtisanCrafts"

        msg = Message(
        'Order Confirmation - ArtisanCrafts',
        sender=app.config['MAIL_USERNAME'],
        recipients=[user_email]
        )

        msg.body = email_body

        mail.send(msg)
        cur.close()
       

        return redirect(url_for("invoice_cart", user_id=user_id))
    
# #------------------------------------(Admin_Orders)----------------------------------------
@app.route('/orders')
def  orders():

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM orders ORDER BY order_date DESC")

    orders = cur.fetchall()

    cur.close()

    return render_template("orders.html", orders=orders)

#----------------------------------------(Profile)------------------------------------
@app.route('/profile')
def profile():

    if 'loggedin' in session:

        user_id = session['user_id']

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("SELECT id, full_name, email FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()

        cur.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY order_date DESC", (user_id,))
        orders = cur.fetchall()

        cur.close()

        return render_template("profile.html", user=user, orders=orders)

    return redirect(url_for('login'))
#--------------------------------------(add to cart )----------------------------------------------
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute(
        "SELECT * FROM cart WHERE user_id=%s AND product_id=%s",
        (user_id, product_id)
    )

    item = cur.fetchone()

    if item:
        cur.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id=%s",
            (item['id'],)
        )
    else:
        cur.execute(
            "INSERT INTO cart (user_id, product_id, quantity) VALUES (%s,%s,1)",
            (user_id, product_id)
        )

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('products'))
#-------------------------------------------(Cart)-------------------------------------------
@app.route('/cart')
def cart():

    user_id = session['user_id']

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
       SELECT cart.product_id, cart.quantity,
       product.product_name, product.price, product.image_name
       FROM cart
       JOIN product ON cart.product_id = product.id
       WHERE cart.user_id=%s
    """, (user_id,))

    cart_items = cur.fetchall()

    total = 0
    for item in cart_items:
        total += item['price'] * item['quantity']

    return render_template("cart.html", cart_items=cart_items, total=total)

# ------------------------------------(checkout_cart)-------------------------------------
@app.route('/checkout')
def checkout_cart():

    user_id = session['user_id']

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
    SELECT cart.product_id, cart.quantity,
           product.product_name, product.image_name, product.price
    FROM cart
    JOIN product ON cart.product_id = product.id
    WHERE cart.user_id=%s
    """,(user_id,))

    cart_items = cur.fetchall()

    total_amount = 0

    for item in cart_items:
        total_amount += item['price'] * item['quantity']

    return render_template(
        "checkout_cart.html",
        cart_items=cart_items,
        total_amount=total_amount
    )
#-----------------------------------------(Remove item)----------------------
@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):

    user_id = session['user_id']

    cur = mysql.connection.cursor()

    cur.execute(
        "DELETE FROM cart WHERE user_id=%s AND product_id=%s",
        (user_id, product_id)
    )

    mysql.connection.commit()

    return redirect(url_for('cart'))

#-----------------------------------------(single product)---------------------------
@app.route('/invoice_single/<int:order_id>')
def invoice_single(order_id):

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM orders WHERE order_id=%s",(order_id,))
    order = cur.fetchone()

    cur.close()

    return render_template("invoice_single.html", order=order)
# ---------------------------------------(cart_invoice)---------------------------------
@app.route('/invoice_cart/<int:user_id>')
def invoice_cart(user_id):

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
    SELECT order_date 
    FROM orders 
    WHERE user_id=%s 
    ORDER BY order_date DESC 
    LIMIT 1
    """,(user_id,))

    latest_order = cur.fetchone()

    if not latest_order:
        return "Order not found"

    order_time = latest_order["order_date"]

    cur.execute("""
    SELECT * FROM orders
    WHERE user_id=%s AND order_date=%s
    """,(user_id, order_time))

    orders = cur.fetchall()

    grand_total = 0
    for item in orders:
        grand_total = grand_total + item["price"]*item["quantity"]

    cur.close()

    return render_template(
        "invoice_cart.html",
        orders=orders,
        grand_total=grand_total
    )
# -------------------------------------(cart count)---------------------------------------------
@app.context_processor
def inject_cart_count():
    if "user_id" in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT SUM(quantity) FROM cart WHERE user_id=%s", (session["user_id"],))
        result = cur.fetchone()[0]
        cur.close()

        return dict(cart_count=result if result else 0)

    return dict(cart_count=0)
# ----------------------------------------(cancel Order)-------------------------------------
@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT * FROM orders WHERE order_id=%s", (order_id,))
    order = cur.fetchone()

    if not order:
        return "Order not found"

    if order["order_status"] != "Pending":
        return "Cannot cancel this order"

    cur.execute("""
        UPDATE product 
        SET qty = qty + %s 
        WHERE product_name=%s
    """, (order["quantity"], order["product_id"]))

    cur.execute("""
        UPDATE orders 
        SET order_status='Cancelled' 
        WHERE order_id=%s
    """, (order_id,))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('profile'))
# ---------------------------------<My orders>--------------------------------------------------
@app.route('/my_orders')
def my_orders():
    user_id = session["user_id"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY order_id DESC", (user_id,))
    orders = cur.fetchall()

    return render_template("my_orders.html", orders=orders)

# ----------------------------------(add review)-----------------------------------------
@app.route('/add_review', methods=['POST'])
def add_review():
    order_id = request.form['order_id']
    rating = request.form['rating']
    comment = request.form['comment']

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE orders 
        SET rating=%s, comment=%s 
        WHERE order_id=%s
    """, (rating, comment, order_id))

    mysql.connection.commit()
    cur.close()

    flash("Review submitted successfully!", "success")
    return redirect(url_for('my_orders'))


if __name__=="__main__":
    app.run(debug=True)