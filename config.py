import os

# Configuration for printserver

# Map CUPS printer name -> Tapo plug IP
PRINTERS = {
    "HP_LaserJet_CP1525N": "192.168.178.114",
    # "Lexmark_Optra_N": "192.168.178.115",
    "HP_Laserjet_2100TN": "192.168.178.116"
}

# Credentials from environment variables
TAPO_EMAIL = os.environ.get('TAPO_EMAIL', 'default@example.com')
TAPO_PASSWORD = os.environ.get('TAPO_PASSWORD', 'default_password')
