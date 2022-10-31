import json
import os
from telegram import User

DEBUG = False

REPORT_CHANNEL = int(os.environ.get("REPORT_CHANNEL"))
TEST_CHANNEL = int(os.environ.get("TEST_CHANNEL"))
GROUP_CHAT = int(os.environ.get("GROUP_CHAT"))
DEVELOPER_CHAT = int(os.environ.get("DEVELOPER_CHAT"))
TEAM_LEADER_CHAT = int(os.environ.get("TEAM_LEADER_CHAT"))
ADMINS = json.loads(os.environ.get("ADMINS"))

OWNER_ID = int(os.environ.get("OWNER_ID"))
OWNER = User(id=OWNER_ID, first_name="Alexander Cingolani", is_bot=False)



ADMIN_CHAT_COMMANDS = [
    ("lista_presenze", "Invia la lista presenze dell'evento di oggi.")
]
ADMIN_COMMANDS = [
    ("help", "Ricevi Informazioni sull'utilizzo del bot."),
    ("nuova_segnalazione", "Crea una nuova segnalazione."),
    ("segnalazioni", "Giudica le segnalazioni in coda."),
    ("salva_risultati", "Salva i risultati delle ultime gare."),
]
LEADER_COMMANDS = [
    ("help", "Ricevi Informazioni sull'utilizzo del bot."),
    ("nuova_segnalazione", "Crea una nuova segnalazione."),
]
PRIVATE_CHAT_COMMANDS = [("help", "Ricevi Informazioni sull'utilizzo del bot.")]

REASONS = [
    "{b} manca il punto di staccata spingendo {a} fuori pista.",
    "{b} non rispetta le bandiere blu nei confronti di {a}.",
    "{b} effettua cambi di traiettoria ripetuti sul rettilineo.",
    "{b} tampona {a} in curva facendogli perdere il controllo dell'auto",
]

if DEBUG:
    REPORT_CHANNEL = TEST_CHANNEL
    GROUP_CHAT = DEVELOPER_CHAT
