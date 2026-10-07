import os
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.config import config
from app.core.logging_config import logger

router = APIRouter(tags=["Backup"])

BACKUPS_DIR = config["storage"]["diretorio_backups"]
DOCUMENTOS_DIR = config["storage"]["diretorio_documentos"]
METADATA_DIR = config["storage"]["diretorio_metadata"]

os.makedirs(BACKUPS_DIR, exist_ok=True)


@router.post("/backup", status_code=201)
def criar_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    nome_arquivo = f"backup_{timestamp}.zip"
    caminho_backup = os.path.join(BACKUPS_DIR, nome_arquivo)

    if os.path.exists(caminho_backup):
        logger.error("BACKUP_CONFLITO arquivo=%s", nome_arquivo)
        raise HTTPException(
            status_code=409,
            detail="Já existe um backup com esse nome. Tente novamente em instantes.",
        )

    try:
        with zipfile.ZipFile(caminho_backup, "w", zipfile.ZIP_DEFLATED) as zipf:
            # documentos físicos
            for nome_arquivo_doc in os.listdir(DOCUMENTOS_DIR):
                caminho_doc = os.path.join(DOCUMENTOS_DIR, nome_arquivo_doc)
                if os.path.isfile(caminho_doc):
                    zipf.write(caminho_doc, arcname=os.path.join("documentos", nome_arquivo_doc))

            # metadados
            caminho_json = os.path.join(METADATA_DIR, "documentos.json")
            if os.path.exists(caminho_json):
                zipf.write(caminho_json, arcname=os.path.join("metadata", "documentos.json"))
    except Exception:
        if os.path.exists(caminho_backup):
            os.remove(caminho_backup)
        logger.error("ERRO_BACKUP arquivo=%s", nome_arquivo)
        raise HTTPException(status_code=500, detail="Erro ao gerar o backup.")

    tamanho = os.path.getsize(caminho_backup)
    logger.info("BACKUP_CRIADO arquivo=%s tamanho=%s", nome_arquivo, tamanho)

    return {"arquivo": nome_arquivo, "tamanho": tamanho}


@router.get("/backups")
def listar_backups():
    if not os.path.exists(BACKUPS_DIR):
        return []

    backups = []
    for nome_arquivo in sorted(os.listdir(BACKUPS_DIR)):
        caminho = os.path.join(BACKUPS_DIR, nome_arquivo)
        if os.path.isfile(caminho):
            backups.append({
                "arquivo": nome_arquivo,
                "tamanho": os.path.getsize(caminho),
            })

    logger.info("LISTAGEM_BACKUPS total=%s", len(backups))

    return backups