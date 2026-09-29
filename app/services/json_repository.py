import json
import os
from typing import List, Optional

from app.models import Documento

METADATA_DIR = "storage/metadata"
METADATA_FILE = os.path.join(METADATA_DIR, "documentos.json")

os.makedirs(METADATA_DIR, exist_ok=True)


def ler_todos() -> List[Documento]:
    if not os.path.exists(METADATA_FILE):
        return []

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        conteudo = f.read().strip()

    if not conteudo:
        return []

    dados = json.loads(conteudo)
    return [Documento(**item) for item in dados]


def salvar_todos(documentos: List[Documento]) -> None:
    dados = [json.loads(doc.model_dump_json()) for doc in documentos]

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


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