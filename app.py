from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_students'
DB_FILE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS cars 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, 
                    price_per_day INTEGER, suggestion TEXT, seats INTEGER, transmission TEXT, fuel TEXT, stock INTEGER DEFAULT 1)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS bookings 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, car_id INTEGER, 
                    start_date TEXT, end_date TEXT, is_delivery TEXT, delivery_address TEXT, total_price INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(car_id) REFERENCES cars(id))''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, message TEXT, timestamp TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id))''')
                    
    conn.execute('''CREATE TABLE IF NOT EXISTS reviews
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, car_id INTEGER, rating INTEGER, comment TEXT, timestamp TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(car_id) REFERENCES cars(id))''')
    
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM cars')
    if cur.fetchone()[0] == 0:
        cars = [
            ('Toyota Corolla', 'Reliable and fuel-efficient.', 45, 'Great for city driving!', 5, 'Auto', '6.0L/100km', 2),
            ('Honda Civic Type R (FL5)', 'Comfortable and smooth.', 50, 'Perfect for a weekend getaway.', 4, 'Manual', '6.4L/100km', 1),
            ('ford mustang 2026', 'Sporty and fun.', 120, 'Drive with style.', 4, 'Manual', '11.0L/100km', 1),
            ('Hyundai Elantra', 'Great for city driving.', 40, 'Easy to park.', 5, 'Auto', '7.0L/100km', 3),
            ('Tesla Model Y', 'Electric and fast.', 155, 'Bring a charger!', 5, 'Auto', 'Electric', 1)
        ]
        cur.executemany('INSERT INTO cars (name, description, price_per_day, suggestion, seats, transmission, fuel, stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', cars)
        
        admin_pw = generate_password_hash("marcial")
        cur.execute('INSERT INTO users (username, password) VALUES (?, ?)', ("prince_admin", admin_pw))
        
    conn.commit()
    conn.close()

with app.app_context():
    init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    cars = conn.execute('SELECT * FROM cars').fetchall()
    conn.close()
    return render_template('index.html', cars=cars)

@app.route('/car/<int:car_id>')
def car_details(car_id):
    conn = get_db_connection()
    car = conn.execute('SELECT * FROM cars WHERE id = ?', (car_id,)).fetchone()
    reviews = conn.execute('''SELECT reviews.*, users.username FROM reviews 
                              JOIN users ON reviews.user_id = users.id 
                              WHERE car_id = ? ORDER BY timestamp DESC''', (car_id,)).fetchall()
    conn.close()
    return render_template('car_details.html', car=car, reviews=reviews)

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except:
            flash("Username already exists!", "error")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials!", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/book/<int:car_id>', methods=('GET', 'POST'))
def book(car_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    car = conn.execute('SELECT * FROM cars WHERE id = ?', (car_id,)).fetchone()
    
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        delivery_choice = request.form['delivery']
        delivery_address = request.form.get('delivery_address', '') if delivery_choice == 'delivery' else ''
        
        if start_date <= end_date:
            overlapping_count = conn.execute('''SELECT COUNT(*) FROM bookings 
                                                WHERE car_id = ? AND (? <= end_date AND ? >= start_date)''', 
                                             (car_id, start_date, end_date)).fetchone()[0]
            
            if overlapping_count < car['stock']:
                d1 = datetime.strptime(start_date, "%Y-%m-%d")
                d2 = datetime.strptime(end_date, "%Y-%m-%d")
                days = max((d2 - d1).days, 1)
                total = days * car['price_per_day']
                
                conn.execute('''INSERT INTO bookings (user_id, car_id, start_date, end_date, is_delivery, delivery_address, total_price) 
                                VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                             (session['user_id'], car_id, start_date, end_date, delivery_choice, delivery_address, total))
                conn.commit()
                flash("Booking confirmed!", "success")
                conn.close()
                return redirect(url_for('index'))
            else:
                flash("Sorry, this car is fully booked for those dates!", "error")
        else:
            flash("End date must be after start date!", "error")
            
    conn.close()
    return render_template('book.html', car=car)

@app.route('/contact', methods=('GET', 'POST'))
def contact():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        subject = request.form['subject']
        message = request.form['message']
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = get_db_connection()
        conn.execute('INSERT INTO messages (user_id, subject, message, timestamp) VALUES (?, ?, ?, ?)', 
                     (session['user_id'], subject, message, now))
        conn.commit()
        conn.close()
        flash("Your message was sent to support!", "success")
        return redirect(url_for('index'))
    return render_template('contact.html')

@app.route('/rate/<int:car_id>', methods=['POST'])
def rate_car(car_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    rating = request.form['rating']
    comment = request.form['comment']
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_db_connection()
    conn.execute('INSERT INTO reviews (user_id, car_id, rating, comment, timestamp) VALUES (?, ?, ?, ?, ?)', 
                 (session['user_id'], car_id, rating, comment, now))
    conn.commit()
    conn.close()
    flash("Thank you for your review!", "success")
    return redirect(url_for('car_details', car_id=car_id))

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')


@app.route('/admin', methods=('GET', 'POST'))
def admin():
    if session.get('username') != 'prince_admin':
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    
    if request.method == 'POST' and 'add_car' in request.form:
        name = request.form['name']
        desc = request.form['description']
        price = request.form['price_per_day']
        sug = request.form['suggestion']
        seats = request.form['seats']
        trans = request.form['transmission']
        fuel = request.form['fuel']
        stock = request.form['stock']
        conn.execute('''INSERT INTO cars (name, description, price_per_day, suggestion, seats, transmission, fuel, stock) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (name, desc, price, sug, seats, trans, fuel, stock))
        conn.commit()
        flash("New vehicle added to inventory!", "success")
        
    bookings = conn.execute('''SELECT bookings.*, users.username, cars.name FROM bookings 
                                JOIN users ON bookings.user_id = users.id 
                                JOIN cars ON bookings.car_id = cars.id''').fetchall()
    messages = conn.execute('''SELECT messages.*, users.username FROM messages 
                               JOIN users ON messages.user_id = users.id ORDER BY timestamp DESC''').fetchall()
    conn.close()
    return render_template('admin.html', bookings=bookings, messages=messages)

if __name__ == '__main__':
    app.run(debug=True)