from fastapi import APIRouter, HTTPException

from app.core.logging_config import logger
from app.services.json_repository import ler_todos

router = APIRouter(prefix="/processos", tags=["Processos"])

DOCUMENTOS_OBRIGATORIOS = ["edital", "proposta", "contrato", "ata"]


@router.get("/{numero_processo}/checklist")
def checklist_processo(numero_processo: str):
    documentos = ler_todos()
    documentos_do_processo = [
        d for d in documentos if d.numero_processo == numero_processo
    ]

    if not documentos_do_processo:
        logger.warning("PROCESSO_NAO_ENCONTRADO numero_processo=%s", numero_processo)
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum documento encontrado para o processo {numero_processo}.",
        )

    tipos_encontrados = {
        d.tipo_documento.value
        for d in documentos_do_processo
        if d.tipo_documento is not None
    }

    tipos_faltantes = [
        tipo for tipo in DOCUMENTOS_OBRIGATORIOS if tipo not in tipos_encontrados
    ]

    completo = len(tipos_faltantes) == 0

    logger.info(
        "CONSULTA_CHECKLIST processo=%s completo=%s faltantes=%s",
        numero_processo,
        completo,
        ",".join(tipos_faltantes) if tipos_faltantes else "nenhum",
    )

    return {
        "numero_processo": numero_processo,
        "documentos_esperados": DOCUMENTOS_OBRIGATORIOS,
        "documentos_encontrados": sorted(tipos_encontrados),
        "documentos_faltantes": tipos_faltantes,
        "completo": completo,
    }