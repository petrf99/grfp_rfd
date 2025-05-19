import os
import time
import requests

_cached_token = None
_token_expires_at = 0

def get_access_token():
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at:
        return _cached_token

    resp = requests.post("https://api.tailscale.com/api/v2/oauth/token", data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("TAILSCALE_CLIENT_ID"),
        "client_secret": os.getenv("TAILSCALE_CLIENT_SECRET"),
    })
    resp.raise_for_status()
    data = resp.json()

    _cached_token = data["access_token"]
    _token_expires_at = time.time() + data["expires_in"] - 30  # немного заранее
    return _cached_token