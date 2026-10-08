from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging_config import logger
from app.routes.documentos import router as documentos_router
from app.routes.documentos import router_integridade
from app.routes.exportacao import router as exportacao_router
from app.routes.backup import router as backup_router
from app.routes.processos import router as processos_router
from app.services.json_repository import RepositorioError

app = FastAPI(title="Cofre Digital - Licitações e Compras")
app.include_router(documentos_router)
app.include_router(router_integridade)
app.include_router(exportacao_router)
app.include_router(backup_router)
app.include_router(processos_router)


@app.exception_handler(RepositorioError)
async def tratar_erro_repositorio(request: Request, erro: RepositorioError):
    logger.error("ERRO_REPOSITORIO rota=%s detalhe=%s", request.url.path, erro)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro ao acessar os metadados. Verifique o documentos.json "
            "ou restaure um backup."
        },
    )