#!/usr/bin/env python3
import datetime
import os
import sys

# Ensure sibling imports work when run directly.
sys.path.append(os.path.dirname(__file__))

from send_mail import send_mail


def main():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = "Raspi: Printserver mail test"
    body = f"This is a test mail from your printserver.\n\nSent at: {timestamp}\n"

    sent, message = send_mail(subject, body)
    if sent:
        print("Test mail sent successfully.")
    else:
        print(f"Test mail not sent: {message}")


if __name__ == "__main__":
    main()
