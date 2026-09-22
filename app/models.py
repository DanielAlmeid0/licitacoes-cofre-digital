from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class Modalidade(str, Enum):
    PREGAO_ELETRONICO = "pregao_eletronico"
    CONCORRENCIA = "concorrencia"
    DISPENSA = "dispensa"
    INEXIGIBILIDADE = "inexigibilidade"
    TOMADA_DE_PRECOS = "tomada_de_precos"

class SituacaoProcesso(str, Enum):
    EM_ANDAMENTO = "em_andamento"
    HOMOLOGADDA = "homologada"
    CANCELADA = "cancelada"
    DESERTA = "deserta"
    FRACASADA = "fracassada"

class TipoDocumento(str, Enum):
    EDITAL = "edital"
    PROPOSTA = "proposta"
    CONTRATO = "contrato"
    ATA = "ata"
    TERMO_DE_REFERENCIA =  "termo_de_referencia"
    NOTA_DE_EMPENHO = "nota_de_empenho"
    OUTRO = "outro"

class Documento(BaseModel):
    #-- Campos comuns a todos os temas
    id: int
    nome_original: str
    nome_armazenado: str
    extensao: str
    tipo_mime: str
    tamanho: int
    categoria: str
    desccricao: Optional[str] = None
    data_upload: datetime
    sha256: str

    #-- Campos especificos: Licitações e compras

    numero_processo: str
    tipo_documento: TipoDocumento
    modalidade: Optional[Modalidade] = None
    orgao_responsavel: Optional[str] = None
    valor_estimado: Optional[float] = Field(default =None, ge=0)
    valor_contratado: Optional[float] = Field(default=None, ge=0)
    data_abertura: Optional[datetime] = None
    date_homologacao: Optional[datetime] = None
    situacao: Optional[SituacaoProcesso] = None
