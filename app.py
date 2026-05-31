from functools import wraps
import datetime
import hashlib
import os

from flask import (
    Flask, flash, redirect, render_template_string, request, send_file, session,
    url_for,
)
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "aiu@Leang7788"),
    "database": os.environ.get("MYSQL_DATABASE", "school_erp"),
}

UPLOADS_DIR = "erp_uploads"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "gif", "zip", "ppt", "pptx", "xls", "xlsx"}

app = Flask(__name__)
app.secret_key = os.environ.get("ERP_SECRET_KEY", "change-this-secret-key")
app.config["UPLOAD_FOLDER"] = UPLOADS_DIR
os.makedirs(UPLOADS_DIR, exist_ok=True)


def get_connection(database=True):
    cfg = DB_CONFIG.copy()
    if not database:
        cfg.pop("database", None)
    return mysql.connector.connect(**cfg)


def db_execute(query, params=(), fetch=False, one=False, lastrowid=False):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(query, params)
        if fetch:
            return cur.fetchone() if one else cur.fetchall()
        conn.commit()
        return cur.lastrowid if lastrowid else True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def db_fetchone(query, params=()):
    return db_execute(query, params, fetch=True, one=True)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def calculate_grade(percentage):
    if percentage >= 90:
        return "A+", 4.0
    if percentage >= 80:
        return "A", 3.7
    if percentage >= 70:
        return "B+", 3.3
    if percentage >= 60:
        return "B", 3.0
    if percentage >= 50:
        return "C+", 2.7
    if percentage >= 40:
        return "C", 2.3
    if percentage >= 33:
        return "D", 2.0
    return "F", 0.0


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename):
        raise ValueError("File type is not allowed.")
    base = secure_filename(file_storage.filename)
    stem, ext = os.path.splitext(base)
    unique = f"{stem}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], unique)
    file_storage.save(path)
    return path


def initialize_database():
    if not MYSQL_AVAILABLE:
        return
    conn = get_connection(database=False)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
    cur.close()
    conn.close()

    stmts = [
        """CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role ENUM('Admin','Teacher','Student') NOT NULL,
            fullname VARCHAR(200) NOT NULL,
            email VARCHAR(200),
            phone VARCHAR(20),
            status ENUM('Active','Inactive') DEFAULT 'Active',
            created_date DATE DEFAULT (CURRENT_DATE)
        )""",
        """CREATE TABLE IF NOT EXISTS teachers (
            teacher_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            department VARCHAR(100),
            subjects VARCHAR(500),
            qualification VARCHAR(200),
            experience VARCHAR(50),
            address TEXT,
            joining_date DATE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS students (
            student_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            class VARCHAR(50),
            section VARCHAR(5),
            roll_no VARCHAR(20),
            dob DATE,
            gender VARCHAR(10),
            address TEXT,
            parent_name VARCHAR(200),
            parent_phone VARCHAR(20),
            admission_date DATE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS subjects (
            subject_id INT AUTO_INCREMENT PRIMARY KEY,
            subject_name VARCHAR(200) NOT NULL,
            subject_code VARCHAR(50),
            class VARCHAR(50),
            teacher_id INT,
            department VARCHAR(100)
        )""",
        """CREATE TABLE IF NOT EXISTS classes (
            class_id INT AUTO_INCREMENT PRIMARY KEY,
            class_name VARCHAR(50),
            section VARCHAR(5),
            class_teacher_id INT
        )""",
        """CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            date DATE NOT NULL,
            subject_id INT NOT NULL,
            status ENUM('Present','Absent') NOT NULL,
            marked_by INT
        )""",
        """CREATE TABLE IF NOT EXISTS marks (
            mark_id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            subject_id INT NOT NULL,
            exam_type VARCHAR(50),
            marks_obtained FLOAT,
            total_marks FLOAT,
            date DATE,
            teacher_id INT
        )""",
        """CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT,
            class_name VARCHAR(50),
            section VARCHAR(10) DEFAULT 'All',
            title VARCHAR(300),
            description TEXT,
            teacher_id INT,
            assigned_date DATE,
            due_date DATE,
            file_path VARCHAR(500)
        )""",
        """CREATE TABLE IF NOT EXISTS submissions (
            submission_id INT AUTO_INCREMENT PRIMARY KEY,
            assignment_id INT,
            student_id INT,
            submitted_date DATE,
            file_path VARCHAR(500),
            status VARCHAR(50) DEFAULT 'Submitted',
            grade VARCHAR(10),
            feedback TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS notices (
            notice_id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(300),
            content TEXT,
            posted_by INT,
            posted_date DATETIME,
            target_role VARCHAR(20) DEFAULT 'All'
        )""",
        """CREATE TABLE IF NOT EXISTS study_materials (
            material_id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT,
            title VARCHAR(300),
            description TEXT,
            teacher_id INT,
            upload_date DATE,
            file_path VARCHAR(500)
        )""",
        """CREATE TABLE IF NOT EXISTS timetable (
            timetable_id INT AUTO_INCREMENT PRIMARY KEY,
            day VARCHAR(20),
            period INT,
            class_name VARCHAR(50),
            section VARCHAR(5),
            subject_id INT,
            teacher_id INT,
            start_time VARCHAR(10),
            end_time VARCHAR(10)
        )""",
        """CREATE TABLE IF NOT EXISTS notice_read (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            notice_id INT,
            read_date DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS student_subjects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            subject_id INT,
            assigned_date DATE
        )""",
    ]
    for stmt in stmts:
        db_execute(stmt)

    # Ensure existing tables can store longer class names
    migrations = [
        "ALTER TABLE students MODIFY class VARCHAR(50)",
        "ALTER TABLE subjects MODIFY class VARCHAR(50)",
        "ALTER TABLE classes MODIFY class_name VARCHAR(50)",
        "ALTER TABLE assignments MODIFY class_name VARCHAR(50)",
        "ALTER TABLE timetable MODIFY class_name VARCHAR(50)",
    ]
    for migration in migrations:
        try:
            db_execute(migration)
        except Exception:
            pass

    if not db_fetchone("SELECT user_id FROM users WHERE username=%s", ("admin",)):
        db_execute(
            "INSERT INTO users (username,password,role,fullname,email,phone,status,created_date) VALUES (%s,%s,%s,%s,%s,%s,'Active',%s)",
            ("admin", hash_password("admin123"), "Admin", "System Administrator", "admin@school.com", "9999999999", datetime.date.today()),
        )


def require_login(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def unread_notice_count():
    if "user_id" not in session:
        return 0
    row = db_fetchone(
        "SELECT COUNT(*) AS cnt FROM notices WHERE target_role IN ('All',%s) AND notice_id NOT IN (SELECT notice_id FROM notice_read WHERE user_id=%s)",
        (session["role"], session["user_id"]),
    )
    return row["cnt"] if row else 0


def nav_for(role):
    menus = {
        "Admin": [
            ("Dashboard", "admin_dashboard"), ("Users", "admin_users"), ("Teachers", "admin_teachers"),
            ("Students", "admin_students"), ("Subjects", "admin_subjects"), ("Classes", "admin_classes"),
            ("Student Subjects", "admin_student_subjects"), ("Timetable", "admin_timetable"),
            ("Notices", "admin_notices"), ("Reports", "admin_reports"),
        ],
        "Teacher": [
            ("Dashboard", "teacher_dashboard"), ("My Subjects", "teacher_subjects"),
            ("Timetable", "teacher_timetable"), ("Mark Attendance", "teacher_attendance"), ("Add Marks", "teacher_marks"),
            ("Study Materials", "teacher_materials"), ("Assignments", "teacher_assignments"),
            ("Notices", "role_notices"), ("Profile", "profile"),
        ],
        "Student": [
            ("Dashboard", "student_dashboard"), ("Timetable", "student_timetable"),
            ("My Attendance", "student_attendance"), ("My Marks", "student_marks"),
            ("Study Materials", "student_materials"), ("Assignments", "student_assignments"),
            ("Notices", "role_notices"), ("Profile", "profile"),
        ],
    }
    return menus.get(role, [])


BASE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} - School ERP</title>
  <style>
    :root { --admin:#1a73e8; --teacher:#16a085; --student:#8e44ad; --bg:#f0f2f5; --text:#202124; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: "Segoe UI", Arial, sans-serif; background:var(--bg); color:var(--text); }
    a { color:inherit; text-decoration:none; }
    .login-wrap { min-height:100vh; display:grid; grid-template-columns:1fr 420px; gap:48px; align-items:center; padding:48px 9vw; background:#1a73e8; color:white; }
    .login-panel, .card, .table-wrap, .form-card { background:white; color:var(--text); border:1px solid #dfe3e8; border-radius:8px; }
    .login-panel { padding:32px; }
    .topbar { height:64px; display:flex; align-items:center; gap:16px; padding:0 24px; background:var(--role-color); color:white; position:sticky; top:0; z-index:2; }
    .brand { font-size:20px; font-weight:800; margin-right:auto; }
    .badge { background:#d93025; color:white; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:700; }
    .shell { display:grid; grid-template-columns:245px 1fr; min-height:calc(100vh - 64px); }
    .sidebar { background:var(--side-color); color:white; padding:20px 0; }
    .sidebar a { display:block; padding:13px 22px; color:white; font-weight:600; }
    .sidebar a:hover { background:rgba(255,255,255,.12); }
    .content { padding:26px; max-width:1500px; width:100%; }
    h1 { margin:0 0 18px; font-size:28px; }
    h2 { margin:22px 0 12px; font-size:20px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin:16px 0 24px; }
    .stat { padding:22px; border-left:5px solid var(--role-color); }
    .stat strong { display:block; font-size:32px; margin-bottom:6px; }
    .actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:12px 0; }
    .btn, button { border:0; border-radius:6px; background:var(--role-color); color:white; padding:9px 13px; font-weight:700; cursor:pointer; display:inline-block; }
    .btn.secondary { background:#5f6368; }
    .btn.danger { background:#d93025; }
    .btn.success { background:#27ae60; }
    .btn.warning { background:#f39c12; }
    input, select, textarea { width:100%; border:1px solid #ccd2da; border-radius:6px; padding:10px; font:inherit; background:white; }
    textarea { min-height:105px; resize:vertical; }
    label { font-weight:700; display:block; margin:10px 0 5px; }
    .form-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px 18px; }
    .form-card { padding:18px; margin:12px 0 20px; }
    .table-wrap { overflow:auto; }
    table { width:100%; border-collapse:collapse; background:white; min-width:760px; }
    th, td { padding:11px 12px; border-bottom:1px solid #eceff3; text-align:left; vertical-align:top; }
    th { background:#34495e; color:white; position:sticky; top:0; }
    tr:nth-child(even) td { background:#fafbfc; }
    .flash { padding:12px 14px; border-radius:6px; margin:8px 0; background:#e8f0fe; border:1px solid #c9ddff; }
    .flash.danger { background:#fde8e8; border-color:#f6b3b3; }
    .flash.success { background:#e6f4ea; border-color:#b7e2c1; }
    .flash.warning { background:#fff8e1; border-color:#f6d778; }
    .notice { padding:16px; margin:10px 0; border-radius:8px; border:1px solid #ddd; background:white; }
    .notice.unread { background:#fff9e6; border-color:#f4d37a; }
    .muted { color:#6b7280; }
    .split { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
    .inline-form { display:inline; }
    .info-box { background:#e8f0fe; border:1px solid #c9ddff; border-radius:6px; padding:12px 16px; margin:10px 0; color:#1a73e8; }
    @media(max-width:850px){ .login-wrap,.shell,.split{ grid-template-columns:1fr; } .sidebar{ display:flex; overflow:auto; padding:0; } .sidebar a{ white-space:nowrap; } }
  </style>
</head>
<body style="--role-color:{{ role_color }}; --side-color:{{ side_color }};">
{% if session.get('user_id') %}
  <header class="topbar">
    <div class="brand">Myanmar University of Technology ERP</div>
    {% if notice_count %}<a class="badge" href="{{ url_for('role_notices') }}">{{ notice_count }} new notices</a>{% endif %}
    <span>{{ session.fullname }} ({{ session.role }})</span>
    <a class="btn danger" href="{{ url_for('logout') }}">Logout</a>
  </header>
  <main class="shell">
    <nav class="sidebar">
      {% for label, endpoint in nav %}
        <a href="{{ url_for(endpoint) }}">{{ label }}</a>
      {% endfor %}
    </nav>
    <section class="content">
      {% for category, message in get_flashed_messages(with_categories=true) %}
        <div class="flash {{ category }}">{{ message }}</div>
      {% endfor %}
      {{ body|safe }}
    </section>
  </main>
{% else %}
  {{ body|safe }}
{% endif %}
</body>
</html>
"""


def render_page(title, body, role=None):
    role = role or session.get("role", "Admin")
    colors = {
        "Admin": ("#1a73e8", "#1557b0"),
        "Teacher": ("#16a085", "#0e6b5a"),
        "Student": ("#8e44ad", "#6c3483"),
    }
    role_color, side_color = colors.get(role, colors["Admin"])
    count = unread_notice_count() if session.get("user_id") else 0
    return render_template_string(
        BASE_TEMPLATE,
        title=title,
        body=Markup(body),
        nav=nav_for(role),
        notice_count=count,
        role_color=role_color,
        side_color=side_color,
    )


def html_table(rows, columns, actions=None, empty="No records found."):
    if not rows:
        return f"<p class='muted'>{escape(empty)}</p>"
    head = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
    if actions:
        head += "<th>Actions</th>"
    body = []
    for row in rows:
        cells = "".join(f"<td>{escape(row.get(key) or '')}</td>" for key, _ in columns)
        if actions:
            cells += f"<td>{actions(row)}</td>"
        body.append(f"<tr>{cells}</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def stats_cards(cards):
    return "<div class='grid'>" + "".join(
        f"<div class='card stat'><strong>{escape(str(value))}</strong><span>{escape(label)}</span></div>"
        for label, value in cards
    ) + "</div>"


def option_tags(rows, value_key, label_fn, selected=None, blank=False):
    html = ["<option value=''>-- Select --</option>"] if blank else []
    for row in rows:
        value = str(row[value_key])
        sel = " selected" if selected is not None and str(selected) == value else ""
        html.append(f"<option value='{escape(value)}'{sel}>{escape(label_fn(row))}</option>")
    return "".join(html)


@app.before_request
def boot_database():
    global MYSQL_AVAILABLE
    if not getattr(app, "_db_ready", False):
        if MYSQL_AVAILABLE:
            try:
                initialize_database()
            except Exception as e:
                print(f"Database initialization failed: {e}")
                MYSQL_AVAILABLE = False
        app._db_ready = True


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for(f"{session['role'].lower()}_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not MYSQL_AVAILABLE:
        body = "<div class='login-wrap'><div><h1>Missing Package</h1><p>Install mysql-connector-python and restart.</p></div></div>"
        return render_page("Missing Package", body)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db_fetchone("SELECT * FROM users WHERE username=%s AND password=%s", (username, hash_password(password)))
        if user and user["status"] == "Active":
            session.clear()
            session.update(user_id=user["user_id"], role=user["role"], fullname=user["fullname"], username=user["username"], password=user["password"])
            return redirect(url_for("index"))
        flash("Invalid credentials or inactive account.", "danger")
    body = """
    <div class="login-wrap">
      <div>
        <div style="font-size:74px">🎓</div>
        <h1>Myanmar University of Technology</h1>
        <p>Delivering quality education and developing skilled professionals.</p>
        <p>Roles: Admin | Teacher | Student</p>
      </div>
      <form class="login-panel" method="post">
        <h1>Welcome Back</h1>
        {% for category, message in get_flashed_messages(with_categories=true) %}
          <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
        <label>Username</label><input name="username" required autofocus>
        <label>Password</label><input name="password" type="password" required>
        <button style="width:100%; margin-top:18px;">LOGIN</button>
        <p class="muted">Default: admin / admin123</p>
      </form>
    </div>
    """
    return render_template_string(BASE_TEMPLATE, title="Login", body=Markup(render_template_string(body)), role_color="#1a73e8", side_color="#1557b0", nav=[], notice_count=0)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


def count_table(table):
    try:
        return db_fetchone(f"SELECT COUNT(*) AS c FROM {table}")["c"]
    except Exception:
        return 0


# ─────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────

@app.route("/admin/dashboard")
@require_login("Admin")
def admin_dashboard():
    users = db_execute("SELECT user_id,username,role,fullname,status FROM users ORDER BY user_id DESC LIMIT 6", fetch=True)
    body = "<h1>Dashboard Overview</h1>"
    body += stats_cards([
        ("Total Users", count_table("users")), ("Students", count_table("students")),
        ("Teachers", count_table("teachers")), ("Subjects", count_table("subjects")),
        ("Notices", count_table("notices")),
    ])
    body += "<h2>Recent Users</h2>" + html_table(users, [("user_id", "ID"), ("username", "Username"), ("role", "Role"), ("fullname", "Full Name"), ("status", "Status")])
    return render_page("Admin Dashboard", body, "Admin")


@app.route("/admin/users")
@require_login("Admin")
def admin_users():
    users = db_execute("SELECT * FROM users ORDER BY user_id", fetch=True)
    def actions(row):
        uid = row["user_id"]
        return (
            f"<a class='btn warning' href='{url_for('admin_toggle_user', user_id=uid)}'>Toggle</a> "
            f"<form class='inline-form' method='post' action='{url_for('admin_delete_user', user_id=uid)}' onsubmit=\"return confirm('Delete this user and related data?')\"><button class='danger'>Delete</button></form>"
        )
    form = """
    <form class="form-card" method="post" action="{{ url_for('admin_create_user') }}" autocomplete="off">
      <h2>Create New User</h2>
      <div class="form-grid">
        <div><label>Username *</label><input name="username" required autocomplete="new-username" placeholder="Example: student001"></div>
        <div><label>Password *</label><input name="password" type="password" required autocomplete="new-password"></div>
        <div><label>Role *</label><select name="role"><option>Admin</option><option>Teacher</option><option selected>Student</option></select></div>
        <div><label>Full Name *</label><input name="fullname" required></div>
        <div><label>Email</label><input name="email"></div>
        <div><label>Phone</label><input name="phone"></div>
      </div><div class="actions"><button>Create User</button></div>
    </form>
    """
    body = "<h1>User Management</h1>" + render_template_string(form)
    body += html_table(users, [("user_id", "ID"), ("username", "Username"), ("role", "Role"), ("fullname", "Full Name"), ("email", "Email"), ("phone", "Phone"), ("status", "Status"), ("created_date", "Created")], actions)
    return render_page("Users", body, "Admin")


@app.post("/admin/users/create")
@require_login("Admin")
def admin_create_user():
    username = request.form["username"].strip()
    if db_fetchone("SELECT user_id FROM users WHERE username=%s", (username,)):
        flash(f"Username '{username}' already exists. Use a new username like student001 or teacher001.", "danger")
        return redirect(url_for("admin_users"))
    db_execute(
        "INSERT INTO users (username,password,role,fullname,email,phone,status,created_date) VALUES (%s,%s,%s,%s,%s,%s,'Active',%s)",
        (username, hash_password(request.form["password"]), request.form["role"], request.form["fullname"].strip(), request.form.get("email", "").strip(), request.form.get("phone", "").strip(), datetime.date.today()),
    )
    flash("User created.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/toggle")
@require_login("Admin")
def admin_toggle_user(user_id):
    user = db_fetchone("SELECT status FROM users WHERE user_id=%s", (user_id,))
    if user:
        db_execute("UPDATE users SET status=%s WHERE user_id=%s", ("Inactive" if user["status"] == "Active" else "Active", user_id))
        flash("User status updated.", "success")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/delete")
@require_login("Admin")
def admin_delete_user(user_id):
    if user_id == 1:
        flash("System admin cannot be deleted.", "danger")
        return redirect(url_for("admin_users"))
    student = db_fetchone("SELECT student_id FROM students WHERE user_id=%s", (user_id,))
    if student:
        sid = student["student_id"]
        for table in ["student_subjects", "submissions", "attendance", "marks"]:
            db_execute(f"DELETE FROM {table} WHERE student_id=%s", (sid,))
        db_execute("DELETE FROM students WHERE student_id=%s", (sid,))
    teacher = db_fetchone("SELECT teacher_id FROM teachers WHERE user_id=%s", (user_id,))
    if teacher:
        tid = teacher["teacher_id"]
        db_execute("UPDATE subjects SET teacher_id=NULL WHERE teacher_id=%s", (tid,))
        db_execute("UPDATE timetable SET teacher_id=NULL WHERE teacher_id=%s", (tid,))
        db_execute("UPDATE classes SET class_teacher_id=NULL WHERE class_teacher_id=%s", (tid,))
        for table in ["study_materials", "assignments", "marks"]:
            db_execute(f"DELETE FROM {table} WHERE teacher_id=%s", (tid,))
        db_execute("DELETE FROM attendance WHERE marked_by=%s", (tid,))
        db_execute("DELETE FROM teachers WHERE teacher_id=%s", (tid,))
    db_execute("DELETE FROM notice_read WHERE user_id=%s", (user_id,))
    db_execute("DELETE FROM notices WHERE posted_by=%s", (user_id,))
    db_execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    flash("User and related data deleted.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/teachers", methods=["GET", "POST"])
@require_login("Admin")
def admin_teachers():
    if request.method == "POST":
        user_id = int(request.form["user_id"])
        if db_fetchone("SELECT teacher_id FROM teachers WHERE user_id=%s", (user_id,)):
            flash("Teacher profile already exists for that user.", "danger")
        else:
            db_execute(
                "INSERT INTO teachers (user_id,name,department,subjects,qualification,experience,address,joining_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (user_id, request.form["name"], request.form["department"], request.form.get("subjects", ""), request.form.get("qualification", ""), request.form.get("experience", "0"), request.form.get("address", ""), datetime.date.today()),
            )
            flash("Teacher profile created.", "success")
        return redirect(url_for("admin_teachers"))
    teachers = db_execute("SELECT * FROM teachers ORDER BY teacher_id", fetch=True)
    users = db_execute("SELECT * FROM users WHERE role='Teacher' AND user_id NOT IN (SELECT user_id FROM teachers)", fetch=True)
    form = f"""
    <form class="form-card" method="post"><h2>Add Teacher Profile</h2><div class="form-grid">
      <div><label>User Account *</label><select name="user_id" required>{option_tags(users, 'user_id', lambda u: f"{u['username']} ({u['fullname']})", blank=True)}</select></div>
      <div><label>Name *</label><input name="name" required></div>
      <div><label>Department *</label><input name="department" required></div>
      <div><label>Subjects</label><input name="subjects"></div>
      <div><label>Qualification</label><input name="qualification"></div>
      <div><label>Experience</label><input name="experience" value="0"></div>
      <div><label>Address</label><input name="address"></div>
    </div><div class="actions"><button>Save Teacher</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('admin_delete_teacher', teacher_id=row['teacher_id'])}' onsubmit=\"return confirm('Delete teacher and related data?')\"><button class='danger'>Delete</button></form>"
    body = "<h1>Teacher Management</h1>" + form + html_table(teachers, [("teacher_id", "ID"), ("name", "Name"), ("department", "Department"), ("subjects", "Subjects"), ("qualification", "Qualification"), ("experience", "Experience"), ("joining_date", "Joining Date")], actions)
    return render_page("Teachers", body, "Admin")


@app.post("/admin/teachers/<int:teacher_id>/delete")
@require_login("Admin")
def admin_delete_teacher(teacher_id):
    db_execute("UPDATE subjects SET teacher_id=NULL WHERE teacher_id=%s", (teacher_id,))
    db_execute("UPDATE timetable SET teacher_id=NULL WHERE teacher_id=%s", (teacher_id,))
    db_execute("UPDATE classes SET class_teacher_id=NULL WHERE class_teacher_id=%s", (teacher_id,))
    for table in ["study_materials", "assignments", "marks"]:
        db_execute(f"DELETE FROM {table} WHERE teacher_id=%s", (teacher_id,))
    db_execute("DELETE FROM attendance WHERE marked_by=%s", (teacher_id,))
    db_execute("DELETE FROM teachers WHERE teacher_id=%s", (teacher_id,))
    flash("Teacher deleted.", "success")
    return redirect(url_for("admin_teachers"))


@app.route("/admin/students", methods=["GET", "POST"])
@require_login("Admin")
def admin_students():
    if request.method == "POST":
        user_id = int(request.form["user_id"])
        if db_fetchone("SELECT student_id FROM students WHERE user_id=%s", (user_id,)):
            flash("Student profile already exists for that user.", "danger")
        else:
            db_execute(
                "INSERT INTO students (user_id,name,class,section,roll_no,dob,gender,address,parent_name,parent_phone,admission_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (user_id, request.form["name"], request.form["class"], request.form["section"], request.form["roll_no"], request.form["dob"], request.form["gender"], request.form.get("address", ""), request.form["parent_name"], request.form["parent_phone"], datetime.date.today()),
            )
            flash("Student profile created.", "success")
        return redirect(url_for("admin_students"))
    students = db_execute("SELECT * FROM students ORDER BY student_id", fetch=True)
    users = db_execute("SELECT * FROM users WHERE role='Student' AND user_id NOT IN (SELECT user_id FROM students)", fetch=True)
    form = f"""
    <form class="form-card" method="post"><h2>Add Student Profile</h2><div class="form-grid">
      <div><label>User Account *</label><select name="user_id" required>{option_tags(users, 'user_id', lambda u: f"{u['username']} ({u['fullname']})", blank=True)}</select></div>
      <div><label>Name *</label><input name="name" required></div><div><label>Class *</label><input name="class" required></div>
      <div><label>Section *</label><input name="section" required></div><div><label>Roll No *</label><input name="roll_no" required></div>
      <div><label>DOB *</label><input type="date" name="dob" required></div><div><label>Gender *</label><select name="gender"><option>Male</option><option>Female</option><option>Other</option></select></div>
      <div><label>Parent Name *</label><input name="parent_name" required></div><div><label>Parent Phone *</label><input name="parent_phone" required></div>
      <div><label>Address</label><input name="address"></div>
    </div><div class="actions"><button>Save Student</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('admin_delete_student', student_id=row['student_id'])}' onsubmit=\"return confirm('Delete student and related data?')\"><button class='danger'>Delete</button></form>"
    body = "<h1>Student Management</h1>" + form + html_table(students, [("student_id", "ID"), ("name", "Name"), ("class", "Class"), ("section", "Section"), ("roll_no", "Roll No"), ("gender", "Gender"), ("parent_name", "Parent"), ("parent_phone", "Parent Phone"), ("admission_date", "Admission")], actions)
    return render_page("Students", body, "Admin")


@app.post("/admin/students/<int:student_id>/delete")
@require_login("Admin")
def admin_delete_student(student_id):
    for table in ["student_subjects", "submissions", "attendance", "marks"]:
        db_execute(f"DELETE FROM {table} WHERE student_id=%s", (student_id,))
    db_execute("DELETE FROM students WHERE student_id=%s", (student_id,))
    flash("Student deleted.", "success")
    return redirect(url_for("admin_students"))


@app.route("/admin/subjects", methods=["GET", "POST"])
@require_login("Admin")
def admin_subjects():
    if request.method == "POST":
        teacher_id = request.form.get("teacher_id") or None
        db_execute(
            "INSERT INTO subjects (subject_name,subject_code,class,teacher_id,department) VALUES (%s,%s,%s,%s,%s)",
            (request.form["subject_name"], request.form["subject_code"], request.form["class"], teacher_id, request.form["department"]),
        )
        flash("Subject added.", "success")
        return redirect(url_for("admin_subjects"))
    subjects = db_execute("SELECT s.*, t.name AS teacher_name FROM subjects s LEFT JOIN teachers t ON t.teacher_id=s.teacher_id ORDER BY s.subject_id", fetch=True)
    teachers = db_execute("SELECT teacher_id,name FROM teachers", fetch=True)
    form = f"""
    <form class="form-card" method="post"><h2>Add Subject</h2><div class="form-grid">
      <div><label>Subject Name *</label><input name="subject_name" required></div><div><label>Subject Code *</label><input name="subject_code" required></div>
      <div><label>Class *</label><input name="class" required></div><div><label>Department *</label><input name="department" required></div>
      <div><label>Teacher</label><select name="teacher_id">{option_tags(teachers, 'teacher_id', lambda t: t['name'], blank=True)}</select></div>
    </div><div class="actions"><button>Save Subject</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('admin_delete_subject', subject_id=row['subject_id'])}' onsubmit=\"return confirm('Delete subject and related data?')\"><button class='danger'>Delete</button></form>"
    body = "<h1>Subject Management</h1>" + form + html_table(subjects, [("subject_id", "ID"), ("subject_name", "Name"), ("subject_code", "Code"), ("class", "Class"), ("teacher_name", "Teacher"), ("department", "Department")], actions)
    return render_page("Subjects", body, "Admin")


@app.post("/admin/subjects/<int:subject_id>/delete")
@require_login("Admin")
def admin_delete_subject(subject_id):
    for table in ["student_subjects", "attendance", "marks", "study_materials", "assignments", "timetable"]:
        db_execute(f"DELETE FROM {table} WHERE subject_id=%s", (subject_id,))
    db_execute("DELETE FROM subjects WHERE subject_id=%s", (subject_id,))
    flash("Subject deleted.", "success")
    return redirect(url_for("admin_subjects"))


@app.route("/admin/classes", methods=["GET", "POST"])
@require_login("Admin")
def admin_classes():
    if request.method == "POST":
        teacher_id = request.form.get("class_teacher_id") or None
        db_execute("INSERT INTO classes (class_name,section,class_teacher_id) VALUES (%s,%s,%s)", (request.form["class_name"], request.form["section"], teacher_id))
        flash("Class added.", "success")
        return redirect(url_for("admin_classes"))
    classes = db_execute("SELECT c.*, t.name AS teacher_name FROM classes c LEFT JOIN teachers t ON t.teacher_id=c.class_teacher_id ORDER BY c.class_name,c.section", fetch=True)
    teachers = db_execute("SELECT teacher_id,name FROM teachers", fetch=True)
    form = f"""
    <form class="form-card" method="post"><h2>Add Class/Section</h2><div class="form-grid">
      <div><label>Class *</label><input name="class_name" required></div><div><label>Section *</label><input name="section" required></div>
      <div><label>Class Teacher</label><select name="class_teacher_id">{option_tags(teachers, 'teacher_id', lambda t: t['name'], blank=True)}</select></div>
    </div><div class="actions"><button>Save Class</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('admin_delete_class', class_id=row['class_id'])}' onsubmit=\"return confirm('Delete class?')\"><button class='danger'>Delete</button></form>"
    body = "<h1>Class Management</h1>" + form + html_table(classes, [("class_id", "ID"), ("class_name", "Class"), ("section", "Section"), ("teacher_name", "Class Teacher")], actions)
    return render_page("Classes", body, "Admin")


@app.post("/admin/classes/<int:class_id>/delete")
@require_login("Admin")
def admin_delete_class(class_id):
    db_execute("DELETE FROM classes WHERE class_id=%s", (class_id,))
    flash("Class deleted.", "success")
    return redirect(url_for("admin_classes"))


@app.route("/admin/student-subjects", methods=["GET", "POST"])
@require_login("Admin")
def admin_student_subjects():
    if request.method == "POST":
        student_id = int(request.form["student_id"])
        if request.form.get("auto_class"):
            student = db_fetchone("SELECT class FROM students WHERE student_id=%s", (student_id,))
            subjects = db_execute("SELECT subject_id FROM subjects WHERE class=%s", (student["class"],), fetch=True) if student else []
            classmates = db_execute("SELECT student_id FROM students WHERE class=%s", (student["class"],), fetch=True) if student else []
            count = 0
            for st in classmates:
                for su in subjects:
                    if not db_fetchone("SELECT id FROM student_subjects WHERE student_id=%s AND subject_id=%s", (st["student_id"], su["subject_id"])):
                        db_execute("INSERT INTO student_subjects (student_id,subject_id,assigned_date) VALUES (%s,%s,%s)", (st["student_id"], su["subject_id"], datetime.date.today()))
                        count += 1
            flash(f"Assigned {count} subject links.", "success")
        else:
            subject_id = int(request.form["subject_id"])
            if not db_fetchone("SELECT id FROM student_subjects WHERE student_id=%s AND subject_id=%s", (student_id, subject_id)):
                db_execute("INSERT INTO student_subjects (student_id,subject_id,assigned_date) VALUES (%s,%s,%s)", (student_id, subject_id, datetime.date.today()))
                flash("Subject assigned.", "success")
            else:
                flash("That assignment already exists.", "warning")
        return redirect(url_for("admin_student_subjects"))
    students = db_execute("SELECT * FROM students ORDER BY name", fetch=True)
    subjects = db_execute("SELECT * FROM subjects ORDER BY subject_name", fetch=True)
    rows = db_execute("SELECT ss.id, s.name AS student_name, s.class, s.section, sub.subject_name, ss.assigned_date FROM student_subjects ss LEFT JOIN students s ON s.student_id=ss.student_id LEFT JOIN subjects sub ON sub.subject_id=ss.subject_id ORDER BY ss.id DESC", fetch=True)
    form = f"""
    <form class="form-card" method="post"><h2>Assign Subject</h2>
    <div class="info-box">💡 Use <b>Auto-Assign Whole Class</b> to assign all subjects of a class to all students in that class at once.</div>
    <div class="form-grid">
      <div><label>Student *</label><select name="student_id" required>{option_tags(students, 'student_id', lambda s: f"{s['name']} - Class {s['class']}-{s['section']}", blank=True)}</select></div>
      <div><label>Subject (leave blank for Auto-Assign)</label><select name="subject_id">{option_tags(subjects, 'subject_id', lambda s: f"{s['subject_name']} - Class {s['class']}", blank=True)}</select></div>
    </div><div class="actions"><button>Assign Subject</button><button name="auto_class" value="1" class="secondary">Auto-Assign Whole Class</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('admin_remove_student_subject', row_id=row['id'])}'><button class='danger'>Remove</button></form>"
    body = "<h1>Student Subject Assignment</h1>" + form + html_table(rows, [("id", "ID"), ("student_name", "Student"), ("class", "Class"), ("section", "Section"), ("subject_name", "Subject"), ("assigned_date", "Assigned Date")], actions)
    return render_page("Student Subjects", body, "Admin")


@app.post("/admin/student-subjects/<int:row_id>/remove")
@require_login("Admin")
def admin_remove_student_subject(row_id):
    db_execute("DELETE FROM student_subjects WHERE id=%s", (row_id,))
    flash("Assignment removed.", "success")
    return redirect(url_for("admin_student_subjects"))


@app.route("/admin/timetable", methods=["GET", "POST"])
@require_login("Admin")
def admin_timetable():
    if request.method == "POST":
        db_execute(
            "INSERT INTO timetable (day,period,class_name,section,subject_id,teacher_id,start_time,end_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (request.form["day"], request.form["period"], request.form["class_name"], request.form["section"], request.form["subject_id"], request.form["teacher_id"], request.form["start_time"], request.form["end_time"]),
        )
        flash("Timetable period added.", "success")
        return redirect(url_for("admin_timetable"))
    subjects = db_execute("SELECT subject_id,subject_name,class FROM subjects", fetch=True)
    teachers = db_execute("SELECT teacher_id,name FROM teachers", fetch=True)
    rows = db_execute("SELECT tt.*, sub.subject_name, t.name AS teacher_name FROM timetable tt LEFT JOIN subjects sub ON sub.subject_id=tt.subject_id LEFT JOIN teachers t ON t.teacher_id=tt.teacher_id ORDER BY FIELD(tt.day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), tt.period", fetch=True)
    form = f"""
    <form class="form-card" method="post"><h2>Add Period</h2><div class="form-grid">
      <div><label>Day *</label><select name="day">{''.join(f'<option>{d}</option>' for d in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'])}</select></div>
      <div><label>Period *</label><input type="number" name="period" min="1" value="1" required></div><div><label>Class *</label><input name="class_name" required></div>
      <div><label>Section *</label><input name="section" required></div><div><label>Subject *</label><select name="subject_id" required>{option_tags(subjects, 'subject_id', lambda s: f"{s['subject_name']} - Class {s['class']}", blank=True)}</select></div>
      <div><label>Teacher *</label><select name="teacher_id" required>{option_tags(teachers, 'teacher_id', lambda t: t['name'], blank=True)}</select></div>
      <div><label>Start Time</label><input name="start_time" value="08:00"></div><div><label>End Time</label><input name="end_time" value="09:00"></div>
    </div><div class="actions"><button>Save Period</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('admin_delete_period', timetable_id=row['timetable_id'])}'><button class='danger'>Delete</button></form>"
    body = "<h1>Timetable Management</h1>" + form + html_table(rows, [("timetable_id", "ID"), ("day", "Day"), ("period", "Period"), ("class_name", "Class"), ("section", "Section"), ("subject_name", "Subject"), ("teacher_name", "Teacher"), ("start_time", "Start"), ("end_time", "End")], actions)
    return render_page("Timetable", body, "Admin")


@app.post("/admin/timetable/<int:timetable_id>/delete")
@require_login("Admin")
def admin_delete_period(timetable_id):
    db_execute("DELETE FROM timetable WHERE timetable_id=%s", (timetable_id,))
    flash("Period deleted.", "success")
    return redirect(url_for("admin_timetable"))


@app.route("/admin/notices", methods=["GET", "POST"])
@require_login("Admin")
def admin_notices():
    if request.method == "POST":
        db_execute(
            "INSERT INTO notices (title,content,posted_by,posted_date,target_role) VALUES (%s,%s,%s,%s,%s)",
            (request.form["title"], request.form["content"], session["user_id"], datetime.datetime.now(), request.form["target_role"]),
        )
        flash("Notice posted.", "success")
        return redirect(url_for("admin_notices"))
    notices = db_execute("SELECT * FROM notices ORDER BY notice_id DESC", fetch=True)
    form = """
    <form class="form-card" method="post"><h2>Post Notice</h2>
      <label>Title *</label><input name="title" required>
      <label>Content *</label><textarea name="content" required></textarea>
      <label>Target Audience *</label><select name="target_role"><option>All</option><option>Student</option><option>Teacher</option><option>Admin</option></select>
      <div class="actions"><button>Post Notice</button></div>
    </form>
    """
    body = "<h1>Notices</h1>" + form + render_notices(notices, markable=False)
    return render_page("Notices", body, "Admin")


@app.route("/admin/reports")
@require_login("Admin")
def admin_reports():
    att = db_execute("SELECT a.student_id, s.name, s.class, COUNT(*) AS total, SUM(a.status='Present') AS present FROM attendance a LEFT JOIN students s ON s.student_id=a.student_id GROUP BY a.student_id", fetch=True)
    for r in att:
        total = r["total"] or 0
        present = int(r["present"] or 0)
        r["absent"] = total - present
        r["percentage"] = f"{present / total * 100:.1f}%" if total else "0%"
    academic = db_execute("SELECT m.student_id, s.name, s.class, AVG(m.marks_obtained/m.total_marks*100) AS avg_pct FROM marks m LEFT JOIN students s ON s.student_id=m.student_id WHERE m.total_marks>0 GROUP BY m.student_id ORDER BY avg_pct DESC", fetch=True)
    for i, r in enumerate(academic, 1):
        avg = float(r["avg_pct"] or 0)
        grade, gpa = calculate_grade(avg)
        r["average"] = f"{avg:.1f}%"
        r["grade"] = grade
        r["gpa"] = f"{gpa:.1f}"
        r["rank"] = i
    teachers = db_execute("SELECT t.teacher_id,t.name,t.department, COUNT(DISTINCT sub.subject_id) AS subjects_count, COUNT(DISTINCT m.mark_id) AS marks_entered, COUNT(DISTINCT a.date) AS attendance_sessions FROM teachers t LEFT JOIN subjects sub ON sub.teacher_id=t.teacher_id LEFT JOIN marks m ON m.teacher_id=t.teacher_id LEFT JOIN attendance a ON a.marked_by=t.teacher_id GROUP BY t.teacher_id", fetch=True)
    subjects = db_execute("SELECT sub.subject_id, sub.subject_name, sub.class, COUNT(m.mark_id) AS total_entries, AVG(m.marks_obtained/m.total_marks*100) AS avg_pct FROM subjects sub LEFT JOIN marks m ON m.subject_id=sub.subject_id GROUP BY sub.subject_id", fetch=True)
    for r in subjects:
        r["average"] = f"{float(r['avg_pct'] or 0):.1f}%" if r["total_entries"] else "N/A"
    body = "<h1>Reports & Analytics</h1>"
    body += "<h2>Attendance Report</h2>" + html_table(att, [("student_id", "Student ID"), ("name", "Name"), ("class", "Class"), ("total", "Total Classes"), ("present", "Present"), ("absent", "Absent"), ("percentage", "Percentage")])
    body += "<h2>Academic Performance</h2>" + html_table(academic, [("student_id", "Student ID"), ("name", "Name"), ("class", "Class"), ("average", "Average"), ("grade", "Grade"), ("gpa", "GPA"), ("rank", "Rank")])
    body += "<h2>Teacher Performance</h2>" + html_table(teachers, [("teacher_id", "Teacher ID"), ("name", "Name"), ("department", "Department"), ("subjects_count", "Subjects"), ("marks_entered", "Marks Entered"), ("attendance_sessions", "Attendance Sessions")])
    body += "<h2>Subject Analysis</h2>" + html_table(subjects, [("subject_id", "Subject ID"), ("subject_name", "Subject"), ("class", "Class"), ("total_entries", "Entries"), ("average", "Average")])
    return render_page("Reports", body, "Admin")


# ─────────────────────────────────────────────
# TEACHER ROUTES
# ─────────────────────────────────────────────

def teacher_info():
    return db_fetchone("SELECT * FROM teachers WHERE user_id=%s", (session["user_id"],))


@app.route("/teacher/dashboard")
@require_login("Teacher")
def teacher_dashboard():
    teacher = teacher_info()
    if not teacher:
        flash("Teacher profile not found. Ask admin to create your profile.", "danger")
        return redirect(url_for("logout"))
    tid = teacher["teacher_id"]
    body = f"<h1>Welcome, {escape(teacher['name'])}</h1>"
    body += stats_cards([
        ("My Subjects", db_fetchone("SELECT COUNT(*) AS c FROM subjects WHERE teacher_id=%s", (tid,))["c"]),
        ("Attendance Sessions", db_fetchone("SELECT COUNT(DISTINCT date) AS c FROM attendance WHERE marked_by=%s", (tid,))["c"]),
        ("Marks Entered", db_fetchone("SELECT COUNT(*) AS c FROM marks WHERE teacher_id=%s", (tid,))["c"]),
        ("Assignments Created", db_fetchone("SELECT COUNT(*) AS c FROM assignments WHERE teacher_id=%s", (tid,))["c"]),
    ])
    rows = db_execute(
        "SELECT a.student_id, s.name, s.class, COUNT(*) AS total, SUM(a.status='Present') AS present FROM attendance a LEFT JOIN students s ON s.student_id=a.student_id WHERE a.marked_by=%s GROUP BY a.student_id",
        (tid,), fetch=True
    )
    for r in rows:
        total = r["total"] or 0
        present = int(r["present"] or 0)
        r["absent"] = total - present
        r["percentage"] = f"{present / total * 100:.1f}%" if total else "0%"
    body += "<h2>Student Attendance Summary</h2>" + html_table(rows, [("student_id", "Student ID"), ("name", "Name"), ("class", "Class"), ("total", "Total"), ("present", "Present"), ("absent", "Absent"), ("percentage", "Attendance %")])
    return render_page("Teacher Dashboard", body, "Teacher")


@app.route("/teacher/subjects")
@require_login("Teacher")
def teacher_subjects():
    teacher = teacher_info()
    rows = db_execute("SELECT * FROM subjects WHERE teacher_id=%s", (teacher["teacher_id"],), fetch=True) if teacher else []
    body = "<h1>My Assigned Subjects</h1>" + html_table(rows, [("subject_id", "ID"), ("subject_name", "Subject"), ("subject_code", "Code"), ("class", "Class"), ("department", "Department")])
    return render_page("My Subjects", body, "Teacher")


@app.route("/teacher/timetable")
@require_login("Teacher")
def teacher_timetable():
    teacher = teacher_info()
    rows = db_execute(
        "SELECT tt.*, sub.subject_name, t.name AS teacher_name FROM timetable tt LEFT JOIN subjects sub ON sub.subject_id=tt.subject_id LEFT JOIN teachers t ON t.teacher_id=tt.teacher_id WHERE tt.teacher_id=%s OR sub.teacher_id=%s ORDER BY FIELD(tt.day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), tt.period",
        (teacher["teacher_id"], teacher["teacher_id"]), fetch=True
    )
    body = "<h1>My Timetable</h1>" + html_table(rows, [("day", "Day"), ("period", "Period"), ("class_name", "Class"), ("section", "Section"), ("subject_name", "Subject"), ("teacher_name", "Teacher"), ("start_time", "Start"), ("end_time", "End")])
    return render_page("Timetable", body, "Teacher")

@app.route("/teacher/attendance", methods=["GET", "POST"])
@require_login("Teacher")
def teacher_attendance():
    teacher = teacher_info()
    if not teacher:
        flash("Teacher profile not found. Ask admin to create your profile.", "danger")
        return redirect(url_for("logout"))
    tid = teacher["teacher_id"]

    # Subjects assigned to this teacher; fallback to all subjects
    subjects = db_execute("SELECT * FROM subjects WHERE teacher_id=%s", (tid,), fetch=True)
    if not subjects:
        subjects = db_execute("SELECT * FROM subjects", fetch=True) or []

    selected_subject = request.values.get("subject_id", "").strip()
    date_value = request.values.get("date") or str(datetime.date.today())

    if request.method == "POST":
        if not selected_subject:
            flash("Please select a subject before saving attendance.", "danger")
            return redirect(url_for("teacher_attendance"))
        # Delete existing records for this subject+date and re-insert
        db_execute("DELETE FROM attendance WHERE subject_id=%s AND date=%s AND marked_by=%s",
                   (selected_subject, date_value, tid))
        saved = 0
        for key, value in request.form.items():
            if key.startswith("student_"):
                try:
                    sid = int(key.split("_", 1)[1])
                    db_execute(
                        "INSERT INTO attendance (student_id,date,subject_id,status,marked_by) VALUES (%s,%s,%s,%s,%s)",
                        (sid, date_value, selected_subject, value, tid)
                    )
                    saved += 1
                except Exception:
                    pass
        flash(f"Attendance saved for {saved} student(s).", "success")
        return redirect(url_for("teacher_attendance", subject_id=selected_subject, date=date_value))

    # ── Build the load-students form ──
    subject_options = option_tags(subjects, 'subject_id',
                                   lambda s: f"{s['subject_name']} - Class {s['class']}",
                                   selected_subject, True)
    form = f"""
    <form class="form-card" method="get">
      <h2>Load Students</h2>
      <div class="form-grid">
        <div><label>Subject *</label><select name="subject_id" required>{subject_options}</select></div>
        <div><label>Date</label><input type="date" name="date" value="{escape(date_value)}"></div>
      </div>
      <div class="actions"><button>Load Students</button></div>
    </form>
    """

    # ── Load students if a subject is selected ──
    students = []
    subject = None
    if selected_subject:
        subject = db_fetchone("SELECT * FROM subjects WHERE subject_id=%s", (selected_subject,))
        if not subject:
            flash("The selected subject could not be found. Please choose a valid subject.", "danger")
            return redirect(url_for("teacher_attendance"))
        # PRIMARY: students enrolled via student_subjects
        students = db_execute(
            """SELECT DISTINCT s.* FROM students s
               JOIN student_subjects ss ON ss.student_id = s.student_id
               WHERE ss.subject_id = %s
               ORDER BY s.roll_no, s.name""",
            (selected_subject,), fetch=True
        )
        # FALLBACK: if no enrollments, load by class name
        if not students:
            students = db_execute(
                "SELECT * FROM students WHERE class=%s ORDER BY roll_no, name",
                (subject["class"],), fetch=True
            ) or []

    if selected_subject and not students:
        form += "<div class='info-box'>⚠️ No students found for this subject. Go to <b>Admin → Student Subjects</b> and assign students to this subject, or use <b>Auto-Assign Whole Class</b>.</div>"

    if students:
        # Load existing attendance for pre-selecting dropdowns
        existing_records = db_execute(
            "SELECT student_id, status FROM attendance WHERE subject_id=%s AND date=%s AND marked_by=%s",
            (selected_subject, date_value, tid), fetch=True
        ) or []
        existing_map = {r["student_id"]: r["status"] for r in existing_records}

        rows_html = ""
        for s in students:
            current_status = existing_map.get(s["student_id"], "Present")
            present_sel = " selected" if current_status == "Present" else ""
            absent_sel = " selected" if current_status == "Absent" else ""
            rows_html += (
                f"<tr>"
                f"<td>{escape(str(s.get('roll_no', '')))}</td>"
                f"<td>{escape(s['name'])}</td>"
                f"<td>{escape(str(s.get('class', '')))}-{escape(str(s.get('section', '')))}</td>"
                f"<td>"
                f"<select name='student_{s['student_id']}' style='width:auto'>"
                f"<option{present_sel}>Present</option>"
                f"<option{absent_sel}>Absent</option>"
                f"</select>"
                f"</td>"
                f"</tr>"
            )

        form += f"""
        <form method="post" class="form-card">
          <input type="hidden" name="subject_id" value="{escape(selected_subject)}">
          <input type="hidden" name="date" value="{escape(date_value)}">
          <h2>Mark Attendance — {escape(subject['subject_name'] if subject else '')} | {escape(date_value)} | {len(students)} students</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Roll No</th><th>Name</th><th>Class</th><th>Status</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>
          <div class="actions">
            <button class="success">Save Attendance</button>
          </div>
        </form>
        """

    body = "<h1>Mark Student Attendance</h1>" + form
    return render_page("Mark Attendance", body, "Teacher")


@app.route("/teacher/marks", methods=["GET", "POST"])
@require_login("Teacher")
def teacher_marks():
    teacher = teacher_info()
    tid = teacher["teacher_id"]
    subjects = db_execute("SELECT * FROM subjects WHERE teacher_id=%s", (tid,), fetch=True) or db_execute("SELECT * FROM subjects", fetch=True)
    students = db_execute("SELECT * FROM students ORDER BY name", fetch=True)
    if request.method == "POST":
        marks = float(request.form["marks_obtained"])
        total = float(request.form["total_marks"])
        if marks < 0 or total <= 0 or marks > total:
            flash("Marks must be between 0 and total marks.", "danger")
        else:
            db_execute(
                "INSERT INTO marks (student_id,subject_id,exam_type,marks_obtained,total_marks,date,teacher_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (request.form["student_id"], request.form["subject_id"], request.form["exam_type"], marks, total, datetime.date.today(), tid)
            )
            flash("Marks saved.", "success")
        return redirect(url_for("teacher_marks"))
    rows = db_execute(
        "SELECT m.*, s.name AS student_name, sub.subject_name FROM marks m LEFT JOIN students s ON s.student_id=m.student_id LEFT JOIN subjects sub ON sub.subject_id=m.subject_id WHERE m.teacher_id=%s ORDER BY m.date DESC",
        (tid,), fetch=True
    )
    for r in rows:
        pct = float(r["marks_obtained"] or 0) / float(r["total_marks"] or 1) * 100
        r["percentage"] = f"{pct:.1f}%"
        r["grade"] = calculate_grade(pct)[0]
    form = f"""
    <form class="form-card" method="post"><h2>Add Marks</h2><div class="form-grid">
      <div><label>Subject *</label><select name="subject_id" required>{option_tags(subjects, 'subject_id', lambda s: s['subject_name'], blank=True)}</select></div>
      <div><label>Student *</label><select name="student_id" required>{option_tags(students, 'student_id', lambda s: f"{s['name']} - Class {s['class']}", blank=True)}</select></div>
      <div><label>Exam Type</label><select name="exam_type"><option>Internal</option><option>Mid-Term</option><option>Final</option><option>Assignment</option><option>Quiz</option></select></div>
      <div><label>Marks Obtained</label><input type="number" step="0.01" name="marks_obtained" required></div>
      <div><label>Total Marks</label><input type="number" step="0.01" name="total_marks" required></div>
    </div><div class="actions"><button>Save Marks</button></div></form>
    """
    body = "<h1>Add / Update Student Marks</h1>" + form + html_table(rows, [("mark_id", "ID"), ("student_name", "Student"), ("subject_name", "Subject"), ("exam_type", "Exam"), ("marks_obtained", "Marks"), ("total_marks", "Total"), ("percentage", "Percentage"), ("grade", "Grade"), ("date", "Date")])
    return render_page("Marks", body, "Teacher")


@app.route("/teacher/materials", methods=["GET", "POST"])
@require_login("Teacher")
def teacher_materials():
    teacher = teacher_info()
    tid = teacher["teacher_id"]
    subjects = db_execute("SELECT * FROM subjects WHERE teacher_id=%s", (tid,), fetch=True) or db_execute("SELECT * FROM subjects", fetch=True)
    if request.method == "POST":
        try:
            path = save_upload(request.files.get("file"))
            db_execute(
                "INSERT INTO study_materials (subject_id,title,description,teacher_id,upload_date,file_path) VALUES (%s,%s,%s,%s,%s,%s)",
                (request.form["subject_id"], request.form["title"], request.form.get("description", ""), tid, datetime.date.today(), path)
            )
            flash("Material uploaded.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("teacher_materials"))
    rows = db_execute(
        "SELECT sm.*, sub.subject_name FROM study_materials sm LEFT JOIN subjects sub ON sub.subject_id=sm.subject_id WHERE sm.teacher_id=%s ORDER BY sm.upload_date DESC",
        (tid,), fetch=True
    )
    for r in rows:
        r["file_name"] = os.path.basename(str(r.get("file_path") or ""))
    form = f"""
    <form class="form-card" method="post" enctype="multipart/form-data"><h2>Upload Material</h2><div class="form-grid">
      <div><label>Subject *</label><select name="subject_id" required>{option_tags(subjects, 'subject_id', lambda s: s['subject_name'], blank=True)}</select></div>
      <div><label>Title *</label><input name="title" required></div><div><label>Description</label><input name="description"></div>
      <div><label>File *</label><input type="file" name="file" required></div>
    </div><div class="actions"><button>Upload</button></div></form>
    """
    def actions(row):
        delete_form = f"<form class='inline-form' method='post' action='{url_for('teacher_delete_material', material_id=row['material_id'])}' onsubmit=\"return confirm('Delete this material?')\"><button class='danger'>Delete</button></form>"
        download_link = f"<a class='btn' href='{url_for('download_file', kind='material', item_id=row['material_id'])}'>Open</a>" if row.get("file_path") else ""
        return f"{download_link} {delete_form}"
    body = "<h1>Study Materials</h1>" + form + html_table(rows, [("material_id", "ID"), ("subject_name", "Subject"), ("title", "Title"), ("description", "Description"), ("upload_date", "Date"), ("file_name", "File")], actions)
    return render_page("Materials", body, "Teacher")

@app.post("/teacher/materials/<int:material_id>/delete")
@require_login("Teacher")
def teacher_delete_material(material_id):
    teacher = teacher_info()
    row = db_fetchone("SELECT teacher_id FROM study_materials WHERE material_id=%s", (material_id,))
    if not row or row["teacher_id"] != teacher["teacher_id"]:
        flash("Material not found or permission denied.", "danger")
    else:
        db_execute("DELETE FROM study_materials WHERE material_id=%s", (material_id,))
        flash("Material deleted.", "success")
    return redirect(url_for("teacher_materials"))


@app.route("/teacher/assignments", methods=["GET", "POST"])
@require_login("Teacher")
def teacher_assignments():
    teacher = teacher_info()
    tid = teacher["teacher_id"]
    subjects = db_execute("SELECT * FROM subjects WHERE teacher_id=%s", (tid,), fetch=True) or db_execute("SELECT * FROM subjects", fetch=True)
    if request.method == "POST":
        try:
            path = save_upload(request.files.get("file")) if request.files.get("file") and request.files["file"].filename else ""
            db_execute(
                "INSERT INTO assignments (subject_id,class_name,section,title,description,teacher_id,assigned_date,due_date,file_path) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (request.form["subject_id"], request.form["class_name"], request.form.get("section", "All"), request.form["title"], request.form.get("description", ""), tid, datetime.date.today(), request.form["due_date"], path)
            )
            flash("Assignment created.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("teacher_assignments"))
    rows = db_execute(
        "SELECT a.*, sub.subject_name, (SELECT COUNT(*) FROM submissions s WHERE s.assignment_id=a.assignment_id) AS submissions FROM assignments a LEFT JOIN subjects sub ON sub.subject_id=a.subject_id WHERE a.teacher_id=%s ORDER BY a.due_date DESC",
        (tid,), fetch=True
    )
    subs = db_execute(
        "SELECT subm.*, a.title AS assignment_title, s.name AS student_name FROM submissions subm JOIN assignments a ON a.assignment_id=subm.assignment_id LEFT JOIN students s ON s.student_id=subm.student_id WHERE a.teacher_id=%s ORDER BY subm.submitted_date DESC",
        (tid,), fetch=True
    )
    form = f"""
    <form class="form-card" method="post" enctype="multipart/form-data"><h2>Create Assignment</h2><div class="form-grid">
      <div><label>Subject *</label><select name="subject_id" required>{option_tags(subjects, 'subject_id', lambda s: s['subject_name'], blank=True)}</select></div>
      <div><label>Class *</label><input name="class_name" required></div><div><label>Section</label><input name="section" value="All"></div>
      <div><label>Title *</label><input name="title" required></div><div><label>Due Date *</label><input type="date" name="due_date" required></div>
      <div><label>Attach File</label><input type="file" name="file"></div>
    </div><label>Description</label><textarea name="description"></textarea><div class="actions"><button>Create Assignment</button></div></form>
    """
    def actions(row):
        return f"<form class='inline-form' method='post' action='{url_for('teacher_delete_assignment', assignment_id=row['assignment_id'])}'><button class='danger'>Delete</button></form>"
    body = "<h1>Assignments</h1>" + form + "<h2>My Assignments</h2>" + html_table(rows, [("assignment_id", "ID"), ("subject_name", "Subject"), ("class_name", "Class"), ("section", "Section"), ("title", "Title"), ("due_date", "Due"), ("submissions", "Submissions")], actions)
    body += "<h2>Review Submissions</h2>" + html_table(subs, [("submission_id", "Sub ID"), ("assignment_title", "Assignment"), ("student_name", "Student"), ("submitted_date", "Submitted"), ("status", "Status"), ("grade", "Grade"), ("feedback", "Feedback")], lambda r: f"<a class='btn' href='{url_for('grade_submission', submission_id=r['submission_id'])}'>Grade</a>")
    return render_page("Assignments", body, "Teacher")


@app.post("/teacher/assignments/<int:assignment_id>/delete")
@require_login("Teacher")
def teacher_delete_assignment(assignment_id):
    db_execute("DELETE FROM submissions WHERE assignment_id=%s", (assignment_id,))
    db_execute("DELETE FROM assignments WHERE assignment_id=%s", (assignment_id,))
    flash("Assignment deleted.", "success")
    return redirect(url_for("teacher_assignments"))


@app.route("/teacher/submissions/<int:submission_id>/grade", methods=["GET", "POST"])
@require_login("Teacher")
def grade_submission(submission_id):
    if request.method == "POST":
        db_execute(
            "UPDATE submissions SET grade=%s,feedback=%s,status='Graded' WHERE submission_id=%s",
            (request.form["grade"], request.form.get("feedback", ""), submission_id)
        )
        flash("Submission graded.", "success")
        return redirect(url_for("teacher_assignments"))
    sub = db_fetchone(
        "SELECT subm.*, a.title, s.name AS student_name FROM submissions subm LEFT JOIN assignments a ON a.assignment_id=subm.assignment_id LEFT JOIN students s ON s.student_id=subm.student_id WHERE subm.submission_id=%s",
        (submission_id,)
    )
    body = f"""
    <h1>Grade Submission</h1>
    <div class="card form-card"><p><b>Assignment:</b> {escape(sub['title'])}</p><p><b>Student:</b> {escape(sub['student_name'])}</p></div>
    <form class="form-card" method="post">
      <label>Grade</label>
      <select name="grade"><option>A+</option><option>A</option><option>B+</option><option>B</option><option>C+</option><option>C</option><option>D</option><option>F</option><option>Pending Review</option></select>
      <label>Feedback</label><textarea name="feedback">{escape(sub.get('feedback') or '')}</textarea>
      <div class="actions"><button>Save Grade</button></div>
    </form>
    """
    return render_page("Grade Submission", body, "Teacher")


# ─────────────────────────────────────────────
# STUDENT ROUTES
# ─────────────────────────────────────────────

def student_info():
    return db_fetchone("SELECT * FROM students WHERE user_id=%s", (session["user_id"],))


@app.route("/student/dashboard")
@require_login("Student")
def student_dashboard():
    student = student_info()
    if not student:
        flash("Student profile not found. Ask admin to create your profile.", "danger")
        return redirect(url_for("logout"))
    sid = student["student_id"]
    att = db_fetchone("SELECT COUNT(*) AS total, SUM(status='Present') AS present FROM attendance WHERE student_id=%s", (sid,))
    total = att["total"] or 0 if att else 0
    present = int(att["present"] or 0) if att else 0
    avg = db_fetchone("SELECT AVG(marks_obtained/total_marks*100) AS pct FROM marks WHERE student_id=%s AND total_marks>0", (sid,))
    avg_pct = float(avg["pct"] or 0) if avg and avg["pct"] else 0
    grade, _ = calculate_grade(avg_pct)
    pending = db_fetchone(
        "SELECT COUNT(*) AS c FROM assignments a WHERE a.class_name=%s AND a.section IN ('All',%s) AND a.assignment_id NOT IN (SELECT assignment_id FROM submissions WHERE student_id=%s)",
        (student["class"], student["section"], sid)
    )["c"]
    body = f"<h1>Hello, {escape(student['name'])}</h1>"
    body += stats_cards([
        ("Class", f"{student['class']}-{student['section']}"),
        ("Attendance", f"{present / total * 100:.1f}%" if total else "0%"),
        ("Academic Average", f"{avg_pct:.1f}% {grade}"),
        ("Pending Assignments", pending),
    ])
    notices = db_execute("SELECT * FROM notices WHERE target_role IN ('All','Student') ORDER BY notice_id DESC LIMIT 3", fetch=True)
    body += "<h2>Recent Notices</h2>" + render_notices(notices, markable=False)
    return render_page("Student Dashboard", body, "Student")


@app.route("/student/timetable")
@require_login("Student")
def student_timetable():
    student = student_info()
    student_class = student.get("class", "") if student else ""
    student_section = student.get("section", "") if student else ""
    rows = db_execute(
        "SELECT tt.*, sub.subject_name, t.name AS teacher_name FROM timetable tt LEFT JOIN subjects sub ON sub.subject_id=tt.subject_id LEFT JOIN teachers t ON t.teacher_id=tt.teacher_id WHERE COALESCE(TRIM(LOWER(tt.class_name)),'') = COALESCE(TRIM(LOWER(%s)),'') AND (COALESCE(TRIM(LOWER(tt.section)),'') = 'all' OR COALESCE(TRIM(LOWER(tt.section)),'') = COALESCE(TRIM(LOWER(%s)),'') OR COALESCE(TRIM(LOWER(%s)),'') = '' OR tt.section='' OR tt.section IS NULL) ORDER BY FIELD(tt.day,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'), tt.period",
        (student_class, student_section, student_section), fetch=True
    )
    if not rows:
        body = f"<h1>My Timetable</h1><div class='info-box'>No timetable entries found for class {escape(student_class)} section {escape(student_section)}. Ask admin to verify the timetable class/section values.</div>"
    else:
        body = "<h1>My Timetable</h1>" + html_table(rows, [("day", "Day"), ("period", "Period"), ("subject_name", "Subject"), ("teacher_name", "Teacher"), ("start_time", "Start"), ("end_time", "End")])
    return render_page("Timetable", body, "Student")


@app.route("/student/attendance")
@require_login("Student")
def student_attendance():
    student = student_info()
    rows = db_execute(
        "SELECT a.*, sub.subject_name FROM attendance a LEFT JOIN subjects sub ON sub.subject_id=a.subject_id WHERE a.student_id=%s ORDER BY a.date DESC",
        (student["student_id"],), fetch=True
    )
    total = len(rows)
    present = sum(1 for r in rows if r["status"] == "Present")
    body = "<h1>My Attendance Record</h1>" + stats_cards([
        ("Total Classes", total), ("Present", present),
        ("Absent", total - present), ("Attendance %", f"{present / total * 100:.1f}%" if total else "0%")
    ])
    body += html_table(rows, [("date", "Date"), ("subject_name", "Subject"), ("status", "Status")])
    return render_page("Attendance", body, "Student")


@app.route("/student/marks")
@require_login("Student")
def student_marks():
    student = student_info()
    rows = db_execute(
        "SELECT m.*, sub.subject_name FROM marks m LEFT JOIN subjects sub ON sub.subject_id=m.subject_id WHERE m.student_id=%s ORDER BY m.date DESC",
        (student["student_id"],), fetch=True
    )
    for r in rows:
        pct = float(r["marks_obtained"] or 0) / float(r["total_marks"] or 1) * 100
        r["percentage"] = f"{pct:.1f}%"
        r["grade"] = calculate_grade(pct)[0]
    avg = sum(float(r["percentage"].replace("%", "")) for r in rows) / len(rows) if rows else 0
    body = "<h1>My Marks & Results</h1>" + stats_cards([
        ("Overall Average", f"{avg:.1f}%"), ("Grade", calculate_grade(avg)[0]), ("Entries", len(rows))
    ])
    body += html_table(rows, [("subject_name", "Subject"), ("exam_type", "Exam"), ("marks_obtained", "Marks"), ("total_marks", "Total"), ("percentage", "Percentage"), ("grade", "Grade"), ("date", "Date")])
    return render_page("Marks", body, "Student")


@app.route("/student/materials")
@require_login("Student")
def student_materials():
    student = student_info()
    rows = db_execute(
        "SELECT sm.*, sub.subject_name FROM study_materials sm LEFT JOIN subjects sub ON sub.subject_id=sm.subject_id LEFT JOIN student_subjects ss ON ss.subject_id=sm.subject_id AND ss.student_id=%s WHERE sub.class=%s OR ss.student_id=%s ORDER BY sm.upload_date DESC",
        (student["student_id"], student["class"], student["student_id"]), fetch=True
    )
    for r in rows:
        r["file_name"] = os.path.basename(str(r.get("file_path") or ""))
    body = "<h1>Study Materials</h1>" + html_table(
        rows,
        [("material_id", "ID"), ("subject_name", "Subject"), ("title", "Title"), ("description", "Description"), ("upload_date", "Date"), ("file_name", "File")],
        lambda r: f"<a class='btn' href='{url_for('download_file', kind='material', item_id=r['material_id'])}'>Open</a>" if r.get("file_path") else ""
    )
    return render_page("Materials", body, "Student")


@app.route("/student/assignments", methods=["GET", "POST"])
@require_login("Student")
def student_assignments():
    student = student_info()
    sid = student["student_id"]
    if request.method == "POST":
        assignment = db_fetchone("SELECT * FROM assignments WHERE assignment_id=%s", (request.form["assignment_id"],))
        status = "Submitted"
        if assignment and assignment.get("due_date") and datetime.date.today() > assignment["due_date"]:
            status = "Late"
        try:
            path = save_upload(request.files.get("file")) if request.files.get("file") and request.files["file"].filename else ""
            db_execute(
                "INSERT INTO submissions (assignment_id,student_id,submitted_date,file_path,status,grade,feedback) VALUES (%s,%s,%s,%s,%s,'','')",
                (request.form["assignment_id"], sid, datetime.date.today(), path, status)
            )
            flash(f"Assignment {status.lower()}.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("student_assignments"))
    rows = db_execute(
        "SELECT a.*, sub.subject_name, s.status AS submit_status, s.grade, s.feedback FROM assignments a LEFT JOIN subjects sub ON sub.subject_id=a.subject_id LEFT JOIN submissions s ON s.assignment_id=a.assignment_id AND s.student_id=%s WHERE a.class_name=%s AND a.section IN ('All',%s) ORDER BY a.due_date",
        (sid, student["class"], student["section"]), fetch=True
    )
    def actions(row):
        if row.get("submit_status"):
            return escape(f"{row['submit_status']} {row.get('grade') or ''}")
        return f"<form method='post' enctype='multipart/form-data'><input type='hidden' name='assignment_id' value='{row['assignment_id']}'><input type='file' name='file'><button>Submit</button></form>"
    body = "<h1>My Assignments</h1>" + html_table(rows, [("assignment_id", "ID"), ("subject_name", "Subject"), ("title", "Title"), ("description", "Description"), ("due_date", "Due"), ("submit_status", "Status"), ("grade", "Grade"), ("feedback", "Feedback")], actions)
    return render_page("Assignments", body, "Student")


# ─────────────────────────────────────────────
# SHARED ROUTES
# ─────────────────────────────────────────────

def render_notices(notices, markable=True):
    if not notices:
        return "<p class='muted'>No notices available.</p>"
    read_ids = set()
    if session.get("user_id"):
        recs = db_execute("SELECT notice_id FROM notice_read WHERE user_id=%s", (session["user_id"],), fetch=True)
        read_ids = {str(r["notice_id"]) for r in recs}
    html = []
    for notice in notices:
        unread = str(notice["notice_id"]) not in read_ids
        btn = ""
        css_class = "unread" if unread else ""
        new_badge = '<span class="badge">NEW</span>' if unread else ""
        if markable and unread:
            btn = f"<form method='post' action='{url_for('mark_notice_read', notice_id=notice['notice_id'])}'><button class='secondary'>Mark as Read</button></form>"
        html.append(f"<div class='notice {css_class}'><h2>{escape(notice['title'])} {new_badge}</h2><p>{escape(notice['content'])}</p><p class='muted'>{escape(str(notice['posted_date']))} | {escape(notice['target_role'])}</p>{btn}</div>")
    return "".join(html)


@app.route("/notices")
@require_login()
def role_notices():
    notices = db_execute("SELECT * FROM notices WHERE target_role IN ('All',%s) ORDER BY notice_id DESC", (session["role"],), fetch=True)
    return render_page("Notices", "<h1>Notices & Announcements</h1>" + render_notices(notices), session["role"])


@app.post("/notices/<int:notice_id>/read")
@require_login()
def mark_notice_read(notice_id):
    if not db_fetchone("SELECT notice_id FROM notice_read WHERE user_id=%s AND notice_id=%s", (session["user_id"], notice_id)):
        db_execute("INSERT INTO notice_read (user_id,notice_id,read_date) VALUES (%s,%s,%s)", (session["user_id"], notice_id, datetime.datetime.now()))
    return redirect(url_for("role_notices"))


@app.route("/profile", methods=["GET", "POST"])
@require_login()
def profile():
    user = db_fetchone("SELECT * FROM users WHERE user_id=%s", (session["user_id"],))
    if request.method == "POST":
        if request.form.get("change_password"):
            if hash_password(request.form["current_password"]) != user["password"]:
                flash("Current password is incorrect.", "danger")
            elif request.form["new_password"] != request.form["confirm_password"]:
                flash("Passwords do not match.", "danger")
            elif len(request.form["new_password"]) < 6:
                flash("Password must be at least 6 characters.", "danger")
            else:
                db_execute("UPDATE users SET password=%s WHERE user_id=%s", (hash_password(request.form["new_password"]), session["user_id"]))
                flash("Password changed.", "success")
        else:
            db_execute(
                "UPDATE users SET fullname=%s,email=%s,phone=%s WHERE user_id=%s",
                (request.form["fullname"], request.form.get("email", ""), request.form.get("phone", ""), session["user_id"])
            )
            session["fullname"] = request.form["fullname"]
            flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    role_profile = None
    if session["role"] == "Teacher":
        role_profile = teacher_info()
    elif session["role"] == "Student":
        role_profile = student_info()
    role_rows = "".join(
        f"<tr><th>{escape(k.replace('_',' ').title())}</th><td>{escape(str(v) if v is not None else '')}</td></tr>"
        for k, v in (role_profile or {}).items()
    )
    body = f"""
    <h1>My Profile</h1>
    <div class="split">
      <form class="form-card" method="post">
        <h2>Contact Info</h2>
        <label>Full Name</label><input name="fullname" value="{escape(user.get('fullname') or '')}" required>
        <label>Email</label><input name="email" value="{escape(user.get('email') or '')}">
        <label>Phone</label><input name="phone" value="{escape(user.get('phone') or '')}">
        <div class="actions"><button>Save Changes</button></div>
      </form>
      <form class="form-card" method="post">
        <h2>Change Password</h2>
        <input type="hidden" name="change_password" value="1">
        <label>Current Password</label><input type="password" name="current_password" required>
        <label>New Password</label><input type="password" name="new_password" required>
        <label>Confirm Password</label><input type="password" name="confirm_password" required>
        <div class="actions"><button class="danger">Change Password</button></div>
      </form>
    </div>
    <h2>Role Profile</h2>
    <div class="table-wrap"><table>{role_rows}</table></div>
    """
    return render_page("Profile", body, session["role"])


@app.route("/download/<kind>/<int:item_id>")
@require_login()
def download_file(kind, item_id):
    tables = {
        "material": ("study_materials", "material_id"),
        "assignment": ("assignments", "assignment_id"),
        "submission": ("submissions", "submission_id"),
    }
    if kind not in tables:
        flash("Invalid file request.", "danger")
        return redirect(url_for("index"))
    table, key = tables[kind]
    row = db_fetchone(f"SELECT file_path FROM {table} WHERE {key}=%s", (item_id,))
    if not row or not row.get("file_path") or not os.path.exists(row["file_path"]):
        flash("File could not be located.", "danger")
        return redirect(url_for("index"))
    return send_file(row["file_path"], as_attachment=False)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)