from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from datetime import timezone
import json
import base64
import io
import csv
from functools import wraps
import sqlite3
import os
import psycopg2
import psycopg2.extras
import traceback

app = Flask(__name__)
CORS(app, origins=['https://raven-png.github.io'])

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'schoolhub-secret-key-2026')
app.config['JWT_EXPIRATION_HOURS'] = 24
USE_POSTGRES = os.environ.get('DATABASE_URL') is not None

# ============ DATABASE CONNECTION ============
def get_db():
    if USE_POSTGRES:
        return psycopg2.connect(os.environ.get('DATABASE_URL'))
    else:
        conn = sqlite3.connect('schoolhub.db')
        conn.row_factory = sqlite3.Row
        return conn

def get_cursor(conn):
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

def safe_fetchone(result):
    if result is None:
        return None
    if isinstance(result, dict):
        return result
    return result

# ============ DATABASE INITIALIZATION ============
def init_db():
    conn = get_db()
    if USE_POSTGRES:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        c = conn.cursor()

    # Students table
    if USE_POSTGRES:
        c.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL,
                password_hash TEXT, class TEXT NOT NULL, combination TEXT,
                is_candidate BOOLEAN DEFAULT FALSE, subjects TEXT DEFAULT '[]',
                subsidiaries TEXT DEFAULT '[]', image TEXT, join_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY, student_id INTEGER, year INTEGER, term INTEGER,
                phase TEXT, marks TEXT, total_marks INTEGER, average REAL,
                points INTEGER, position INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY, student_id INTEGER, filename TEXT,
                file_data TEXT, upload_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id SERIAL PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                target TEXT DEFAULT 'all', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY, student_id INTEGER, message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # NEW TABLES FOR MARKS & REVIEWS
        c.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, paper1_max INTEGER DEFAULT 50,
                paper2_max INTEGER DEFAULT 50, class TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS teacher_subjects (
                id SERIAL PRIMARY KEY, teacher_email TEXT NOT NULL, subject_id INTEGER,
                class TEXT NOT NULL, assigned_by TEXT, assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS marks (
                id SERIAL PRIMARY KEY, student_id INTEGER, subject_id INTEGER,
                paper1_score INTEGER, paper2_score INTEGER, total INTEGER,
                grade TEXT, exam_type TEXT, term INTEGER, year INTEGER,
                entered_by TEXT, entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS review_requests (
                id SERIAL PRIMARY KEY, student_id INTEGER, subject_id INTEGER,
                current_marks INTEGER, requested_marks INTEGER, reason TEXT,
                evidence TEXT, status TEXT DEFAULT 'pending',
                class_teacher_response TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY, student_id INTEGER, class TEXT,
                subject TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id SERIAL PRIMARY KEY, user_id TEXT, action TEXT,
                details TEXT, ip_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS terms (
                id SERIAL PRIMARY KEY, year INTEGER, term INTEGER,
                is_active BOOLEAN DEFAULT FALSE, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            )
        ''')
    else:
        c.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL,
                password_hash TEXT, class TEXT NOT NULL, combination TEXT,
                is_candidate BOOLEAN DEFAULT 0, subjects TEXT DEFAULT '[]',
                subsidiaries TEXT DEFAULT '[]', image TEXT, join_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, year INTEGER,
                term INTEGER, phase TEXT, marks TEXT, total_marks INTEGER, average REAL,
                points INTEGER, position INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, filename TEXT,
                file_data TEXT, upload_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL,
                target TEXT DEFAULT 'all', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                paper1_max INTEGER DEFAULT 50, paper2_max INTEGER DEFAULT 50,
                class TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS teacher_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_email TEXT NOT NULL,
                subject_id INTEGER, class TEXT NOT NULL, assigned_by TEXT,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, subject_id INTEGER,
                paper1_score INTEGER, paper2_score INTEGER, total INTEGER,
                grade TEXT, exam_type TEXT, term INTEGER, year INTEGER,
                entered_by TEXT, entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS review_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, subject_id INTEGER,
                current_marks INTEGER, requested_marks INTEGER, reason TEXT,
                evidence TEXT, status TEXT DEFAULT 'pending',
                class_teacher_response TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, class TEXT,
                subject TEXT, message TEXT, is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, action TEXT,
                details TEXT, ip_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER, term INTEGER,
                is_active BOOLEAN DEFAULT FALSE, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            )
        ''')

    # Create default admin
    default_email = os.environ.get('ADMIN_EMAIL', 'admin@school.com')
    default_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')

    if USE_POSTGRES:
        c.execute("SELECT * FROM admins WHERE email = %s", (default_email,))
    else:
        c.execute("SELECT * FROM admins WHERE email = ?", (default_email,))

    if not safe_fetchone(c.fetchone()):
        admin_hash = generate_password_hash(default_pass, method='pbkdf2:sha256', salt_length=16)
        if USE_POSTGRES:
            c.execute("INSERT INTO admins (email, password_hash) VALUES (%s, %s)", (default_email, admin_hash))
        else:
            c.execute("INSERT INTO admins (email, password_hash) VALUES (?, ?)", (default_email, admin_hash))
        print(f"✅ Default admin: {default_email} / {default_pass}")

    # Create default active term
    current_year = datetime.datetime.now().year
    if USE_POSTGRES:
        c.execute("SELECT * FROM terms WHERE is_active = %s", (True,))
    else:
        c.execute("SELECT * FROM terms WHERE is_active = ?", (True,))
    if not safe_fetchone(c.fetchone()):
        if USE_POSTGRES:
            c.execute("INSERT INTO terms (year, term, is_active) VALUES (%s, %s, %s)", (current_year, 1, True))
        else:
            c.execute("INSERT INTO terms (year, term, is_active) VALUES (?, ?, ?)", (current_year, 1, True))
        print("✅ Default term created")

    conn.commit()
    conn.close()

init_db()

# ============ HELPER FUNCTIONS ============
def cors_response(data, status_code=200):
    response = make_response(jsonify(data), status_code)
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return cors_response({'success': False, 'error': 'Token malformed'}, 401)
        if not token:
            return cors_response({'success': False, 'error': 'Token missing'}, 401)
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            request.current_user = data
        except jwt.ExpiredSignatureError:
            return cors_response({'success': False, 'error': 'Token expired'}, 401)
        except jwt.InvalidTokenError:
            return cors_response({'success': False, 'error': 'Invalid token'}, 401)
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.current_user.get('role') != 'admin':
            return cors_response({'success': False, 'error': 'Admin required'}, 403)
        return f(*args, **kwargs)
    return decorated

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        role = request.current_user.get('role')
        if role not in ['admin', 'teacher', 'classteacher']:
            return cors_response({'success': False, 'error': 'Teacher access required'}, 403)
        return f(*args, **kwargs)
    return decorated
# ============ AUTHENTICATION ENDPOINTS ============

@app.route('/auth/student/login', methods=['POST', 'OPTIONS'])
def student_login():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    try:
        data = request.get_json()
        if not data:
            return cors_response({'success': False, 'error': 'No data'}, 400)

        phone = data.get('phone', '').strip()
        password = data.get('password', '')

        if not phone:
            return cors_response({'success': False, 'error': 'Phone required'}, 400)

        conn = get_db()
        c = get_cursor(conn)

        if USE_POSTGRES:
            c.execute("SELECT * FROM students WHERE phone = %s", (phone,))
        else:
            c.execute("SELECT * FROM students WHERE phone = ?", (phone,))

        student = safe_fetchone(c.fetchone())

        if not student:
            conn.close()
            return cors_response({'success': False, 'error': 'Phone not registered'}, 404)

        # First time login - create password
        if not student.get('password_hash'):
            if not password or len(password) < 4:
                conn.close()
                return cors_response({
                    'success': False,
                    'error': 'Create password (min 4 chars) and login again',
                    'require_password_creation': True
                }, 200)

            pw_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
            if USE_POSTGRES:
                c.execute("UPDATE students SET password_hash = %s WHERE id = %s", (pw_hash, student['id']))
            else:
                c.execute("UPDATE students SET password_hash = ? WHERE id = ?", (pw_hash, student['id']))

            conn.commit()
            conn.close()
            return cors_response({
                'success': True,
                'message': 'Password created! Login again.',
                'password_created': True
            })

        # Normal login
        if not check_password_hash(student['password_hash'], password):
            conn.close()
            return cors_response({'success': False, 'error': 'Wrong password'}, 401)

        token = jwt.encode({
            'user_id': student['id'],
            'role': 'student',
            'exp': datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        subjects = json.loads(student.get('subjects', '[]')) if student.get('subjects') else []
        subsidiaries = json.loads(student.get('subsidiaries', '[]')) if student.get('subsidiaries') else []

        conn.close()

        return cors_response({
            'success': True,
            'token': token,
            'user': {
                'id': student['id'], 'name': student['name'],
                'phone': student['phone'], 'class': student['class'],
                'combination': student.get('combination') or '',
                'is_candidate': bool(student.get('is_candidate', False)),
                'subjects': subjects, 'subsidiaries': subsidiaries,
                'image': student.get('image') or '',
                'joinDate': student.get('join_date') or datetime.date.today().isoformat(),
                'role': 'student'
            }
        })

    except Exception as e:
        print(f"STUDENT LOGIN ERROR: {e}")
        traceback.print_exc()
        return cors_response({'success': False, 'error': str(e)}, 500)


@app.route('/auth/admin/login', methods=['POST', 'OPTIONS'])
def admin_login():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    try:
        data = request.get_json()
        if not data:
            return cors_response({'success': False, 'error': 'No data'}, 400)

        email = data.get('email', '').strip().lower()
        if not email:
            email = data.get('username', '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            return cors_response({'success': False, 'error': 'Email and password required'}, 400)

        conn = get_db()
        c = get_cursor(conn)

        if USE_POSTGRES:
            c.execute("SELECT * FROM admins WHERE email = %s", (email,))
        else:
            c.execute("SELECT * FROM admins WHERE email = ?", (email,))

        admin = safe_fetchone(c.fetchone())
        conn.close()

        if not admin:
            return cors_response({'success': False, 'error': 'Admin not found'}, 404)

        if not check_password_hash(admin['password_hash'], password):
            return cors_response({'success': False, 'error': 'Wrong password'}, 401)

        token = jwt.encode({
            'user_id': admin['id'],
            'role': 'admin',
            'exp': datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return cors_response({
            'success': True,
            'token': token,
            'user': {'id': admin['id'], 'email': admin['email'], 'role': 'admin'}
        })

    except Exception as e:
        print(f"ADMIN LOGIN ERROR: {e}")
        traceback.print_exc()
        return cors_response({'success': False, 'error': str(e)}, 500)


@app.route('/auth/reset-password', methods=['POST', 'OPTIONS'])
def reset_password():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    data = request.get_json()
    phone = data.get('phone', '').strip()
    new_password = data.get('new_password', '')

    if not phone or not new_password or len(new_password) < 4:
        return cors_response({'success': False, 'error': 'Phone and password required'}, 400)

    pw_hash = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=16)
    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute("UPDATE students SET password_hash = %s WHERE phone = %s", (pw_hash, phone))
    else:
        c.execute("UPDATE students SET password_hash = ? WHERE phone = ?", (pw_hash, phone))

    if c.rowcount == 0:
        conn.close()
        return cors_response({'success': False, 'error': 'Phone not found'}, 404)

    conn.commit()
    conn.close()
    return cors_response({'success': True, 'message': 'Password reset'})


@app.route('/auth/verify', methods=['GET', 'OPTIONS'])
@token_required
def verify_token():
    return cors_response({
        'success': True,
        'user_id': request.current_user['user_id'],
        'role': request.current_user['role']
    })
# ============ STUDENT MANAGEMENT ============

@app.route('/students', methods=['GET', 'OPTIONS'])
@token_required
@admin_required
def get_students():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    try:
        class_filter = request.args.get('class', 'all')
        search = request.args.get('search', '').lower()

        conn = get_db()
        c = get_cursor(conn)
        params = []

        if USE_POSTGRES:
            query = "SELECT * FROM students WHERE 1=1"
            if class_filter != 'all':
                query += " AND class = %s"
                params.append(class_filter)
            if search:
                query += " AND (LOWER(name) LIKE %s OR phone LIKE %s)"
                params.extend([f'%{search}%', f'%{search}%'])
        else:
            query = "SELECT * FROM students WHERE 1=1"
            if class_filter != 'all':
                query += " AND class = ?"
                params.append(class_filter)
            if search:
                query += " AND (LOWER(name) LIKE ? OR phone LIKE ?)"
                params.extend([f'%{search}%', f'%{search}%'])

        query += " ORDER BY id DESC"
        c.execute(query, params)
        students = c.fetchall()
        conn.close()

        result = []
        for s in students:
            student = safe_fetchone(s)
            # FIXED: Using .get() to avoid KeyError
            subjects = json.loads(student.get('subjects', '[]')) if student.get('subjects') else []
            subsidiaries = json.loads(student.get('subsidiaries', '[]')) if student.get('subsidiaries') else []
            result.append({
                'id': student.get('id'), 'name': student.get('name'), 'phone': student.get('phone'),
                'class': student.get('class'), 'combination': student.get('combination') or '',
                'isCandidate': bool(student.get('is_candidate', False)),
                'subjects': subjects, 'subsidiaries': subsidiaries,
                'image': student.get('image') or '',
                'joinDate': student.get('join_date') or datetime.date.today().isoformat()
            })

        return cors_response({'success': True, 'data': result})

    except Exception as e:
        print(f"ERROR in get_students: {e}")
        traceback.print_exc()
        return cors_response({'success': False, 'error': str(e)}, 500)


@app.route('/students', methods=['POST', 'OPTIONS'])
@token_required
@admin_required
def create_student():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    data = request.get_json()
    required = ['name', 'phone', 'class']
    for field in required:
        if not data.get(field):
            return cors_response({'success': False, 'error': f'{field} required'}, 400)

    conn = get_db()
    c = get_cursor(conn)

    # Get new ID
    try:
        if USE_POSTGRES:
            c.execute("SELECT COALESCE(MAX(id), 1000) + 1 as new_id FROM students")
            result = c.fetchone()
            if isinstance(result, dict):
                new_id = result.get('new_id', 1001)
            else:
                new_id = result[0] if result else 1001
        else:
            c.execute("SELECT COALESCE(MAX(id), 1000) + 1 FROM students")
            new_id = c.fetchone()[0]
    except Exception as e:
        new_id = 1001

    # Check duplicate phone
    if USE_POSTGRES:
        c.execute("SELECT id FROM students WHERE phone = %s", (data['phone'],))
    else:
        c.execute("SELECT id FROM students WHERE phone = ?", (data['phone'],))

    if safe_fetchone(c.fetchone()):
        conn.close()
        return cors_response({'success': False, 'error': 'Phone already exists'}, 409)

    subjects_json = json.dumps(data.get('subjects', []))
    subsidiaries_json = json.dumps(data.get('subsidiaries', []))
    is_candidate = data.get('is_candidate', data['class'] in ['Senior 4', 'Senior 6'])

    try:
        if USE_POSTGRES:
            c.execute('''
                INSERT INTO students (id, name, phone, class, combination, is_candidate, subjects, subsidiaries, join_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (new_id, data['name'], data['phone'], data['class'],
                  data.get('combination', ''), is_candidate,
                  subjects_json, subsidiaries_json, datetime.date.today().isoformat()))
        else:
            c.execute('''
                INSERT INTO students (id, name, phone, class, combination, is_candidate, subjects, subsidiaries, join_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (new_id, data['name'], data['phone'], data['class'],
                  data.get('combination', ''), is_candidate,
                  subjects_json, subsidiaries_json, datetime.date.today().isoformat()))

        conn.commit()
        conn.close()

        return cors_response({
            'success': True,
            'message': 'Student created',
            'student_id': new_id
        }, 201)
    except Exception as e:
        conn.close()
        print(f"CREATE STUDENT ERROR: {e}")
        traceback.print_exc()
        return cors_response({'success': False, 'error': str(e)}, 500)


@app.route('/students/<int:student_id>', methods=['PUT', 'DELETE', 'OPTIONS'])
@token_required
@admin_required
def manage_student(student_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute("SELECT id FROM students WHERE id = %s", (student_id,))
    else:
        c.execute("SELECT id FROM students WHERE id = ?", (student_id,))

    if not safe_fetchone(c.fetchone()):
        conn.close()
        return cors_response({'success': False, 'error': 'Student not found'}, 404)

    if request.method == 'DELETE':
        if USE_POSTGRES:
            c.execute("DELETE FROM students WHERE id = %s", (student_id,))
        else:
            c.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        conn.close()
        return cors_response({'success': True, 'message': 'Student deleted'})

    # PUT - Update
    data = request.get_json()
    updates = []
    params = []

    fields = ['name', 'phone', 'class', 'combination', 'image']
    for field in fields:
        if field in data:
            updates.append(f"{field} = %s" if USE_POSTGRES else f"{field} = ?")
            params.append(data[field])

    if 'subjects' in data:
        updates.append("subjects = %s" if USE_POSTGRES else "subjects = ?")
        params.append(json.dumps(data['subjects']))

    if 'subsidiaries' in data:
        updates.append("subsidiaries = %s" if USE_POSTGRES else "subsidiaries = ?")
        params.append(json.dumps(data['subsidiaries']))

    if 'class' in data:
        updates.append("is_candidate = %s" if USE_POSTGRES else "is_candidate = ?")
        params.append(data['class'] in ['Senior 4', 'Senior 6'])

    if not updates:
        conn.close()
        return cors_response({'success': False, 'error': 'No fields to update'}, 400)

    params.append(student_id)
    query = f"UPDATE students SET {', '.join(updates)} WHERE id = %s" if USE_POSTGRES else f"UPDATE students SET {', '.join(updates)} WHERE id = ?"
    c.execute(query, params)
    conn.commit()
    conn.close()
    return cors_response({'success': True, 'message': 'Student updated'})


@app.route('/students/export', methods=['GET', 'OPTIONS'])
@token_required
@admin_required
def export_csv():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)
    if USE_POSTGRES:
        c.execute("SELECT * FROM students")
    else:
        c.execute("SELECT * FROM students")
    students = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone', 'Class', 'Combination', 'Subjects', 'Subsidiaries'])

    for s in students:
        student = safe_fetchone(s)
        # FIXED: Using .get() to avoid KeyError
        subjects = json.loads(student.get('subjects', '[]')) if student.get('subjects') else []
        subsidiaries = json.loads(student.get('subsidiaries', '[]')) if student.get('subsidiaries') else []
        writer.writerow([
            student.get('id'), student.get('name'), student.get('phone'),
            student.get('class'), student.get('combination') or 'N/A',
            '|'.join(subjects), '|'.join(subsidiaries)
        ])

    output.seek(0)
    response = send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', download_name='students.csv')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/students/import', methods=['POST', 'OPTIONS'])
@token_required
@admin_required
def import_csv():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if 'file' not in request.files:
        return cors_response({'success': False, 'error': 'No file'}, 400)

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return cors_response({'success': False, 'error': 'CSV only'}, 400)

    try:
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)

        conn = get_db()
        c = get_cursor(conn)
        imported = 0

        for row in reader:
            if USE_POSTGRES:
                c.execute("SELECT COALESCE(MAX(id), 1000) + 1 as new_id FROM students")
                result = c.fetchone()
                new_id = result.get('new_id', 1001) if isinstance(result, dict) else 1001
            else:
                c.execute("SELECT COALESCE(MAX(id), 1000) + 1 FROM students")
                new_id = c.fetchone()[0]

            name = row.get('Name', '').strip()
            phone = row.get('Phone', '').strip()
            class_name = row.get('Class', '').strip()

            if not name or not phone or not class_name:
                continue

            if USE_POSTGRES:
                c.execute("SELECT id FROM students WHERE phone = %s", (phone,))
            else:
                c.execute("SELECT id FROM students WHERE phone = ?", (phone,))
            if safe_fetchone(c.fetchone()):
                continue

            subjects = row.get('Subjects', '').split('|') if row.get('Subjects') else []

            if USE_POSTGRES:
                c.execute('''
                    INSERT INTO students (id, name, phone, class, combination, is_candidate, subjects, subsidiaries, join_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (new_id, name, phone, class_name, row.get('Combination', ''), class_name in ['Senior 4', 'Senior 6'], json.dumps(subjects), json.dumps([]), datetime.date.today().isoformat()))
            else:
                c.execute('''
                    INSERT INTO students (id, name, phone, class, combination, is_candidate, subjects, subsidiaries, join_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (new_id, name, phone, class_name, row.get('Combination', ''), class_name in ['Senior 4', 'Senior 6'], json.dumps(subjects), json.dumps([]), datetime.date.today().isoformat()))
            imported += 1

        conn.commit()
        conn.close()
        return cors_response({'success': True, 'imported': imported})

    except Exception as e:
        return cors_response({'success': False, 'error': str(e)}, 500)

# ============ RESULTS & MARKS ENTRY ============

@app.route('/results', methods=['POST', 'OPTIONS'])
@token_required
@admin_required
def add_result():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    data = request.get_json()
    student_id = data.get('student_id')
    marks_list = data.get('marks', [])
    year = data.get('year', datetime.date.today().year)
    term = data.get('term', 1)
    phase = data.get('phase', 'Beginning')

    if not student_id or not marks_list:
        return cors_response({'success': False, 'error': 'Student ID and marks required'}, 400)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute("SELECT class FROM students WHERE id = %s", (student_id,))
    else:
        c.execute("SELECT class FROM students WHERE id = ?", (student_id,))

    student = safe_fetchone(c.fetchone())
    if not student:
        conn.close()
        return cors_response({'success': False, 'error': 'Student not found'}, 404)

    student_class = student['class']
    is_a_level = student_class in ['Senior 5', 'Senior 6']
    processed = []
    total_points = total_marks = 0

    for item in marks_list:
        subject = item.get('subject', '')
        marks = int(item.get('marks', 0))

        if is_a_level:
            is_sub = any(s in subject for s in ['General Paper (Sub)', 'ICT (Sub)', 'Sub-Mathematics'])
            if is_sub:
                grade_info = {'grade': 'O', 'points': 1} if marks >= 60 else {'grade': 'F', 'points': 0}
            else:
                if marks >= 80: grade_info = {'grade': 'A', 'points': 6}
                elif marks >= 70: grade_info = {'grade': 'B', 'points': 5}
                elif marks >= 60: grade_info = {'grade': 'C', 'points': 4}
                elif marks >= 50: grade_info = {'grade': 'D', 'points': 3}
                elif marks >= 45: grade_info = {'grade': 'E', 'points': 2}
                else: grade_info = {'grade': 'F', 'points': 0}
        else:
            if marks >= 80: grade_info = {'grade': 'A', 'points': 1}
            elif marks >= 70: grade_info = {'grade': 'B', 'points': 2}
            elif marks >= 60: grade_info = {'grade': 'C', 'points': 3}
            elif marks >= 50: grade_info = {'grade': 'D', 'points': 4}
            elif marks >= 40: grade_info = {'grade': 'E', 'points': 5}
            else: grade_info = {'grade': 'F', 'points': 6}

        processed.append({
            'subject': subject, 'marks': marks,
            'grade': grade_info['grade'], 'points': grade_info['points']
        })
        total_points += grade_info['points']
        total_marks += marks

    avg = round(total_marks / len(marks_list), 1) if marks_list else 0
    marks_json = json.dumps(processed)

    if USE_POSTGRES:
        c.execute('''
            INSERT INTO results (student_id, year, term, phase, marks, total_marks, average, points)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (student_id, year, term, phase, marks_json, total_marks, avg, total_points))
    else:
        c.execute('''
            INSERT INTO results (student_id, year, term, phase, marks, total_marks, average, points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, year, term, phase, marks_json, total_marks, avg, total_points))

    conn.commit()
    conn.close()

    return cors_response({
        'success': True,
        'data': {
            'student_id': student_id, 'average': avg,
            'points': total_points, 'marks': processed
        }
    })


@app.route('/students/<int:student_id>/results', methods=['GET', 'OPTIONS'])
@token_required
def get_student_results(student_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if request.current_user['role'] != 'admin' and request.current_user['user_id'] != student_id:
        return cors_response({'success': False, 'error': 'Unauthorized'}, 403)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute('SELECT * FROM results WHERE student_id = %s ORDER BY year DESC, term DESC', (student_id,))
    else:
        c.execute('SELECT * FROM results WHERE student_id = ? ORDER BY year DESC, term DESC', (student_id,))

    results = c.fetchall()
    conn.close()

    data = []
    for r in results:
        result = safe_fetchone(r)
        marks = json.loads(result['marks']) if result['marks'] else []
        data.append({
            'id': result['id'], 'year': result['year'], 'term': result['term'],
            'phase': result['phase'], 'marks': marks,
            'average': result['average'], 'points': result['points']
        })

    return cors_response({'success': True, 'data': data})


# ============ NEW: PAPER 1 & PAPER 2 MARKS ENTRY ============

@app.route('/subjects', methods=['POST', 'OPTIONS'])
@token_required
@admin_required
def create_subject():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    data = request.get_json()
    name = data.get('name', '').strip()
    paper1_max = data.get('paper1_max', 50)
    paper2_max = data.get('paper2_max', 50)
    class_name = data.get('class', '')

    if not name or not class_name:
        return cors_response({'success': False, 'error': 'Subject name and class required'}, 400)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute('''
            INSERT INTO subjects (name, paper1_max, paper2_max, class)
            VALUES (%s, %s, %s, %s) RETURNING id
        ''', (name, paper1_max, paper2_max, class_name))
        new_id = c.fetchone()['id']
    else:
        c.execute('''
            INSERT INTO subjects (name, paper1_max, paper2_max, class)
            VALUES (?, ?, ?, ?)
        ''', (name, paper1_max, paper2_max, class_name))
        new_id = c.lastrowid

    conn.commit()
    conn.close()
    return cors_response({'success': True, 'id': new_id}, 201)


@app.route('/subjects', methods=['GET', 'OPTIONS'])
@token_required
def get_subjects():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    class_name = request.args.get('class', '')
    conn = get_db()
    c = get_cursor(conn)

    if class_name:
        if USE_POSTGRES:
            c.execute("SELECT * FROM subjects WHERE class = %s ORDER BY name", (class_name,))
        else:
            c.execute("SELECT * FROM subjects WHERE class = ? ORDER BY name", (class_name,))
    else:
        c.execute("SELECT * FROM subjects ORDER BY name")

    subjects = c.fetchall()
    conn.close()

    result = []
    for s in subjects:
        subj = safe_fetchone(s)
        result.append({
            'id': subj['id'], 'name': subj['name'],
            'paper1_max': subj['paper1_max'], 'paper2_max': subj['paper2_max'],
            'class': subj['class']
        })

    return cors_response({'success': True, 'data': result})


@app.route('/teacher-subjects', methods=['POST', 'OPTIONS'])
@token_required
@admin_required
def assign_teacher_subject():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    data = request.get_json()
    teacher_email = data.get('teacher_email', '').strip().lower()
    subject_id = data.get('subject_id')
    class_name = data.get('class', '')

    if not teacher_email or not subject_id or not class_name:
        return cors_response({'success': False, 'error': 'All fields required'}, 400)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute('''
            INSERT INTO teacher_subjects (teacher_email, subject_id, class, assigned_by)
            VALUES (%s, %s, %s, %s)
        ''', (teacher_email, subject_id, class_name, request.current_user.get('email', 'admin')))
    else:
        c.execute('''
            INSERT INTO teacher_subjects (teacher_email, subject_id, class, assigned_by)
            VALUES (?, ?, ?, ?)
        ''', (teacher_email, subject_id, class_name, request.current_user.get('email', 'admin')))

    conn.commit()
    conn.close()
    return cors_response({'success': True, 'message': 'Teacher assigned to subject'})


@app.route('/teacher-subjects', methods=['GET', 'OPTIONS'])
@token_required
def get_teacher_subjects():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    teacher_email = request.args.get('teacher_email', '')
    if not teacher_email and request.current_user['role'] != 'admin':
        teacher_email = request.current_user.get('email', '')

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        if teacher_email:
            c.execute('''
                SELECT ts.*, s.name, s.paper1_max, s.paper2_max
                FROM teacher_subjects ts
                JOIN subjects s ON ts.subject_id = s.id
                WHERE ts.teacher_email = %s
            ''', (teacher_email,))
        else:
            c.execute('''
                SELECT ts.*, s.name, s.paper1_max, s.paper2_max
                FROM teacher_subjects ts
                JOIN subjects s ON ts.subject_id = s.id
            ''')
    else:
        if teacher_email:
            c.execute('''
                SELECT ts.*, s.name, s.paper1_max, s.paper2_max
                FROM teacher_subjects ts
                JOIN subjects s ON ts.subject_id = s.id
                WHERE ts.teacher_email = ?
            ''', (teacher_email,))
        else:
            c.execute('''
                SELECT ts.*, s.name, s.paper1_max, s.paper2_max
                FROM teacher_subjects ts
                JOIN subjects s ON ts.subject_id = s.id
            ''')

    assignments = c.fetchall()
    conn.close()

    result = []
    for a in assignments:
        assign = safe_fetchone(a)
        result.append({
            'id': assign['id'], 'teacher_email': assign['teacher_email'],
            'subject_id': assign['subject_id'], 'subject_name': assign['name'],
            'paper1_max': assign['paper1_max'], 'paper2_max': assign['paper2_max'],
            'class': assign['class']
        })

    return cors_response({'success': True, 'data': result})


@app.route('/marks', methods=['POST', 'OPTIONS'])
@token_required
@teacher_required
def enter_marks():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    data = request.get_json()
    student_id = data.get('student_id')
    subject_id = data.get('subject_id')
    paper1_score = data.get('paper1_score', 0)
    paper2_score = data.get('paper2_score', 0)
    exam_type = data.get('exam_type', 'End')  # Beginning, Mid, End
    term = data.get('term', 1)
    year = data.get('year', datetime.date.today().year)

    if not student_id or not subject_id:
        return cors_response({'success': False, 'error': 'Student ID and Subject ID required'}, 400)

    # Get subject max marks
    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute("SELECT paper1_max, paper2_max FROM subjects WHERE id = %s", (subject_id,))
    else:
        c.execute("SELECT paper1_max, paper2_max FROM subjects WHERE id = ?", (subject_id,))

    subject = safe_fetchone(c.fetchone())
    if not subject:
        conn.close()
        return cors_response({'success': False, 'error': 'Subject not found'}, 404)

    # Validate marks
    if paper1_score > subject['paper1_max']:
        conn.close()
        return cors_response({'success': False, 'error': f'Paper 1 marks cannot exceed {subject["paper1_max"]}'}, 400)
    if paper2_score > subject['paper2_max']:
        conn.close()
        return cors_response({'success': False, 'error': f'Paper 2 marks cannot exceed {subject["paper2_max"]}'}, 400)

    total = paper1_score + paper2_score
    max_total = subject['paper1_max'] + subject['paper2_max']
    percentage = (total / max_total) * 100 if max_total > 0 else 0

    # Calculate grade
    if percentage >= 80: grade = 'A'
    elif percentage >= 70: grade = 'B'
    elif percentage >= 60: grade = 'C'
    elif percentage >= 50: grade = 'D'
    elif percentage >= 40: grade = 'E'
    else: grade = 'F'

    # Check if marks already exist
    if USE_POSTGRES:
        c.execute('''
            SELECT id FROM marks WHERE student_id = %s AND subject_id = %s
            AND term = %s AND year = %s AND exam_type = %s
        ''', (student_id, subject_id, term, year, exam_type))
    else:
        c.execute('''
            SELECT id FROM marks WHERE student_id = ? AND subject_id = ?
            AND term = ? AND year = ? AND exam_type = ?
        ''', (student_id, subject_id, term, year, exam_type))

    existing = safe_fetchone(c.fetchone())

    if existing:
        # Update existing
        if USE_POSTGRES:
            c.execute('''
                UPDATE marks SET paper1_score = %s, paper2_score = %s, total = %s,
                grade = %s, entered_by = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (paper1_score, paper2_score, total, grade, request.current_user.get('email', 'teacher'), existing['id']))
        else:
            c.execute('''
                UPDATE marks SET paper1_score = ?, paper2_score = ?, total = ?,
                grade = ?, entered_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (paper1_score, paper2_score, total, grade, request.current_user.get('email', 'teacher'), existing['id']))
    else:
        # Insert new
        if USE_POSTGRES:
            c.execute('''
                INSERT INTO marks (student_id, subject_id, paper1_score, paper2_score, total, grade, exam_type, term, year, entered_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (student_id, subject_id, paper1_score, paper2_score, total, grade, exam_type, term, year, request.current_user.get('email', 'teacher')))
        else:
            c.execute('''
                INSERT INTO marks (student_id, subject_id, paper1_score, paper2_score, total, grade, exam_type, term, year, entered_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, subject_id, paper1_score, paper2_score, total, grade, exam_type, term, year, request.current_user.get('email', 'teacher')))

    conn.commit()
    conn.close()

    return cors_response({'success': True, 'message': 'Marks saved', 'grade': grade, 'total': total})

# ============ REVIEW REQUESTS & NOTIFICATIONS ============

@app.route('/review-requests', methods=['POST', 'OPTIONS'])
@token_required
def create_review_request():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if request.current_user['role'] != 'student':
        return cors_response({'success': False, 'error': 'Only students can request reviews'}, 403)

    data = request.get_json()
    student_id = request.current_user['user_id']
    subject_id = data.get('subject_id')
    current_marks = data.get('current_marks')
    requested_marks = data.get('requested_marks')
    reason = data.get('reason', '').strip()
    evidence = data.get('evidence', '')  # Base64 string

    if not subject_id or not reason:
        return cors_response({'success': False, 'error': 'Subject and reason required'}, 400)

    conn = get_db()
    c = get_cursor(conn)

    # Check if request already exists for this subject/term
    current_term = 1  # Get from active term
    current_year = datetime.date.today().year

    if USE_POSTGRES:
        c.execute('''
            SELECT id FROM review_requests WHERE student_id = %s AND subject_id = %s
            AND status = 'pending'
        ''', (student_id, subject_id))
    else:
        c.execute('''
            SELECT id FROM review_requests WHERE student_id = ? AND subject_id = ?
            AND status = 'pending'
        ''', (student_id, subject_id))

    if safe_fetchone(c.fetchone()):
        conn.close()
        return cors_response({'success': False, 'error': 'Pending review request already exists'}, 400)

    if USE_POSTGRES:
        c.execute('''
            INSERT INTO review_requests (student_id, subject_id, current_marks, requested_marks, reason, evidence)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (student_id, subject_id, current_marks, requested_marks, reason, evidence))
    else:
        c.execute('''
            INSERT INTO review_requests (student_id, subject_id, current_marks, requested_marks, reason, evidence)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, subject_id, current_marks, requested_marks, reason, evidence))

    conn.commit()
    conn.close()

    return cors_response({'success': True, 'message': 'Review request submitted'})


@app.route('/review-requests', methods=['GET', 'OPTIONS'])
@token_required
def get_review_requests():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    role = request.current_user['role']
    user_id = request.current_user['user_id']

    conn = get_db()
    c = get_cursor(conn)

    if role == 'admin':
        if USE_POSTGRES:
            c.execute('''
                SELECT rr.*, s.name as student_name, sub.name as subject_name
                FROM review_requests rr
                JOIN students s ON rr.student_id = s.id
                JOIN subjects sub ON rr.subject_id = sub.id
                ORDER BY rr.created_at DESC
            ''')
        else:
            c.execute('''
                SELECT rr.*, s.name as student_name, sub.name as subject_name
                FROM review_requests rr
                JOIN students s ON rr.student_id = s.id
                JOIN subjects sub ON rr.subject_id = sub.id
                ORDER BY rr.created_at DESC
            ''')
    elif role == 'classteacher':
        # Get class teacher's class
        if USE_POSTGRES:
            c.execute("SELECT class FROM users WHERE id = %s", (user_id,))
        else:
            c.execute("SELECT class FROM users WHERE id = ?", (user_id,))
        teacher = safe_fetchone(c.fetchone())
        teacher_class = teacher['class'] if teacher else ''

        if USE_POSTGRES:
            c.execute('''
                SELECT rr.*, s.name as student_name, sub.name as subject_name
                FROM review_requests rr
                JOIN students s ON rr.student_id = s.id
                JOIN subjects sub ON rr.subject_id = sub.id
                WHERE s.class = %s
                ORDER BY rr.created_at DESC
            ''', (teacher_class,))
        else:
            c.execute('''
                SELECT rr.*, s.name as student_name, sub.name as subject_name
                FROM review_requests rr
                JOIN students s ON rr.student_id = s.id
                JOIN subjects sub ON rr.subject_id = sub.id
                WHERE s.class = ?
                ORDER BY rr.created_at DESC
            ''', (teacher_class,))
    else:
        # Student view their own requests
        if USE_POSTGRES:
            c.execute('''
                SELECT rr.*, sub.name as subject_name
                FROM review_requests rr
                JOIN subjects sub ON rr.subject_id = sub.id
                WHERE rr.student_id = %s
                ORDER BY rr.created_at DESC
            ''', (user_id,))
        else:
            c.execute('''
                SELECT rr.*, sub.name as subject_name
                FROM review_requests rr
                JOIN subjects sub ON rr.subject_id = sub.id
                WHERE rr.student_id = ?
                ORDER BY rr.created_at DESC
            ''', (user_id,))

    requests = c.fetchall()
    conn.close()

    result = []
    for r in requests:
        req = safe_fetchone(r)
        result.append({
            'id': req['id'], 'student_id': req['student_id'],
            'student_name': req.get('student_name', ''),
            'subject_id': req['subject_id'], 'subject_name': req.get('subject_name', ''),
            'current_marks': req['current_marks'], 'requested_marks': req['requested_marks'],
            'reason': req['reason'], 'evidence': req.get('evidence', ''),
            'status': req['status'], 'class_teacher_response': req.get('class_teacher_response', ''),
            'created_at': req['created_at']
        })

    return cors_response({'success': True, 'data': result})


@app.route('/review-requests/<int:request_id>', methods=['PUT', 'OPTIONS'])
@token_required
def resolve_review_request(request_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    role = request.current_user['role']
    if role not in ['admin', 'classteacher']:
        return cors_response({'success': False, 'error': 'Unauthorized'}, 403)

    data = request.get_json()
    status = data.get('status')  # 'approved' or 'rejected'
    response_msg = data.get('response', '')
    new_marks = data.get('new_marks')

    if status not in ['approved', 'rejected']:
        return cors_response({'success': False, 'error': 'Invalid status'}, 400)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute('''
            UPDATE review_requests SET status = %s, class_teacher_response = %s,
            resolved_at = CURRENT_TIMESTAMP WHERE id = %s
        ''', (status, response_msg, request_id))
    else:
        c.execute('''
            UPDATE review_requests SET status = ?, class_teacher_response = ?,
            resolved_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (status, response_msg, request_id))

    # If approved and new marks provided, update the marks
    if status == 'approved' and new_marks is not None:
        # Get the review request to find subject and student
        if USE_POSTGRES:
            c.execute("SELECT student_id, subject_id FROM review_requests WHERE id = %s", (request_id,))
        else:
            c.execute("SELECT student_id, subject_id FROM review_requests WHERE id = ?", (request_id,))
        review = safe_fetchone(c.fetchone())

        if review:
            # Update marks - you need exam_type, term, year
            if USE_POSTGRES:
                c.execute('''
                    UPDATE marks SET paper1_score = %s, total = %s,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = %s AND subject_id = %s
                ''', (new_marks, new_marks, review['student_id'], review['subject_id']))
            else:
                c.execute('''
                    UPDATE marks SET paper1_score = ?, total = ?,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ? AND subject_id = ?
                ''', (new_marks, new_marks, review['student_id'], review['subject_id']))

    conn.commit()
    conn.close()

    return cors_response({'success': True, 'message': f'Review request {status}'})

@app.route('/notifications', methods=['GET', 'OPTIONS'])
@token_required
def get_notifications():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    role = request.current_user['role']
    user_id = request.current_user['user_id']

    conn = get_db()
    c = get_cursor(conn)

    if role == 'classteacher':
        if USE_POSTGRES:
            c.execute("SELECT class FROM users WHERE id = %s", (user_id,))
        else:
            c.execute("SELECT class FROM users WHERE id = ?", (user_id,))
        teacher = safe_fetchone(c.fetchone())
        teacher_class = teacher['class'] if teacher else ''

        if USE_POSTGRES:
            c.execute('''
                SELECT * FROM notifications WHERE class = %s OR student_id IS NULL
                ORDER BY created_at DESC LIMIT 50
            ''', (teacher_class,))
        else:
            c.execute('''
                SELECT * FROM notifications WHERE class = ? OR student_id IS NULL
                ORDER BY created_at DESC LIMIT 50
            ''', (teacher_class,))
    elif role == 'student':
        if USE_POSTGRES:
            c.execute('''
                SELECT * FROM notifications WHERE student_id = %s
                ORDER BY created_at DESC LIMIT 50
            ''', (user_id,))
        else:
            c.execute('''
                SELECT * FROM notifications WHERE student_id = ?
                ORDER BY created_at DESC LIMIT 50
            ''', (user_id,))
    else:
        if USE_POSTGRES:
            c.execute('SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100')
        else:
            c.execute('SELECT * FROM notifications ORDER BY created_at DESC LIMIT 100')

    notifications = c.fetchall()
    conn.close()

    result = []
    for n in notifications:
        note = safe_fetchone(n)
        result.append({
            'id': note['id'], 'student_id': note.get('student_id'),
            'class': note.get('class'), 'subject': note.get('subject'),
            'message': note['message'], 'is_read': note['is_read'],
            'created_at': note['created_at']
        })

    return cors_response({'success': True, 'data': result})


@app.route('/notifications/<int:notification_id>/read', methods=['PUT', 'OPTIONS'])
@token_required
def mark_notification_read(notification_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute("UPDATE notifications SET is_read = %s WHERE id = %s", (True, notification_id))
    else:
        c.execute("UPDATE notifications SET is_read = ? WHERE id = ?", (True, notification_id))

    conn.commit()
    conn.close()

    return cors_response({'success': True, 'message': 'Notification marked as read'})

# ============ FILE UPLOADS (Images & Reports) ============

@app.route('/students/<int:student_id>/upload-image', methods=['POST', 'OPTIONS'])
@token_required
@admin_required
def upload_image(student_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if 'image' not in request.files:
        return cors_response({'success': False, 'error': 'No image'}, 400)

    file = request.files['image']
    try:
        file_data = base64.b64encode(file.read()).decode('utf-8')
        data_url = f"data:{file.content_type};base64,{file_data}"

        conn = get_db()
        c = get_cursor(conn)
        if USE_POSTGRES:
            c.execute("UPDATE students SET image = %s WHERE id = %s", (data_url, student_id))
        else:
            c.execute("UPDATE students SET image = ? WHERE id = ?", (data_url, student_id))
        conn.commit()
        conn.close()
        return cors_response({'success': True, 'image_url': data_url})
    except Exception as e:
        return cors_response({'success': False, 'error': str(e)}, 500)

@app.route('/students/<int:student_id>/reports', methods=['GET', 'POST', 'OPTIONS'])
@token_required
def handle_reports(student_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if request.method == 'GET':
        if request.current_user['role'] != 'admin' and request.current_user['user_id'] != student_id:
            return cors_response({'success': False, 'error': 'Unauthorized'}, 403)

        conn = get_db()
        c = get_cursor(conn)
        if USE_POSTGRES:
            c.execute("SELECT id, filename, upload_date FROM reports WHERE student_id = %s ORDER BY id DESC", (student_id,))
        else:
            c.execute("SELECT id, filename, upload_date FROM reports WHERE student_id = ? ORDER BY id DESC", (student_id,))
        reports = c.fetchall()
        conn.close()
        return cors_response({'success': True, 'data': [{'id': r['id'], 'filename': r['filename'], 'upload_date': r['upload_date']} for r in reports]})

    # POST
    if request.current_user['role'] != 'admin':
        return cors_response({'success': False, 'error': 'Admin only'}, 403)

    if 'file' not in request.files:
        return cors_response({'success': False, 'error': 'No file'}, 400)

    file = request.files['file']
    filename = file.filename

    try:
        file_data = base64.b64encode(file.read()).decode('utf-8')
        conn = get_db()
        c = get_cursor(conn)
        if USE_POSTGRES:
            c.execute('INSERT INTO reports (student_id, filename, file_data, upload_date) VALUES (%s, %s, %s, %s)',
                     (student_id, filename, file_data, datetime.date.today().isoformat()))
        else:
            c.execute('INSERT INTO reports (student_id, filename, file_data, upload_date) VALUES (?, ?, ?, ?)',
                     (student_id, filename, file_data, datetime.date.today().isoformat()))
        conn.commit()
        conn.close()
        return cors_response({'success': True, 'filename': filename})
    except Exception as e:
        return cors_response({'success': False, 'error': str(e)}, 500)


@app.route('/reports/<int:report_id>/download', methods=['GET', 'OPTIONS'])
@token_required
def download_report(report_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)

    if USE_POSTGRES:
        c.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
    else:
        c.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    report = safe_fetchone(c.fetchone())

    if not report:
        conn.close()
        return cors_response({'success': False, 'error': 'Not found'}, 404)

    if request.current_user['role'] != 'admin' and report['student_id'] != request.current_user['user_id']:
        conn.close()
        return cors_response({'success': False, 'error': 'Unauthorized'}, 403)

    try:
        file_data = base64.b64decode(report['file_data'])
        return send_file(io.BytesIO(file_data), download_name=report['filename'], as_attachment=True)
    except Exception as e:
        return cors_response({'success': False, 'error': str(e)}, 500)
# ============ ALERTS & ANNOUNCEMENTS ============

@app.route('/students/<int:student_id>/alerts', methods=['GET', 'POST', 'OPTIONS'])
@token_required
def handle_alerts(student_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)

    if request.method == 'POST':
        if request.current_user['role'] != 'admin':
            conn.close()
            return cors_response({'success': False, 'error': 'Admin only'}, 403)
        data = request.get_json()
        message = data.get('message', '')
        if USE_POSTGRES:
            c.execute("INSERT INTO alerts (student_id, message) VALUES (%s, %s)", (student_id, message))
        else:
            c.execute("INSERT INTO alerts (student_id, message) VALUES (?, ?)", (student_id, message))
        conn.commit()
        conn.close()
        return cors_response({'success': True, 'message': 'Alert sent'})

    # GET
    if request.current_user['role'] != 'admin' and request.current_user['user_id'] != student_id:
        conn.close()
        return cors_response({'success': False, 'error': 'Unauthorized'}, 403)

    if USE_POSTGRES:
        c.execute("SELECT * FROM alerts WHERE student_id = %s ORDER BY created_at DESC", (student_id,))
    else:
        c.execute("SELECT * FROM alerts WHERE student_id = ? ORDER BY created_at DESC", (student_id,))
    alerts = c.fetchall()
    conn.close()
    return cors_response({'success': True, 'data': [{'id': a['id'], 'message': a['message'], 'd': a['created_at']} for a in alerts]})


@app.route('/announcements', methods=['GET', 'POST', 'OPTIONS'])
@token_required
def handle_announcements():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)

    if request.method == 'POST':
        if request.current_user['role'] != 'admin':
            conn.close()
            return cors_response({'success': False, 'error': 'Admin only'}, 403)
        data = request.get_json()
        if USE_POSTGRES:
            c.execute('INSERT INTO announcements (title, body, target) VALUES (%s, %s, %s)',
                     (data['title'], data['body'], data.get('target', 'all')))
        else:
            c.execute('INSERT INTO announcements (title, body, target) VALUES (?, ?, ?)',
                     (data['title'], data['body'], data.get('target', 'all')))
        conn.commit()
        conn.close()
        return cors_response({'success': True, 'message': 'Announcement created'})

    # GET
    if request.current_user['role'] == 'admin':
        if USE_POSTGRES:
            c.execute("SELECT * FROM announcements ORDER BY created_at DESC")
        else:
            c.execute("SELECT * FROM announcements ORDER BY created_at DESC")
    else:
        if USE_POSTGRES:
            c.execute("SELECT class FROM students WHERE id = %s", (request.current_user['user_id'],))
        else:
            c.execute("SELECT class FROM students WHERE id = ?", (request.current_user['user_id'],))
        student = safe_fetchone(c.fetchone())
        target = student['class'] if student else 'all'

        if USE_POSTGRES:
            c.execute("SELECT * FROM announcements WHERE target = 'all' OR target = %s ORDER BY created_at DESC", (target,))
        else:
            c.execute("SELECT * FROM announcements WHERE target = 'all' OR target = ? ORDER BY created_at DESC", (target,))

    announcements = c.fetchall()
    conn.close()
    return cors_response({'success': True, 'data': [{'id': a['id'], 'title': a['title'], 'body': a['body'], 'target': a['target'], 'd': a['created_at']} for a in announcements]})

@app.route('/announcements/<int:ann_id>', methods=['DELETE', 'OPTIONS'])
@token_required
@admin_required
def delete_announcement(ann_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    conn = get_db()
    c = get_cursor(conn)
    if USE_POSTGRES:
        c.execute("DELETE FROM announcements WHERE id = %s", (ann_id,))
    else:
        c.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    conn.commit()
    conn.close()
    return cors_response({'success': True, 'message': 'Deleted'})

# ============ REPORT DATA (JSON ONLY - NO HTML) ============

@app.route('/report/data/<int:student_id>', methods=['GET', 'OPTIONS'])
@token_required
def get_report_data(student_id):
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    # Check authorization
    role = request.current_user.get('role')
    user_id = request.current_user.get('user_id')

    if role not in ['admin', 'classteacher'] and user_id != student_id:
        return cors_response({'success': False, 'error': 'Unauthorized'}, 403)

    conn = get_db()
    c = get_cursor(conn)

    # Get student
    if USE_POSTGRES:
        c.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    else:
        c.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = safe_fetchone(c.fetchone())

    if not student:
        conn.close()
        return cors_response({'success': False, 'error': 'Student not found'}, 404)

    # Get marks with subject and teacher info
    if USE_POSTGRES:
        c.execute('''
            SELECT m.*, s.name as subject_name, s.paper1_max, s.paper2_max,
                   ts.teacher_email
            FROM marks m
            JOIN subjects s ON m.subject_id = s.id
            LEFT JOIN teacher_subjects ts ON ts.subject_id = s.id AND ts.class = s.class
            WHERE m.student_id = %s
            ORDER BY m.year DESC, m.term DESC
        ''', (student_id,))
    else:
        c.execute('''
            SELECT m.*, s.name as subject_name, s.paper1_max, s.paper2_max,
                   ts.teacher_email
            FROM marks m
            JOIN subjects s ON m.subject_id = s.id
            LEFT JOIN teacher_subjects ts ON ts.subject_id = s.id AND ts.class = s.class
            WHERE m.student_id = ?
            ORDER BY m.year DESC, m.term DESC
        ''', (student_id,))

    marks = c.fetchall()
    conn.close()

    # Get active term
    term_conn = get_db()
    term_c = get_cursor(term_conn)
    if USE_POSTGRES:
        term_c.execute("SELECT year, term FROM terms WHERE is_active = %s LIMIT 1", (True,))
    else:
        term_c.execute("SELECT year, term FROM terms WHERE is_active = ? LIMIT 1", (True,))
    active_term = safe_fetchone(term_c.fetchone())
    term_conn.close()

    if not active_term:
        active_term = {'year': datetime.date.today().year, 'term': 1}

    # Process marks into list
    marks_list = []
    for m in marks:
        mark = safe_fetchone(m)
        marks_list.append({
            'subject': mark['subject_name'],
            'paper1_score': mark.get('paper1_score', 0),
            'paper1_max': mark.get('paper1_max', 50),
            'paper2_score': mark.get('paper2_score', 0),
            'paper2_max': mark.get('paper2_max', 50),
            'total': mark.get('total', 0),
            'grade': mark.get('grade', 'N/A'),
            'teacher': mark.get('teacher_email', 'Not assigned'),
            'exam_type': mark.get('exam_type', 'End'),
            'term': mark.get('term', active_term['term']),
            'year': mark.get('year', active_term['year'])
        })

    # Calculate summary
    total_possible = sum(m['paper1_max'] + m['paper2_max'] for m in marks_list)
    total_obtained = sum(m['total'] for m in marks_list)
    percentage = (total_obtained / total_possible * 100) if total_possible > 0 else 0

    if percentage >= 80: overall_grade = 'A'
    elif percentage >= 70: overall_grade = 'B'
    elif percentage >= 60: overall_grade = 'C'
    elif percentage >= 50: overall_grade = 'D'
    elif percentage >= 40: overall_grade = 'E'
    else: overall_grade = 'F'

    # Get subjects list
    subjects = json.loads(student.get('subjects', '[]')) if student.get('subjects') else []
    subsidiaries = json.loads(student.get('subsidiaries', '[]')) if student.get('subsidiaries') else []
    all_subjects = subjects + subsidiaries

    # Return JSON data only (frontend will generate HTML)
    return cors_response({
        'success': True,
        'data': {
            'student': {
                'id': student['id'],
                'name': student['name'],
                'phone': student['phone'],
                'class': student['class'],
                'combination': student.get('combination') or '',
                'image': student.get('image') or '',
                'join_date': student.get('join_date'),
                'subjects': all_subjects
            },
            'marks': marks_list,
            'term': {
                'year': active_term['year'],
                'term': active_term['term']
            },
            'summary': {
                'total_obtained': total_obtained,
                'total_possible': total_possible,
                'percentage': round(percentage, 1),
                'overall_grade': overall_grade
            },
            'report_date': datetime.datetime.now().isoformat()
        }
    })
# ============ STUDENT DASHBOARD (WITH MARKS) ============

@app.route('/student/dashboard', methods=['GET', 'OPTIONS'])
@token_required
def student_dashboard():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if request.current_user['role'] != 'student':
        return cors_response({'success': False, 'error': 'Students only'}, 403)

    student_id = request.current_user['user_id']
    conn = get_db()
    c = get_cursor(conn)

    # Get student
    if USE_POSTGRES:
        c.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    else:
        c.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = safe_fetchone(c.fetchone())

    if not student:
        conn.close()
        return cors_response({'success': False, 'error': 'Not found'}, 404)

    # Get results
    if USE_POSTGRES:
        c.execute("SELECT * FROM results WHERE student_id = %s ORDER BY year DESC, term DESC", (student_id,))
    else:
        c.execute("SELECT * FROM results WHERE student_id = ? ORDER BY year DESC, term DESC", (student_id,))
    results = c.fetchall()

    # Get alerts
    if USE_POSTGRES:
        c.execute("SELECT * FROM alerts WHERE student_id = %s ORDER BY created_at DESC", (student_id,))
    else:
        c.execute("SELECT * FROM alerts WHERE student_id = ? ORDER BY created_at DESC", (student_id,))
    alerts = c.fetchall()

    # Get reports
    if USE_POSTGRES:
        c.execute("SELECT id, filename, upload_date FROM reports WHERE student_id = %s ORDER BY id DESC", (student_id,))
    else:
        c.execute("SELECT id, filename, upload_date FROM reports WHERE student_id = ? ORDER BY id DESC", (student_id,))
    reports = c.fetchall()

    # Get announcements
    if USE_POSTGRES:
        c.execute("SELECT * FROM announcements WHERE target = 'all' OR target = %s ORDER BY created_at DESC LIMIT 10", (student['class'],))
    else:
        c.execute("SELECT * FROM announcements WHERE target = 'all' OR target = ? ORDER BY created_at DESC LIMIT 10", (student['class'],))
    announcements = c.fetchall()

    # Get marks (Paper 1 & Paper 2)
    if USE_POSTGRES:
        c.execute('''
            SELECT m.*, s.name as subject_name, s.paper1_max, s.paper2_max
            FROM marks m
            JOIN subjects s ON m.subject_id = s.id
            WHERE m.student_id = %s
            ORDER BY m.year DESC, m.term DESC
        ''', (student_id,))
    else:
        c.execute('''
            SELECT m.*, s.name as subject_name, s.paper1_max, s.paper2_max
            FROM marks m
            JOIN subjects s ON m.subject_id = s.id
            WHERE m.student_id = ?
            ORDER BY m.year DESC, m.term DESC
        ''', (student_id,))
    marks = c.fetchall()

    conn.close()

    subjects = json.loads(student.get('subjects', '[]')) if student.get('subjects') else []
    subsidiaries = json.loads(student.get('subsidiaries', '[]')) if student.get('subsidiaries') else []
    all_subjects = subjects + subsidiaries

    results_data = []
    for r in results:
        result = safe_fetchone(r)
        marks_data = json.loads(result['marks']) if result['marks'] else []
        results_data.append({
            'id': result['id'], 'year': result['year'], 'term': result['term'],
            'phase': result['phase'], 'marks': marks_data,
            'average': result['average'], 'points': result['points']
        })

    marks_data = []
    for m in marks:
        mark = safe_fetchone(m)
        marks_data.append({
            'id': mark['id'], 'subject_name': mark['subject_name'],
            'paper1_score': mark.get('paper1_score', 0), 'paper1_max': mark.get('paper1_max', 50),
            'paper2_score': mark.get('paper2_score', 0), 'paper2_max': mark.get('paper2_max', 50),
            'total': mark.get('total', 0), 'grade': mark.get('grade', 'N/A'),
            'exam_type': mark.get('exam_type', 'End'), 'term': mark.get('term', 1), 'year': mark.get('year', 2026)
        })

    return cors_response({
        'success': True,
        'student': {
            'id': student['id'], 'name': student['name'],
            'phone': student['phone'], 'class': student['class'],
            'combination': student.get('combination') or '',
            'isCandidate': bool(student.get('is_candidate', False)),
            'image': student.get('image') or '',
            'joinDate': student.get('join_date'),
            'subjects': all_subjects
        },
        'results': results_data,
        'marks': marks_data,
        'alerts': [{'id': a['id'], 'message': a['message'], 'created_at': a['created_at']} for a in alerts],
        'reports': [{'id': r['id'], 'filename': r['filename'], 'upload_date': r['upload_date']} for r in reports],
        'announcements': [{'id': a['id'], 'title': a['title'], 'body': a['body'], 'created_at': a['created_at']} for a in announcements]
    })
# ============ TEACHER DASHBOARD DATA ============

@app.route('/teacher/dashboard', methods=['GET', 'OPTIONS'])
@token_required
def teacher_dashboard():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    role = request.current_user.get('role')
    if role not in ['teacher', 'classteacher', 'admin']:
        return cors_response({'success': False, 'error': 'Teacher access required'}, 403)

    teacher_email = request.current_user.get('email', '')
    conn = get_db()
    c = get_cursor(conn)

    # Get assigned subjects
    if USE_POSTGRES:
        c.execute('''
            SELECT ts.*, s.name as subject_name, s.paper1_max, s.paper2_max
            FROM teacher_subjects ts
            JOIN subjects s ON ts.subject_id = s.id
            WHERE ts.teacher_email = %s
        ''', (teacher_email,))
    else:
        c.execute('''
            SELECT ts.*, s.name as subject_name, s.paper1_max, s.paper2_max
            FROM teacher_subjects ts
            JOIN subjects s ON ts.subject_id = s.id
            WHERE ts.teacher_email = ?
        ''', (teacher_email,))

    assignments = c.fetchall()
    conn.close()

    subjects_list = []
    for a in assignments:
        assign = safe_fetchone(a)
        subjects_list.append({
            'id': assign['subject_id'],
            'name': assign['subject_name'],
            'class': assign['class'],
            'paper1_max': assign['paper1_max'],
            'paper2_max': assign['paper2_max']
        })

    return cors_response({
        'success': True,
        'subjects': subjects_list,
        'role': role
    })
@app.route('/')
def serve_frontend():
    return jsonify({'message': 'Raven Systems API is running', 'status': 'online', 'version': '3.0'})

@app.errorhandler(500)
def handle_500(e):
    traceback.print_exc()
    return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/student/my-report', methods=['GET', 'OPTIONS'])
@token_required
def student_my_report():
    if request.method == 'OPTIONS':
        return cors_response({'success': True}, 200)

    if request.current_user['role'] != 'student':
        return cors_response({'success': False, 'error': 'Students only'}, 403)

    student_id = request.current_user['user_id']

    conn = get_db()
    c = get_cursor(conn)

    # Get student
    if USE_POSTGRES:
        c.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    else:
        c.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = safe_fetchone(c.fetchone())

    if not student:
        conn.close()
        return cors_response({'success': False, 'error': 'Student not found'}, 404)

    # Get marks with subject and teacher info
    if USE_POSTGRES:
        c.execute('''
            SELECT m.*, s.name as subject_name, s.paper1_max, s.paper2_max,
                   ts.teacher_email
            FROM marks m
            JOIN subjects s ON m.subject_id = s.id
            LEFT JOIN teacher_subjects ts ON ts.subject_id = s.id AND ts.class = s.class
            WHERE m.student_id = %s
            ORDER BY m.year DESC, m.term DESC
        ''', (student_id,))
    else:
        c.execute('''
            SELECT m.*, s.name as subject_name, s.paper1_max, s.paper2_max,
                   ts.teacher_email
            FROM marks m
            JOIN subjects s ON m.subject_id = s.id
            LEFT JOIN teacher_subjects ts ON ts.subject_id = s.id AND ts.class = s.class
            WHERE m.student_id = ?
            ORDER BY m.year DESC, m.term DESC
        ''', (student_id,))
    marks = c.fetchall()
    conn.close()
    # Get active term
    term_conn = get_db()
    term_c = get_cursor(term_conn)
    if USE_POSTGRES:
        term_c.execute("SELECT year, term FROM terms WHERE is_active = %s LIMIT 1", (True,))
    else:
        term_c.execute("SELECT year, term FROM terms WHERE is_active = ? LIMIT 1", (True,))
    active_term = safe_fetchone(term_c.fetchone())
    term_conn.close()

    if not active_term:
        active_term = {'year': datetime.date.today().year, 'term': 1}

    # Process marks
    marks_list = []
    for m in marks:
        mark = safe_fetchone(m)
        marks_list.append({
            'subject': mark['subject_name'],
            'paper1_score': mark.get('paper1_score', 0),
            'paper1_max': mark.get('paper1_max', 50),
            'paper2_score': mark.get('paper2_score', 0),
            'paper2_max': mark.get('paper2_max', 50),
            'total': mark.get('total', 0),
            'grade': mark.get('grade', 'N/A'),
            'teacher': mark.get('teacher_email', 'Not assigned'),
            'exam_type': mark.get('exam_type', 'End'),
            'term': mark.get('term', active_term['term']),
            'year': mark.get('year', active_term['year'])
        })

    # Calculate summary
    total_possible = sum(m['paper1_max'] + m['paper2_max'] for m in marks_list)
    total_obtained = sum(m['total'] for m in marks_list)
    percentage = (total_obtained / total_possible * 100) if total_possible > 0 else 0

    if percentage >= 80: overall_grade = 'A'
    elif percentage >= 70: overall_grade = 'B'
    elif percentage >= 60: overall_grade = 'C'
    elif percentage >= 50: overall_grade = 'D'
    elif percentage >= 40: overall_grade = 'E'
    else: overall_grade = 'F'

    subjects = json.loads(student.get('subjects', '[]')) if student.get('subjects') else []
    subsidiaries = json.loads(student.get('subsidiaries', '[]')) if student.get('subsidiaries') else []
    all_subjects = subjects + subsidiaries

    return cors_response({
        'success': True,
        'data': {
            'student': {
                'id': student['id'],
                'name': student['name'],
                'phone': student['phone'],
                'class': student['class'],
                'combination': student.get('combination') or '',
                'image': student.get('image') or '',
                'join_date': student.get('join_date'),
                'subjects': all_subjects
            },
            'marks': marks_list,
            'term': {
                'year': active_term['year'],
                'term': active_term['term']
            },
            'summary': {
                'total_obtained': total_obtained,
                'total_possible': total_possible,
                'percentage': round(percentage, 1),
                'overall_grade': overall_grade
            },
            'report_date': datetime.datetime.now().isoformat()
        }
    })
# ============ MAIN ============
if __name__ == '__main__':
    print("=" * 50)
    print(" RAVEN SYSTEMS v3.0 - FULLY WORKING")
    print(" Admin: admin@school.com / admin123")
    print("=" * 50)
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
