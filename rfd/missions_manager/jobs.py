from tech_utils.logger import init_logger
logger = init_logger("Jobs")

from tech_utils.db import get_conn
from tech_utils.email_utils import send_email, ground_teams_email

# Function to alert ground teams about pending flight tasks
def alert_pending_tasks():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Query all flight tasks that are still marked as 'new'
                cur.execute("""
                    SELECT task_id, location, time_window, drone_type, created_at
                    FROM grfp_flight_tasks
                    WHERE status = 'new'
                """)
                rows = cur.fetchall()

        # If there are any pending tasks, prepare and send an email
        if rows:
            body = "Pending Missions:\n\n"
            for r in rows:
                # Append each task's summary to the email body
                body += f"ID: {r[0]}, Loc: {r[1]}, Time: {r[2]}, Drone: {r[3]}, Created: {r[4]}\n"

            # Send the email to the ground teams
            send_email("[GRFP] Hourly Alert: Pending Missions", body, ground_teams_email)
            logger.info(f"Email sent to ground teams: {ground_teams_email}")
            logger.info("Pending missions alert sent")

    except Exception as e:
        # Log any exception that occurs
        logger.error(f"Error sending pending missions alert: {e}")
