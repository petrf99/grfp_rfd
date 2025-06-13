import hashlib
import requests
import json
from datetime import datetime, timedelta, timezone

from tech_utils.logger import init_logger
logger = init_logger(name="TokenManager", component="cm")

from rfd.config import TOKEN_EXPIRE_TMP, TAILSCALE_API_KEY, TAILNET

# Ensure required environment variables are set
if not TAILSCALE_API_KEY or not TAILNET:
    raise RuntimeError("TAILSCALE_API_KEY or TAILNET not set in environment")

# Convert token expiration time from seconds to hours
TS_AUTH_KEY_EXP_HOURS = TOKEN_EXPIRE_TMP // 3600

# === Create new Tailscale auth key ===
def create_tailscale_auth_key(hostname, tag, ephemeral=True, preauthorized=True, reusable=False, expiry_hours=TS_AUTH_KEY_EXP_HOURS):
    """
    Creates a new Tailscale authentication key with specific capabilities.

    Args:
        hostname (str): Human-readable identifier, used in the key description.
        tag (str): Tailscale tag to assign to the device (e.g., 'gcs' or 'client').
        ephemeral (bool): Whether the key is ephemeral (short-lived, non-reusable).
        preauthorized (bool): Whether the device can join automatically without approval.
        reusable (bool): Whether the key can be reused for multiple devices.
        expiry_hours (int): Key expiration in hours.

    Returns:
        tuple: (auth key as str, expiry time in hours)

    Raises:
        RuntimeError: if key creation fails.
    """
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys"
    headers = {"Content-Type": "application/json"}
    auth = (TAILSCALE_API_KEY, "")  # Basic auth with API key as username

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
    """
    Securely hashes the token using SHA-256 and returns the uppercase hex digest.

    Args:
        token (str): The plain text token.

    Returns:
        str: SHA-256 hash of the token in uppercase hex.
    """
    return hashlib.sha256(token.encode()).hexdigest().upper()


def create_token(hostname_base, tag):
    """
    High-level wrapper that creates a Tailscale auth key, computes its hash,
    calculates expiration time, and generates a hostname.

    Args:
        hostname_base (str): Base string to generate the hostname.
        tag (str): Tag assigned to the device.

    Returns:
        tuple: (token, token_hash, expiration datetime, hostname)
    """
    # Hostname includes tag and suffix of the base for uniqueness
    hostname = tag + '-' + str(hostname_base)[-8:]
    
    # Create the Tailscale auth key
    token, exp_hours = create_tailscale_auth_key(hostname, tag)

    # Hash the token for secure DB storage or validation
    token_hash = hash_token(token)

    # Compute expiration time in UTC
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=exp_hours)

    logger.info(f"Tokens created successfully {token[-10:]}, {now}, {expires}. Hash: {hash_token(token)}")
    
    return token, token_hash, expires, hostname