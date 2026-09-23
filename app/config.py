from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"

def carregar_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)

def garantir_diretorios(config: dict) -> None:
    caminhos = [
        config["storage"]["diretorio_documentos"],
        config["storage"]["diretorio_backups"],
        config["storage"]["diretorio_metadata"],

        Path(config["logging"]["arquivo"]).parent,
    ]

    for caminho in caminhos:
        Path(caminho).mkdir(parents=True, exist_ok=True)


config = carregar_config()
garantir_diretorios(config)

