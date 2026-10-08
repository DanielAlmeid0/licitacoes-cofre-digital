import csv
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.core.logging_config import logger
from app.services.json_repository import ler_todos

router = APIRouter(tags=["Exportação"])

COLUNAS_CSV = [
    "id",
    "nome_original",
    "extensao",
    "categoria",
    "tamanho",
    "data_upload",
    "sha256",
       "numero_processo",
    "tipo_documento",
    "fornecedor",
    "modalidade",
    "orgao_responsavel",
    "valor_estimado",
    "valor_contratado",
    "data_abertura",
    "data_homologacao",
    "situacao",
]


@router.get("/exportar/csv")
def exportar_csv():
    documentos = ler_todos()

    buffer = io.StringIO()
    escritor = csv.writer(buffer)

    escritor.writerow(COLUNAS_CSV)

    for doc in documentos:
        linha = []
        for coluna in COLUNAS_CSV:
            valor = getattr(doc, coluna, "")
            if hasattr(valor, "value"):  # Enum (ex: modalidade, situacao)
                valor = valor.value
            linha.append(valor if valor is not None else "")
        escritor.writerow(linha)

    buffer.seek(0)

    logger.info("EXPORTACAO_CSV total=%s", len(documentos))

    nome_arquivo = f"documentos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )

_CONTROLE_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # inválidos em XML 1.0

CAMPOS_DOCUMENTO_XML = [
    "nome_original", "nome_armazenado", "extensao", "tipo_mime", "tamanho",
    "categoria", "descricao", "data_upload", "sha256", "tipo_documento",
    "valor_estimado", "valor_contratado", "data_abertura", "data_homologacao",
]
ATRIBUTOS_PROCESSO_XML = ["modalidade", "situacao", "fornecedor", "orgao_responsavel"]


def _texto(valor) -> str:
    if hasattr(valor, "value"):  # Enum
        valor = valor.value
    if hasattr(valor, "isoformat"):  # datetime
        valor = valor.isoformat(timespec="seconds")
    return _CONTROLE_XML.sub("", str(valor))


@router.get("/exportar/xml")
def exportar_xml():
    documentos = ler_todos()

    por_processo: dict[str, list] = {}
    for doc in documentos:
        por_processo.setdefault(doc.numero_processo, []).append(doc)

    raiz = ET.Element(
        "catalogo",
        {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "total_processos": str(len(por_processo)),
            "total_documentos": str(len(documentos)),
        },
    )

    for numero, docs in por_processo.items():
        processo = ET.SubElement(raiz, "processo", {"numero_processo": _texto(numero)})
        for atributo in ATRIBUTOS_PROCESSO_XML:
            valor = next((getattr(d, atributo) for d in docs if getattr(d, atributo) is not None), None)
            if valor is not None:
                processo.set(atributo, _texto(valor))

        for doc in docs:
            no_doc = ET.SubElement(processo, "documento", {"id": str(doc.id)})
            for campo in CAMPOS_DOCUMENTO_XML:
                valor = getattr(doc, campo)
                if valor is not None:
                    ET.SubElement(no_doc, campo).text = _texto(valor)

    ET.indent(raiz)
    conteudo = ET.tostring(raiz, encoding="utf-8", xml_declaration=True)

    try:
        ET.fromstring(conteudo)  # garante XML bem formado antes de devolver
    except ET.ParseError as erro:
        logger.error("XML_INVALIDO detalhe=%s", erro)
        raise HTTPException(status_code=500, detail="Falha ao gerar um XML válido.") from erro

    logger.info("EXPORTACAO_XML processos=%s documentos=%s", len(por_processo), len(documentos))
    nome_arquivo = f"documentos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"

    return Response(
        content=conteudo,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )