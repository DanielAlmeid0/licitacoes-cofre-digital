import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

CHAVES_OBRIGATORIAS = {
    "storage": [
        "diretorio_documentos",
        "diretorio_backups",
        "diretorio_metadata",
        "diretorio_exportacoes",
    ],
    "upload": ["tamanho_maximo_mb"],
    "hash": ["algoritmo"],
    "logging": ["arquivo", "nivel"],
    "backup": ["formato"],
}

NIVEIS_VALIDOS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

class ConfigError(Exception):
    """Arquivo de configuração ausente ou inválido."""


def carregar_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as arquivo:
            dados = yaml.safe_load(arquivo)
    except FileNotFoundError as erro:
        raise ConfigError(f"Arquivo de configuração não encontrado: {CONFIG_PATH}") from erro
    except yaml.YAMLError as erro:
        raise ConfigError(f"YAML inválido em {CONFIG_PATH}: {erro}") from erro
    except OSError as erro:
        raise ConfigError(f"Erro ao ler {CONFIG_PATH}: {erro}") from erro

    validar_config(dados)
    return dados

def validar_config(dados) -> None:
    if not isinstance(dados, dict):
        raise ConfigError("O config.yaml está vazio ou não é um mapeamento chave: valor.")

    for secao, chaves in CHAVES_OBRIGATORIAS.items():
        if not isinstance(dados.get(secao), dict):
            raise ConfigError(f"Seção ausente no config.yaml: '{secao}'")
        for chave in chaves:
            if dados[secao].get(chave) in (None, ""):
                raise ConfigError(f"Chave ausente no config.yaml: '{secao}.{chave}'")

    limite = dados["upload"]["tamanho_maximo_mb"]
    if isinstance(limite, bool) or not isinstance(limite, (int, float)) or limite <= 0:
        raise ConfigError("upload.tamanho_maximo_mb deve ser um número maior que zero.")

    if str(dados["logging"]["nivel"]).upper() not in NIVEIS_VALIDOS:
        raise ConfigError(
            f"logging.nivel inválido: {dados['logging']['nivel']} (use {sorted(NIVEIS_VALIDOS)})"
        )

    if str(dados["hash"]["algoritmo"]).lower() != "sha256":
        raise ConfigError("hash.algoritmo: apenas 'sha256' é suportado (campo sha256 do modelo).")

    if str(dados["backup"]["formato"]).lower() != "zip":
        raise ConfigError("backup.formato: apenas 'zip' é suportado.")


def garantir_diretorios(config: dict) -> None:
    caminhos = [
        config["storage"]["diretorio_documentos"],
        config["storage"]["diretorio_backups"],
        config["storage"]["diretorio_metadata"],
        config["storage"]["diretorio_exportacoes"],
        Path(config["logging"]["arquivo"]).parent,
    ]
    for caminho in caminhos:
        Path(caminho).mkdir(parents=True, exist_ok=True)


try:
    config = carregar_config()
    garantir_diretorios(config)
except (ConfigError, OSError) as _erro:
    print(f"[ERRO DE CONFIGURAÇÃO] {_erro}", file=sys.stderr)
    raise SystemExit(1)