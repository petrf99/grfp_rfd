import bcrypt
import jwt
import time

from rfd.auth.config import *

from tech_utils.db import get_conn
from tech_utils.logger import init_logger

logger = init_logger(name="Logic", component="auth")

# -------------------------------
# Инициализация базы данных
# -------------------------------

def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    auth_provider TEXT,
                    password_hash TEXT
                )
            ''')
        conn.commit()
    except Exception as e:
        logger.error(f"Users table creation failed: {e}")
    finally:
        conn.close()

# -------------------------------
# Регистрация пользователя
# -------------------------------

def register_user(email: str, password: str) -> bool:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT user_id FROM users WHERE email = %s',
                (email,)
            )
            row = cur.fetchone()
            if row:
                logger.warning(f"Email {email} already exists")
                return False
            cur.execute(
                'INSERT INTO users (email, password_hash, auth_provider) VALUES (%s, %s, %s)',
                (email, password_hash, 'local')
            )
        conn.commit()
        logger.info(f"{email} registered")
        return True
    except Exception as e:
        logger.error(f"Registration error for {email} - {e}")
        return None
    finally:
        conn.close()

# -------------------------------
# Проверка пароля и выдача токена
# -------------------------------

def login_user(email: str, password: str) -> str | None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT user_id, password_hash FROM users WHERE email = %s',
                (email,)
            )
            row = cur.fetchone()
            if not row:
                logger.warning(f"Login error failed: Email {email} not found")
                return False

            user_id, password_hash = row
            if bcrypt.checkpw(password.encode(), password_hash.encode()):
                logger.info(f"{email} log in")
                return generate_jwt(user_id, email)
            else:
                logger.warning(f"Invalid password for {email} login")
                return False
    except Exception as e:
        logger.error(f"Login failed for {email} - {e}")
        return None
    finally:
        conn.close()

# -------------------------------
# Генерация и проверка JWT
# -------------------------------

def generate_jwt(user_id: int, email: str) -> str:
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': int(time.time()) + JWT_EXP_SECONDS
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.error(f"Token {token} expired")
        return None
    except jwt.InvalidTokenError:
        logger.error(f"Invalid token {token}")
        return None
    

if __name__ == '__main__':
    init_db()
