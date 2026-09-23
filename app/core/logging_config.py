import logging
import logging.config
import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGGING_FILE = BASE_DIR / "logging.yaml"
LOG_DIR = BASE_DIR / "storage" / "logs"

with open(LOGGING_FILE, "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)

os.makedirs(LOG_DIR, exist_ok=True)
config["handlers"]["file"]["filename"] = str(LOG_DIR / "sistema.log")

logging.config.dictConfig(config)

logger = logging.getLogger("cofre_licitacoes")
logger.info("INICIALIZACAO sistema=cofre_licitacoes status=ok")