import os
import json
import requests
from datetime import datetime, timedelta

from tech_utils.logger import init_logger
logger = init_logger("RFD_TSOauth")

TOKEN_PATH = "rfd/flight_sessions_manager/tailscale_tokens.json"

CLIENT_ID = os.getenv("TAILSCALE_CLIENT_ID")
CLIENT_SECRET = os.getenv("TAILSCALE_CLIENT_SECRET")


def load_tokens():
    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError("Token file not found. Please perform initial OAuth exchange manually.")
    with open(TOKEN_PATH, "r") as f:
        return json.load(f)


def save_tokens(data):
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)


def is_token_expired(tokens):
    expires_at = datetime.fromisoformat(tokens["expires_at"])
    return datetime.utcnow() >= expires_at


def refresh_access_token(tokens):
    logger.info("[Tailscale] Refreshing access token...")
    resp = requests.post("https://api.tailscale.com/api/v2/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    resp.raise_for_status()
    new_data = resp.json()
    tokens["access_token"] = new_data["access_token"]
    tokens["expires_at"] = (datetime.utcnow() + timedelta(seconds=new_data["expires_in"])).isoformat()
    save_tokens(tokens)
    logger.info(f"Refresh access token succeeded: {tokens}")
    return tokens


def get_access_token():
    tokens = load_tokens()
    if is_token_expired(tokens):
        tokens = refresh_access_token(tokens)
    return tokens["access_token"]
