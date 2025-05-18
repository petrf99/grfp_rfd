from tech_utils.logger import init_logger
logger = init_logger("RFD_FlightSessionsManagerVPN")


import requests
import time
import os

from tech_utils.db import get_conn

# === НАСТРОЙКИ ===
from urllib.parse import quote
 
TAILSCALE_API_KEY = os.getenv("TAILSCALE_API_KEY")
TAILNET = quote(os.getenv("TAILNET"))
POLL_INTERVAL = int(os.getenv("TAILSCALE_IP_POLL_INTERVAL"))
TIMEOUT = os.getenv(os.getenv("TAILSCALE_IP_POLL_TIMEOUT"))

def get_devices():
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/devices"
    auth = (TAILSCALE_API_KEY, "")
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    return response.json()


def get_auth_keys():
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys"
    auth = (TAILSCALE_API_KEY, "")
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    return response.json().get("keys", [])

def gcs_client_connection_wait(mission_id, session_id, timeout=TIMEOUT, interval=POLL_INTERVAL):
    hostname_client = f"client_{session_id}"
    hostname_gcs = f"gcs_{session_id}"

    start_time = time.time()

    while True:
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
                        status
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

            disconnect_session(session_id)
            logger.info(f"Session {session_id} disconnected due to timeout")
            raise TimeoutError(f"Timeout error. No connected devices for session_id={session_id} found")
        
        logger.info(f"Waiting to connect client_{session_id} and gcs_{session_id}...")
        time.sleep(interval)


def delete_device(device_id):
    url = f"https://api.tailscale.com/api/v2/device/{device_id}"
    auth = (TAILSCALE_API_KEY, "")
    response = requests.delete(url, auth=auth)
    if response.status_code == 200:
        logger.info(f"Device {device_id} successsfully deleted.")
    else:
        logger.error(f"Tailscale error while deleting device {device_id}: {response.status_code} {response.text}")


def delete_auth_key(key_id):
    url = f"https://api.tailscale.com/api/v2/tailnet/{TAILNET}/keys/{key_id}"
    auth = (TAILSCALE_API_KEY, "")
    response = requests.delete(url, auth=auth)
    if response.status_code == 200:
        logger.info(f"Authkey {key_id} deleted.")
    elif response.status_code == 404:
        logger.error(f"Authkey {key_id} doesn't exist.")
    else:
        logger.error(f"Error while deleting authkey {key_id}: {response.status_code} {response.text}")


def disconnect_session(session_id):
    devices = get_devices()
    authkeys = get_auth_keys()
    seen_keys = set()
    deleted = 0

    for d in devices:
        hostname = d.get("hostname", "")
        if hostname in [f"client_{session_id}", f"gcs_{session_id}"]:
            device_id = d["id"]
            logger.info(f"Device {hostname} found (ID: {device_id}) — deleting...")
            delete_device(device_id)
            deleted += 1

    for key in authkeys:
        desc = key.get("description", "")
        key_id = key.get("id")
        if session_id == desc.split('_')[2]:
            logger.info(f"Authkey '{desc}' found — deleting...")
            delete_auth_key(key_id)
            deleted += 1

    if deleted == 0:
        logger.info(f"No devices found in session_id={session_id} to delete.")
    else:
        logger.info(f"Session {session_id} disconected. All devices and authkeys removed from Tailnet")