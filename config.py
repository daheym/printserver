import os

# Configuration for printserver

# Map CUPS printer name -> Tapo plug IP
PRINTERS = {
    "HP_LaserJet_CP1525N": "192.168.178.114",
    # "Lexmark_Optra_N": "192.168.178.115",
    "HP_Laserjet_2100TN": "192.168.178.116"
}

# Tapo credentials - loaded from .tapo_credentials file
def load_key_value_file(path):
    credentials = {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    # Handle lines that start with 'export '
                    if line.startswith('export '):
                        line = line[7:]  # Remove 'export ' prefix
                    key, value = line.split('=', 1)
                    key = key.strip()
                    # Remove quotes if present
                    value = value.strip('"\'')
                    credentials[key] = value
    except FileNotFoundError:
        pass
    return credentials


def load_credentials():
    credentials_file = os.path.join(os.path.dirname(__file__), '..', '.tapo_credentials')
    return load_key_value_file(credentials_file)


def get_int_setting(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


credentials = load_credentials()
TAPO_EMAIL = credentials.get('TAPO_EMAIL', os.environ.get('TAPO_EMAIL', 'default@example.com'))
TAPO_PASSWORD = credentials.get('TAPO_PASSWORD', os.environ.get('TAPO_PASSWORD', 'default_password'))

# Mail notifications - loaded from a git-ignored local file in the repo root
mail_credentials = load_key_value_file(
    os.path.join(os.path.dirname(__file__), '.mail_credentials')
)
MAIL_SENDER = mail_credentials.get('MAIL_SENDER', os.environ.get('MAIL_SENDER', ''))
MAIL_RECEIVER = mail_credentials.get('MAIL_RECEIVER', os.environ.get('MAIL_RECEIVER', MAIL_SENDER))
MAIL_PASSWORD = mail_credentials.get('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
MAIL_SMTP_HOST = mail_credentials.get('MAIL_SMTP_HOST', os.environ.get('MAIL_SMTP_HOST', 'smtp.gmail.com'))
MAIL_SMTP_PORT = get_int_setting(
    mail_credentials.get('MAIL_SMTP_PORT', os.environ.get('MAIL_SMTP_PORT', '465')),
    465,
)
MAIL_ENABLED = bool(MAIL_SENDER and MAIL_RECEIVER and MAIL_PASSWORD)

# Default runtime configuration. The web dashboard stores live overrides
# in runtime_config.json without modifying this file.
TURN_OFF_DELAY = 600

# Users in this list automatically trigger the temporary "Disable Auto-Off"
# override when the dashboard backend sees one of their jobs in CUPS.
AUTO_OFF_DISABLE_USERS = []
