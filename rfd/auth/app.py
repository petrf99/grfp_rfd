from flask import Flask
from rfd.auth.endpoints import register, login, auth_google, delete_account
from apscheduler.schedulers.background import BackgroundScheduler
from rfd.auth.logic import init_db, register_user
from rfd.config import RFD_ADMIN_PASSWORD, RFD_ADMIN_EMAIL

from tech_utils.logger import init_logger
logger = init_logger(name="Server", component="auth")

app = Flask(__name__)

# Add endpoints
app.add_url_rule("/register", view_func=register, methods=["POST"])
app.add_url_rule("/login", view_func=login, methods=["POST"])
app.add_url_rule("/google", view_func=auth_google, methods=["POST"])
app.add_url_rule("/delete-account", view_func=delete_account, methods=["DELETE"])

def main():
    logger.info("DB init")
    init_db()
    logger.info("Register admin")
    register_user(RFD_ADMIN_EMAIL, RFD_ADMIN_PASSWORD)
    logger.info("Starting server")
    app.run(host="127.0.0.1", port=8002)

if __name__ == "__main__":
    main()
