import json
import os
import tempfile
from typing import List, Optional

from pydantic import ValidationError

from app.core.config import config
from app.models import Documento

METADATA_DIR = config["storage"]["diretorio_metadata"]
METADATA_FILE = os.path.join(METADATA_DIR, "documentos.json")

os.makedirs(METADATA_DIR, exist_ok=True)


class RepositorioError(Exception):
    """Falha ao ler ou gravar os metadados (JSON inválido, dados fora do modelo, erro de disco)."""


def ler_todos() -> List[Documento]:
    if not os.path.exists(METADATA_FILE):
        return []

    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
    except OSError as erro:
        raise RepositorioError(f"Não foi possível ler {METADATA_FILE}: {erro}") from erro

    if not conteudo:
        return []

    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError as erro:
        raise RepositorioError(f"JSON inválido em {METADATA_FILE}: {erro}") from erro

    if not isinstance(dados, list):
        raise RepositorioError(f"{METADATA_FILE}: a raiz deve ser uma lista de documentos.")

    try:
        return [Documento(**item) for item in dados]
    except (TypeError, ValidationError) as erro:
        raise RepositorioError(f"Metadado inválido em {METADATA_FILE}: {erro}") from erro


def salvar_todos(documentos: List[Documento]) -> None:
    """Grava em arquivo temporário e troca com os.replace, para nunca deixar JSON pela metade."""
    dados = [json.loads(doc.model_dump_json()) for doc in documentos]

    caminho_tmp = None
    try:
        os.makedirs(METADATA_DIR, exist_ok=True)
        fd, caminho_tmp = tempfile.mkstemp(
            dir=METADATA_DIR, prefix=".documentos_", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(caminho_tmp, METADATA_FILE)
    except OSError as erro:
        if caminho_tmp and os.path.exists(caminho_tmp):
            os.remove(caminho_tmp)
        raise RepositorioError(f"Não foi possível gravar {METADATA_FILE}: {erro}") from erro


def proximo_id() -> int:
    documentos = ler_todos()
    if not documentos:
        return 1
    return max(doc.id for doc in documentos) + 1


def adicionar(documento: Documento) -> None:
    documentos = ler_todos()
    documentos.append(documento)
    salvar_todos(documentos)


def buscar_por_id(documento_id: int) -> Optional[Documento]:
    for doc in ler_todos():
        if doc.id == documento_id:
            return doc
    return None


def atualizar(documento: Documento) -> None:
    documentos = ler_todos()
    documentos = [documento if doc.id == documento.id else doc for doc in documentos]
    salvar_todos(documentos)


def remover(documento_id: int) -> bool:
    documentos = ler_todos()
    restantes = [doc for doc in documentos if doc.id != documento_id]

    if len(restantes) == len(documentos):
        return False

    salvar_todos(restantes)
    return True