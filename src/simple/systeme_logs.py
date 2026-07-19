import logging
import os
from rich.logging import RichHandler
import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs_SIMPLE")
os.makedirs(LOG_DIR, exist_ok=True)

date_du_jour = datetime.datetime.now().strftime("%Y-%m-%d")
compteur = 1

LOG_FILE = os.path.join(LOG_DIR, f"simple_app_{date_du_jour}_{compteur}.log")
while os.path.exists(LOG_FILE):
    compteur += 1
    LOG_FILE = os.path.join(LOG_DIR, f"simple_app_{date_du_jour}_{compteur}.log")

# 1. Configuration de base du logger
logger = logging.getLogger("simple_logger")
logger.setLevel(logging.DEBUG) # Le logger principal écoute tout

# 2. Handler pour écrire dans le fichier (Texte brut pour les archives)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG) # On garde tout dans le fichier
file_format = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
file_handler.setFormatter(file_format)


# rich_tracebacks=True 
rich_handler = RichHandler(rich_tracebacks=True, markup=True)
rich_handler.setLevel(logging.WARNING) # On n'affiche en console que les choses importantes (WARNING, ERROR, CRITICAL)
rich_format = logging.Formatter('%(message)s')
rich_handler.setFormatter(rich_format)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(rich_handler)