import requests
import time
import os

from tech_utils.logger import init_logger
logger = init_logger(name="TSmanager", component="cm")

# === Load API credentials from environment variables ===
TAILSCALE_API_KEY = os.getenv("TAILSCALE_API_KEY")
TAILNET = os.getenv("TAILNET")

# === Token caching for Tailscale OAuth API ===
_cached_token = None
_token_expires_at = 0

def get_access_token():
    """
    Get an OAuth access token for the Tailscale API using client credentials grant.
    Token is cached until expiration to avoid unnecessary requests.
    """
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at:
        return _cached_token

    resp = requests.post("https://api.tailscale.com/api/v2/oauth/token", data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("OAUTH_CLIENT_SECRET"),
    })
    resp.raise_for_status()
    data = resp.json()

    _cached_token = data["access_token"]
    _token_expires_at = time.time() + data["expires_in"] - 30  # expire slightly early for safety
    return _cached_token


# === Tailnet management functions ===

def get_devices():
    """
    Get the list of devices currently connected to the Tailnet.
    """
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/devices"
    headers = {
        "Authorization": f"Bearer {get_access_token()}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        devices = data.get("devices", [])

        if not isinstance(devices, list):
            raise ValueError("Invalid format: 'devices' is not a list")

        return devices

    except requests.HTTPError as e:
        logger.error(f"[Tailscale] get_devices failed: {e} — {response.text}", exc_info=True)
    except Exception as e:
        logger.error(f"[Tailscale] Unexpected error in get_devices: {e}", exc_info=True)

    return []  # fallback


def get_auth_keys():
    """
    Retrieve all authentication keys (auth keys) associated with the Tailnet.
    """
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys"
    auth = (TAILSCALE_API_KEY, "")

    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        keys = data.get("keys", [])
        auth_keys = [key for key in keys if key.get("keyType") == "auth"]
        return auth_keys

    except requests.HTTPError as e:
        logger.error(f"[Tailscale] get_auth_keys failed: {e} — {response.text}", exc_info=True)
    except Exception as e:
        logger.error(f"[Tailscale] Unexpected error in get_auth_keys: {e}", exc_info=True)

    return []  # fallback


def delete_device(device_id):
    """
    Remove a device from the Tailnet by its device ID.
    """
    url = f"https://api.tailscale.com/api/v2/device/{device_id}"
    headers = {
        "Authorization": f"Bearer {get_access_token()}"
    }

    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        logger.info(f"Device {device_id} successfully deleted.")
        return True
    else:
        logger.error(f"Tailscale error while deleting device {device_id}: {response.status_code} {response.text}")
        return False


def delete_auth_key(key_id):
    """
    Delete an authentication key by its ID.
    """
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys/{key_id}"
    auth = (TAILSCALE_API_KEY, "")

    response = requests.delete(url, auth=auth)
    if response.status_code == 200:
        logger.info(f"Authkey {key_id} deleted.")
        return True
    elif response.status_code == 404:
        logger.error(f"Authkey {key_id} doesn't exist.")
        return False
    else:
        logger.error(f"Error while deleting authkey {key_id}: {response.status_code} {response.text}")
        return False


def remove_from_tailnet(target_hostname):
    """
    Remove all devices and auth keys associated with a specific hostname from the Tailnet.
    """
    logger.info(f"Start removing {target_hostname} from Tailnet")
    
    # Fetch current devices and auth keys
    devices = get_devices()
    authkeys = get_auth_keys()

    deleted_dev = 0
    deleted_keys = 0

    # Delete matching devices
    for d in devices:
        hostname = d.get("hostname", "")
        if hostname == target_hostname:
            device_id = d["id"]
            logger.info(f"Deleting device with hostname: {hostname} and id: {device_id}")
            if delete_device(device_id):
                deleted_dev += 1

    # Delete matching auth keys
    for key in authkeys:
        desc = key.get("description", "")
        key_id = key.get("id")
        try:
            if desc == target_hostname:
                logger.info(f"Deleting auth_key with desc: {desc} and id: {key_id}")
                if delete_auth_key(key_id):
                    deleted_keys += 1
        except Exception as e:
            logger.warning(f"Clear session: Exception while deleting key: {e}")
            pass

    if deleted_dev + deleted_keys == 0:
        logger.info(f"Remove from Tailnet {target_hostname}: Nothing found to delete.")
    else:
        logger.info(f"Hostname {target_hostname} removed from Tailnet. {deleted_dev} devices and {deleted_keys} authkeys have been deleted")
