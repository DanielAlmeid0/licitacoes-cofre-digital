import json
import os
import re
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import config
from app.core.logging_config import logger
from app.models import Documento
from app.services.json_repository import ler_todos

router = APIRouter(prefix="/processos", tags=["Processos"])

DOCUMENTOS_DIR = config["storage"]["diretorio_documentos"]
EXPORTACOES_DIR = config["storage"]["diretorio_exportacoes"]

DOCUMENTOS_OBRIGATORIOS = ["edital", "proposta", "contrato", "ata"]
DOCUMENTOS_POR_MODALIDADE = {
    "pregao_eletronico": ["edital", "proposta", "ata", "contrato"],
    "concorrencia": ["edital", "proposta", "ata", "contrato"],
    "tomada_de_precos": ["edital", "proposta", "ata", "contrato"],
    "dispensa": ["cotacao", "contrato"],
    "inexigibilidade": ["documento_fornecedor", "contrato"],
}


def _documentos_do_processo(numero_processo: str) -> list[Documento]:
    documentos = [d for d in ler_todos() if d.numero_processo == numero_processo]

    if not documentos:
        logger.warning("PROCESSO_NAO_ENCONTRADO numero=%s", numero_processo)
        raise HTTPException(
            status_code=404,
            detail="Processo não encontrado: nenhum documento cadastrado com esse número.",
        )

    return documentos


def _primeiro_valor(documentos: list[Documento], campo: str):
    for doc in documentos:
        valor = getattr(doc, campo, None)
        if valor is not None:
            return valor.value if hasattr(valor, "value") else valor
    return None


@router.get("")
def listar_processos():
    por_processo: dict[str, list[Documento]] = {}
    for doc in ler_todos():
        por_processo.setdefault(doc.numero_processo, []).append(doc)

    resposta = []
    for numero, docs in por_processo.items():
        resposta.append(
            {
                "numero_processo": numero,
                "total_documentos": len(docs),
                "tipos_documento": sorted({d.tipo_documento.value for d in docs}),
                "modalidade": _primeiro_valor(docs, "modalidade"),
                "situacao": _primeiro_valor(docs, "situacao"),
                "fornecedor": _primeiro_valor(docs, "fornecedor"),
            }
        )

    logger.info("LISTAGEM_PROCESSOS total=%s", len(resposta))
    return resposta


@router.get("/{numero_processo:path}/documentos")
def documentos_do_processo(numero_processo: str):
    numero_processo = numero_processo.strip()
    documentos = _documentos_do_processo(numero_processo)

    logger.info(
        "CONSULTA_PROCESSO numero=%s total_documentos=%s",
        numero_processo,
        len(documentos),
    )

    return {
        "numero_processo": numero_processo,
        "total_documentos": len(documentos),
        "modalidade": _primeiro_valor(documentos, "modalidade"),
        "situacao": _primeiro_valor(documentos, "situacao"),
        "fornecedor": _primeiro_valor(documentos, "fornecedor"),
        "documentos": documentos,
    }


@router.get("/{numero_processo:path}/zip")
def zip_do_processo(numero_processo: str):
    numero_processo = numero_processo.strip()
    documentos = _documentos_do_processo(numero_processo)

    try:
        os.makedirs(EXPORTACOES_DIR, exist_ok=True)
    except OSError as erro:
        logger.error("ERRO_ESCRITA diretorio=%s detalhe=%s", EXPORTACOES_DIR, erro)
        raise HTTPException(
            status_code=500, detail="Erro ao preparar o diretório de exportações."
        ) from erro

    numero_seguro = re.sub(r"[^A-Za-z0-9_-]+", "-", numero_processo).strip("-") or "processo"
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_zip = f"processo_{numero_seguro}_{carimbo}.zip"
    caminho_zip = os.path.join(EXPORTACOES_DIR, nome_zip)

    contador = 1
    while os.path.exists(caminho_zip):
        contador += 1
        nome_zip = f"processo_{numero_seguro}_{carimbo}_{contador}.zip"
        caminho_zip = os.path.join(EXPORTACOES_DIR, nome_zip)

    incluidos: list[Documento] = []
    ausentes: list[int] = []

    try:
        with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for doc in documentos:
                caminho_doc = os.path.join(DOCUMENTOS_DIR, doc.nome_armazenado)

                if not os.path.isfile(caminho_doc):
                    ausentes.append(doc.id)
                    logger.error(
                        "ARQUIVO_FISICO_AUSENTE id=%s arquivo=%s",
                        doc.id,
                        doc.nome_armazenado,
                    )
                    continue

                zipf.write(caminho_doc, arcname=f"documentos/{doc.nome_armazenado}")
                incluidos.append(doc)

            metadados = [d.model_dump(mode="json") for d in incluidos]
            zipf.writestr(
                "metadados.json", json.dumps(metadados, ensure_ascii=False, indent=2)
            )
    except Exception as erro:
        if os.path.exists(caminho_zip):
            os.remove(caminho_zip)
        logger.error(
            "ERRO_ZIP numero=%s arquivo=%s detalhe=%s", numero_processo, nome_zip, erro
        )
        raise HTTPException(
            status_code=500, detail="Erro ao gerar o ZIP do processo."
        ) from erro

    if not incluidos:
        os.remove(caminho_zip)
        raise HTTPException(
            status_code=404,
            detail="Nenhum arquivo físico deste processo foi encontrado no armazenamento.",
        )

    tamanho = os.path.getsize(caminho_zip)
    logger.info(
        "PROCESSO_ZIP numero=%s arquivo=%s documentos=%s ausentes=%s tamanho=%s",
        numero_processo,
        nome_zip,
        len(incluidos),
        len(ausentes),
        tamanho,
    )

    cabecalhos = {}
    if ausentes:
        cabecalhos["X-Arquivos-Ausentes"] = ",".join(str(i) for i in ausentes)

    return FileResponse(
        path=caminho_zip,
        filename=nome_zip,
        media_type="application/zip",
        headers=cabecalhos,
    )


@router.get("/{numero_processo:path}/checklist")
def checklist_processo(numero_processo: str):
    numero_processo = numero_processo.strip()
    documentos_do_processo = _documentos_do_processo(numero_processo)

    tipos_encontrados = {
        d.tipo_documento.value
        for d in documentos_do_processo
        if d.tipo_documento is not None
    }

    modalidade = _primeiro_valor(documentos_do_processo, "modalidade")
    esperados = DOCUMENTOS_POR_MODALIDADE.get(modalidade, DOCUMENTOS_OBRIGATORIOS)

    tipos_faltantes = [tipo for tipo in esperados if tipo not in tipos_encontrados]

    completo = len(tipos_faltantes) == 0

    logger.info(
        "CONSULTA_CHECKLIST processo=%s modalidade=%s completo=%s faltantes=%s",
        numero_processo,
        modalidade,
        completo,
        ",".join(tipos_faltantes) if tipos_faltantes else "nenhum",
    )

    return {
        "numero_processo": numero_processo,
        "modalidade": modalidade,
        "documentos_esperados": esperados,
        "documentos_encontrados": sorted(tipos_encontrados),
        "documentos_faltantes": tipos_faltantes,
        "completo": completo,
    }