from functools import wraps
from flask import request, jsonify
from rfd.auth.logic import verify_jwt

def require_auth(allowed_emails=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"error": "Authorization required"}), 401

            token = auth_header.split(" ", 1)[1]
            payload = verify_jwt(token)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401

            request.user = payload

            # Проверка по email
            if allowed_emails:
                if payload.get('email') not in allowed_emails:
                    return jsonify({"error": "Access denied"}), 403

            return f(*args, **kwargs)
        return wrapped
    return decorator