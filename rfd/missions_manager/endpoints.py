from flask import Flask, request, jsonify

from tech_utils.db import get_conn, update_versioned, RealDictCursor
from tech_utils.email_utils import send_email, ground_teams_email
import uuid

from tech_utils.logger import init_logger
logger = init_logger("RFD_MM_Endpoints")


# === Endpoint to create a new mission ===
def mission_request():
    mission_id = str(uuid.uuid4())  # Generate a unique mission ID
    logger.info(f"mission-request request received {mission_id}")
    data = request.get_json()

    # Check for required fields
    required = ["user_id", "location", "time_window", "drone_type"]
    if not data or not all(k in data for k in required):
        return jsonify({"status": "error", "reason": "Missing parameters"}), 400

    # Prepare values for SQL INSERT
    columns = ['mission_id']
    placeholders = ['%s']
    values = [mission_id]  

    # Optional field
    if "mission_group" in data:
        columns.append('mission_group')
        placeholders.append('%s')
        values.append(data["mission_group"])

    # Add required fields
    columns += ['user_id', 'location', 'time_window', 'drone_type']
    placeholders += ['%s'] * 4
    values += [data['user_id'], data["location"], data["time_window"], data["drone_type"]]

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
        send_email(subject, body, ground_teams_email)
        logger.info(f"Email sent to ground teams: {ground_teams_email}")

        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Error creating mission {mission_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500


# === Endpoint to create a new mission group ===
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
        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Error creating mission group {mission_group}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500


# === Endpoint to change the status of an existing mission ===
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
        send_email(subject, body, ground_teams_email)
        logger.info(f"Email sent to ground teams: {ground_teams_email}")

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Error changing mission status {data['mission_id']}: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "DB insert error"}), 500
    finally:
        conn.close()


# === Endpoint to retrieve a list of missions ===
def get_missions_list():
    logger.info(f"get-missions-list request received")
    data = request.get_json(silent=True) or {}

    # Default condition: only active missions
    where_clauses = ["valid_to IS NULL"]
    args = []

    # Optional filters
    if "user_id" in data:
        where_clauses.append("user_id = %s")
        args.append(data["user_id"])

    if "mission_group" in data:
        where_clauses.append("mission_group = %s")
        args.append(data["mission_group"])

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

        return jsonify({'status': 'ok', 'data': rows})

    except Exception as e:
        logger.error(f"Error in getting missions list: {e}", exc_info=True)
        return jsonify({"status": "error", "reason": "Internal server error"}), 500
