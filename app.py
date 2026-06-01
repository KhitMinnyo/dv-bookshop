from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, make_response, send_file,
    send_from_directory, abort, Response
)
import sqlite3
import os
import hashlib
import time
import pickle
import base64
import subprocess
import json
import re
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import urlparse
from urllib.request import urlopen
from xml.etree import ElementTree as ET

# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__)
# J5 — Hardcoded secret key (Sensitive Data Exposure)
app.secret_key = 'bookshop_secret_key_2025_khitminnyo'

# F3 — Session cookie missing Secure/HttpOnly flags
app.config['SESSION_COOKIE_HTTPONLY'] = False
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = None

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

USER_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
SHOP_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bookshop.db')

STATIC_RESET_SECRET = 'khitminnyo2025'  # Used for predictable password reset tokens (E1)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_user_db():
    """Connect to persistent user database."""
    conn = sqlite3.connect(USER_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_shop_db():
    """Connect to resettable shop database."""
    conn = sqlite3.connect(SHOP_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_user_db():
    """Initialize persistent user database. Only seeds if empty."""
    conn = get_user_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        credit_card_number TEXT,
        credit_card_expiry TEXT,
        credit_card_cvv TEXT,
        balance REAL DEFAULT 1000.0,
        secret_note TEXT DEFAULT '',
        profile_pic TEXT DEFAULT 'default.png',
        bio TEXT DEFAULT '',
        reset_token TEXT,
        reset_token_expiry TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('SELECT COUNT(*) as cnt FROM users')
    if c.fetchone()['cnt'] == 0:
        users = [
            ('admin', 'admin@bookshop.com', 'SuperSecurePass2025!', 'admin',
             '4532-0000-0000-0001', '12/27', '999', 9999.0,
             'CTF{Bl1nd_SQL1_M4st3r_T1m3_B4s3d_2025}', 'default.png', 'System Administrator', None, None, 1),
            ('alice_hacker', 'alice@hack.com', 'password123', 'user',
             '4532-1234-5678-9012', '12/25', '123', 1500.0,
             'Just a regular note', 'default.png', 'Love reading hacking books!', None, None, 1),
            ('bob_secure', 'bob@secure.net', 'bob2025secure', 'user',
             '4532-9876-5432-1098', '03/26', '456', 2000.0,
             'Nothing special here', 'default.png', 'Security enthusiast', None, None, 1),
            ('charlie_cyber', 'charlie@cyber.org', 'charlie789!', 'user',
             '4532-4567-8901-2345', '06/25', '789', 1200.0,
             'My secret shopping list', 'default.png', 'Cyber defense specialist', None, None, 1),
            ('david_code', 'david@code.com', 'david_pass_abc', 'user',
             '4532-3456-7890-1234', '09/26', '012', 1800.0,
             'Remember to update password', 'default.png', 'Code monkey', None, None, 1),
            ('eve_binary', 'eve@binary.net', 'eve_def_456', 'user',
             '4532-2345-6789-0123', '11/25', '345', 2500.0,
             'Binary is life!', 'default.png', 'Reverse engineer', None, None, 1),
            ('frank_root', 'frank@root.io', 'fr4nk_r00t!', 'moderator',
             '4916-1111-2222-3333', '05/27', '567', 3000.0,
             'Moderator secrets here', 'default.png', 'System moderator', None, None, 1),
            ('grace_shell', 'grace@shell.com', 'gr4ce_sh3ll', 'user',
             '4916-4444-5555-6666', '08/26', '890', 800.0,
             'Shell scripting is fun', 'default.png', 'Shell enthusiast', None, None, 1),
            ('heidi_crypto', 'heidi@crypto.dev', 'h3idi_crypt0', 'user',
             '4916-7777-8888-9999', '02/27', '234', 1100.0,
             'Cryptography notes', 'default.png', 'Crypto researcher', None, None, 1),
            ('ivan_net', 'ivan@network.org', 'iv4n_n3tw0rk', 'user',
             '4539-0000-1111-2222', '07/26', '678', 950.0,
             'Network diagrams stored locally', 'default.png', 'Network admin', None, None, 1),
            ('judy_exploit', 'judy@exploit.io', 'judy_3xpl0it!', 'user',
             '4539-3333-4444-5555', '10/26', '901', 1600.0,
             'Exploit development journal', 'default.png', 'Exploit developer', None, None, 1),
            ('kevin_malware', 'kevin@malware.net', 'k3vin_m4lw4r3', 'user',
             '4539-6666-7777-8888', '01/27', '345', 2200.0,
             'Malware analysis reports', 'default.png', 'Malware analyst', None, None, 1),
            ('lisa_pentest', 'lisa@pentest.com', 'l1sa_p3nt3st', 'user',
             '4556-1234-0000-1111', '04/27', '678', 1750.0,
             'Pentest methodology notes', 'default.png', 'Penetration tester', None, None, 1),
            ('mike_debug', 'mike@debug.io', 'm1ke_d3bug!', 'user',
             '4556-2222-3333-4444', '06/26', '012', 900.0,
             'Debugging is an art', 'default.png', 'Bug hunter', None, None, 1),
            ('nancy_recon', 'nancy@recon.org', 'n4ncy_r3c0n', 'user',
             '4556-5555-6666-7777', '09/27', '345', 1400.0,
             'OSINT techniques', 'default.png', 'Recon specialist', None, None, 1),
            ('oscar_phish', 'oscar@phish.net', '0sc4r_ph1sh', 'user',
             '4485-0000-1111-2222', '11/26', '678', 1050.0,
             'Social engineering notes', 'default.png', 'Social engineer', None, None, 1),
            ('pat_bruteforce', 'pat@bruteforce.io', 'p4t_brut3!', 'user',
             '4485-3333-4444-5555', '03/27', '901', 1900.0,
             'Wordlist collection', 'default.png', 'Brute force specialist', None, None, 1),
            ('quinn_overflow', 'quinn@overflow.com', 'qu1nn_0v3rfl0w', 'user',
             '4485-6666-7777-8888', '05/26', '234', 2100.0,
             'Buffer overflow notes', 'default.png', 'Low-level hacker', None, None, 1),
            ('rachel_scan', 'rachel@scan.dev', 'r4ch3l_sc4n!', 'user',
             '4485-9999-0000-1111', '08/27', '567', 1300.0,
             'Nmap scan results archive', 'default.png', 'Scanner expert', None, None, 1),
            ('sam_backdoor', 'sam@backdoor.org', 's4m_b4ckd00r', 'user',
             '4485-2222-3333-4444', '12/26', '890', 1650.0,
             'Persistence techniques', 'default.png', 'Red teamer', None, None, 1),
        ]
        c.executemany('''INSERT INTO users
            (username, email, password, role,
             credit_card_number, credit_card_expiry, credit_card_cvv, balance,
             secret_note, profile_pic, bio, reset_token, reset_token_expiry, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', users)

    conn.commit()
    conn.close()


def init_shop_db():
    """Initialize (or reset) the shop database."""
    conn = get_shop_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT DEFAULT 'default_book.png',
        description TEXT DEFAULT '',
        category TEXT DEFAULT 'General',
        stock INTEGER DEFAULT 100
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        shipping_address TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        rating INTEGER DEFAULT 5,
        comment TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_percent REAL NOT NULL,
        is_active INTEGER DEFAULT 1,
        max_uses INTEGER DEFAULT 1,
        current_uses INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        admin_reply TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS uploaded_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_user_id INTEGER,
        details TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Seed books
    c.execute('SELECT COUNT(*) as cnt FROM books')
    if c.fetchone()['cnt'] == 0:
        books = [
            ('Basic Hacking Techniques', 'Khit Minnyo', 29.99, 'book1.jpg',
             'A comprehensive guide to basic hacking techniques covering reconnaissance, scanning, and exploitation.', 'Hacking', 50),
            ('Grade 3 Hacking', 'Khit Minnyo', 24.99, 'book2.jpg',
             'Advanced hacking techniques for experienced practitioners. Covers advanced exploitation and post-exploitation.', 'Hacking', 30),
            ('WiFi Hacking', 'Khit Minnyo', 19.99, 'book3.jpg',
             'Learn the art of wireless network security. WPA2 cracking, evil twin attacks, and more.', 'Networking', 75),
            ('The First Step Towards Hacking', 'Khit Minnyo', 22.99, 'book4.png',
             'Begin your journey into ethical hacking. Perfect for absolute beginners.', 'Beginner', 100),
            ('Linux For Hackers', 'Khit Minnyo', 21.99, 'book5.png',
             'Master Linux for security testing. Command line, scripting, and system administration.', 'Linux', 60),
            ('Networking For Hackers', 'Khit Minnyo', 23.99, 'book6.png',
             'Network fundamentals for security professionals. TCP/IP, routing, firewalls, and IDS.', 'Networking', 45),
            ('Web Application Security', 'Khit Minnyo', 27.99, 'book1.jpg',
             'OWASP Top 10, SQL injection, XSS, CSRF, and modern web vulnerabilities.', 'Web Security', 80),
            ('Reverse Engineering Mastery', 'Khit Minnyo', 34.99, 'book2.jpg',
             'Binary analysis, disassembly, debugging, and malware reverse engineering.', 'Reverse Engineering', 25),
            ('Python for Pentesters', 'Khit Minnyo', 26.99, 'book3.jpg',
             'Automate penetration testing with Python. Scapy, Requests, and custom exploit development.', 'Programming', 90),
            ('Social Engineering Tactics', 'Khit Minnyo', 18.99, 'book4.png',
             'The art of human hacking. Phishing, pretexting, and physical social engineering.', 'Social Engineering', 55),
        ]
        c.executemany('''INSERT INTO books (title, author, price, image, description, category, stock)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''', books)

    # Seed coupons
    c.execute('SELECT COUNT(*) as cnt FROM coupons')
    if c.fetchone()['cnt'] == 0:
        coupons = [
            ('HACK10', 10.0, 1, 100, 0),
            ('CYBER20', 20.0, 1, 50, 0),
            ('ELITE50', 50.0, 1, 5, 0),
            ('FREESHIP', 15.0, 1, 200, 0),
            ('WELCOME25', 25.0, 1, 1000, 0),
        ]
        c.executemany('''INSERT INTO coupons (code, discount_percent, is_active, max_uses, current_uses)
                        VALUES (?, ?, ?, ?, ?)''', coupons)

    # Seed some reviews
    c.execute('SELECT COUNT(*) as cnt FROM reviews')
    if c.fetchone()['cnt'] == 0:
        reviews = [
            (2, 1, 5, 'Amazing book! Learned so much about hacking basics.', '2025-01-15 10:30:00'),
            (3, 1, 4, 'Good content but could use more examples.', '2025-02-01 14:00:00'),
            (4, 2, 5, 'Best advanced hacking book out there!', '2025-01-20 09:15:00'),
            (5, 3, 3, 'Decent WiFi hacking guide, but a bit outdated.', '2025-03-10 16:45:00'),
            (2, 4, 5, 'Perfect for beginners! Highly recommended.', '2025-02-14 11:00:00'),
            (6, 5, 4, 'Great Linux reference for security work.', '2025-04-01 08:30:00'),
        ]
        c.executemany('''INSERT INTO reviews (user_id, book_id, rating, comment, created_at)
                        VALUES (?, ?, ?, ?, ?)''', reviews)

    conn.commit()
    conn.close()


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_cart_count():
    """Get cart item count for current user."""
    if 'user_id' not in session:
        return 0
    try:
        conn = get_shop_db()
        c = conn.cursor()
        c.execute('SELECT SUM(quantity) as total FROM cart WHERE user_id = ?', (session['user_id'],))
        row = c.fetchone()
        conn.close()
        return row['total'] or 0
    except Exception:
        return 0


def login_required(f):
    """Decorator — requires login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator — requires admin role (F4: only checks session, no server-side DB verification)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        # F4 — Broken access control: only checks session role, not DB
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def waf_check(input_str):
    """Simplified WAF — intentionally bypassable."""
    if not input_str:
        return False

    input_lower = input_str.lower()

    # Allow MySQL-style comment bypass
    if "/*!50000" in input_lower:
        return False

    blacklist = [
        "union", "select", "from", "where",
        "drop", "delete", "insert", "update", "alter",
        "/*", "*/", "#", "--", "xp_", "sp_",
        "sleep", "benchmark", "wait", "delay"
    ]

    for pattern in blacklist:
        if pattern in input_lower:
            return True

    return False


def log_admin_action(admin_id, action, target_user_id=None, details=''):
    """Log admin actions."""
    try:
        conn = get_shop_db()
        c = conn.cursor()
        c.execute('''INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                     VALUES (?, ?, ?, ?)''', (admin_id, action, target_user_id, details))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ============================================================
# CONTEXT PROCESSOR — inject cart_count into all templates
# ============================================================

@app.context_processor
def inject_cart_count():
    return dict(cart_count=get_cart_count())


# ============================================================
# L5 — Missing security headers (applied globally)
# ============================================================

@app.after_request
def add_headers(response):
    # Intentionally NOT setting security headers
    # No CSP, no X-Frame-Options, no X-Content-Type-Options
    # L6 — Clickjacking: No X-Frame-Options
    return response


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        conn = get_user_db()
        c = conn.cursor()

        try:
            # Try safe login first
            c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
            user = c.fetchone()

            if user:
                # E3 — Session fixation: not regenerating session
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                flash('Login successful!', 'success')

                # L1 — Open redirect
                next_url = request.form.get('next', '') or request.args.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect(url_for('index'))

            # A5 — SQL injection in login (vulnerable path)
            if not waf_check(username) and not waf_check(password):
                query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
                try:
                    c.execute(query)
                    user = c.fetchone()
                    if user:
                        session['user_id'] = user['id']
                        session['username'] = user['username']
                        session['role'] = user['role']
                        flash('Login successful!', 'success')
                        return redirect(url_for('index'))
                except sqlite3.Error:
                    pass
            else:
                flash('WAF Detection: Potential SQL injection detected!', 'danger')

            # E5 — Username enumeration: different error messages
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            if c.fetchone():
                flash('Incorrect password.', 'danger')
            else:
                flash('User not found.', 'danger')

        except Exception as e:
            flash(f'Login error occurred.', 'danger')
        finally:
            conn.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    # L5 — Logout via GET (CSRF logout attack possible)
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        credit_card_number = request.form.get('credit_card_number', '')
        credit_card_expiry = request.form.get('credit_card_expiry', '')
        credit_card_cvv = request.form.get('credit_card_cvv', '')

        conn = get_user_db()
        c = conn.cursor()

        c.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email))
        if c.fetchone():
            flash('Username or email already exists!', 'danger')
            conn.close()
            return render_template('register.html')

        try:
            # F2 — Plaintext password storage
            c.execute('''INSERT INTO users (username, email, password,
                        credit_card_number, credit_card_expiry, credit_card_cvv,
                        balance, secret_note, bio)
                        VALUES (?, ?, ?, ?, ?, ?, 1000.0, 'Welcome to the bookshop!', '')''',
                     (username, email, password,
                      credit_card_number, credit_card_expiry, credit_card_cvv))
            conn.commit()

            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = c.fetchone()

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            flash("Registration successful! Welcome to Khit's Bookshop!", 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('An error occurred during registration.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '')

        conn = get_user_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()

        if user:
            # E1 — Predictable reset token: MD5(username + static_secret)
            token = hashlib.md5(f"{username}{STATIC_RESET_SECRET}".encode()).hexdigest()
            expiry = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

            c.execute('UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?',
                     (token, expiry, user['id']))
            conn.commit()

            # E2 — No rate limiting on password reset
            flash(f'Password reset link: /reset_password/{token}', 'info')
        else:
            # E5 — Username enumeration
            flash('User not found.', 'danger')

        conn.close()

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_user_db()
    c = conn.cursor()

    c.execute('SELECT * FROM users WHERE reset_token = ?', (token,))
    user = c.fetchone()

    if not user:
        flash('Invalid or expired reset token.', 'danger')
        conn.close()
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        # No old password required, no password strength check
        c.execute('UPDATE users SET password = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?',
                 (new_password, user['id']))
        conn.commit()
        flash('Password reset successful!', 'success')
        conn.close()
        return redirect(url_for('login'))

    conn.close()
    return render_template('reset_password.html', token=token)


# ============================================================
# MAIN ROUTES (Index, Books, Book Details)
# ============================================================

@app.route('/')
def index():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM books')
    books = c.fetchall()
    conn.close()
    return render_template('index.html', books=books)


@app.route('/books')
def books():
    search = request.args.get('search', '')
    conn = get_shop_db()
    c = conn.cursor()

    if search:
        # A7 — SQL injection in search (vulnerable path alongside safe path)
        if not waf_check(search):
            try:
                query = f"SELECT * FROM books WHERE title LIKE '%{search}%' OR author LIKE '%{search}%'"
                c.execute(query)
                book_list = c.fetchall()
            except sqlite3.Error:
                book_list = []
                flash('Search error occurred.', 'danger')
        else:
            flash('WAF Detection: Suspicious input detected!', 'danger')
            book_list = []
    else:
        c.execute('SELECT * FROM books')
        book_list = c.fetchall()

    conn.close()
    # B1 — Reflected XSS: search value passed to template (rendered with |safe in template)
    return render_template('books.html', books=book_list, search=search)


@app.route('/book_details')
def book_details():
    book_id = request.args.get('id', '')

    if not book_id:
        flash('Book ID is required.', 'danger')
        return redirect(url_for('books'))

    conn = get_shop_db()
    c = conn.cursor()

    try:
        # WAF check — bypassable
        if waf_check(book_id):
            return "WAF blocked suspicious input", 403

        # Strip MySQL-style comments for SQLite compatibility
        cleaned_id = book_id.replace("/*!50000", "").replace("*/", "")

        # A1/A2 — Error-based & UNION-based SQL injection
        query = f"SELECT id, title, author, price, image, description, category, stock FROM books WHERE id = {cleaned_id}"

        try:
            c.execute(query)
            book = c.fetchone()
        except sqlite3.OperationalError as sql_err:
            # J3 — Verbose error messages
            conn.close()
            return f"SQL Error: {str(sql_err)}", 500

        if not book:
            conn.close()
            return "Book not found", 404

        # Get reviews for this book (with username from users.db)
        c.execute('SELECT * FROM reviews WHERE book_id = ? ORDER BY created_at DESC', (book['id'],))
        reviews_raw = c.fetchall()
        conn.close()

        # Fetch usernames from user DB
        uconn = get_user_db()
        uc = uconn.cursor()
        reviews = []
        for r in reviews_raw:
            uc.execute('SELECT username FROM users WHERE id = ?', (r['user_id'],))
            u = uc.fetchone()
            reviews.append({
                'id': r['id'],
                'user_id': r['user_id'],
                'book_id': r['book_id'],
                'rating': r['rating'],
                'comment': r['comment'],
                'created_at': r['created_at'],
                'username': u['username'] if u else 'Unknown'
            })
        uconn.close()

        return render_template('book_details.html', book=book, reviews=reviews)

    except Exception as e:
        return f"Error: {str(e)}", 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# PROFILE ROUTES
# ============================================================

@app.route('/profile')
@login_required
def profile():
    # D1 — IDOR: user_id parameter allows viewing other users' profiles
    user_id = request.args.get('user_id', session['user_id'])

    conn = get_user_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    # Get user's orders
    sconn = get_shop_db()
    sc = sconn.cursor()
    sc.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5', (user_id,))
    orders = sc.fetchall()
    sconn.close()

    return render_template('profile.html', user=user, orders=orders)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    conn = get_user_db()
    c = conn.cursor()

    if request.method == 'POST':
        bio = request.form.get('bio', '')
        email = request.form.get('email', '')

        # B4 — Stored XSS: bio stored without sanitization, rendered with |safe
        c.execute('UPDATE users SET bio = ?, email = ? WHERE id = ?',
                 (bio, email, session['user_id']))
        conn.commit()
        flash('Profile updated successfully!', 'success')
        conn.close()
        return redirect(url_for('profile'))

    c.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = c.fetchone()
    conn.close()
    return render_template('edit_profile.html', user=user)


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    # C1 — CSRF: No CSRF token validation
    new_password = request.form.get('new_password', '')

    if not new_password:
        flash('Password cannot be empty.', 'danger')
        return redirect(url_for('edit_profile'))

    conn = get_user_db()
    c = conn.cursor()
    c.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, session['user_id']))
    conn.commit()
    conn.close()

    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/change_email', methods=['POST'])
@login_required
def change_email():
    # C2 — CSRF: No CSRF token validation
    new_email = request.form.get('new_email', '')

    if not new_email:
        flash('Email cannot be empty.', 'danger')
        return redirect(url_for('edit_profile'))

    conn = get_user_db()
    c = conn.cursor()
    c.execute('UPDATE users SET email = ? WHERE id = ?', (new_email, session['user_id']))
    conn.commit()
    conn.close()

    flash('Email changed successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    # C5 — CSRF: No CSRF token validation
    conn = get_user_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_active = 0 WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()

    session.clear()
    flash('Account deleted.', 'info')
    return redirect(url_for('index'))


@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('edit_profile'))

    file = request.files['avatar']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('edit_profile'))

    # G1 — Unrestricted file upload: no extension/type validation
    # G2 — Path traversal: filename used directly
    # G3 — No MIME type validation
    filename = file.filename  # No secure_filename!
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # B5 — XSS via filename: original filename stored and rendered
    conn = get_user_db()
    c = conn.cursor()
    c.execute('UPDATE users SET profile_pic = ? WHERE id = ?', (filename, session['user_id']))
    conn.commit()

    # Log uploaded file
    sconn = get_shop_db()
    sc = sconn.cursor()
    sc.execute('INSERT INTO uploaded_files (user_id, filename, original_filename) VALUES (?, ?, ?)',
              (session['user_id'], filename, file.filename))
    sconn.commit()
    sconn.close()

    conn.close()
    flash('Avatar uploaded successfully!', 'success')
    return redirect(url_for('profile'))


# ============================================================
# SHOPPING ROUTES (Cart, Checkout, Orders)
# ============================================================

@app.route('/add_to_cart/<int:book_id>', methods=['POST'])
@login_required
def add_to_cart(book_id):
    # C3 — CSRF: No token validation
    # K1 — Negative quantity: accepts any quantity value
    quantity = request.form.get('quantity', 1, type=int)

    conn = get_shop_db()
    c = conn.cursor()

    c.execute('SELECT * FROM books WHERE id = ?', (book_id,))
    book = c.fetchone()
    if not book:
        conn.close()
        flash('Book not found.', 'danger')
        return redirect(url_for('index'))

    c.execute('SELECT * FROM cart WHERE user_id = ? AND book_id = ?',
              (session['user_id'], book_id))
    cart_item = c.fetchone()

    if cart_item:
        c.execute('UPDATE cart SET quantity = quantity + ? WHERE user_id = ? AND book_id = ?',
                 (quantity, session['user_id'], book_id))
    else:
        c.execute('INSERT INTO cart (user_id, book_id, quantity) VALUES (?, ?, ?)',
                 (session['user_id'], book_id, quantity))

    conn.commit()
    conn.close()

    flash('Book added to cart!', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/cart')
@login_required
def view_cart():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('''SELECT books.*, cart.quantity, cart.id as cart_id
                 FROM cart
                 JOIN books ON cart.book_id = books.id
                 WHERE cart.user_id = ?''', (session['user_id'],))
    cart_items = c.fetchall()
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    conn.close()
    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/remove_from_cart/<int:book_id>', methods=['POST'])
@login_required
def remove_from_cart(book_id):
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('DELETE FROM cart WHERE user_id = ? AND book_id = ?',
              (session['user_id'], book_id))
    conn.commit()
    conn.close()
    flash('Item removed from cart.', 'success')
    return redirect(url_for('view_cart'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('''SELECT books.*, cart.quantity
                 FROM cart
                 JOIN books ON cart.book_id = books.id
                 WHERE cart.user_id = ?''', (session['user_id'],))
    cart_items = c.fetchall()

    if not cart_items:
        conn.close()
        flash('Your cart is empty.', 'danger')
        return redirect(url_for('view_cart'))

    total = sum(item['price'] * item['quantity'] for item in cart_items)

    if request.method == 'POST':
        shipping_address = request.form.get('shipping_address', '')
        # K3 — Price manipulation: uses client-submitted total instead of server-calculated
        submitted_total = request.form.get('total', total, type=float)

        uconn = get_user_db()
        uc = uconn.cursor()
        uc.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],))
        user = uc.fetchone()

        # K5 — Insufficient balance bypass: uses submitted_total
        if user['balance'] < submitted_total:
            uconn.close()
            conn.close()
            flash('Insufficient balance!', 'danger')
            return redirect(url_for('checkout'))

        # Deduct balance
        uc.execute('UPDATE users SET balance = balance - ? WHERE id = ?',
                  (submitted_total, session['user_id']))
        uconn.commit()
        uconn.close()

        # Create order
        c.execute('''INSERT INTO orders (user_id, total, status, shipping_address)
                     VALUES (?, ?, 'confirmed', ?)''',
                 (session['user_id'], submitted_total, shipping_address))
        order_id = c.lastrowid

        # Create order items
        for item in cart_items:
            c.execute('''INSERT INTO order_items (order_id, book_id, quantity, price)
                        VALUES (?, ?, ?, ?)''',
                     (order_id, item['id'], item['quantity'], item['price']))

        # Clear cart
        c.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        conn.close()

        flash(f'Order #{order_id} placed successfully!', 'success')
        return redirect(url_for('order_detail', order_id=order_id))

    conn.close()

    # Get user balance
    uconn = get_user_db()
    uc = uconn.cursor()
    uc.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = uc.fetchone()
    uconn.close()

    return render_template('checkout.html', cart_items=cart_items, total=total, user=user)


@app.route('/apply_coupon', methods=['POST'])
@login_required
def apply_coupon():
    code = request.form.get('code', '')

    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM coupons WHERE code = ? AND is_active = 1', (code,))
    coupon = c.fetchone()

    if coupon:
        # K4 — Coupon reuse: max_uses not properly enforced
        session['coupon_discount'] = coupon['discount_percent']
        session['coupon_code'] = code
        flash(f'Coupon applied! {coupon["discount_percent"]}% discount.', 'success')
    else:
        flash('Invalid or expired coupon code.', 'danger')

    conn.close()
    return redirect(url_for('checkout'))


@app.route('/order_history')
@login_required
def order_history():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC',
              (session['user_id'],))
    orders = c.fetchall()
    conn.close()
    return render_template('order_history.html', orders=orders)


@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    conn = get_shop_db()
    c = conn.cursor()

    # D2 — IDOR: No check if order belongs to current user
    c.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = c.fetchone()

    if not order:
        conn.close()
        flash('Order not found.', 'danger')
        return redirect(url_for('order_history'))

    c.execute('''SELECT order_items.*, books.title, books.author, books.image
                 FROM order_items
                 JOIN books ON order_items.book_id = books.id
                 WHERE order_items.order_id = ?''', (order_id,))
    items = c.fetchall()
    conn.close()

    return render_template('order_detail.html', order=order, items=items)


@app.route('/download_receipt/<int:order_id>')
@login_required
def download_receipt(order_id):
    # D3 — IDOR: No ownership check
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = c.fetchone()

    if not order:
        conn.close()
        return "Order not found", 404

    c.execute('''SELECT order_items.*, books.title
                 FROM order_items
                 JOIN books ON order_items.book_id = books.id
                 WHERE order_items.order_id = ?''', (order_id,))
    items = c.fetchall()
    conn.close()

    # Generate text receipt
    receipt = f"=== RECEIPT — Order #{order_id} ===\n"
    receipt += f"Date: {order['created_at']}\n"
    receipt += f"Status: {order['status']}\n"
    receipt += f"Shipping: {order['shipping_address']}\n\n"
    receipt += "Items:\n"
    for item in items:
        receipt += f"  - {item['title']} x{item['quantity']} @ ${item['price']:.2f}\n"
    receipt += f"\nTotal: ${order['total']:.2f}\n"

    response = make_response(receipt)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Content-Disposition'] = f'attachment; filename=receipt_{order_id}.txt'
    return response


# ============================================================
# REVIEW ROUTES
# ============================================================

@app.route('/review/<int:book_id>', methods=['POST'])
@login_required
def add_review(book_id):
    rating = request.form.get('rating', 5, type=int)
    comment = request.form.get('comment', '')

    # B2 — Stored XSS: comment stored without sanitization
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('''INSERT INTO reviews (user_id, book_id, rating, comment)
                VALUES (?, ?, ?, ?)''',
             (session['user_id'], book_id, rating, comment))
    conn.commit()
    conn.close()

    flash('Review posted!', 'success')
    return redirect(url_for('book_details', id=book_id))


@app.route('/edit_review/<int:review_id>', methods=['POST'])
@login_required
def edit_review(review_id):
    # D4 — IDOR: No ownership check on review
    comment = request.form.get('comment', '')
    rating = request.form.get('rating', 5, type=int)

    conn = get_shop_db()
    c = conn.cursor()
    c.execute('UPDATE reviews SET comment = ?, rating = ? WHERE id = ?',
              (comment, rating, review_id))
    conn.commit()

    c.execute('SELECT book_id FROM reviews WHERE id = ?', (review_id,))
    review = c.fetchone()
    conn.close()

    flash('Review updated.', 'success')
    if review:
        return redirect(url_for('book_details', id=review['book_id']))
    return redirect(url_for('books'))


@app.route('/delete_review/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    # D4 — IDOR: No ownership check
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT book_id FROM reviews WHERE id = ?', (review_id,))
    review = c.fetchone()
    c.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
    conn.commit()
    conn.close()

    flash('Review deleted.', 'success')
    if review:
        return redirect(url_for('book_details', id=review['book_id']))
    return redirect(url_for('books'))


# ============================================================
# BALANCE TRANSFER
# ============================================================

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer_balance():
    if request.method == 'POST':
        # C4 — CSRF: No token validation for money transfer
        recipient_username = request.form.get('recipient', '')
        amount = request.form.get('amount', 0, type=float)

        if amount <= 0:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('transfer_balance'))

        conn = get_user_db()
        c = conn.cursor()

        # Check sender balance
        c.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
        sender = c.fetchone()

        if sender['balance'] < amount:
            flash('Insufficient balance.', 'danger')
            conn.close()
            return redirect(url_for('transfer_balance'))

        # Find recipient
        c.execute('SELECT * FROM users WHERE username = ?', (recipient_username,))
        recipient = c.fetchone()

        if not recipient:
            flash('Recipient not found.', 'danger')
            conn.close()
            return redirect(url_for('transfer_balance'))

        if recipient['id'] == session['user_id']:
            flash('Cannot transfer to yourself.', 'danger')
            conn.close()
            return redirect(url_for('transfer_balance'))

        # K2 — Race condition: no locking, vulnerable to double-spend
        c.execute('UPDATE users SET balance = balance - ? WHERE id = ?',
                 (amount, session['user_id']))
        c.execute('UPDATE users SET balance = balance + ? WHERE id = ?',
                 (amount, recipient['id']))
        conn.commit()
        conn.close()

        flash(f'${amount:.2f} transferred to {recipient_username}!', 'success')
        return redirect(url_for('profile'))

    # GET — show transfer form
    conn = get_user_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = c.fetchone()
    conn.close()

    return render_template('transfer.html', user=user)


# ============================================================
# SUPPORT TICKET ROUTES
# ============================================================

@app.route('/support')
@login_required
def support_tickets():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC',
              (session['user_id'],))
    tickets = c.fetchall()
    conn.close()
    return render_template('support_tickets.html', tickets=tickets)


@app.route('/support/new', methods=['GET', 'POST'])
@login_required
def new_ticket():
    if request.method == 'POST':
        subject = request.form.get('subject', '')
        message = request.form.get('message', '')

        conn = get_shop_db()
        c = conn.cursor()
        c.execute('''INSERT INTO support_tickets (user_id, subject, message)
                    VALUES (?, ?, ?)''',
                 (session['user_id'], subject, message))
        conn.commit()
        conn.close()

        flash('Support ticket submitted!', 'success')
        return redirect(url_for('support_tickets'))

    return render_template('new_ticket.html')


# ============================================================
# API ROUTES (various vulnerabilities)
# ============================================================

@app.route('/api/check_username')
def api_check_username():
    """A3 — Blind Boolean SQL injection."""
    username = request.args.get('username', '')

    conn = get_user_db()
    c = conn.cursor()

    try:
        # Vulnerable to blind boolean SQLi
        query = f"SELECT * FROM users WHERE username = '{username}'"
        c.execute(query)
        user = c.fetchone()
        conn.close()

        if user:
            return jsonify({'exists': True, 'message': 'Username is taken'})
        else:
            return jsonify({'exists': False, 'message': 'Username is available'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/check_coupon')
def api_check_coupon():
    """A4 — Time-based Blind SQL injection."""
    code = request.args.get('code', '')

    conn = get_shop_db()
    c = conn.cursor()

    try:
        # Vulnerable to time-based blind SQLi (SQLite doesn't have SLEEP but
        # we simulate with a heavy query or use CASE WHEN with randomblob)
        query = f"SELECT * FROM coupons WHERE code = '{code}'"
        c.execute(query)
        coupon = c.fetchone()
        conn.close()

        if coupon:
            return jsonify({'valid': True, 'discount': coupon['discount_percent']})
        else:
            return jsonify({'valid': False})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/<int:user_id>/card')
def api_user_card(user_id):
    """D5 — IDOR: API endpoint exposing credit card info without auth check."""
    conn = get_user_db()
    c = conn.cursor()
    c.execute('SELECT username, credit_card_number, credit_card_expiry FROM users WHERE id = ?',
              (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        return jsonify({
            'username': user['username'],
            'card_number': user['credit_card_number'],
            'card_expiry': user['credit_card_expiry']
        })
    return jsonify({'error': 'User not found'}), 404


@app.route('/api/update_role', methods=['POST'])
def api_update_role():
    """F5 — Privilege escalation: hidden endpoint to change user role."""
    user_id = request.form.get('user_id', '')
    new_role = request.form.get('role', 'user')

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400

    conn = get_user_db()
    c = conn.cursor()
    c.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'Role updated to {new_role}'})


@app.route('/api/import_books', methods=['POST'])
def api_import_books():
    """L3 — XXE: XML External Entity injection via book import."""
    if 'xml_file' not in request.files:
        xml_data = request.data
    else:
        xml_data = request.files['xml_file'].read()

    if not xml_data:
        return jsonify({'error': 'No XML data provided'}), 400

    try:
        # XXE vulnerable: parsing XML without disabling external entities
        root = ET.fromstring(xml_data)
        books_added = 0

        conn = get_shop_db()
        c = conn.cursor()

        for book_elem in root.findall('book'):
            title = book_elem.findtext('title', '')
            author = book_elem.findtext('author', '')
            price = float(book_elem.findtext('price', '0'))
            description = book_elem.findtext('description', '')
            category = book_elem.findtext('category', 'General')

            c.execute('''INSERT INTO books (title, author, price, description, category)
                        VALUES (?, ?, ?, ?, ?)''',
                     (title, author, price, description, category))
            books_added += 1

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'books_added': books_added})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load_cart', methods=['POST'])
def api_load_cart():
    """L4 — Insecure deserialization: pickle-based cart restore."""
    cart_data = request.form.get('cart_data', '')

    if not cart_data:
        return jsonify({'error': 'No cart data provided'}), 400

    try:
        # Insecure deserialization — pickle.loads on user input
        decoded = base64.b64decode(cart_data)
        cart = pickle.loads(decoded)
        return jsonify({'success': True, 'cart': str(cart)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# ADMIN ROUTES
# ============================================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    # Get stats
    uconn = get_user_db()
    uc = uconn.cursor()
    uc.execute('SELECT COUNT(*) as cnt FROM users')
    total_users = uc.fetchone()['cnt']
    uc.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 5')
    recent_users = uc.fetchall()
    uconn.close()

    sconn = get_shop_db()
    sc = sconn.cursor()
    sc.execute('SELECT COUNT(*) as cnt FROM books')
    total_books = sc.fetchone()['cnt']
    sc.execute('SELECT COUNT(*) as cnt FROM orders')
    total_orders = sc.fetchone()['cnt']
    sc.execute('SELECT COALESCE(SUM(total), 0) as rev FROM orders')
    total_revenue = sc.fetchone()['rev']
    sc.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 5')
    recent_orders = sc.fetchall()

    # Get open tickets count
    sc.execute("SELECT COUNT(*) as cnt FROM support_tickets WHERE status = 'open'")
    open_tickets = sc.fetchone()['cnt']
    sconn.close()

    stats = {
        'total_users': total_users,
        'total_books': total_books,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'open_tickets': open_tickets,
    }

    return render_template('admin_dashboard.html', stats=stats,
                          recent_orders=recent_orders, recent_users=recent_users)


@app.route('/admin/users')
@admin_required
def admin_users():
    """F6 — Forced browsing: URL directly accessible if role check bypassed."""
    conn = get_user_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY id')
    users = c.fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)


@app.route('/admin/logs')
@admin_required
def admin_logs():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT 100')
    logs = c.fetchall()
    conn.close()

    # Enrich with usernames
    uconn = get_user_db()
    uc = uconn.cursor()
    enriched_logs = []
    for log in logs:
        uc.execute('SELECT username FROM users WHERE id = ?', (log['admin_id'],))
        admin = uc.fetchone()
        enriched_logs.append({
            'id': log['id'],
            'admin_username': admin['username'] if admin else 'Unknown',
            'action': log['action'],
            'details': log['details'],
            'created_at': log['created_at'],
        })
    uconn.close()

    return render_template('admin_logs.html', logs=enriched_logs)


@app.route('/admin/tickets')
@admin_required
def admin_tickets():
    conn = get_shop_db()
    c = conn.cursor()
    c.execute('SELECT * FROM support_tickets ORDER BY created_at DESC')
    tickets = c.fetchall()
    conn.close()

    # Enrich with usernames
    uconn = get_user_db()
    uc = uconn.cursor()
    enriched = []
    for t in tickets:
        uc.execute('SELECT username FROM users WHERE id = ?', (t['user_id'],))
        u = uc.fetchone()
        enriched.append({**dict(t), 'username': u['username'] if u else 'Unknown'})
    uconn.close()

    return render_template('admin_tickets.html', tickets=enriched)


@app.route('/admin/ticket/<int:ticket_id>/reply', methods=['POST'])
@admin_required
def admin_reply_ticket(ticket_id):
    reply = request.form.get('reply', '')
    conn = get_shop_db()
    c = conn.cursor()
    # A6 — Second-order SQLi potential: admin_reply stored, could be reflected elsewhere
    c.execute("UPDATE support_tickets SET admin_reply = ?, status = 'closed' WHERE id = ?",
              (reply, ticket_id))
    conn.commit()
    conn.close()

    log_admin_action(session['user_id'], 'reply_ticket', details=f'Ticket #{ticket_id}')
    flash('Reply sent.', 'success')
    return redirect(url_for('admin_tickets'))


@app.route('/admin/ping', methods=['GET', 'POST'])
@admin_required
def admin_ping():
    result = None
    if request.method == 'POST':
        host = request.form.get('host', '')

        # H1 — OS Command Injection
        try:
            output = subprocess.check_output(
                f"ping -c 2 {host}",
                shell=True,
                stderr=subprocess.STDOUT,
                timeout=10
            )
            result = output.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            result = "Command timed out"
        except subprocess.CalledProcessError as e:
            result = e.output.decode('utf-8', errors='replace')
        except Exception as e:
            result = f"Error: {str(e)}"

        log_admin_action(session['user_id'], 'ping', details=f'Host: {host}')

    return render_template('admin_ping.html', result=result)


@app.route('/admin/preview_url', methods=['GET', 'POST'])
@admin_required
def admin_preview_url():
    content = None
    if request.method == 'POST':
        url = request.form.get('url', '')

        # I1 — SSRF: No URL validation, fetches arbitrary URLs
        try:
            response = urlopen(url, timeout=5)
            content = response.read().decode('utf-8', errors='replace')[:5000]
        except Exception as e:
            content = f"Error fetching URL: {str(e)}"

        log_admin_action(session['user_id'], 'preview_url', details=f'URL: {url}')

    return render_template('admin_preview.html', content=content)


@app.route('/admin/export')
@admin_required
def admin_export():
    fmt = request.args.get('format', 'csv')

    # H2 — Command injection in export
    try:
        conn = get_shop_db()
        c = conn.cursor()
        c.execute('SELECT * FROM books')
        books = c.fetchall()
        conn.close()

        if fmt == 'csv':
            output = "id,title,author,price,category,stock\n"
            for b in books:
                output += f"{b['id']},{b['title']},{b['author']},{b['price']},{b['category']},{b['stock']}\n"

            response = make_response(output)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=books.csv'
            return response
        else:
            # Vulnerable: format parameter injected into shell command
            cmd = f"echo 'Export format: {fmt}' && date"
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=5)
            return result.decode('utf-8', errors='replace')
    except Exception as e:
        return f"Export error: {str(e)}", 500


@app.route('/admin/reset_data', methods=['POST'])
@admin_required
def admin_reset_data():
    """Reset shop data (bookshop.db) while preserving users (users.db)."""
    try:
        conn = get_shop_db()
        c = conn.cursor()

        # Drop all shop tables
        tables = ['books', 'cart', 'orders', 'order_items', 'reviews',
                   'coupons', 'support_tickets', 'uploaded_files', 'admin_logs']
        for table in tables:
            c.execute(f'DROP TABLE IF EXISTS {table}')

        conn.commit()
        conn.close()

        # Reinitialize
        init_shop_db()

        log_admin_action(session['user_id'], 'reset_data', details='Full shop data reset')
        flash('Shop data has been reset. User accounts are preserved.', 'success')
    except Exception as e:
        flash(f'Reset error: {str(e)}', 'danger')

    return redirect(url_for('admin_dashboard'))


# ============================================================
# MISCELLANEOUS VULNERABILITY ROUTES
# ============================================================

@app.route('/redirect')
def open_redirect():
    """L1 — Open redirect: no URL validation."""
    url = request.args.get('url', '/')
    return redirect(url)


@app.route('/set_language')
def set_language():
    """L2 — HTTP header injection."""
    lang = request.args.get('lang', 'en')
    response = make_response(redirect(url_for('index')))
    # Header injection: lang value injected into Set-Cookie header
    response.headers['Set-Cookie'] = f'language={lang}; Path=/'
    return response


@app.route('/debug_db')
def debug_db():
    """J2 — Debug endpoint exposing sensitive data."""
    try:
        conn = get_user_db()
        c = conn.cursor()
        c.execute('SELECT username, email, password, secret_note, credit_card_number FROM users')
        users = c.fetchall()
        conn.close()

        output = "<h2>Debug Database Dump</h2><pre>"
        for u in users:
            output += f"User: {u['username']} | Email: {u['email']} | Pass: {u['password']} | Card: {u['credit_card_number']} | Note: {u['secret_note']}\n"
        output += "</pre>"

        return output
    except Exception as e:
        return f"Debug error: {str(e)}", 500


@app.route('/robots.txt')
def robots():
    """J4 — Information leakage via robots.txt."""
    content = """User-agent: *
Disallow: /admin
Disallow: /debug_db
Disallow: /api/
Disallow: /static/uploads/
Disallow: /admin/ping
Disallow: /admin/preview_url
Disallow: /.git/
"""
    return Response(content, mimetype='text/plain')


# J6 — Directory listing for uploads
@app.route('/uploads')
def list_uploads():
    """J6 — Directory listing of uploaded files."""
    try:
        files = os.listdir(UPLOAD_FOLDER)
        output = "<h2>Uploaded Files</h2><ul>"
        for f in files:
            output += f'<li><a href="/static/uploads/{f}">{f}</a></li>'
        output += "</ul>"
        return output
    except Exception as e:
        return f"Error: {str(e)}", 500


# J7 — Backup file exposure
@app.route('/app.py.bak')
def backup_file():
    """J7 — Backup file exposure."""
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py'),
                     mimetype='text/plain')


# B3 — DOM-based XSS: served via a specific page route
# (The actual vulnerability is in the JavaScript in base.html)


# ============================================================
# TEMPLATE CONTEXT — DOM XSS payload
# ============================================================

@app.route('/search')
def search_page():
    """B1 — Reflected XSS via search page."""
    q = request.args.get('q', '')
    conn = get_shop_db()
    c = conn.cursor()

    if q:
        c.execute('SELECT * FROM books WHERE title LIKE ? OR author LIKE ?',
                 (f'%{q}%', f'%{q}%'))
    else:
        c.execute('SELECT * FROM books')

    results = c.fetchall()
    conn.close()

    # B1 — search query passed to template, rendered with |safe
    return render_template('search.html', query=q, results=results)


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error_code=404, error_message='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error_code=500, error_message='Internal server error'), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    init_user_db()
    init_shop_db()
    app.run(debug=True, host='0.0.0.0', port=5005)
