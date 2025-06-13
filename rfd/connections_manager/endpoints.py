# rfd_server.py

from flask import request, jsonify
import uuid

from tech_utils.logger import init_logger
logger = init_logger(name="CMEndpoints", component="cm")

from tech_utils.db import get_conn, update_versioned
from rfd.connections_manager.token_manager import create_token
from rfd.connections_manager.tailscale_manager import remove_from_tailnet

import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

from rfd.config import GCS_PROOF_TOKENS_FILE, GCS_PROOF_TOKEN_BASE
import hashlib

# === Endpoint for registering a new GCS by generating a unique proof token ===
def register_gcs():
    logger.info("register-gcs request received")

    # Read existing proof tokens from file
    try:
        with open(GCS_PROOF_TOKENS_FILE, "r") as f:
            existing_tokens = f.read().split()
    except FileNotFoundError:
        logger.warning("No GCS_PROOF_TOKENS_FILE found")
        existing_tokens = []

    # Generate new proof token using hash of incremented exponentiation
    n = len(existing_tokens)
    raw = str(GCS_PROOF_TOKEN_BASE ** (n + 1)).encode()
    gcs_proof_token = hashlib.md5(raw).hexdigest()

    # Append new token to the file
    with open(GCS_PROOF_TOKENS_FILE, "a") as f:
        f.write(gcs_proof_token + "\n")

    logger.info("GCS registered successfully")
    return jsonify({"status": "ok", "gcs_proof_token": gcs_proof_token}), 200

# === Endpoint to request VPN connection for a client or GCS ===
def get_vpn_connection():
    logger.info("get-vpn-connection request received")
    data = request.get_json()

    # Validate basic request structure
    required = ["tag"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing tag"}), 400

    # Load public key to encrypt the response token
    public_pem = data.get("rsa_pub_key")
    if not public_pem:
        return jsonify({"status": "error", "reason": "Missing public key"}), 400

    try:
        public_key = serialization.load_pem_public_key(public_pem.encode())
    except ValueError:
        return jsonify({"status": "error", "reason": "Invalid public key format"}), 400

    tag = data.get("tag")

    # Load allowed GCS proof tokens
    with open(GCS_PROOF_TOKENS_FILE, "r") as f:
        GCS_PROOF_TOKENS = f.read().split()

    # Validate tag and extract relevant mission/session
    if tag == "gcs":
        if data.get("gcs_proof_token") not in GCS_PROOF_TOKENS or not data.get("mission_group"):
            return jsonify({"status": "error", "reason": "Missing or invalid gcs_proof_token or mission_group"}), 400
        parent_id = data["mission_group"]
        parent_name = "mission_group"
        hostname_base = data.get("gcs_proof_token")

    elif tag == "client":
        if not data.get("mission_id"):
            return jsonify({"status": "error", "reason": "Missing mission_id"}), 400
        parent_id = data["mission_id"]
        parent_name = "mission_id"

    else:
        return jsonify({"status": "error", "reason": "Invalid tag"}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check if mission exists and is in progress
                cur.execute(f"""
                    SELECT * FROM grfp_missions WHERE {parent_name} = %s
                    AND status = 'in progress'
                    AND valid_to IS NULL
                    """, (parent_id,))
                row = cur.fetchone()
                if not row:
                    return jsonify({"status": "error", "reason": "Missions not found"}), 403

                # If client, fetch current session
                if tag == 'client':
                    cur.execute("""
                        SELECT session_id
                        FROM grfp_sessions
                        WHERE valid_to IS NULL
                        AND mission_id = %s
                        AND status = 'in progress'
                        ORDER BY valid_from DESC
                        LIMIT 1
                                """, (parent_id,))
                    row = cur.fetchone()
                    if not row:
                        return jsonify({"status": "error", "reason": "No active sessions"}), 403

                    parent_name = 'session_id'
                    parent_id = row[0]
                    hostname_base = parent_id

                # Generate token and store VPN connection in DB
                token, token_hash, expires, hostname = create_token(hostname_base, tag)
                cur.execute("""
                INSERT INTO vpn_connections (parent_id, parent_name, token_hash, hostname, tag, token_expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (parent_id, parent_name, token_hash, hostname, tag, expires))
                conn.commit()

                # Encrypt token with public key
                encrypted_token = public_key.encrypt(
                    token.encode(),
                    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
                )

                encrypted_b64 = base64.b64encode(encrypted_token).decode()

        logger.info(f"get-vpn-connection succeeded for {hostname}")
        return jsonify({"status": "ok", "token": encrypted_b64, "hostname": hostname, "token_hash": token_hash}), 200

    except Exception as e:
        logger.error(f"Exception in get-vpn-connection: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

# === Endpoint to deactivate VPN connection and remove from tailnet ===
def delete_vpn_connection():
    logger.info("delete-vpn-connection request received")
    data = request.get_json()
    required = ["hostname", "token_hash"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400

    hostname = data.get("hostname")
    token_hash = data.get("token_hash")

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Validate active connection exists
                cur.execute("""
                    SELECT * FROM vpn_connections
                    WHERE hostname = %s AND token_hash = %s
                    AND is_active_flg = TRUE AND valid_to IS NULL
                    """, (hostname, token_hash))
                row = cur.fetchone()
                if not row:
                    return jsonify({"status": "error", "reason": "No active connections"}), 403

                # Remove from Tailscale and deactivate in DB
                remove_from_tailnet(hostname)
                update_versioned(conn, 'vpn_connections', {'token_hash': token_hash, 'hostname': hostname}, {'is_active_flg': False})

        logger.info(f"delete-vpn-connection succeeded for {hostname}")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Exception in delete-vpn-connection for {hostname}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

# === Endpoint to start a flight session ===
def start_session():
    logger.info("start-session request received")
    data = request.get_json()
    required = ["gcs_proof_token", "session_id", "mission_id"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400

    session_id = data.get("session_id")
    mission_id = data.get("mission_id")
    gcs_proof_token = data.get("gcs_proof_token")

    try:
        # Validate GCS proof token
        with open(GCS_PROOF_TOKENS_FILE, "r") as f:
            if gcs_proof_token not in f.read().split():
                return jsonify({"status": "error", "reason": "Gcs proof token not found"}), 400

        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check mission exists and is active
                cur.execute("""
                    SELECT * FROM grfp_missions WHERE mission_id = %s
                    AND status = 'in progress' AND valid_to IS NULL
                    """, (mission_id,))
                row = cur.fetchone()
                if not row:
                    return jsonify({"status": "error", "reason": "Mission not found"}), 403

                # Create new session
                cur.execute("""
                        INSERT INTO grfp_sessions 
                        (session_id, mission_id, status)
                        VALUES (%s, %s, 'in progress')
                    """, (session_id, mission_id))
                conn.commit()

        logger.info(f"start-session succeeded for {session_id}")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Exception in start-session: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500

# === Endpoint to close a session and set its result status ===
def close_session():
    logger.info("close-session request received")
    data = request.get_json()
    required = ["session_id", "result", "gcs_proof_token"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400

    session_id = data.get("session_id")
    result = data.get("result")
    gcs_proof_token = data.get("gcs_proof_token")

    try:
        # Validate GCS proof token
        with open(GCS_PROOF_TOKENS_FILE, "r") as f:
            if gcs_proof_token not in f.read().split():
                return jsonify({"status": "error", "reason": "Gcs proof token not found"}), 400

        with get_conn() as conn:
            with conn.cursor() as cur:
                # Ensure the session is valid and in progress
                cur.execute("""
                    SELECT * FROM grfp_sessions
                    WHERE session_id = %s AND valid_to IS NULL AND status = 'in progress'
                    """, (session_id,))
                row = cur.fetchone()
                if not row:
                    return jsonify({"status": "error", "reason": "Session not found"}), 403

                # Mark session with final status
                update_versioned(conn, 'grfp_sessions', {'session_id': session_id}, {'status': result})

        logger.info(f"close-session succeeded for {session_id}")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Exception in close-session: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
