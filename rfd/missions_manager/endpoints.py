from flask import Flask, request, jsonify, g

from tech_utils.db import get_conn, update_versioned, RealDictCursor
from tech_utils.email_utils import send_email
from rfd.config import GROUND_TEAMS_EMAIL, RFD_ADMIN_EMAIL
from rfd.auth.require_auth_dec import require_auth
import rfd.missions_manager.field_validators as fv
import uuid

from tech_utils.logger import init_logger
logger = init_logger(name="MMEndpoints", component="mm")


# === Endpoint to create a new mission ===
#@require_auth(allowed_emails = None) - TBD: require auth
def mission_request():
    mission_id = str(uuid.uuid4())  # Generate a unique mission ID
    logger.info(f"mission-request request received {mission_id}")
    data = request.get_json()

    # Check for required fields
    required = ["time_window", "drone_type"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing parameters: time_window or drone_type"}), 400
    if not fv.drone_type_val(data.get("drone_type")):
        return jsonify({"status": "error", "reason": "Drone type does not exist"}), 404

    # User ID extraction - to be replaced with JWT data
    if not 'email' in data:
        return jsonify({"status": "error", "reason": "Email required"}), 400
    if not fv.email_val(data.get('email')):
        return jsonify({"status": "error", "reason": "User with given email does not exist"}), 404

    # Prepare values for SQL INSERT
    columns = ['mission_id']
    placeholders = ['%s']
    values = [mission_id]  

    # Optional fields
    if "mission_group" in data:
        if not fv.mission_group_val(data.get("mission_group")):
            return jsonify({"status": "error", "reason": "Mission_group does not exist"}), 404 
        columns.append('mission_group')
        placeholders.append('%s')
        values.append(data.get("mission_group"))
    if "mission_type" in data:
        if not fv.mission_type_val(data.get("mission_type")):
            return jsonify({"status": "error", "reason": "Mission_type does not exist"}), 404 
        columns.append('mission_type')
        placeholders.append('%s')
        values.append(data.get("mission_type"))
    if "location" in data:
        if not fv.location_val(data.get("location")):
            return jsonify({"status": "error", "reason": "Location does not exist"}), 404 
        columns.append('location')
        placeholders.append('%s')
        values.append(data.get("location"))

    # Add required fields
    columns += ['email', 'time_window', 'drone_type']
    placeholders += ['%s'] * 3
    values += [data.get("email"), data.get("time_window"), data.get("drone_type")]

    try:
        # Insert into database
        with get_conn() as conn:
            with conn.cursor() as cur:
                sql = f"""
                    INSERT INTO grfp_missions ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                """
                cur.execute(sql, values)
                conn.commit()

        logger.info(f"Mission request processed: {mission_id}")

        # Notify ground teams via email
        subject = f"[GRFP] New Mission Request: {mission_id}"
        body = "\n".join([f"{k}: {data[k]}" for k in required])
        send_email(subject, body, GROUND_TEAMS_EMAIL)
        logger.info(f"Email sent to ground teams: {GROUND_TEAMS_EMAIL}")

        return jsonify({"status": "ok", "mission_id": mission_id}), 200

    except Exception as e:
        logger.error(f"Error creating mission {mission_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500


# === Endpoint to create a new mission group ===
@require_auth(allowed_emails=[RFD_ADMIN_EMAIL, GROUND_TEAMS_EMAIL])
def mission_group_request():
    logger.info("Mission group request received")
    data = request.get_json()
    if "mission_group" in data:
        mission_group = data.get('mission_group')
        logger.info(f"mission-group-request received {mission_group}")
    else:
        return jsonify({"status": "error", "reason": "Missing mission_group value"}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check if mission group already exists
                cur.execute("""
                    SELECT *
                    FROM grfp_mission_groups
                    WHERE mission_group = %s AND valid_to IS NULL
                """, (mission_group,))

                if cur.fetchall():
                    logger.error(f"Mission group already exists: {mission_group}", exc_info=True)
                    return jsonify({"status": "error", "reason": "Mission group already exists"}), 400
                
                # Create new mission group
                cur.execute("""
                    INSERT INTO grfp_mission_groups (mission_group) VALUES (%s)
                """, (mission_group,))
                conn.commit()

        logger.info(f"Mission group request processed: {mission_group}")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Error creating mission group {mission_group}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500


# === Endpoint to change the status of an existing mission ===
#@require_auth(allowed_emails=[RFD_ADMIN_EMAIL, GROUND_TEAMS_EMAIL])
def change_mission_status():
    logger.info(f"change-mission-status request received")
    data = request.get_json()

    required = ["mission_id", "new_status"]
    if not all(k in data for k in required):
        logger.info("Wrong status change request: missing parameters")
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400
    
    logger.info(f"Mission status change request: {data['mission_id']}. New status: {data['new_status']}")
    
    conn = get_conn()
    try:
        # Update mission status using versioning logic
        update_versioned(conn, 'grfp_missions', {'mission_id': data['mission_id']}, {'status': data['new_status']})
        logger.info(f"Successfully changed status for {data['mission_id']} to {data['new_status']}")
        
        # Send status update email
        subject = f"[GRFP] Mission Status Changed"
        body = "\n".join([data['mission_id'] + '\n', 'New status:', data['new_status']])
        send_email(subject, body, GROUND_TEAMS_EMAIL)
        logger.info(f"Email sent to ground teams: {GROUND_TEAMS_EMAIL}")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error changing mission status {data['mission_id']}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "DB insert error"}), 500
    finally:
        conn.close()


# === Endpoint to retrieve a list of missions ===
#@require_auth(allowed_emails=None) - TBD: Require Auth
def get_missions_list():
    logger.info(f"get-missions-list request received")
    data = request.get_json(silent=True) or {}

    required = ['email', 'mission_group']
    if not any(field in required for field in data):
        return jsonify({"status": "error", "reason": "Provide email or mission_group"}), 400 

    # Default condition: only active missions
    where_clauses = ["valid_to IS NULL"]
    args = []

    # Optional filters
    if "email" in data:
        where_clauses.append("email = %s")
        args.append(str(data["email"]))

    if "mission_group" in data:
        where_clauses.append("mission_group = %s")
        args.append(str(data["mission_group"]))

    if "status" in data:
        where_clauses.append("status = %s")
        args.append(str(data["status"]))

    where_sql = " AND ".join(where_clauses)

    try:
        # Fetch filtered missions from DB
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT *
                    FROM grfp_missions
                    WHERE {where_sql}
                    ORDER BY valid_from DESC
                """, args)
                rows = cur.fetchall()
                logger.info("Successfully fetched missions list")

        return jsonify({'status': 'ok', 'data': rows}), 200

    except Exception as e:
        logger.error(f"Error in getting missions list: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
