import csv
import io
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

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
    "modalidade",
    "orgao_responsavel",
    "valor_estimado",
    "valor_contratado",
    "data_abertura",
    "date_homologacao",
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