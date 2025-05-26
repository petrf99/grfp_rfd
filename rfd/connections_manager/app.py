from flask import Flask, request, jsonify

from rfd.connections_manager.endpoints import get_vpn_connection, delete_vpn_connection, start_session, close_session, register_gcs

from tech_utils.logger import init_logger
logger = init_logger("RFD_CM_Server")

from rfd.config import CLEANER_INTERVAL

app = Flask(__name__)

from apscheduler.schedulers.background import BackgroundScheduler
from rfd.connections_manager.cleaner import cleaner

from rfd.connections_manager.db_init import db_init

scheduler = BackgroundScheduler()
scheduler.add_job(cleaner, "interval", seconds=CLEANER_INTERVAL)
scheduler.start()

app.add_url_rule("/register-gcs", view_func=register_gcs, methods=["POST"])
app.add_url_rule("/get-vpn-connection", view_func=get_vpn_connection, methods=["POST"])
app.add_url_rule("/delete-vpn-connection", view_func=delete_vpn_connection, methods=["POST"])
app.add_url_rule("/start-session", view_func=start_session, methods=["POST"])
app.add_url_rule("/close-session", view_func=close_session, methods=["POST"])

def main():
    logger.info("DB init")
    db_init()
    logger.info("Starting server")
    app.run(host="0.0.0.0", port=8001)

if __name__ == "__main__":
    main()
