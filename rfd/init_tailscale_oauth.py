import os
import json
import requests
from datetime import datetime, timedelta

from tech_utils.logger import init_logger
logger = init_logger("RFD_TSOauth_Init")

CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
TOKEN_PATH = "rfd/flight_sessions_manager/tailscale_tokens.json"


def tailscale_oauth_init():
    if not os.path.exists(TOKEN_PATH):
        code = input("Paste your authorization code from Tailscale: ").strip()
    else:
        return

    response = requests.post("https://api.tailscale.com/api/v2/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    })

    if response.status_code != 200:
        logger.error("Error getting token:", response.status_code, response.text)
        return

    data = response.json()
    expires_in = data["expires_in"]
    data["expires_at"] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)

    logger.info("✅ Tailscale tokens saved to tailscale_tokens.json")
    logger.info("Access token expires at:", data["expires_at"])


if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Please set TAILSCALE_CLIENT_ID and TAILSCALE_CLIENT_SECRET as environment variables.")
    else:
        tailscale_oauth_init()
