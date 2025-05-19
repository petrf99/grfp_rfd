import os
import hashlib
import uuid
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from tech_utils.logger import init_logger
logger = init_logger("RFD_FSM_TokenManager")

load_dotenv()

from tech_utils.db import get_conn

def generate_token():
    raw = uuid.uuid4().hex
    token = hashlib.md5(raw.encode()).hexdigest()
    return token



TAILSCALE_API_KEY = os.getenv("TAILSCALE_API_KEY")
TAILNET = os.getenv("TAILNET")

if not TAILSCALE_API_KEY or not TAILNET:
    raise RuntimeError("TAILSCALE_API_KEY or TAILNET not set in environment")

TS_AUTH_KEY_EXP_HOURS = int(os.getenv("TS_AUTH_KEY_EXP_HOURS", 3))

# Создание нового auth key
def create_tailscale_auth_key(session_id, tag: str = None, ephemeral=True, preauthorized=True, reusable=False, expiry_hours=TS_AUTH_KEY_EXP_HOURS):
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
        "description": f"{tag}-{session_id[:8]}"
    }

    response = requests.post(url, headers=headers, auth=auth, data=json.dumps(payload))

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Tailscale Auth Key created. Key: {data['key'][-10:]}. Expires in: {expiry_hours}d")
        return data['key'], expiry_hours
    else:
        logger.error(f"Failed to create key: {response.status_code}, {response.text}")
        logger.error(f"Tailscale auth_token creation failed\n")
        raise RuntimeError("Failed to create Tailscale auth key")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest().upper()


def create_token(mission_id, session_id, tag):
    token, exp_hours = create_tailscale_auth_key(session_id=session_id, tag=tag)
    now = datetime.utcnow()
    expires = now + timedelta(hours=exp_hours)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO grfp_sm_auth_tokens 
                (token_hash, mission_id, session_id, is_active_flg, tag, created_at, expires_at, updated_at)
                VALUES (%s, %s, %s, TRUE, %s, %s, %s, %s)
            """, (hash_token(token), mission_id, session_id, tag, now, expires, now,))
            conn.commit()
    logger.info(f"Tokens created successfully {token[-10:]}, {now}, {expires}\n")
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
    print(create_token('test_mission_id1', 'test_session_id1', 'client'))