import hashlib
import mimetypes
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import config
from app.core.logging_config import logger
from app.models import Documento, Modalidade, SituacaoProcesso, TipoDocumento
from app.services.json_repository import adicionar, buscar_por_id, proximo_id

router = APIRouter(prefix="/documentos", tags=["Documentos"])

DOCUMENTOS_DIR = config["storage"]["diretorio_documentos"]
os.makedirs(DOCUMENTOS_DIR, exist_ok=True)


@router.post("", response_model=Documento, status_code=status.HTTP_201_CREATED)
async def upload_documento(
    arquivo: UploadFile = File(...),
    categoria: str = Form(...),
    descricao: Optional[str] = Form(None),
    numero_processo: str = Form(...),
    tipo_documento: TipoDocumento = Form(...),
    modalidade: Optional[Modalidade] = Form(None),
    orgao_responsavel: Optional[str] = Form(None),
    valor_estimado: Optional[float] = Form(None),
    valor_contratado: Optional[float] = Form(None),
    data_abertura: Optional[datetime] = Form(None),
    date_homologacao: Optional[datetime] = Form(None),
    situacao: Optional[SituacaoProcesso] = Form(None),
):
    novo_id = proximo_id()

    nome_original = arquivo.filename
    extensao = os.path.splitext(nome_original)[1]
    nome_armazenado = f"{novo_id}_{nome_original}"
    caminho_arquivo = os.path.join(DOCUMENTOS_DIR, nome_armazenado)

    conteudo = await arquivo.read()
    with open(caminho_arquivo, "wb") as f:
        f.write(conteudo)

    tipo_mime = (
        arquivo.content_type
        or mimetypes.guess_type(nome_original)[0]
        or "application/octet-stream"
    )

    tamanho = len(conteudo)
    sha256 = hashlib.sha256(conteudo).hexdigest()

    documento = Documento(
        id=novo_id,
        nome_original=nome_original,
        nome_armazenado=nome_armazenado,
        extensao=extensao,
        tipo_mime=tipo_mime,
        tamanho=tamanho,
        categoria=categoria,
        desccricao=descricao,
        data_upload=datetime.now(),
        sha256=sha256,
        numero_processo=numero_processo,
        tipo_documento=tipo_documento,
        modalidade=modalidade,
        orgao_responsavel=orgao_responsavel,
        valor_estimado=valor_estimado,
        valor_contratado=valor_contratado,
        data_abertura=data_abertura,
        date_homologacao=date_homologacao,
        situacao=situacao,
    )

    try:
        adicionar(documento)
    except Exception:
        os.remove(caminho_arquivo)
        logger.error("ERRO_PERSISTENCIA id=%s arquivo=%s", novo_id, nome_original)
        raise HTTPException(
            status_code=500, detail="Erro ao registrar metadados do documento."
        )

    logger.info(
        "UPLOAD id=%s arquivo=%s categoria=%s processo=%s",
        documento.id,
        documento.nome_original,
        documento.categoria,
        documento.numero_processo,
    )

    return documento


@router.get("/{documento_id}", response_model=Documento)
def consultar_documento(documento_id: int):
    documento = buscar_por_id(documento_id)

    if not documento:
        logger.warning("DOCUMENTO_NAO_ENCONTRADO id=%s", documento_id)
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    return documento