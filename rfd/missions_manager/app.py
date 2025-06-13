from flask import Flask

from rfd.missions_manager.endpoints import mission_request, mission_group_request, get_missions_list, change_mission_status

from apscheduler.schedulers.background import BackgroundScheduler
from rfd.missions_manager.jobs import alert_pending_tasks

from rfd.missions_manager.db_init import db_init

from tech_utils.logger import init_logger
logger = init_logger(name="Server", component="mm")

app = Flask(__name__)

# Add alert pending tasks job
scheduler = BackgroundScheduler()
scheduler.add_job(alert_pending_tasks, "interval", hours=3)
scheduler.start()

# Add endpoints
app.add_url_rule("/mission-request", view_func=mission_request, methods=["POST"])
app.add_url_rule("/mission-group-request", view_func=mission_group_request, methods=["POST"])
app.add_url_rule("/change-mission-status", view_func=change_mission_status, methods=["POST"])
app.add_url_rule("/get-missions-list", view_func=get_missions_list, methods=["POST"])

def main():
    logger.info("DB init")
    db_init()
    logger.info("Starting server")
    app.run(host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()
