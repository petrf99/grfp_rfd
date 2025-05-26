# rfd_server.py
from flask import request, jsonify
import uuid

from tech_utils.logger import init_logger
logger = init_logger("RFD_CM_Endpoints")

from tech_utils.db import get_conn, update_versioned

from rfd.connections_manager.token_manager import create_token
from rfd.connections_manager.tailscale_manager import remove_from_tailnet

import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

from rfd.config import GCS_PROOF_TOKENS_FILE, GCS_PROOF_TOKEN_BASE
import hashlib

def register_gcs():
    logger.info("register-gcs request received")
    try:
        with open(GCS_PROOF_TOKENS_FILE, "r") as f:
            existing_tokens = f.read().split()
    except FileNotFoundError:
        logger.warning("No GCS_PROOF_TOKENS_FILE found")
        existing_tokens = []

    n = len(existing_tokens)
    
    raw = str(GCS_PROOF_TOKEN_BASE ** (n + 1)).encode()
    gcs_proof_token = hashlib.md5(raw).hexdigest()

    with open(GCS_PROOF_TOKENS_FILE, "a") as f:
        f.write(gcs_proof_token + "\n")

    logger.info("GCS registered successfully")
    return jsonify({"status": "ok", "gcs_proof_token": gcs_proof_token})

    

def get_vpn_connection():
    logger.info("get-vpn-connection request received")
    data = request.get_json()
    required = ["tag"]
    if not data or not all(k in data for k in required):
        logger.warning("get-vpn-connection: Missing tag")
        return jsonify({"status": "error", "reason": "Missing tag"}), 400
    
    public_pem = data.get("rsa_pub_key")
    if not public_pem:
        return jsonify({"status": "error", "reason": "Missing public key"}), 400
    public_key = serialization.load_pem_public_key(public_pem.encode())

    tag = data.get("tag")

    with open(GCS_PROOF_TOKENS_FILE, "r") as f:
        GCS_PROOF_TOKENS = f.read().split()

    if tag == "gcs":
        if data.get("gcs_proof_token") not in GCS_PROOF_TOKENS or not data.get("mission_group"):
            logger.warning(f"get-vpn-connection: Mission or invalid gcs_proof_token {data.get('gcs_proof_token')} or mission_group {data.get('mission_group')}")
            return jsonify({"status": "error", "reason": "Missing or invalid gcs_proof_token or mission_group"}), 400
        parent_id = data["mission_group"]
        parent_name = "mission_group"
        hostname_base = data.get("gcs_proof_token")

    elif tag == "client":
        if not data.get("mission_id"):
            logger.warning(f"get-vpn-connection: Missing mission id for client's request")
            return jsonify({"status": "error", "reason": "Missing mission_id"}), 400
        parent_id = data["mission_id"]
        parent_name = "mission_id"

    else:
        logger.warning(f"get-vpn-connection: Invalid tag {tag}")
        return jsonify({"status": "error", "reason": "Invalid tag"}), 400


    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT * FROM grfp_missions WHERE {parent_name} = {parent_id}
                    WHERE status = 'in progress'
                    AND valid_to IS NULL
                    """)
                row = cur.fetchone()

                if not row:
                    logger.warning(f"get-vpn-connection: missions found in grfp_missions table for {parent_name}={parent_id}")
                    return jsonify({"status": "error", "reason": "No active missions"}), 403

                if tag == 'client':
                    cur.execute(f"""
                        SELECT session_id
                        FROM grfp_sessions
                        WHERE valid_to IS NULL
                        AND mission_id = {parent_id}
                        AND status = 'in progress'
                        ORDER BY valid_from DESC
                        LIMIT 1
                                """)

                    row = cur.fetchone()
                    if not row:
                        logger.warning(f"get-vpn-connection: no active sessions found for client's request {parent_name}={parent_id}")
                        return jsonify({"status": "error", "reason": "No active sessions"}), 403
                    
                    else:
                        parent_name = 'session_id'
                        parent_id = row[0]
                        hostname_base = parent_id

                token, token_hash, expires, hostname = create_token(hostname_base, tag)

                cur.execute(f"""
                INSERT INTO vpn_connections (parent_id, parent_name, token_hash, hostname, tag, token_expires_at)
                VALUES ({parent_id}, {parent_name}, {token_hash}, {hostname}, {tag}, {expires})
                """)
                conn.commit()

                encrypted_token = public_key.encrypt(
                    token.encode(),
                    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
                )

                encrypted_b64 = base64.b64encode(encrypted_token).decode()

        logger.info(f"get-vpn-connection succeeded. Token: {token[-10:]}. Hostname: {hostname}. {parent_name} = {parent_id}")
        return jsonify({"status": "ok", "token": encrypted_b64, "hostname": hostname, "token_hash": token_hash})

    except Exception as e:
        logger.error(f"Exception in get-vpn-connection: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
    

def delete_vpn_connection():
    logger.info("delete-vpn-connection request received")
    data = request.get_json()
    required = ["hostname", "token_hash"]
    if not data or not all(k in data for k in required):
        logger.warning(f"delete-vpn-connection: Missing parameters in {data}")
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400
    
    hostname = data.get("hostname")
    token_hash = data.get("token_hash")

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT * FROM vpn_connections WHERE hostname = {hostname} and token_hash = {token_hash}
                    WHERE is_active_flg = TRUE
                    AND valid_to IS NULL
                    """)
                row = cur.fetchone()

                if not row:
                    logger.warning(f"delete-vpn-connection: no active connections found for hostname={hostname}, token_hash={token_hash}")
                    return jsonify({"status": "error", "reason": "No active connections"}), 403
                
                logger.info(f"delete-vpn-connection: delete {hostname} from tailnet")
                remove_from_tailnet(hostname)

                logger.info(f"delete-vpn-connection: deactivating record in DB for hostname: {hostname}, token_hash: {token_hash}")
                update_versioned(conn, 'vpn_connections', {'token_hash': token_hash, 'hostname': hostname}, {'is_active_flg': False})

        logger.info(f"delete-vpn-connection: success. Hostname: {hostname}")  
        return jsonify({"status": "ok"}), 200  

    except Exception as e:
        logger.error(f"Exception in delete-vpn-connection for {hostname}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500



def start_session():
    logger.info("start-session request received")
    data = request.get_json()
    required = ["gcs_proof_token", "session_id", "mission_id"]
    if not data or not all(k in data for k in required):
        logger.warning(f"delete-vpn-connection: Missing parameters in {data}")
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400
    
    session_id = data.get("session_id")
    mission_id = data.get("mission_id")
    gcs_proof_token = data.get("gcs_proof_token")

    try:
        with open(GCS_PROOF_TOKENS_FILE, "r") as f:
            GCS_PROOF_TOKENS = f.read().split()
            if gcs_proof_token not in GCS_PROOF_TOKENS:
                return jsonify({"status": "error", "reason": "Gcs proof token not found"}), 400
    
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                        INSERT INTO grfp_sm_sessions 
                                (session_id, mission_id, status)
                        VALUES (%s, %s, 'in progress')
                    """, (session_id, mission_id))
                conn.commit()
        
        logger.info(f"start-session: success. Session ID: {session_id} Mission ID: {mission_id}")
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        logger.error(f"Exception in start-session with id {session_id} (mission: {mission_id}): {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
    

def close_session():
    logger.info("close-session request received")
    data = request.get_json()
    required = ["session_id", "result", "gcs_proof_token"]
    if not data or not all(k in data for k in required):
        logger.warning(f"delete-vpn-connection: Missing parameters in {data}")
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400
    
    session_id = data.get("session_id")
    result = data.get("result")
    gcs_proof_token = data.get("gcs_proof_token")

    try:
        with open(GCS_PROOF_TOKENS_FILE, "r") as f:
            GCS_PROOF_TOKENS = f.read().split()
            if gcs_proof_token not in GCS_PROOF_TOKENS:
                return jsonify({"status": "error", "reason": "Gcs proof token not found"}), 400
    
        with get_conn() as conn:
            with conn.cursor() as cur:
                update_versioned(conn, 'grfp_sessions', {'session_id', session_id}, {'status': result})

        logger.info(f"close-session: success. Session ID: {session_id}")
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        logger.error(f"Exception in close-session with id {session_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
