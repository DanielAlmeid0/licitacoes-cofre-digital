import hashlib
import os
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.logging_config import logger
from app.models import Documento, TipoDocumento

router = APIRouter(prefix="/documentos", tags=["Documentos"])

DOCUMENTOS_DIR = "storage/documentos"
os.makedirs(DOCUMENTOS_DIR, exist_ok=True)


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_documento(
    arquivo: UploadFile = File(...),
    numero_processo: str = "",
    tipo_documento: TipoDocumento = TipoDocumento.OUTRO,
    categoria: str = "geral",
):
    conteudo = await arquivo.read()

    novo_id = 1  # TODO: gerar id real a partir do que já está persistido
    nome_armazenado = f"{novo_id}_{arquivo.filename}"
    caminho_arquivo = os.path.join(DOCUMENTOS_DIR, nome_armazenado)

    with open(caminho_arquivo, "wb") as f:
        f.write(conteudo)

    sha256 = hashlib.sha256(conteudo).hexdigest()

    documento = Documento(
        id=novo_id,
        nome_original=arquivo.filename,
        nome_armazenado=nome_armazenado,
        extensao=os.path.splitext(arquivo.filename)[1],
        tipo_mime=arquivo.content_type,
        tamanho=len(conteudo),
        categoria=categoria,
        data_upload=datetime.now(),
        sha256=sha256,
        numero_processo=numero_processo,
        tipo_documento=tipo_documento,
    )

    # TODO: persistir "documento" no storage/metadata/documentos.json

    # <<< AQUI é onde entra o trecho que te passei antes >>>
    logger.info(
        "UPLOAD id=%s arquivo=%s categoria=%s",
        documento.id,
        documento.nome_original,
        documento.categoria,
    )

    return documento


@router.get("/{documento_id}")
def consultar_documento(documento_id: int):
    # TODO: buscar no JSON

    documento = None  # placeholder

    if not documento:
        # <<< aqui entra o warning >>>
        logger.warning("DOCUMENTO_NAO_ENCONTRADO id=%s", documento_id)
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    return documento