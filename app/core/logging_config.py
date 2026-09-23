import logging
from pathlib import Path

from app.core.config import config

LOG_PATH = Path(config["logging"]["arquivo"])
LOG_LEVEL = config["logging"]["nivel"]

logging.basicConfig(
    filename=str(LOG_PATH),
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("cofre_licitacoes")
logger.info("INICIALIZACAO sistema=cofre_licitacoes status=ok")