import hashlib

from app.core.config import config

ALGORITMO_HASH = str(config["hash"]["algoritmo"]).lower()


def calcular_hash(conteudo: bytes) -> str:
    """Hash do conteúdo usando o algoritmo definido em hash.algoritmo (config.yaml)."""
    return hashlib.new(ALGORITMO_HASH, conteudo).hexdigest()