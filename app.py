from flask import Flask, render_template, request, redirect, url_for, flash, session
from mysql.connector.pooling import MySQLConnectionPool
from mysql.connector import Error
import logging

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flash messages

# Database configuration
db_config = {
    'host': 'bloodbridge-db.c3im0204sqil.eu-north-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'bloodbridge',
    'database': 'bloodbridge'
}

# Create a connection pool
cnxpool = MySQLConnectionPool(
    pool_name="mypool",
    pool_size=5,
    **db_config
)

# Function to establish a database connection
def get_db_connection():
    try:
        return cnxpool.get_connection()
    except Error as err:
        print(f"Error: {err}")
        return None

@app.route("/test-db-connection")
def test_db_connection():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")  # Test query to check connection
        db_name = cursor.fetchone()
        cursor.close()
        conn.close()
        return f"Connected to the database: {db_name[0]}"
    except Error as err:
        return f"Error: {err}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        blood_type = request.form['blood_type']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user already exists
        cursor.execute("SELECT * FROM register WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user:
            flash("Email already exists! Please log in.")
            return redirect(url_for('login', email=email))  # redirect to login page

        # Insert the new user into the database
        cursor.execute("INSERT INTO register (fullname, email, password, blood_type) VALUES (%s, %s, %s, %s)", (fullname, email, password, blood_type))
        conn.commit()
        cursor.close()
        conn.close()

        user_data = {
            'fullname': fullname,
            'email': email,
            'blood_type': blood_type
        }
        session['user'] = user_data
        flash("Registration successful! Please log in.")
        return redirect(url_for('confirm', user=user_data))

    return render_template("register.html")

@app.route('/confirm')
def confirm():
    user = session.get('user')
    return render_template('confirmation.html', user=user)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify login credentials
        cursor.execute("SELECT * FROM register WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            user_data = {
                'fullname': user[4],
                'email': user[1],
                'blood_type': user[3]
            }
            session['user'] = user_data
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid login credentials!")
            return redirect(url_for('login'))

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    user = session.get('user')
    if user is None:
        return redirect(url_for('login'))

    email = user['email']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the user's blood group
    cursor.execute("SELECT fullname, email, blood_type FROM register WHERE email = %s", (email,))
    user_data = cursor.fetchone()
    if user_data is None:
        logging.error("User data not found")
        return redirect(url_for('register'))

    user_data = {
        'fullname': user_data[0],
        'email': user_data[1],
        'blood_type': user_data[2]
    }

    # Get blood requests for the user's blood group
    cursor.execute("SELECT * FROM request WHERE blood_type = %s AND status = 'pending'", (user_data['blood_type'],))
    requests = cursor.fetchall()
    
    request_data = []
    for request in requests:
        request_data.append({
            'request_id': request[0],
            'requester_id': request[1],
            'date': request[2],
            'location': request[3],
            'urgency': request[4],
        })

    cursor.close()
    conn.close()
    return render_template("dashboard.html", user=user_data, requests=request_data)

@app.route("/request", methods=['GET', 'POST'])
def req():
    user = session.get('user')
    if request.method == 'POST':
        location = request.form['location']
        blood_type = request.form['blood_type']
        urgency = request.form['urgency']

        if user is None:
            flash("Error: User session parameter is missing!")
            return redirect(url_for('dashboard'))

        email = user['email']
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM register WHERE email = %s", (email,))
        requester_id = cursor.fetchone()[0]

        # Insert the blood request into the database
        try:
            cursor.execute("INSERT INTO request (requester_id, location, blood_type, urgency) VALUES (%s, %s, %s, %s)", (requester_id, location, blood_type, urgency))
            conn.commit()
            flash("Blood request submitted!")
        except Exception as e:
            conn.rollback()
            print(f"An error occurred: {e}")
            flash("An error occurred while submitting your request.")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('dashboard'))

    return render_template("request.html", user=user)

def get_requester_data(requester_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM register WHERE id = %s", (requester_id,))
    requester_data = cursor.fetchone()
    cursor.close()
    conn.close()
    return requester_data

def get_request_data(request_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM request WHERE id = %s", (request_id,))
    request_data = cursor.fetchone()
    cursor.close()
    conn.close()
    return request_data

@app.route("/respond/<int:requester_id>/<int:request_id>")
def respond(requester_id, request_id):
    user = session.get('user')
    request_data = get_request_data(request_id)
    requester_data = get_requester_data(requester_id)

    if request_data is None or requester_data is None:
        return redirect(url_for('dashboard'))

    request_details = {
        "date": request_data[2],
        "location": request_data[3],
        "urgency": request_data[4]
    }
    requester_details = {
        "full_name": requester_data[4],
        "email": requester_data[1],
        "blood_type": requester_data[3]
    }

    return render_template("respond.html", request_data=request_details, requester_data=requester_details, user=user, requester_id=requester_id, request_id=request_id)

@app.route("/donate-blood/<int:request_id>/<int:requester_id>", methods=["POST"])
def donate_blood(request_id, requester_id):
    user = session.get('user')
    if user is None:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE request SET status = 'donated' WHERE id = %s", (request_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Thank you for your donation!")
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(debug=True)
