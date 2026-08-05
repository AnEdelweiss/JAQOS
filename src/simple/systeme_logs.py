import datetime
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs_SIMPLE")
os.makedirs(LOG_DIR, exist_ok=True)

date_du_jour = datetime.datetime.now().strftime("%Y-%m-%d")
compteur = 1

LOG_FILE = os.path.join(LOG_DIR, f"simple_app_{date_du_jour}_{compteur}.log")
while os.path.exists(LOG_FILE):
    compteur += 1
    LOG_FILE = os.path.join(LOG_DIR, f"simple_app_{date_du_jour}_{compteur}.log")

logger = logging.getLogger("simple_logger")
logger.setLevel(logging.DEBUG)  # The core logger catches everything

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG) 
file_format = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
file_handler.setFormatter(file_format)

if not logger.handlers:
    logger.addHandler(file_handler)