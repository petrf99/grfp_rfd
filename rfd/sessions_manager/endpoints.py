# rfd_server.py
from flask import request, jsonify
import uuid
from datetime import datetime, timezone
import threading

from tech_utils.logger import init_logger
logger = init_logger("RFD_FSM_Endpoints")

from rfd.sessions_manager.vpn_establisher import gcs_client_connection_wait

from tech_utils.db import get_conn, update_versioned

def validate_token():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "reason": "Invalid or missing JSON body"}), 400

    token = data.get("token")

    if not token:
        return jsonify({"status": "error", "reason": "Missing token"}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Token has to be the last among all tokens for his mission_id
                cur.execute("""
                    WITH base_token AS (
                        SELECT distinct mission_id
                        FROM grfp_sm_auth_tokens
                        WHERE token_hash = %s
                        and valid_to IS NULL
                    ),
                    latest_tokens AS (
                        SELECT *, ROW_NUMBER() OVER (
                                   PARTITION BY mission_id
                                   ORDER BY valid_from DESC
                               ) AS row_num
                        FROM grfp_sm_auth_tokens
                        WHERE tag = 'client'
                        AND mission_id = (SELECT mission_id FROM base_token)
                        and valid_to IS NULL
                    )
                    SELECT id,
                            CASE WHEN row_num = 1 THEN is_active_flg ELSE FALSE END as is_active_flg, 
                            expires_at, session_id
                    FROM latest_tokens
                    WHERE token_hash = %s
                    ORDER BY valid_from DESC
                    LIMIT 1
                    ;

                """, (token, token))
                row = cur.fetchone()

                if not row:
                    logger.info(f"Token with hash {token} not found in DB")
                    return jsonify({"status": "error", "reason": "Invalid token"}), 403

                token_id, is_active, expires_at, session_id = row

                if not is_active or expires_at < datetime.now(timezone.utc):
                    logger.info(f"Token {token} is inactive or expired")
                    return jsonify({"status": "error", "reason": "Token expired or inactive"}), 403

                logger.info(f"Token {token} validation succeeded. Token_id: {token_id}. Session-id: {session_id}")
                return jsonify({"status": "ok", "session_id": session_id})

    except Exception as e:
        logger.error(f"Exception in validate_token {token}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500




from rfd.sessions_manager.token_manager import create_token
import os

import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

GCS_PROOF_TOKEN = os.getenv("GCS_PROOF_TOKEN")

def gcs_ready():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "reason": "Invalid or missing JSON body"}), 400

    mission_id = data.get("mission_id")
    try:
        uuid.UUID(mission_id)
    except Exception:
        return jsonify({"status": "error", "reason": "Invalid mission_id"}), 400
    gcs_proof_token = data.get("gcs_proof_token")

    if gcs_proof_token != GCS_PROOF_TOKEN:
        return jsonify({"status": "error", "reason": "Seems like your are not GCS"}), 403

    if not mission_id:
        return jsonify({"status": "error", "reason": "Missing mission_id"}), 400
    
    public_pem = data.get("rsa_pub_key")
    if not public_pem:
        return jsonify({"status": "error", "reason": "Missing public key"}), 400
    
    public_key = serialization.load_pem_public_key(public_pem.encode())


    try:
        session_id = str(uuid.uuid4())
        token = create_token(mission_id, session_id, 'gcs')
        client_token = create_token(mission_id, session_id, 'client')

        if os.getenv("LOG_LEVEL") == 'DEBUG':
            with open("client_token.txt", "w") as f:
                f.write(client_token)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status
                    FROM grfp_missions
                    WHERE mission_id = %s
                    and valid_to IS NULL
                            """, (mission_id,))
                
                row = cur.fetchone()
                if row:
                    status = row[0]
                else:
                    logger.error(f"Mission {mission_id} not found")
                    return jsonify({"status": "error", "reason": "mission not found"}), 403

                if status != 'in progress':
                    logger.error(f"Mission {mission_id} is not in progress")
                    return jsonify({"status": "error", "reason": "mission is not in progress"}), 403

                
                # Write session to db
                cur.execute("""
                    INSERT INTO grfp_sm_sessions 
                            (session_id, mission_id, status)
                    VALUES (%s, %s, 'in progress')
                """, (session_id, mission_id))
                conn.commit()

        # Setup VPN
        threading.Thread(
            target=gcs_client_connection_wait,
            args=(mission_id, session_id),
            daemon=True
        ).start()

        encrypted_token = public_key.encrypt(
            token.encode(),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )

        encrypted_b64 = base64.b64encode(encrypted_token).decode()

        logger.info(f"GCS for mission {mission_id} marked as ready. Session: {session_id}")
        return jsonify({
            "status": "ok",
            "session_id": session_id,
            "auth_token": encrypted_b64
        })

    except Exception as e:
        logger.exception(f"GCS-ready for mission {mission_id} failed with exception {e}")
        return jsonify({"status": "error", "reason": "internal server error"}), 500


def get_tailscale_ips():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "reason": "Invalid or missing JSON body"}), 400

    session_id = data.get("session_id")
    try:
        uuid.UUID(session_id)
    except Exception:
        return jsonify({"status": "error", "reason": "Invalid session_id"}), 400

    if not session_id:
        return jsonify({"status": "error", "reason": "Missing session_id"}), 400
    
    hash_auth_token = data.get("hash_auth_token")
    if not hash_auth_token:
        return jsonify({"status": "error", "reason": "Missing hash_auth_token"}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                            SELECT id, used_at
                            FROM grfp_sm_auth_tokens
                            WHERE is_active_flg = TRUE
                            AND valid_to IS NULL
                            AND token_hash = %s
                            AND session_id = %s
                            LIMIT 1
                            """, (hash_auth_token, session_id))
                
                row = cur.fetchone()

                if not row:
                    logger.info(f"Request for tailscale ips failed - invalid hash_auth_token: {hash_auth_token}. Session_id: {session_id}")
                    return jsonify({"status": "error", "reason": "Auth failed: invalid hash_auth_token"}), 403
                
                token_id, used_at = row

                if used_at is None:
                    update_versioned(conn, 'grfp_sm_auth_tokens', {'id': token_id}, {'used_at': datetime.now(timezone.utc)})


                cur.execute("""
                    SELECT gcs_ip, client_ip
                    FROM vpn_connections
                    WHERE session_id = %s
                    AND status = 'in progress'
                    and valid_to IS NULL
                    LIMIT 1
                """, (session_id,))
                row = cur.fetchone()

                if not row:
                    logger.info(f"Request for ip of not-ready vpn-connection. Session_id: {session_id}")
                    return jsonify({"status": "error", "reason": "VPN connection is not ready"}), 403

                gcs_ip, client_ip = row

                logger.info(f"Return tailscale IPs for session {session_id}:\nGCS IP: {gcs_ip}\nClient IP: {client_ip}")
                return jsonify({"status": "ok", "gcs_ip": gcs_ip, "client_ip": client_ip})

    except Exception as e:
        logger.error(f"Exception in retrieving Tailscale IPs for session {session_id}:\n{e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
    

from rfd.sessions_manager.session_manager import close_session
def gcs_session_finish():
    data = request.get_json()
    if not data:
        logger.error("Invalid request: Invalid or missing JSON body")
        return jsonify({"status": "error", "reason": "Invalid or missing JSON body"}), 400

    mission_id = data.get("mission_id")
    try:
        uuid.UUID(mission_id)
    except Exception:
        logger.error("Invalid request: Invalid mission_id")
        return jsonify({"status": "error", "reason": "Invalid mission_id"}), 400
    session_id = data.get("session_id")
    try:
        uuid.UUID(session_id)
    except Exception:
        logger.error("Invalid request: Invalid session_id")
        return jsonify({"status": "error", "reason": "Invalid session_id"}), 400
    result = data.get("result")
    gcs_proof_token = data.get("gcs_proof_token")

    if not result:
        logger.error("Invalid request: Invalid session result")
        return jsonify({"status": "error", "reason": "Missing session result"}), 400

    if not GCS_PROOF_TOKEN == gcs_proof_token:
        logger.error("Invalid request: Invalid gcs_proof_token")
        return jsonify({"status": "error", "reason": "Seems like your are not GCS"}), 400


        # Finish job
    threading.Thread(
            target=close_session,
            args=(session_id, result),
            daemon=True
        ).start()

    logger.info(f"Session {session_id} is being finished.")
    return jsonify({
            "status": "ok"
        })

