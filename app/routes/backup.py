import json
import os
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.core.config import config
from app.core.logging_config import logger
from app.models import Documento
from app.services.json_repository import salvar_todos

router = APIRouter(tags=["Backup"])

BACKUPS_DIR = config["storage"]["diretorio_backups"]
DOCUMENTOS_DIR = config["storage"]["diretorio_documentos"]
METADATA_DIR = config["storage"]["diretorio_metadata"]
FORMATO = str(config["backup"]["formato"]).lower()

os.makedirs(BACKUPS_DIR, exist_ok=True)

ENTRADA_METADADOS = "metadata/documentos.json"


def _caminho_backup_ou_404(nome: str) -> str:
    """Resolve o nome de um backup existente; nunca sai da pasta de backups."""
    caminho = os.path.join(BACKUPS_DIR, os.path.basename(nome))

    if os.path.basename(nome) != nome or not os.path.isfile(caminho):
        logger.warning("BACKUP_NAO_ENCONTRADO arquivo=%s", nome)
        raise HTTPException(status_code=404, detail="Backup não encontrado.")

    return caminho



@router.post("/backup", status_code=201)
def criar_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    nome_arquivo = f"backup_{timestamp}.{FORMATO}"
    caminho_backup = os.path.join(BACKUPS_DIR, nome_arquivo)

    
    contador = 1
    while os.path.exists(caminho_backup):
        contador += 1
        nome_arquivo = f"backup_{timestamp}_{contador}.{FORMATO}"
        caminho_backup = os.path.join(BACKUPS_DIR, nome_arquivo)

    total_documentos = 0
    try:
        with zipfile.ZipFile(caminho_backup, "w", zipfile.ZIP_DEFLATED) as zipf:
            
            for nome_doc in sorted(os.listdir(DOCUMENTOS_DIR)):
                caminho_doc = os.path.join(DOCUMENTOS_DIR, nome_doc)
                if os.path.isfile(caminho_doc):
                    zipf.write(caminho_doc, arcname=f"documentos/{nome_doc}")
                    total_documentos += 1

            
            caminho_json = os.path.join(METADATA_DIR, "documentos.json")
            if os.path.exists(caminho_json):
                zipf.write(caminho_json, arcname=ENTRADA_METADADOS)
    except Exception as erro:
        if os.path.exists(caminho_backup):
            os.remove(caminho_backup)
        logger.error("ERRO_BACKUP arquivo=%s detalhe=%s", nome_arquivo, erro)
        raise HTTPException(status_code=500, detail="Erro ao gerar o backup.") from erro

    tamanho = os.path.getsize(caminho_backup)
    logger.info(
        "BACKUP_CRIADO arquivo=%s documentos=%s tamanho=%s",
        nome_arquivo, total_documentos, tamanho,
    )

    return {"arquivo": nome_arquivo, "documentos": total_documentos, "tamanho": tamanho}



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



@router.get("/backups/{nome}")
def baixar_backup(nome: str):
    caminho = _caminho_backup_ou_404(nome)
    logger.info("BACKUP_DOWNLOAD arquivo=%s", nome)
    return FileResponse(path=caminho, filename=nome, media_type="application/zip")



@router.post("/backups/{nome}/restaurar")
def restaurar_backup(nome: str):
    """Restaura os documentos físicos e o documentos.json a partir de um backup.

    Os metadados atuais são substituídos pelos do backup. Arquivos criados depois
    do backup não são apagados.
    """
    caminho = _caminho_backup_ou_404(nome)

    try:
        with zipfile.ZipFile(caminho) as zipf:
            if zipf.testzip() is not None:
                raise zipfile.BadZipFile("conteúdo corrompido")

            nomes = zipf.namelist()
            if ENTRADA_METADADOS not in nomes:
                logger.error("ERRO_RESTAURACAO arquivo=%s motivo=sem_metadados", nome)
                raise HTTPException(
                    status_code=422, detail=f"Backup sem {ENTRADA_METADADOS}."
                )

            
            try:
                dados = json.loads(zipf.read(ENTRADA_METADADOS).decode("utf-8"))
                if not isinstance(dados, list):
                    raise ValueError("a raiz deve ser uma lista de documentos")
                documentos = [Documento(**item) for item in dados]
            except (ValueError, TypeError, ValidationError) as erro:
                logger.error("ERRO_RESTAURACAO arquivo=%s motivo=metadados_invalidos", nome)
                raise HTTPException(
                    status_code=422, detail=f"Metadados do backup inválidos: {erro}"
                ) from erro

            
            restaurados = 0
            for item in nomes:
                if item.startswith("documentos/") and not item.endswith("/"):
                    destino = os.path.join(DOCUMENTOS_DIR, os.path.basename(item))
                    with open(destino, "wb") as f:
                        f.write(zipf.read(item))
                    restaurados += 1

            
            salvar_todos(documentos)
    except HTTPException:
        raise
    except zipfile.BadZipFile as erro:
        logger.error("ERRO_RESTAURACAO arquivo=%s detalhe=%s", nome, erro)
        raise HTTPException(
            status_code=422, detail="Arquivo de backup inválido ou corrompido."
        ) from erro
    except OSError as erro:
        logger.error("ERRO_ESCRITA restauracao arquivo=%s detalhe=%s", nome, erro)
        raise HTTPException(
            status_code=500, detail="Erro ao gravar os arquivos da restauração."
        ) from erro

    logger.info(
        "BACKUP_RESTAURADO arquivo=%s documentos_registrados=%s arquivos=%s",
        nome, len(documentos), restaurados,
    )
    return {
        "arquivo": nome,
        "documentos_registrados": len(documentos),
        "arquivos_restaurados": restaurados,
    }