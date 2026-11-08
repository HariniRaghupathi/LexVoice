
from flask import (
    Flask, request, jsonify, send_from_directory,
    send_file, session, redirect
)

from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import sqlite3
import re
import os
import uuid
import secrets
from datetime import datetime, timedelta


# ==================================================
# 1. FLASK CONFIGURATION
# ==================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "LEXVOICE_SECRET_KEY",
    "lexvoice-local-development-secret-change-before-deployment"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=12 * 1024 * 1024
)


# ==================================================
# 2. PROJECT PATHS
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

FRONTEND_DIR = BASE_DIR / "frontend"
DATABASE_PATH = BACKEND_DIR / "lexvoice.db"

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "jpg", "jpeg", "png"
}

MAX_FILE_SIZE = 10 * 1024 * 1024


# ==================================================
# 3. DATABASE CONNECTION
# ==================================================

def get_db_connection():
    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=10
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def setup_files_table():
    connection = get_db_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                admin_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                notification_type TEXT DEFAULT 'general',
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            )
        """)
        connection.commit()
        
        print("My Files database table is ready.")

    finally:
        connection.close()


# ==================================================
# 4. AUTHENTICATION HELPERS
# ==================================================

def user_required():
    return "user_id" in session


def admin_required():
    return "admin_id" in session


def login_required_response():
    return jsonify({
        "success": False,
        "message": "Please log in first."
    }), 401


def admin_required_response():
    return jsonify({
        "success": False,
        "message": "Admin login required."
    }), 401


# ==================================================
# 5. HOMEPAGE
# ==================================================
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend"
)

@app.route("/images/<path:filename>")
def serve_frontend_image(filename):
    return send_from_directory(
        os.path.join(FRONTEND_DIR, "images"),
        filename
    )
@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ==================================================
# 6. USER REGISTRATION
# ==================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return send_from_directory(FRONTEND_DIR, "register.html")

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    language = str(data.get("language", "")).strip()
    password = data.get("password", "")

    if not isinstance(password, str):
        password = ""

    if not all([name, email, phone, language, password]):
        return jsonify({
            "success": False,
            "message": "All fields are required."
        }), 400

    if len(name) < 2:
        return jsonify({
            "success": False,
            "message": "Please enter a valid name."
        }), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    if not re.fullmatch(r"[6-9][0-9]{9}", phone):
        return jsonify({
            "success": False,
            "message": "Please enter a valid Indian mobile number."
        }), 400

    if language not in ["English", "Kannada"]:
        return jsonify({
            "success": False,
            "message": "Please select English or Kannada."
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    if not re.search(r"[^A-Za-z0-9]", password):
        return jsonify({
            "success": False,
            "message": "Password must contain a special character."
        }), 400

    hashed_password = generate_password_hash(password)

    connection = get_db_connection()

    try:
        connection.execute("""
            INSERT INTO users
            (name, email, phone, language, password)
            VALUES (?, ?, ?, ?, ?)
        """, (
            name, email, phone, language, hashed_password
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Registration successful! Please login."
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "message": "This email address is already registered."
        }), 409

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Registration error")

        return jsonify({
            "success": False,
            "message": "Database error. Please try again."
        }), 500

    finally:
        connection.close()


# ==================================================
# 7. USER LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return send_from_directory(FRONTEND_DIR, "login.html")

    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not isinstance(password, str):
        password = ""

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required."
        }), 400

    connection = get_db_connection()

    try:
        user = connection.execute("""
            SELECT id, name, email, phone, language, password
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        if user is None or not check_password_hash(
            user["password"], password
        ):
            return jsonify({
                "success": False,
                "message": "Invalid email or password."
            }), 401

        session.clear()

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["language"] = user["language"]

        return jsonify({
            "success": True,
            "message": "Login successful!",
            "redirect": "/index.html"
        })

    except sqlite3.Error:
        app.logger.exception("User login error")

        return jsonify({
            "success": False,
            "message": "Unable to process login."
        }), 500

    finally:
        connection.close()


# ==================================================
# 8. ADMIN LOGIN
# ==================================================

# ==================================================
# FORGOT PASSWORD
# ==================================================

@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({
            "success": False,
            "message": "Please enter your registered email."
        }), 400

    connection = get_db_connection()

    try:
        user = connection.execute(
            "SELECT id, email FROM users WHERE LOWER(email) = ?",
            (email,)
        ).fetchone()

        # Keep the response generic so account existence is not disclosed.
        response = {
            "success": True,
            "message": "If this email is registered, a password reset link has been generated."
        }

        if user:
            token = secrets.token_urlsafe(32)
            expiry = (datetime.now() + timedelta(minutes=30)).isoformat()

            connection.execute("""
                UPDATE users
                SET reset_token = ?, reset_token_expiry = ?
                WHERE id = ?
            """, (token, expiry, user["id"]))

            connection.commit()

            # LOCAL TESTING ONLY:
            # Do not expose reset tokens this way in production.
            response["reset_url"] = (
                "/reset-password.html?token=" + token
            )

        return jsonify(response)

    finally:
        connection.close()


# ==================================================
# RESET PASSWORD
# ==================================================

@app.route("/api/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json(silent=True) or {}

    token = data.get("token", "")
    new_password = data.get("password", "")

    if not isinstance(token, str) or not isinstance(new_password, str):
        return jsonify({
            "success": False,
            "message": "Invalid reset request."
        }), 400

    if not token or not new_password:
        return jsonify({
            "success": False,
            "message": "Token and new password are required."
        }), 400

    if len(new_password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    if not re.search(r"[^A-Za-z0-9]", new_password):
        return jsonify({
            "success": False,
            "message": "Password must contain a special character."
        }), 400

    connection = get_db_connection()

    try:
        user = connection.execute("""
            SELECT id, reset_token_expiry
            FROM users
            WHERE reset_token = ?
        """, (token,)).fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "Invalid or already used reset link."
            }), 400

        expiry = datetime.fromisoformat(user["reset_token_expiry"])

        if datetime.now() > expiry:
            connection.execute("""
                UPDATE users
                SET reset_token = NULL,
                    reset_token_expiry = NULL
                WHERE id = ?
            """, (user["id"],))

            connection.commit()

            return jsonify({
                "success": False,
                "message": "Your reset link has expired. Please request another."
            }), 400

        hashed_password = generate_password_hash(new_password)

        connection.execute("""
            UPDATE users
            SET password = ?,
                reset_token = NULL,
                reset_token_expiry = NULL
            WHERE id = ?
        """, (hashed_password, user["id"]))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Password changed successfully. You can now log in."
        })

    finally:
        connection.close()

@app.route("/admin/login", methods=["POST"])
def admin_login():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not isinstance(password, str):
        password = ""

    if not username or not password:
        return jsonify({
            "success": False,
            "message": "Enter both username and password."
        }), 400

    connection = get_db_connection()

    try:
        admin = connection.execute("""
            SELECT id, username, password
            FROM admins
            WHERE username = ?
        """, (username,)).fetchone()

        if admin is None or not check_password_hash(
            admin["password"], password
        ):
            return jsonify({
                "success": False,
                "message": "Invalid admin username or password."
            }), 401

        session.clear()

        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]

        return jsonify({
            "success": True,
            "message": "Admin login successful.",
            "redirect": "/admin.html"
        })

    except sqlite3.Error:
        app.logger.exception("Admin login error")

        return jsonify({
            "success": False,
            "message": "Unable to process admin login."
        }), 500

    finally:
        connection.close()


# ==================================================
# 9. ADMIN DASHBOARD AND LOGOUT
# ==================================================

@app.route("/admin.html")
def admin_dashboard():

    if not admin_required():
        return redirect("/admin-login.html")

    return send_from_directory(FRONTEND_DIR, "admin.html")


@app.route("/admin-logout")
def admin_logout():

    session.clear()
    return redirect("/admin-login.html")


@app.route("/admin-login.html")
def admin_login_page():

    return send_from_directory(
        FRONTEND_DIR,
        "admin-login.html"
    )


# ==================================================
# 10. ADMIN DASHBOARD STATISTICS
# ==================================================

@app.route("/api/admin/stats", methods=["GET"])
def admin_stats():

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        users = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        lawyers = connection.execute(
            "SELECT COUNT(*) FROM lawyers"
        ).fetchone()[0]

        complaints = connection.execute(
            "SELECT COUNT(*) FROM complaints"
        ).fetchone()[0]

        laws = connection.execute(
            "SELECT COUNT(*) FROM laws"
        ).fetchone()[0]

        return jsonify({
            "success": True,
            "users": users,
            "lawyers": lawyers,
            "complaints": complaints,
            "laws": laws
        })

    except sqlite3.Error:
        app.logger.exception("Admin statistics error")

        return jsonify({
            "success": False,
            "message": "Unable to load dashboard statistics."
        }), 500

    finally:
        connection.close()



# ==================================================
# ADMIN: EDIT REGISTERED USER
# ==================================================

@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
def admin_update_user(user_id):

    if not admin_required():
        return admin_required_response()

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()
    language = str(data.get("language", "")).strip()

    if not name or not email or not phone:
        return jsonify({
            "success": False,
            "message": "Please fill in all required fields."
        }), 400

    if language not in ["English", "Kannada"]:
        return jsonify({
            "success": False,
            "message": "Invalid language selection."
        }), 400

    connection = get_db_connection()

    try:
        existing_user = connection.execute("""
            SELECT id FROM users
            WHERE LOWER(email) = LOWER(?) AND id != ?
        """, (email, user_id)).fetchone()

        if existing_user:
            return jsonify({
                "success": False,
                "message": "This email address is already registered."
            }), 409

        result = connection.execute("""
            UPDATE users
            SET name = ?, email = ?, phone = ?, language = ?
            WHERE id = ?
        """, (name, email, phone, language, user_id))

        if result.rowcount == 0:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        connection.commit()

        return jsonify({
            "success": True,
            "message": "User updated successfully."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Admin update user error")

        return jsonify({
            "success": False,
            "message": "Unable to update user."
        }), 500

    finally:
        connection.close()


# ==================================================
# ADMIN: DELETE REGISTERED USER
# ==================================================

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def admin_delete_user(user_id):

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        user = connection.execute("""
            SELECT id FROM users WHERE id = ?
        """, (user_id,)).fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        connection.execute("BEGIN")

        # Delete the user's uploaded-file records
        connection.execute("""
            DELETE FROM files WHERE user_id = ?
        """, (user_id,))

        # Delete the user's complaints
        connection.execute("""
            DELETE FROM complaints WHERE user_id = ?
        """, (user_id,))

        # Delete the user account
        connection.execute("""
            DELETE FROM users WHERE id = ?
        """, (user_id,))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "User and associated records deleted successfully."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Admin delete user error")

        return jsonify({
            "success": False,
            "message": "Unable to delete user."
        }), 500

    finally:
        connection.close()
@app.route("/api/admin/users", methods=["GET"])

def admin_users():

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        users = connection.execute("""
            SELECT id, name, email, phone, language, created_at
            FROM users
            ORDER BY id DESC
        """).fetchall()

        return jsonify({
            "success": True,
            "users": [dict(row) for row in users]
        })

    except sqlite3.Error:
        app.logger.exception("Admin users error")

        return jsonify({
            "success": False,
            "message": "Unable to load registered users."
        }), 500

    finally:
        connection.close()


# ==================================================
# 12. ADMIN: VIEW, ADD LAWS
# ==================================================

@app.route("/api/admin/laws", methods=["GET", "POST"])
def admin_laws():

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        if request.method == "GET":

            laws = connection.execute("""
                SELECT id, title, category, description, rights, created_at
                FROM laws
                ORDER BY id DESC
            """).fetchall()

            return jsonify({
                "success": True,
                "laws": [dict(row) for row in laws]
            })

        data = request.get_json(silent=True) or {}

        title = str(data.get("title", "")).strip()
        category = str(data.get("category", "")).strip()
        description = str(data.get("description", "")).strip()
        rights = str(data.get("rights", "")).strip()

        if not all([title, category, description, rights]):
            return jsonify({
                "success": False,
                "message": "All law fields are required."
            }), 400

        connection.execute("""
            INSERT INTO laws (title, category, description, rights)
            VALUES (?, ?, ?, ?)
        """, (title, category, description, rights))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Law added successfully."
        }), 201

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Admin add law error")

        return jsonify({
            "success": False,
            "message": "Unable to save law."
        }), 500

    finally:
        connection.close()


# ==================================================
# 13. ADMIN: EDIT AND DELETE LAWS
# ==================================================

@app.route(
    "/api/admin/laws/<int:law_id>",
    methods=["PUT", "DELETE"]
)
def admin_manage_law(law_id):

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        existing = connection.execute(
            "SELECT id FROM laws WHERE id = ?",
            (law_id,)
        ).fetchone()

        if not existing:
            return jsonify({
                "success": False,
                "message": "Law not found."
            }), 404

        if request.method == "DELETE":

            connection.execute(
                "DELETE FROM laws WHERE id = ?",
                (law_id,)
            )

            connection.commit()

            return jsonify({
                "success": True,
                "message": "Law deleted successfully."
            })

        data = request.get_json(silent=True) or {}

        title = str(data.get("title", "")).strip()
        category = str(data.get("category", "")).strip()
        description = str(data.get("description", "")).strip()
        rights = str(data.get("rights", "")).strip()

        if not all([title, category, description, rights]):
            return jsonify({
                "success": False,
                "message": "All law fields are required."
            }), 400

        connection.execute("""
            UPDATE laws
            SET title = ?, category = ?, description = ?, rights = ?
            WHERE id = ?
        """, (title, category, description, rights, law_id))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Law updated successfully."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Admin manage law error")

        return jsonify({
            "success": False,
            "message": "Unable to manage law."
        }), 500

    finally:
        connection.close()


# ==================================================
# 14. ADMIN: VIEW, ADD LAWYERS
# ==================================================

@app.route("/api/admin/lawyers", methods=["GET", "POST"])
def admin_lawyers():

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        if request.method == "GET":

            lawyers = connection.execute("""
                SELECT id, name, specialization, phone, email,
                       address, experience, lawyer_level, created_at
                FROM lawyers
                ORDER BY id DESC
            """).fetchall()

            return jsonify({
                "success": True,
                "lawyers": [dict(row) for row in lawyers]
            })

        data = request.get_json(silent=True) or {}

        name = str(data.get("name", "")).strip()
        specialization = str(data.get("specialization", "")).strip()
        phone = str(data.get("phone", "")).strip()
        email = str(data.get("email", "")).strip()
        address = str(data.get("address", "")).strip()
        experience = str(data.get("experience", "")).strip()
        lawyer_level = str(data.get("lawyer_level", "Other")).strip()

        if not all([name, specialization, phone, email]):
            return jsonify({
                "success": False,
                "message": "Name, specialization, phone and email are required."
            }), 400

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return jsonify({
                "success": False,
                "message": "Enter a valid email address."
            }), 400

        connection.execute("""
            INSERT INTO lawyers (
                name, specialization, phone, email,
                address, experience, lawyer_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name, specialization, phone, email,
            address, experience, lawyer_level
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Lawyer added successfully."
        }), 201

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Admin add lawyer error")

        return jsonify({
            "success": False,
            "message": "Unable to save lawyer."
        }), 500

    finally:
        connection.close()


# ==================================================
# 15. ADMIN: EDIT AND DELETE LAWYERS
# ==================================================

@app.route(
    "/api/admin/lawyers/<int:lawyer_id>",
    methods=["PUT", "DELETE"]
)
def admin_manage_lawyer(lawyer_id):

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        existing = connection.execute(
            "SELECT id FROM lawyers WHERE id = ?",
            (lawyer_id,)
        ).fetchone()

        if not existing:
            return jsonify({
                "success": False,
                "message": "Lawyer not found."
            }), 404

        if request.method == "DELETE":

            connection.execute(
                "DELETE FROM lawyers WHERE id = ?",
                (lawyer_id,)
            )

            connection.commit()

            return jsonify({
                "success": True,
                "message": "Lawyer deleted successfully."
            })

        data = request.get_json(silent=True) or {}

        name = str(data.get("name", "")).strip()
        specialization = str(data.get("specialization", "")).strip()
        phone = str(data.get("phone", "")).strip()
        email = str(data.get("email", "")).strip()
        address = str(data.get("address", "")).strip()
        experience = str(data.get("experience", "")).strip()
        lawyer_level = str(data.get("lawyer_level", "Other")).strip()

        if not all([name, specialization, phone, email]):
            return jsonify({
                "success": False,
                "message": "Name, specialization, phone and email are required."
            }), 400

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return jsonify({
                "success": False,
                "message": "Enter a valid email address."
            }), 400

        connection.execute("""
            UPDATE lawyers
            SET name = ?, specialization = ?, phone = ?, email = ?,
                address = ?, experience = ?, lawyer_level = ?
            WHERE id = ?
        """, (
            name, specialization, phone, email,
            address, experience, lawyer_level, lawyer_id
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Lawyer updated successfully."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Admin manage lawyer error")

        return jsonify({
            "success": False,
            "message": "Unable to manage lawyer."
        }), 500

    finally:
        connection.close()


# ==================================================
# 16. PUBLIC: VIEW JUNIOR LAWYERS
# ==================================================

@app.route("/api/junior-lawyers", methods=["GET"])
def get_junior_lawyers():

    connection = get_db_connection()

    try:
        lawyers = connection.execute("""
            SELECT id, name, specialization, phone, email,
                   address, experience
            FROM lawyers
            WHERE LOWER(COALESCE(lawyer_level, 'Other')) = 'junior'
            ORDER BY name ASC
        """).fetchall()

        return jsonify({
            "success": True,
            "lawyers": [dict(row) for row in lawyers]
        })

    except sqlite3.Error:
        app.logger.exception("Junior lawyer retrieval error")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve junior lawyers."
        }), 500

    finally:
        connection.close()


# ==================================================
# 17. ADMIN: VIEW ALL COMPLAINTS
# ==================================================

@app.route("/api/admin/complaints", methods=["GET"])
def admin_complaints():

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        complaints = connection.execute("""
            SELECT
                complaints.id,
                complaints.subject,
                complaints.description,
                complaints.status,
                complaints.solution,
                complaints.created_at,
                users.id AS user_id,
                users.name AS name,
users.email AS email,
users.phone AS phone
            FROM complaints
            JOIN users ON complaints.user_id = users.id
            ORDER BY complaints.id DESC
        """).fetchall()

        return jsonify({
            "success": True,
            "complaints": [dict(row) for row in complaints]
        })

    except sqlite3.Error:
        app.logger.exception("Admin complaints error")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve complaints."
        }), 500

    finally:
        connection.close()


# ==================================================
# 18. ADMIN: UPDATE COMPLAINT STATUS AND SOLUTION
# ==================================================


@app.route(
    "/api/admin/complaints/<int:complaint_id>/solution",
    methods=["POST"]
)
def update_complaint_solution(complaint_id):

    if not admin_required():
        return admin_required_response()

    data = request.get_json(silent=True) or {}

    solution = str(data.get("solution", "")).strip()
    status = str(data.get("status", "Pending")).strip()

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Resolved"
    ]

    if status not in allowed_statuses:
        return jsonify({
            "success": False,
            "message": "Invalid complaint status."
        }), 400

    if not solution:
        return jsonify({
            "success": False,
            "message": "Please enter a solution or response."
        }), 400

    connection = get_db_connection()

    try:
        # Get complaint and its owner
        complaint = connection.execute("""
            SELECT user_id, subject
            FROM complaints
            WHERE id = ?
        """, (complaint_id,)).fetchone()

        if complaint is None:
            return jsonify({
                "success": False,
                "message": "Complaint not found."
            }), 404

        # Update complaint
        connection.execute("""
            UPDATE complaints
            SET solution = ?, status = ?
            WHERE id = ?
        """, (solution, status, complaint_id))

        # Create user notification
        title = "Complaint Update"

        if status == "Resolved":
            title = "Complaint Resolved"
            notification_message = (
                f"Your complaint '{complaint['subject']}' "
                f"has been resolved. Solution: {solution}"
            )

        elif status == "In Progress":
            notification_message = (
                f"Your complaint '{complaint['subject']}' "
                f"is now in progress. Update: {solution}"
            )

        else:
            notification_message = (
                f"Your complaint '{complaint['subject']}' "
                f"has been updated. Response: {solution}"
            )

        connection.execute("""
            INSERT INTO notifications
            (user_id, title, message, notification_type)
            VALUES (?, ?, ?, 'complaint')
        """, (
            complaint["user_id"],
            title,
            notification_message
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Complaint updated and user notified."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Complaint update error")

        return jsonify({
            "success": False,
            "message": "Unable to update complaint."
        }), 500

    finally:
        connection.close()


# ==================================================
# 19. USER: SUBMIT COMPLAINT
# ==================================================



@app.route("/api/complaints", methods=["POST"])
def submit_complaint():

    if not user_required():
        return login_required_response()

    data = request.get_json(silent=True) or {}

    subject = str(data.get("subject", "")).strip()
    description = str(data.get("description", "")).strip()

    allowed_categories = [
        "Property", "Consumer", "Family",
        "Cyber", "Criminal", "Other"
    ]

    if subject not in allowed_categories:
        return jsonify({
            "success": False,
            "message": "Please select a valid complaint category."
        }), 400

    if len(description) < 10:
        return jsonify({
            "success": False,
            "message": "Complaint description must contain at least 10 characters."
        }), 400

    connection = get_db_connection()

    try:
        user = connection.execute("""
            SELECT name FROM users WHERE id = ?
        """, (session["user_id"],)).fetchone()

        cursor = connection.execute("""
            INSERT INTO complaints
            (user_id, subject, description, status)
            VALUES (?, ?, ?, 'Pending')
        """, (
            session["user_id"],
            subject,
            description
        ))

        complaint_id = cursor.lastrowid
        print("NEW COMPLAINT SAVED:", complaint_id)

        admins = connection.execute("""
            SELECT id FROM admins
        """).fetchall()

        print("ADMINS FOUND:", [dict(a) for a in admins])

        notification_count = 0

        for admin in admins:
            connection.execute("""
                INSERT INTO notifications
                (admin_id, title, message, notification_type)
                VALUES (?, ?, ?, 'complaint')
            """, (
                admin["id"],
                "New Complaint Received",
                f"{user['name'] if user else 'A user'} submitted a new {subject} complaint. Complaint ID: #{complaint_id}."
            ))

            notification_count += 1
            print("NOTIFICATION CREATED FOR ADMIN:", admin["id"])

        connection.commit()

        print("TOTAL NOTIFICATIONS CREATED:", notification_count)

        return jsonify({
            "success": True,
            "message": "Complaint submitted successfully.",
            "complaint_id": complaint_id
        }), 201

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Complaint submission error")

        return jsonify({
            "success": False,
            "message": "Unable to save complaint."
        }), 500

    finally:
        connection.close()


# ==================================================
# 20. USER: VIEW OWN COMPLAINTS
# ==================================================

@app.route("/api/my-complaints", methods=["GET"])
def get_my_complaints():

    if not user_required():
        return login_required_response()

    connection = get_db_connection()

    try:
        complaints = connection.execute("""
            SELECT id, subject, description, status,
                   solution, created_at
            FROM complaints
            WHERE user_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

        return jsonify({
            "success": True,
            "complaints": [dict(row) for row in complaints],
            "count": len(complaints)
        })

    except sqlite3.Error:
        app.logger.exception("User complaints error")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve complaints."
        }), 500

    finally:
        connection.close()


# ==================================================
# 21. CURRENT USER INFORMATION
# ==================================================

@app.route("/api/me", methods=["GET"])
def current_user():

    if not user_required():
        return jsonify({
            "success": False,
            "logged_in": False,
            "message": "You are not logged in."
        }), 401

    return jsonify({
        "success": True,
        "logged_in": True,
        "user": {
            "id": session["user_id"],
            "name": session["user_name"],
            "email": session["user_email"],
            "language": session["language"]
        }
    })


# ==================================================
# 22. USER LOGOUT
# ==================================================

@app.route("/logout", methods=["GET", "POST"])
def logout():

    session.clear()

    if request.method == "GET":
        return redirect("/login")

    return jsonify({
        "success": True,
        "message": "You have logged out successfully.",
        "redirect": "/login"
    })


# ==================================================
# 23. USER PROFILE
# ==================================================

@app.route("/api/profile", methods=["GET"])
def get_profile():

    if not user_required():
        return login_required_response()

    connection = get_db_connection()

    try:
        user = connection.execute("""
            SELECT id, name, email, phone, language
            FROM users
            WHERE id = ?
        """, (session["user_id"],)).fetchone()

        if user is None:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        return jsonify({
            "success": True,
            "user": dict(user)
        })

    except sqlite3.Error:
        app.logger.exception("Profile retrieval error")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve profile."
        }), 500

    finally:
        connection.close()


@app.route("/api/profile/update", methods=["POST"])
def update_profile():

    if not user_required():
        return login_required_response()

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    language = str(data.get("language", "")).strip()

    if len(name) < 2:
        return jsonify({
            "success": False,
            "message": "Enter a valid name."
        }), 400

    if not re.fullmatch(r"[6-9][0-9]{9}", phone):
        return jsonify({
            "success": False,
            "message": "Enter a valid 10-digit Indian mobile number."
        }), 400

    if language not in ["English", "Kannada"]:
        return jsonify({
            "success": False,
            "message": "Select English or Kannada."
        }), 400

    connection = get_db_connection()

    try:
        connection.execute("""
            UPDATE users
            SET name = ?, phone = ?, language = ?
            WHERE id = ?
        """, (
            name, phone, language, session["user_id"]
        ))

        connection.commit()

        session["user_name"] = name
        session["language"] = language

        return jsonify({
            "success": True,
            "message": "Profile updated successfully."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Profile update error")

        return jsonify({
            "success": False,
            "message": "Unable to update profile."
        }), 500

    finally:
        connection.close()


# ==================================================
# 24. MY FILES: FILE VALIDATION
# ==================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ==================================================
# 25. MY FILES: USER UPLOAD
# ==================================================

@app.route("/api/my-files", methods=["POST"])
def upload_my_file():

    if not user_required():
        return login_required_response()

    if "file" not in request.files:
        return jsonify({
            "success": False,
            "message": "No file was selected."
        }), 400

    file = request.files["file"]

    if not file or not file.filename:
        return jsonify({
            "success": False,
            "message": "Please select a file."
        }), 400

    original_filename = secure_filename(file.filename)

    if not original_filename or not allowed_file(original_filename):
        return jsonify({
            "success": False,
            "message": "Only PDF, DOC, DOCX, JPG, JPEG and PNG files are allowed."
        }), 400

    file_data = file.read(MAX_FILE_SIZE + 1)

    if not file_data:
        return jsonify({
            "success": False,
            "message": "The selected file is empty."
        }), 400

    if len(file_data) > MAX_FILE_SIZE:
        return jsonify({
            "success": False,
            "message": "File size must not exceed 10 MB."
        }), 400

    stored_filename = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = UPLOAD_FOLDER / stored_filename

    connection = None

    try:
        with open(file_path, "wb") as uploaded_file:
            uploaded_file.write(file_data)

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO files
            (user_id, filename, stored_filename)
            VALUES (?, ?, ?)
        """, (
            session["user_id"],
            original_filename,
            stored_filename
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "File uploaded successfully."
        }), 201

    except sqlite3.Error:
        if connection:
            connection.rollback()

        if file_path.exists():
            file_path.unlink()

        app.logger.exception("File upload database error")

        return jsonify({
            "success": False,
            "message": "Unable to save file information."
        }), 500

    except OSError:
        if file_path.exists():
            file_path.unlink()

        app.logger.exception("File storage error")

        return jsonify({
            "success": False,
            "message": "Unable to store the uploaded file."
        }), 500

    finally:
        if connection:
            connection.close()


# ==================================================
# 26. MY FILES: USER VIEW
# ==================================================

@app.route("/api/my-files", methods=["GET"])
def get_my_files():

    if not user_required():
        return login_required_response()

    connection = get_db_connection()

    try:
        files = connection.execute("""
            SELECT id, filename, uploaded_at AS created_at
            FROM files
            WHERE user_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

        return jsonify({
            "success": True,
            "files": [dict(row) for row in files]
        })

    except sqlite3.Error:
        app.logger.exception("My files retrieval error")

        return jsonify({
            "success": False,
            "message": "Unable to retrieve your files."
        }), 500

    finally:
        connection.close()


# ==================================================
# 27. MY FILES: USER DOWNLOAD
# ==================================================

@app.route("/api/files/<int:file_id>/download", methods=["GET"])
def download_my_file(file_id):

    if not user_required():
        return login_required_response()

    connection = get_db_connection()

    try:
        file_record = connection.execute("""
            SELECT filename, stored_filename
            FROM files
            WHERE id = ? AND user_id = ?
        """, (
            file_id, session["user_id"]
        )).fetchone()

    except sqlite3.Error:
        app.logger.exception("File download lookup error")

        return jsonify({
            "success": False,
            "message": "Unable to find the requested file."
        }), 500

    finally:
        connection.close()

    if not file_record:
        return jsonify({
            "success": False,
            "message": "File not found."
        }), 404

    file_path = UPLOAD_FOLDER / file_record["stored_filename"]

    if not file_path.is_file():
        return jsonify({
            "success": False,
            "message": "The stored file is missing."
        }), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_record["filename"]
    )


# ==================================================
# 28. MY FILES: USER DELETE
# ==================================================

@app.route("/api/my-files/<int:file_id>", methods=["DELETE"])
def delete_my_file(file_id):

    if not user_required():
        return login_required_response()

    connection = get_db_connection()

    try:
        file_record = connection.execute("""
            SELECT stored_filename
            FROM files
            WHERE id = ? AND user_id = ?
        """, (
            file_id, session["user_id"]
        )).fetchone()

        if not file_record:
            return jsonify({
                "success": False,
                "message": "File not found."
            }), 404

        connection.execute("""
            DELETE FROM files
            WHERE id = ? AND user_id = ?
        """, (
            file_id, session["user_id"]
        ))

        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("File deletion error")

        return jsonify({
            "success": False,
            "message": "Unable to delete file."
        }), 500

    finally:
        connection.close()

    file_path = UPLOAD_FOLDER / file_record["stored_filename"]

    try:
        if file_path.is_file():
            file_path.unlink()

    except OSError:
        app.logger.exception("Stored file cleanup error")

        return jsonify({
            "success": True,
            "message": "File record deleted, but stored file cleanup failed."
        })

    return jsonify({
        "success": True,
        "message": "File deleted successfully."
    })


# ==================================================
# 29. ADMIN: VIEW ALL UPLOADED DOCUMENTS
# ==================================================

@app.route("/api/admin/files", methods=["GET"])
def admin_files():

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        files = connection.execute("""
            SELECT
                files.id,
                files.filename,
                files.uploaded_at,
                users.id AS user_id,
                users.name AS user_name,
                users.email AS user_email
            FROM files
            JOIN users ON files.user_id = users.id
            ORDER BY files.id DESC
        """).fetchall()

        return jsonify({
            "success": True,
            "files": [dict(row) for row in files]
        })

    except sqlite3.Error:
        app.logger.exception("Admin files retrieval error")

        return jsonify({
            "success": False,
            "message": "Unable to load uploaded documents."
        }), 500

    finally:
        connection.close()


# ==================================================
# 30. ADMIN: DOWNLOAD A USER DOCUMENT
# ==================================================

@app.route("/api/admin/files/<int:file_id>/download", methods=["GET"])
def admin_download_file(file_id):

    if not admin_required():
        return admin_required_response()

    connection = get_db_connection()

    try:
        file_record = connection.execute("""
            SELECT filename, stored_filename
            FROM files
            WHERE id = ?
        """, (file_id,)).fetchone()

    except sqlite3.Error:
        app.logger.exception("Admin file download error")

        return jsonify({
            "success": False,
            "message": "Unable to find document."
        }), 500

    finally:
        connection.close()

    if not file_record:
        return jsonify({
            "success": False,
            "message": "Document not found."
        }), 404

    file_path = UPLOAD_FOLDER / file_record["stored_filename"]

    if not file_path.is_file():
        return jsonify({
            "success": False,
            "message": "Stored document is missing."
        }), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_record["filename"]
    )


# ==================================================
# 31. COMPLAINT DATABASE CHECK
# ==================================================

@app.route("/api/complaints/check", methods=["GET"])
def complaint_database_check():

    if not user_required():
        return login_required_response()

    connection = get_db_connection()

    try:
        total = connection.execute("""
            SELECT COUNT(*)
            FROM complaints
            WHERE user_id = ?
        """, (session["user_id"],)).fetchone()[0]

        return jsonify({
            "success": True,
            "database": str(DATABASE_PATH),
            "logged_in_user_id": session["user_id"],
            "complaints_saved_for_user": total
        })

    except sqlite3.Error:
        app.logger.exception("Complaint database check error")

        return jsonify({
            "success": False,
            "message": "Unable to check complaint database."
        }), 500

    finally:
        connection.close()



# ==================================================
# 32. ADD JUNIOR LAWYER + FRONTEND PAGES
# ==================================================

# ADMIN: ADD JUNIOR LAWYER
@app.route("/api/admin/junior-lawyers", methods=["POST"])
def add_junior_lawyer():

    # Check admin login
    if not admin_required():
        return admin_required_response()

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    specialization = str(data.get("specialization", "")).strip()
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()
    address = str(data.get("address", "")).strip()
    experience = str(data.get("experience", "")).strip()

    # Validate required fields
    if not name or not specialization or not phone or not email:
        return jsonify({
            "success": False,
            "message": "Please fill in all required fields."
        }), 400

    # Validate email
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    connection = None

    try:
        connection = get_db_connection()

        cursor = connection.execute("""
            INSERT INTO lawyers (
                name,
                specialization,
                phone,
                email,
                address,
                experience,
                lawyer_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            specialization,
            phone,
            email,
            address,
            experience,
            "Junior"
        ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Junior lawyer added successfully!",
            "lawyer_id": cursor.lastrowid
        }), 201

    except sqlite3.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Add junior lawyer error")

        return jsonify({
            "success": False,
            "message": "Database error. Unable to add junior lawyer."
        }), 500

    finally:
        if connection:
            connection.close()


# ==================================================
# PUBLIC: VIEW SENIOR LAWYERS
# ==================================================

@app.route("/api/lawyers", methods=["GET"])
def get_senior_lawyers():

    connection = get_db_connection()

    try:
        lawyers = connection.execute("""
            SELECT
                id,
                name,
                specialization,
                phone,
                email,
                address,
                experience,
                lawyer_level
            FROM lawyers
            WHERE LOWER(TRIM(COALESCE(lawyer_level, ''))) = 'senior'
            ORDER BY id DESC
        """).fetchall()

        return jsonify({
            "success": True,
            "lawyers": [dict(row) for row in lawyers]
        })

    except sqlite3.Error:
        app.logger.exception("Senior lawyer retrieval error")
        return jsonify({
            "success": False,
            "message": "Unable to retrieve senior lawyers."
        }), 500

    finally:
        connection.close()


# ==================================================
# FRONTEND PAGES
# ==================================================

@app.route("/<path:filename>")
def frontend_pages(filename):

    protected_pages = [
    "admin.html",
    "admin-users.html",
    "admin-laws.html"
    "admin-notifications.html"
]

    if filename in protected_pages and not admin_required():
        return redirect("/admin-login.html")

    return send_from_directory(FRONTEND_DIR, filename)


# ==================================================
# START FLASK SERVER
# ==================================================
# ==================================================
# DELETE USER'S OWN COMPLAINT
# ==================================================

@app.route("/api/my-complaints/<int:complaint_id>", methods=["DELETE"])
def delete_my_complaint(complaint_id):

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Please log in first."
        }), 401

    connection = get_db_connection()

    try:
        result = connection.execute(
            "DELETE FROM complaints WHERE id = ? AND user_id = ?",
            (complaint_id, user_id)
        )

        connection.commit()

        if result.rowcount == 0:
            return jsonify({
                "success": False,
                "message": "Complaint not found."
            }), 404

        return jsonify({
            "success": True,
            "message": "Complaint deleted successfully."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Delete complaint error")

        return jsonify({
            "success": False,
            "message": "Unable to delete complaint."
        }), 500

    finally:
        connection.close()
        # ==================================================
# NOTIFICATIONS - USER AND ADMIN
# ==================================================

# USER: VIEW NOTIFICATIONS
@app.route("/api/notifications", methods=["GET"])
def get_user_notifications():

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "Please log in."}), 401

    connection = get_db_connection()

    try:
        notifications = connection.execute("""
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,)).fetchall()

        unread = connection.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE user_id = ? AND is_read = 0
        """, (user_id,)).fetchone()[0]

        return jsonify({
            "success": True,
            "notifications": [dict(n) for n in notifications],
            "unread_count": unread
        })

    finally:
        connection.close()


# USER: MARK NOTIFICATION AS READ
@app.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id):

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "Please log in."}), 401

    connection = get_db_connection()

    try:
        result = connection.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))

        connection.commit()

        return jsonify({"success": result.rowcount > 0})

    finally:
        connection.close()


# USER: DELETE NOTIFICATION
@app.route("/api/notifications/<int:notification_id>", methods=["DELETE"])
def delete_notification(notification_id):

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "Please log in."}), 401

    connection = get_db_connection()

    try:
        connection.execute("""
            DELETE FROM notifications
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))

        connection.commit()

        return jsonify({"success": True})

    finally:
        connection.close()


# ADMIN: VIEW ADMIN NOTIFICATIONS
@app.route("/api/admin/notifications", methods=["GET"])
def get_admin_notifications():

    admin_id = session.get("admin_id")

    if not admin_id:
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    connection = get_db_connection()

    try:
        admins = connection.execute(
            "SELECT id FROM admins"
        ).fetchall()

        print("ADMIN RECORDS:", [dict(a) for a in admins])
        print("CURRENT ADMIN ID:", admin_id)

        notifications = connection.execute("""
            SELECT * FROM notifications
            WHERE admin_id = ?
            ORDER BY created_at DESC
        """, (admin_id,)).fetchall()

        print("NOTIFICATIONS FOUND:", len(notifications))

        return jsonify({
            "success": True,
            "notifications": [dict(n) for n in notifications]
        })

    finally:
        connection.close()

# ADMIN: SEND ANNOUNCEMENT TO ALL USERS
@app.route("/api/admin/notifications/announcement", methods=["POST"])
def send_notification_announcement():

    if not session.get("admin_id"):
        return jsonify({"success": False, "message": "Admin login required."}), 401

    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    message = data.get("message", "").strip()

    if not title or not message:
        return jsonify({
            "success": False,
            "message": "Title and message are required."
        }), 400

    connection = get_db_connection()

    try:
        users = connection.execute(
            "SELECT id FROM users"
        ).fetchall()

        connection.executemany("""
            INSERT INTO notifications
            (user_id, title, message, notification_type)
            VALUES (?, ?, ?, 'announcement')
        """, [(user["id"], title, message) for user in users])

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Announcement sent successfully."
        })

    finally:
        connection.close()
if __name__ == "__main__":

    print("\nLexVoice Flask Backend")
    print("Project folder:", BASE_DIR)
    print("Database:", DATABASE_PATH)

    setup_files_table()

    print("Website: http://127.0.0.1:5000")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )