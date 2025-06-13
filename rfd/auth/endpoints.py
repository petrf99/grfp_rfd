from flask import Flask, request, jsonify
import requests
import re
from rfd.auth.logic import register_user, login_user, generate_jwt
from rfd.auth.require_auth_dec import require_auth
from rfd.config import RFD_ADMIN_EMAIL
from tech_utils.db import get_conn
from tech_utils.logger import init_logger

logger = init_logger(name="AuthEndpoints", component="auth")

def extract_credentials(data):
    email = data.get("email")
    password = data.get("password")
    if not email or not password or "@" not in email:
        return None, None, "Missing or invalid fields"
    return email, password, None

# === Endpoint to register a new user ===
def register():
    logger.info("Register request received")
    data = request.get_json()
    if "email" in data and re.match(r"[^@]+@[^@]+\.[^@]+", data.get('email')) and "password" in data:
        email, password, error = extract_credentials(data)
        if error:
            return jsonify({"status": "error", "reason": error}), 400

        res = register_user(email, password)
        if res == True:
            return jsonify({"status": "ok"}), 200
        elif res is None:
            return jsonify({"status": "error", "reason": "Internal server error"}), 500
        elif res == False:
            return jsonify({"status": "error", "reason": f"Email {email} already exists"}), 400
    else:
        return jsonify({"status": "error", "reason": "Missing fields"}), 400

# === Endpoint to register a new user ===
def login():
    logger.info("Login request received")
    data = request.get_json()
    if "email" in data and re.match(r"[^@]+@[^@]+\.[^@]+", data.get('email')) and "password" in data:
        email, password, error = extract_credentials(data)
        if error:
            return jsonify({"status": "error", "reason": error}), 400

        jwt = login_user(email, password)
        if jwt:
            return jsonify({"status": "ok", "jwt": jwt}), 200
        elif jwt == False:
            return jsonify({"status": "error", "reason": f"Login failed"}), 400
        else:
            return jsonify({"status": "error", "reason": "Internal server error"}), 500
    else:
        return jsonify({"status": "error", "reason": "Missing fields"}), 400

# === Endpoint to authentificate via Google
def auth_google():
    data = request.get_json()
    id_token = data.get('id_token')
    if not id_token:
        return jsonify({"status": "error", "reason": "id_token is required"}), 400

    # 1. Проверка токена у Google
    google_resp = requests.get(f'https://oauth2.googleapis.com/tokeninfo?id_token={id_token}')
    if google_resp.status_code != 200:
        return jsonify({"status": "error", "reason": "Invalid id_token"}), 401

    user_info = google_resp.json()
    email = user_info.get('email')
    sub = user_info.get('sub')

    if not email or not sub:
        return jsonify({"status": "error", "reason": "Invalid token payload"}), 400

    # 2. Ищем или создаём пользователя
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, auth_provider FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row:
                user_id, provider = row
                if provider != 'google':
                    logger.warning(f"Google login attempted for local user {email}")
                    return {"status": "error", "reason": "User is already registered"}, 403
            else:
                cur.execute("""
                    INSERT INTO users (email, password_hash, auth_provider)
                    VALUES (%s, NULL, 'google')
                    RETURNING id
                """, (email,))
                user_id = cur.fetchone()[0]
                conn.commit()
    finally:
        conn.close()

    # 3. Выдаём JWT
    jwt = generate_jwt(user_id, email)
    return jsonify({"status": "ok", "jwt": jwt}), 200

# === Endpoint to delete user ===
@require_auth(allowed_emails=[RFD_ADMIN_EMAIL])
def delete_account():
    user_id = request.user.get('user_id')

    if not user_id:
        return jsonify({"error": "Invalid token payload"}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        return jsonify({"message": "Account deleted"}), 200
    except Exception as e:
        print(f"Delete error: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        conn.close()