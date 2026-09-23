from fastapi import FastAPI

from app.core.logging_config import logger
from app.routes.documentos import router as documentos_router

app = FastAPI(title="Cofre Digital - Licitações e Compras")
app.include_router(documentos_router)