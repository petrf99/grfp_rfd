# rfd_server.py
from flask import Flask, request, jsonify
import uuid
from datetime import datetime
import threading

from tech_utils.logger import init_logger
logger = init_logger("RFD_FlightSessionsManager")

from rfd.flight_sessions_manager.vpn_establisher import gcs_client_connection_wait, disconnect_session

from tech_utils.db import get_conn

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
                # Проверим токен
                cur.execute("""
                    SELECT id, is_active_flg, expires_at, session_id
                    FROM grfp_sm_auth_tokens
                    WHERE token_hash = %s
                    AND tag = 'client'
                    LIMIT 1
                """, (token,))
                row = cur.fetchone()

                if not row:
                    logger.info(f"Token with hash {token} not found in DB")
                    return jsonify({"status": "error", "reason": "Invalid token"}), 403

                token_id, is_active, expires_at, session_id = row

                if not is_active or expires_at < datetime.utcnow():
                    logger.info(f"Token {token} is inactive or expired")
                    return jsonify({"status": "error", "reason": "Token expired or inactive"}), 403

                logger.info(f"Token {token} validation succeeded. Token_id: {token_id}. Session-id: {session_id}")
                return jsonify({"status": "ok", "session_id": session_id})

    except Exception as e:
        logger.error(f"Exception in validate_token {token}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500




from rfd.flight_sessions_manager.token_manager import create_token
import os

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
        return jsonify({"status": "error", "reason": "Seems like your are not GCS"}), 400

    if not mission_id:
        return jsonify({"status": "error", "reason": "Missing mission_id"}), 400

    try:
        session_id = str(uuid.uuid4())
        token = create_token(mission_id, session_id, 'gcs')
        client_token = create_token(mission_id, session_id, 'client')

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status
                    FROM grfp_missions
                    WHERE mission_id = %s
                            """, (mission_id,))
                
                row = cur.fetchone()
                if status:
                    status = row[0]
                else:
                    logger.error(f"Mission {mission_id} not found")
                    return jsonify({"status": "error", "reason": "mission not found"}), 400

                if status != 'in progress':
                    logger.error(f"Mission {mission_id} is not in progress")
                    return jsonify({"status": "error", "reason": "mission is not in progress"}), 400

                # Обновим миссию
                cur.execute("""
                    UPDATE grfp_missions
                    SET status = 'ready',
                        updated_at = %s
                    WHERE mission_id = %s
                """, (datetime.utcnow(), mission_id))
                
                # Write session to db
                cur.execute("""
                    INSERT INTO grfp_sm_sessions 
                            (session_id, status)
                    VALUES (%s, 'in progress')
                """, (session_id, ))
                conn.commit()

        # Setup VPN
        threading.Thread(
            target=gcs_client_connection_wait,
            args=(mission_id, session_id),
            daemon=True
        ).start()


        logger.info(f"GCS for mission {mission_id} marked as ready. Session: {session_id}")
        return jsonify({
            "status": "ok",
            "session_id": session_id,
            "auth_token": token
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

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT gcs_ip, client_ip
                    FROM vpn_connections
                    WHERE session_id = %s
                    AND status = 'ready'
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
    


def gcs_session_finish():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "reason": "Invalid or missing JSON body"}), 400

    mission_id = data.get("mission_id")
    try:
        uuid.UUID(mission_id)
    except Exception:
        return jsonify({"status": "error", "reason": "Invalid mission_id"}), 400
    session_id = data.get("session_id")
    try:
        uuid.UUID(session_id)
    except Exception:
        return jsonify({"status": "error", "reason": "Invalid session_id"}), 400
    result = data.get("result")
    gcs_proof_token = data.get("gcs_proof_token")

    if not result:
        return jsonify({"status": "error", "reason": "Missing session result"}), 400

    if not GCS_PROOF_TOKEN == gcs_proof_token:
        return jsonify({"status": "error", "reason": "Seems like your are not GCS"}), 400

    if not mission_id:
        return jsonify({"status": "error", "reason": "Missing mission_id"}), 400
    
    if not session_id:
        return jsonify({"status": "error", "reason": "Missing session_id"}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status
                    FROM grfp_sm_sessions
                    WHERE session_id = %s
                            """, (mission_id,))
                
                row = cur.fetchone()
                if row:
                    status = row[0]
                else:
                    logger.error(f"Session {session_id} not found")
                    return jsonify({"status": "error", "reason": "session not found"}), 400

                if status != 'in progress':
                    logger.error(f"Session {session_id} is not in progress")
                    return jsonify({"status": "error", "reason": "session is not in progress"}), 400

                if result == 'finished':
                    # Обновим миссию
                    cur.execute("""
                        UPDATE grfp_missions
                        SET status = 'finished',
                            updated_at = %s
                        WHERE mission_id = %s
                    """, (datetime.utcnow(), mission_id))

                    logger.info(f"Mission {mission_id} finished")
                
                # Write session to db
                cur.execute("""
                    UPDATE grfp_sm_sessions 
                    SET status = %s
                    where session_id = %s
                """, (result, session_id, ))

                cur.execute("""
                    UPDATE vpn_connections
                    SET status = 'finished'
                    where session_id = %s
                """, (session_id, ))
                conn.commit()


        # Finish VPN
        threading.Thread(
            target=disconnect_session,
            args=(session_id,),
            daemon=True
        ).start()

        logger.info(f"Session {session_id} is being finished.")
        return jsonify({
            "status": "ok"
        })

    except Exception as e:
        logger.exception(f"GCS-sessino-finish for session {session_id} failed with exception {e}")
        return jsonify({"status": "error", "reason": "internal server error"}), 500

