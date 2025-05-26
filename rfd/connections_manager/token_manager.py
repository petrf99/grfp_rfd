import hashlib
import requests
import json
from datetime import datetime, timedelta, timezone

from tech_utils.logger import init_logger
logger = init_logger("RFD_CM_TokenManager")


from rfd.config import TOKEN_EXPIRE_TMP, TAILSCALE_API_KEY, TAILNET
if not TAILSCALE_API_KEY or not TAILNET:
    raise RuntimeError("TAILSCALE_API_KEY or TAILNET not set in environment")

TS_AUTH_KEY_EXP_HOURS = TOKEN_EXPIRE_TMP // 3600

# Создание нового auth key
def create_tailscale_auth_key(hostname, tag, ephemeral=True, preauthorized=True, reusable=False, expiry_hours=TS_AUTH_KEY_EXP_HOURS):
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
        "description": hostname
    }

    response = requests.post(url, headers=headers, auth=auth, data=json.dumps(payload))

    if response.status_code == 200:
        data = response.json()
        logger.info(f"Tailscale Auth Key created. Key: {data['key'][-10:]}. Expires in: {expiry_hours}h")
        return data['key'], expiry_hours
    else:
        logger.error(f"Failed to create key: {response.status_code}, {response.text}")
        logger.error(f"Tailscale auth_token creation failed\n")
        raise RuntimeError("Failed to create Tailscale auth key")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest().upper()


def create_token(hostname_base, tag):
    hostname = tag + '-' + str(hostname_base)[-8:]
    token, exp_hours = create_tailscale_auth_key(hostname, tag)
    token_hash = hash_token(token)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=exp_hours)



    logger.info(f"Tokens created successfully {token[-10:]}, {now}, {expires}. Hash: {hash_token(token)}")
    return token, token_hash, expires, hostname