from tech_utils.logger import init_logger
logger = init_logger("RFD_FSM_VPN")


import requests
import time
import os

from tech_utils.db import get_conn

# === НАСТРОЙКИ ===
from rfd.config import TAILSCALE_IP_POLL_INTERVAL, TAILSCALE_IP_POLL_TIMEOUT, TAILSCALE_IPS_POLL_CHECK_FREQ
TAILSCALE_API_KEY = os.getenv("TAILSCALE_API_KEY")
TAILNET = os.getenv("TAILNET")

from rfd.sessions_manager.tailscale_oauth import get_access_token

def get_devices():
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/devices"
    headers = {
        "Authorization": f"Bearer {get_access_token()}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        #logger.debug(f"[Tailscale] get_devices response: {data}")
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
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys"
    auth = (TAILSCALE_API_KEY, "")

    try:
        response = requests.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        #logger.debug(f"[Tailscale] get_auth_keys response: {data}")
        keys = data.get("keys", [])
        auth_keys = [key for key in keys if key.get("keyType") == "auth"]
        return auth_keys

    except requests.HTTPError as e:
        logger.error(f"[Tailscale] get_auth_keys failed: {e} — {response.text}", exc_info=True)
    except Exception as e:
        logger.error(f"[Tailscale] Unexpected error in get_auth_keys: {e}", exc_info=True)

    return []  # fallback


def is_sess_active(session_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status
                FROM grfp_sm_sessions
                WHERE session_id = %s
                AND valid_to IS NULL
                        """, (session_id,))
            
            row = cur.fetchone()
            if row:
                status = row[0]
                if status == 'in progress':
                    return True
                else:
                    logger.info(f"Session {session_id} which was waiting for connection has been deactivated")
            else:
                logger.info(f"Session {session_id} which was waiting for connection not found")
            return False


def gcs_client_connection_wait(mission_id, session_id, timeout=TAILSCALE_IP_POLL_TIMEOUT, interval=TAILSCALE_IP_POLL_INTERVAL):
    logger.info("Start connecting GCS and Client")
    hostname_client = os.getenv("TEST_CLIENT_HOSTNAME", f"client-{session_id[:8]}")
    hostname_gcs = os.getenv("TEST_GCS_HOSTNAME", f"gcs-{session_id[:8]}")

    start_time = time.time()

    is_active = is_sess_active(session_id)
    n_attempts = 0

    conn = get_conn()
    try:
        while is_active:
            devices = get_devices()
            found = {"client": None, "gcs": None}

            for d in devices:
                name = d.get("name", "").split(".")[0]
                if name == hostname_client:
                    found["client"] = d
                elif name == hostname_gcs:
                    found["gcs"] = d

            if found["client"] and found["gcs"]:
                client_ip = found["client"]["addresses"][0]
                gcs_ip = found["gcs"]["addresses"][0]

                logger.info(f"Both devices connected for session {session_id}. Client: {client_ip}. GCS: {gcs_ip}")
                with conn.cursor() as cur:
                    cur.execute("""
                            INSERT INTO vpn_connections (
                            mission_id,
                            session_id ,
                            gcs_ready_flg,
                            client_ready_flg,
                            tailscale_name_gcs,
                            tailscale_name_client,
                            gcs_ip,
                            client_ip,
                            status )
                            VALUES (%s, %s, TRUE, TRUE, %s, %s, %s, %s, %s)
                        """, (mission_id, session_id, hostname_gcs, hostname_client, gcs_ip, client_ip, 'in progress'))
                    conn.commit()
                    return

            if time.time() - start_time > timeout:
                logger.error(f"Timeout error. No connected devices for session_id={session_id} found")
                logger.info(f"Session {session_id} disconnected due to timeout")
                raise TimeoutError(f"Timeout error. No connected devices for session_id={session_id} found")
            
            logger.info(f"Waiting to connect {hostname_client} and {hostname_gcs}...")
            time.sleep(interval)
            n_attempts += 1
            if n_attempts % TAILSCALE_IPS_POLL_CHECK_FREQ == 0:
                is_active = is_sess_active(session_id)
    except Exception as e:
        logger.exception(f"Client-connection-wait job failed for session {session_id} failed with exception {e}")
        return
    finally:
        conn.close()



def delete_device(device_id):
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
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys/{key_id}"

    auth = (TAILSCALE_API_KEY, "")

    response = requests.delete(url, auth=auth)#, headers=headers)
    if response.status_code == 200:
        logger.info(f"Authkey {key_id} deleted.")
        return True
    elif response.status_code == 404:
        #print("Authkey {key_id} doesn't exist.")
        logger.error(f"Authkey {key_id} doesn't exist.")
        return False
    else:
        #print(f"Error while deleting authkey {key_id}: {response.status_code} {response.text}")
        logger.error(f"Error while deleting authkey {key_id}: {response.status_code} {response.text}")
        return False


def clear_tailnet(session_id):
    devices = get_devices()
    authkeys = get_auth_keys()
    #print(f"######### {authkeys}")
    deleted_dev = 0
    deleted_keys = 0

    hostname_client = f"client-{session_id[:8]}"
    hostname_gcs = f"gcs-{session_id[:8]}"

    for d in devices:
        hostname = d.get("hostname", "")
        if hostname in [hostname_gcs, hostname_client]:
            device_id = d["id"]
            logger.info(f"Device {hostname} found (ID: {device_id}) — deleting...")
            delete_device(device_id)
            deleted_dev += 1

    for key in authkeys:
        desc = key.get("description", "")
        key_id = key.get("id")
        try:
            if desc.split('-')[1] == session_id[:8] and desc.split('-')[0] in ['gcs', 'client']:
                if delete_auth_key(key_id):
                    deleted_keys += 1
        except Exception as e:
            logger.warning(f"Clear session: Exception while deleting key: {e}")
            pass

    if deleted_dev + deleted_keys == 0:
        logger.info(f"Clear session: Nothing found to delete.")
    else:
        logger.info(f"Session {session_id} tailnet cleared. {deleted_dev} devices and {deleted_keys} authkeys removed from Tailnet")


if __name__ == '__main__':
    gcs_client_connection_wait('abc', '325db547-e4ec-465b-a692-f3ebce2521a7')