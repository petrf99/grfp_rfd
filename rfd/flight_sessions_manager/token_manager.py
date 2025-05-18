import os
import hashlib
import uuid
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from tech_utils.logger import init_logger
logger = init_logger("RFD_FlightSessionsManager")

load_dotenv()

from tech_utils.db import get_conn

TOKEN_EXPIRE_TMP = int(os.getenv("TOKEN_EXPIRE_TMP", 300))

def generate_token():
    raw = uuid.uuid4().hex
    token = hashlib.md5(raw.encode()).hexdigest()
    return token



TAILSCALE_API_KEY = os.getenv("TAILSCALE_API_KEY")
TAILNET = os.getenv("TAILNET")

TS_AUTH_KEY_EXP_HOURS = int(os.getenv("TS_AUTH_KEY_EXP_HOURS"))

# Создание нового auth key
def create_tailscale_auth_key(mission_id, session_id, tag: str = None, ephemeral=True, preauthorized=True, reusable=False, expiry_hours=TS_AUTH_KEY_EXP_HOURS):
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys"

    headers = {
        "Content-Type": "application/json",
    }

    auth = (TAILSCALE_API_KEY, "")  # Basic Auth: API Key как username, пустой пароль

    payload = {
        "capabilities": {
            "devices": {
                "create": {
                    "reusable": reusable,
                    "ephemeral": ephemeral,
                    "preauthorized": preauthorized,
                    "tags": [f"tag:{tag}"] if tag else [],
                }
            }
        },
        "expirySeconds": expiry_hours * 3600,
        "description": f"authkey_session_{session_id}_mission_{mission_id}"
    }

    response = requests.post(url, headers=headers, auth=auth, data=json.dumps(payload))

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Tailscale Auth Key created. Key: {data['key']}. Expires in: {expiry_hours}d")
        return data['key'], expiry_hours
    else:
        logger.info(f"Failed to create key: {response.status_code}, {response.text}")
        return None


def create_token(mission_id, session_id, tag):
    token, exp_hours = create_tailscale_auth_key(mission_id, session_id, tag)
    now = datetime.utcnow()
    expires = now + timedelta(hours=exp_hours)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO grfp_sm_auth_tokens 
                (token, mission_id, session_id, is_active_flg, tag, created_at, expires_at, updated_at)
                VALUES (%s, %s, %s, TRUE, %s, %s, %s, %s)
            """, (token, mission_id, session_id, tag, now, expires, now,))
            conn.commit()
    logger.info(f"Tokens created successfully {token}, {now}, {expires}\n")
    return token

def deactivate_expired_tokens():
    try:
        now = datetime.utcnow()
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE grfp_sm_auth_tokens
                    SET is_active_flg = FALSE
                    , updated_at = %s
                    WHERE expires_at <= %s AND is_active_flg = TRUE
                """, (now, now,))
                conn.commit()
            logger.info("Deactivation of expired tokens succeed\n")
    except Exception as e:
        logger.error(f"[!] Error in deactivate_expired_tokens: {e}\n")


if __name__ == "__main__":
    print(create_token())
    print(create_token())