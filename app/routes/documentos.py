import json
import mimetypes
import os
import re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from app.core.config import config
from app.core.logging_config import logger
from app.models import Documento, Modalidade, SituacaoProcesso, TipoDocumento
from app.services.hash_service import calcular_hash
from app.services.json_repository import (
    RepositorioError,
    adicionar,
    atualizar,
    buscar_por_id,
    ler_todos,
    proximo_id,
    remover,
)

router = APIRouter(prefix="/documentos", tags=["Documentos"])
# F10: a verificação global fica em GET /integridade (fora do prefixo /documentos)
router_integridade = APIRouter(tags=["Integridade"])

DOCUMENTOS_DIR = config["storage"]["diretorio_documentos"]
os.makedirs(DOCUMENTOS_DIR, exist_ok=True)

LIMITE_UPLOAD_BYTES = int(config["upload"]["tamanho_maximo_mb"] * 1024 * 1024)


def _erro_422(erro: ValidationError) -> HTTPException:
    detalhes = json.loads(erro.json(include_url=False, include_input=False, include_context=False))
    return HTTPException(status_code=422, detail=detalhes)


def _limpar_nome_arquivo(nome) -> str:
    """Remove caminhos (../, C:\\) e caracteres perigosos; devolve só o nome do arquivo."""
    nome = os.path.basename((nome or "").replace("\\", "/"))
    nome = re.sub(r'[<>:"|?*\x00-\x1f]', "_", nome)
    return nome.strip(" .")


class DocumentoUpdate(BaseModel):
    categoria: Optional[str] = None
    descricao: Optional[str] = None
    tipo_documento: Optional[TipoDocumento] = None
    fornecedor: Optional[str] = None
    modalidade: Optional[Modalidade] = None
    orgao_responsavel: Optional[str] = None
    valor_estimado: Optional[float] = None
    valor_contratado: Optional[float] = None
    data_abertura: Optional[datetime] = None
    data_homologacao: Optional[datetime] = None
    situacao: Optional[SituacaoProcesso] = None


@router.get("", response_model=List[Documento])
def listar_documentos(
    categoria: Optional[str] = None,
    extensao: Optional[str] = None,
    numero_processo: Optional[str] = None,
    tipo_documento: Optional[TipoDocumento] = None,
    modalidade: Optional[Modalidade] = None,
    orgao_responsavel: Optional[str] = None,
    fornecedor: Optional[str] = None,
    situacao: Optional[SituacaoProcesso] = None,
    nome_arquivo: Optional[str] = None,
):

    documentos = ler_todos()

    if categoria is not None:
        documentos = [d for d in documentos if d.categoria == categoria]

    if extensao is not None:
        extensao_normalizada = extensao if extensao.startswith(".") else f".{extensao}"
        documentos = [d for d in documentos if d.extensao == extensao_normalizada]

    if numero_processo is not None:
        documentos = [d for d in documentos if d.numero_processo == numero_processo]

    if tipo_documento is not None:
        documentos = [d for d in documentos if d.tipo_documento == tipo_documento]

    if modalidade is not None:
        documentos = [d for d in documentos if d.modalidade == modalidade]

    if orgao_responsavel is not None:
        documentos = [d for d in documentos if d.orgao_responsavel == orgao_responsavel]

    if fornecedor is not None:
        documentos = [
            d for d in documentos
            if d.fornecedor and d.fornecedor.lower() == fornecedor.lower()
        ]

    if situacao is not None:
        documentos = [d for d in documentos if d.situacao == situacao]

    if nome_arquivo is not None:
        termo = nome_arquivo.lower()
        documentos = [d for d in documentos if termo in d.nome_original.lower()]

    logger.info("LISTAGEM total=%s", len(documentos))

    return documentos


@router.get("/estatisticas")
def estatisticas_documentos():
    documentos = ler_todos()

    total_documentos = len(documentos)
    espaco_utilizado_bytes = sum(d.tamanho for d in documentos)

    por_extensao: dict[str, int] = {}
    por_categoria: dict[str, int] = {}
    por_modalidade: dict[str, int] = {}
    por_situacao: dict[str, int] = {}
    valor_por_processo: dict[str, float] = {}

    for d in documentos:
        por_extensao[d.extensao] = por_extensao.get(d.extensao, 0) + 1
        por_categoria[d.categoria] = por_categoria.get(d.categoria, 0) + 1

        if d.modalidade is not None:
            chave_modalidade = d.modalidade.value
            por_modalidade[chave_modalidade] = por_modalidade.get(chave_modalidade, 0) + 1

        if d.situacao is not None:
            chave_situacao = d.situacao.value
            por_situacao[chave_situacao] = por_situacao.get(chave_situacao, 0) + 1

        # F8: o valor contratado é do processo, então conta uma vez por processo
        if d.valor_contratado is not None and d.numero_processo not in valor_por_processo:
            valor_por_processo[d.numero_processo] = d.valor_contratado

    logger.info("ESTATISTICAS total=%s", total_documentos)

    return {
        "total_documentos": total_documentos,
        "espaco_utilizado_bytes": espaco_utilizado_bytes,
        "por_extensao": por_extensao,
        "por_categoria": por_categoria,
        "por_modalidade": por_modalidade,
        "por_situacao": por_situacao,
        "valor_total_contratado": round(sum(valor_por_processo.values()), 2),
        "valor_contratado_por_processo": valor_por_processo,
    }


@router_integridade.get("/integridade")
def verificar_integridade_global():
    documentos = ler_todos()

    verificados = 0
    integros = 0
    alterados = 0
    ausentes = []

    for documento in documentos:
        verificados += 1
        caminho_arquivo = os.path.join(DOCUMENTOS_DIR, documento.nome_armazenado)

        if not os.path.exists(caminho_arquivo):
            ausentes.append(documento.id)
            logger.error("ARQUIVO_FISICO_AUSENTE id=%s", documento.id)
            continue

        with open(caminho_arquivo, "rb") as f:
            hash_atual = calcular_hash(f.read())

        if hash_atual == documento.sha256:
            integros += 1
        else:
            alterados += 1
            logger.warning("INTEGRIDADE_FALHOU id=%s", documento.id)

    logger.info(
        "INTEGRIDADE_GLOBAL verificados=%s integros=%s alterados=%s ausentes=%s",
        verificados, integros, alterados, len(ausentes),
    )

    return {
        "verificados": verificados,
        "integros": integros,
        "alterados": alterados,
        "arquivos_ausentes": ausentes,
    }


@router.post("", response_model=Documento, status_code=status.HTTP_201_CREATED)
async def upload_documento(
    arquivo: UploadFile = File(...),
    categoria: str = Form(...),
    descricao: Optional[str] = Form(None),
    numero_processo: str = Form(...),
    tipo_documento: TipoDocumento = Form(...),
    modalidade: Optional[Modalidade] = Form(None),
    fornecedor: Optional[str] = Form(None),
    orgao_responsavel: Optional[str] = Form(None),
    valor_estimado: Optional[float] = Form(None),
    valor_contratado: Optional[float] = Form(None),
    data_abertura: Optional[datetime] = Form(None),
    data_homologacao: Optional[datetime] = Form(None),
    situacao: Optional[SituacaoProcesso] = Form(None),
):
    nome_original = _limpar_nome_arquivo(arquivo.filename)
    if not nome_original:
        logger.warning("UPLOAD_RECUSADO motivo=nome_invalido")
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    # lê no máximo limite+1 bytes: basta para saber se passou do limite
    conteudo = await arquivo.read(LIMITE_UPLOAD_BYTES + 1)

    if len(conteudo) == 0:
        logger.warning("UPLOAD_RECUSADO arquivo=%s motivo=arquivo_vazio", nome_original)
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    if len(conteudo) > LIMITE_UPLOAD_BYTES:
        logger.warning("UPLOAD_RECUSADO arquivo=%s motivo=acima_do_limite", nome_original)
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo acima do limite de {config['upload']['tamanho_maximo_mb']} MB.",
        )

    if not categoria.strip() or not numero_processo.strip():
        logger.warning("UPLOAD_RECUSADO arquivo=%s motivo=metadados_vazios", nome_original)
        raise HTTPException(
            status_code=422, detail="categoria e numero_processo não podem ser vazios."
        )

    novo_id = proximo_id()
    extensao = os.path.splitext(nome_original)[1]
    nome_armazenado = f"{novo_id}_{nome_original}"
    caminho_arquivo = os.path.join(DOCUMENTOS_DIR, nome_armazenado)

    tipo_mime = (
        arquivo.content_type
        or mimetypes.guess_type(nome_original)[0]
        or "application/octet-stream"
    )

    # valida TODOS os metadados antes de gravar o arquivo (não sobra arquivo órfão)
    try:
        documento = Documento(
            id=novo_id,
            nome_original=nome_original,
            nome_armazenado=nome_armazenado,
            extensao=extensao,
            tipo_mime=tipo_mime,
            tamanho=len(conteudo),
            categoria=categoria.strip(),
            descricao=descricao,
            data_upload=datetime.now(),
            sha256=calcular_hash(conteudo),
            numero_processo=numero_processo.strip(),
            tipo_documento=tipo_documento,
            fornecedor=fornecedor,
            modalidade=modalidade,
            orgao_responsavel=orgao_responsavel,
            valor_estimado=valor_estimado,
            valor_contratado=valor_contratado,
            data_abertura=data_abertura,
            data_homologacao=data_homologacao,
            situacao=situacao,
        )
    except ValidationError as erro:
        logger.warning("UPLOAD_RECUSADO arquivo=%s motivo=metadados_invalidos", nome_original)
        raise _erro_422(erro) from erro

    try:
        with open(caminho_arquivo, "wb") as f:
            f.write(conteudo)
    except OSError as erro:
        logger.error("ERRO_ESCRITA arquivo=%s detalhe=%s", nome_armazenado, erro)
        raise HTTPException(status_code=500, detail="Erro ao gravar o arquivo.") from erro

    try:
        adicionar(documento)
    except (RepositorioError, OSError) as erro:
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
        logger.error("ERRO_PERSISTENCIA id=%s arquivo=%s detalhe=%s", novo_id, nome_original, erro)
        raise HTTPException(
            status_code=500, detail="Erro ao registrar metadados do documento."
        ) from erro

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

    logger.info("CONSULTA id=%s arquivo=%s", documento.id, documento.nome_original)

    return documento


@router.get("/{documento_id}/download")
def download_documento(documento_id: int):
    documento = buscar_por_id(documento_id)

    if not documento:
        logger.warning("DOCUMENTO_NAO_ENCONTRADO id=%s", documento_id)
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    caminho_arquivo = os.path.join(DOCUMENTOS_DIR, documento.nome_armazenado)

    if not os.path.exists(caminho_arquivo):
        logger.error(
            "ARQUIVO_FISICO_AUSENTE id=%s arquivo=%s", documento_id, documento.nome_armazenado
        )
        raise HTTPException(
            status_code=404,
            detail="Arquivo físico não encontrado no armazenamento.",
        )

    logger.info("DOWNLOAD id=%s arquivo=%s", documento.id, documento.nome_original)

    return FileResponse(
        path=caminho_arquivo,
        filename=documento.nome_original,
        media_type=documento.tipo_mime,
    )


@router.get("/{documento_id}/integridade")
def verificar_integridade(documento_id: int):
    documento = buscar_por_id(documento_id)

    if not documento:
        logger.warning("DOCUMENTO_NAO_ENCONTRADO id=%s", documento_id)
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    caminho_arquivo = os.path.join(DOCUMENTOS_DIR, documento.nome_armazenado)

    if not os.path.exists(caminho_arquivo):
        logger.error(
            "ARQUIVO_FISICO_AUSENTE id=%s arquivo=%s", documento_id, documento.nome_armazenado
        )
        raise HTTPException(
            status_code=404,
            detail="Arquivo físico não encontrado no armazenamento.",
        )

    with open(caminho_arquivo, "rb") as f:
        hash_atual = calcular_hash(f.read())

    integro = hash_atual == documento.sha256

    if integro:
        logger.info("INTEGRIDADE_OK id=%s", documento_id)
    else:
        logger.warning("INTEGRIDADE_FALHOU id=%s", documento_id)

    return {
        "id": documento.id,
        "nome": documento.nome_original,
        "hash_original": documento.sha256,
        "hash_atual": hash_atual,
        "integro": integro,
    }


@router.put("/{documento_id}", response_model=Documento)
def atualizar_documento(documento_id: int, dados: DocumentoUpdate):
    documento = buscar_por_id(documento_id)

    if not documento:
        logger.warning("DOCUMENTO_NAO_ENCONTRADO id=%s", documento_id)
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    atualizacoes = dados.model_dump(exclude_unset=True)

    if "categoria" in atualizacoes and not (atualizacoes["categoria"] or "").strip():
        logger.warning("ATUALIZACAO_RECUSADA id=%s motivo=categoria_vazia", documento_id)
        raise HTTPException(status_code=422, detail="categoria não pode ser vazia.")

    # revalida o documento INTEIRO: null em campo obrigatório ou valor negativo dão 422
    try:
        documento_atualizado = Documento.model_validate(
            {**documento.model_dump(), **atualizacoes}
        )
    except ValidationError as erro:
        logger.warning("ATUALIZACAO_RECUSADA id=%s motivo=metadados_invalidos", documento_id)
        raise _erro_422(erro) from erro

    atualizar(documento_atualizado)

    logger.info(
        "ATUALIZACAO id=%s campos=%s",
        documento_id,
        ",".join(atualizacoes.keys()) if atualizacoes else "nenhum",
    )

    return documento_atualizado


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_documento(documento_id: int):
    documento = buscar_por_id(documento_id)

    if not documento:
        logger.warning("DOCUMENTO_NAO_ENCONTRADO id=%s", documento_id)
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    caminho_arquivo = os.path.join(DOCUMENTOS_DIR, documento.nome_armazenado)

    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)
    else:
        logger.error(
            "ARQUIVO_FISICO_AUSENTE id=%s arquivo=%s", documento_id, documento.nome_armazenado
        )

    remover(documento_id)

    logger.info("EXCLUSAO id=%s arquivo=%s", documento_id, documento.nome_original)

    return None