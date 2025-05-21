from flask import Flask, request, jsonify

from rfd.sessions_manager.endpoints import validate_token, gcs_ready, get_tailscale_ips, gcs_session_finish

from tech_utils.logger import init_logger
logger = init_logger("RFD_FlightSessionsManagerServer")

from rfd.config import CLEAN_SM_DB_INTERVAL

app = Flask(__name__)

from apscheduler.schedulers.background import BackgroundScheduler
from rfd.sessions_manager.session_manager import clean_sm_db

from rfd.sessions_manager.db_init import db_init

scheduler = BackgroundScheduler()
scheduler.add_job(clean_sm_db, "interval", seconds=CLEAN_SM_DB_INTERVAL)
scheduler.start()

app.add_url_rule("/validate-token", view_func=validate_token, methods=["POST"])
app.add_url_rule("/gcs-ready", view_func=gcs_ready, methods=["POST"])
app.add_url_rule("/get-tailscale-ips", view_func=get_tailscale_ips, methods=["POST"])
app.add_url_rule("/gcs-session-finish", view_func=gcs_session_finish, methods=["POST"])

def main():
    logger.info("DB init")
    db_init()
    logger.info("Starting server")
    app.run(host="0.0.0.0", port=8001)

if __name__ == "__main__":
    main()
