import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv
load_dotenv()

ground_teams_email = os.getenv('GROUND_TEAMS_EMAIL')
rfd_admin_email = os.getenv('RFD_ADMIN_EMAIL')

def send_email(subject, body, to):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_USER")
    msg["To"] = to

    with smtplib.SMTP(os.getenv("EMAIL_SMTP"), int(os.getenv("EMAIL_PORT"))) as server:
        server.starttls()
        server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
        server.send_message(msg)
