from fastapi import FastAPI

from app.core.logging_config import logger
from app.routes.documentos import router as documentos_router
from app.routes.exportacao import router as exportacao_router
from app.routes.backup import router as backup_router

app = FastAPI(title="Cofre Digital - Licitações e Compras")
app.include_router(documentos_router)
app.include_router(exportacao_router)
app.include_router(backup_router)