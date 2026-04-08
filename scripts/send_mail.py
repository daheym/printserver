#!/usr/bin/env python3
import datetime
import os
import smtplib
import sys
from email.mime.text import MIMEText

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    MAIL_ENABLED,
    MAIL_PASSWORD,
    MAIL_RECEIVER,
    MAIL_SENDER,
    MAIL_SMTP_HOST,
    MAIL_SMTP_PORT,
)


def build_job_notification_message(job):
    printer = job.get("printer", "unknown-printer")
    job_id = job.get("job_id", "unknown-job")
    user = job.get("user", "unknown-user")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = f"Raspi: Print job received: {printer}-{job_id}"
    body = (
        "A new print job was detected by the printserver.\n\n"
        f"Printer: {printer}\n"
        f"Job ID: {job_id}\n"
        f"User: {user}\n"
        f"Detected at: {timestamp}\n"
    )
    return subject, body


def send_mail(subject, body):
    if not MAIL_ENABLED:
        return False, "mail notifications disabled or incomplete config"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = MAIL_SENDER
    msg["To"] = MAIL_RECEIVER

    with smtplib.SMTP_SSL(MAIL_SMTP_HOST, MAIL_SMTP_PORT) as server:
        server.login(MAIL_SENDER, MAIL_PASSWORD)
        server.send_message(msg)

    return True, "email sent"


def send_print_job_notification(job):
    subject, body = build_job_notification_message(job)
    return send_mail(subject, body)


if __name__ == "__main__":
    demo_job = {"printer": "Example_Printer", "job_id": "123", "user": "demo-user"}
    success, message = send_print_job_notification(demo_job)
    print(message if success else f"Mail not sent: {message}")
