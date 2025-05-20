from tech_utils.logger import init_logger
logger = init_logger("RFD_FSM_VPN")


import requests
import time
import os

from tech_utils.db import get_conn

# === НАСТРОЙКИ ===
 
TAILSCALE_API_KEY = os.getenv("TAILSCALE_API_KEY")
TAILNET = os.getenv("TAILNET")
POLL_INTERVAL = int(os.getenv("TAILSCALE_IP_POLL_INTERVAL"))
TIMEOUT = int(os.getenv("TAILSCALE_IP_POLL_TIMEOUT", 600))
TAILSCALE_IPS_POLL_CHECK_FREQ = int(os.getenv("TAILSCALE_IPS_POLL_CHECK_FREQ"))

from rfd.flight_sessions_manager.tailscale_oauth import get_access_token

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
                        """, (session_id,))
            
            row = cur.fetchone()
            if row == 'in progress':
                return True
            return False


def gcs_client_connection_wait(mission_id, session_id, timeout=TIMEOUT, interval=POLL_INTERVAL):
    hostname_client = f"client-{session_id[:8]}"
    hostname_gcs = f"gcs-{session_id[:8]}"

    start_time = time.time()

    is_active = is_sess_active(session_id)
    n_attempts = 0

    while is_active:
        devices = get_devices()
        found = {"client": None, "gcs": None}

        for d in devices:
            if d.get("hostname") == hostname_client:
                found["client"] = d
            elif d.get("hostname") == hostname_gcs:
                found["gcs"] = d

        if found["client"] and found["gcs"]:
            client_ip = found["client"]["addresses"][0]
            gcs_ip = found["gcs"]["addresses"][0]
            logger.info(f"Both devices connected for session {session_id}. Client: {client_ip}. GCS: {gcs_ip}")
            with get_conn() as conn:
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
                    """, (mission_id, session_id, hostname_gcs, hostname_client, gcs_ip, client_ip, 'ready'))
                    conn.commit()

        if time.time() - start_time > timeout:
            logger.error(f"Timeout error. No connected devices for session_id={session_id} found")
            # Write session to db
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE grfp_sm_sessions 
                        SET status = 'aborted'
                        where session_id = %s
                    """, (session_id, ))

                    cur.execute("""
                        UPDATE vpn_connections
                        SET status = 'timeout'
                        where session_id = %s
                    """, (session_id, ))
                    conn.commit()

            clear_tailnet(session_id)
            logger.info(f"Session {session_id} disconnected due to timeout")
            raise TimeoutError(f"Timeout error. No connected devices for session_id={session_id} found")
        
        logger.info(f"Waiting to connect {hostname_client} and {hostname_gcs}...")
        time.sleep(interval)
        n_attempts += 1
        if n_attempts % TAILSCALE_IPS_POLL_CHECK_FREQ == 0:
            is_active = is_sess_active(session_id)


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
    deleted = 0

    hostname_client = f"client-{session_id[:8]}"
    hostname_gcs = f"gcs-{session_id[:8]}"

    for d in devices:
        hostname = d.get("hostname", "")
        if hostname in [hostname_gcs, hostname_client]:
            device_id = d["id"]
            logger.info(f"Device {hostname} found (ID: {device_id}) — deleting...")
            delete_device(device_id)
            deleted += 1

    for key in authkeys:
        desc = key.get("description", "")
        key_id = key.get("id")
        if desc.split('-')[1] == session_id[:8]:
            logger.info(f"Authkey '{desc}' found — deleting...")
            delete_auth_key(key_id)
            deleted += 1

    if deleted == 0:
        logger.info(f"No devices found in session_id={session_id} to delete.")
    else:
        logger.info(f"Session {session_id} disconected. All devices and authkeys removed from Tailnet")