from flask import Flask, request, jsonify

from tech_utils.db import get_conn, RealDictCursor
from tech_utils.email_utils import send_email, ground_teams_email
import uuid
from datetime import datetime

from tech_utils.logger import init_logger
logger = init_logger("RFD_MissionsManager")

def mission_request():
    mission_id = str(uuid.uuid4())
    logger.info(f"mission-request request received {mission_id}")
    data = request.get_json()
    required = ["user_id", "location", "time_window", "drone_type"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400


    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO grfp_missions (mission_id, user_id, location, time_window, drone_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (mission_id, data['user_id'], data["location"], data["time_window"], data["drone_type"]))
                conn.commit()

        logger.info(f"Mission request processed: {mission_id}")

        # Email alert to ground teams
        subject = f"[GRFP] New Mission Request: {mission_id}"
        body = "\n".join([f"{k}: {data[k]}" for k in required])
        send_email(subject, body, ground_teams_email)
        logger.info(f"Email sent to ground teams: {ground_teams_email}")

        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Error creating mission {mission_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "DB insert error"}), 500



def change_mission_status():
    logger.info(f"change-mission-status request received")
    data = request.get_json()
    required = ["mission_id", "new_status"]
    if not all(k in data for k in required):
        logger.info("Wrong status change request: missing parameters")
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400
    
    logger.info(f"Mission status change request correct {data['mission_id']}. New status: {data['new_status']}")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow()
                cur.execute("""
                        UPDATE grfp_missions
                        SET status = %s
                        , updated_at = %s
                        WHERE mission_id = %s
                        """, (data['new_status'], now, data['mission_id']))
                conn.commit()
                logger.info(f"Successfully changed status for {data['mission_id']}. New status: {data['new_status']}")
        
        # Email alert to ground teams
        subject = f"[GRFP] Mission Status Changed"
        body = "\n".join([data['mission_id'] + '\n', 'New status:', data['new_status']])
        send_email(subject, body, ground_teams_email)
        logger.info(f"Email sent to ground teams: {ground_teams_email}")

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Error changing mission status {data['mission_id']}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "DB insert error"}), 500


def get_missions_list():
    logger.info(f"get-missions-list request received")
    data = request.get_json(silent=True) or {}
    
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if not data.get("user_id"):
                    cur.execute("""
                        SELECT *
                        FROM grfp_missions
                        ORDER BY created_at DESC
                    """)
                    rows = cur.fetchall()
                    logger.info(f"Succseffully fetched missions list")
                else:
                    cur.execute("""
                        SELECT *
                        FROM grfp_missions
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                    """, (data['user_id'],))
                    rows = cur.fetchall()
                    logger.info(f"Succseffully fetched missions list for user {data['user_id']}")
        

        return jsonify({'status': 'ok', 'data': rows})
                
    except Exception as e:
        logger.error(f"Error in getting missions list: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "DB insert error"}), 500