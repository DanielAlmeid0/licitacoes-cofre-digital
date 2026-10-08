"""Popula o Cofre Digital com dados de apresentação, enviando tudo pela API.

Uso (com a API rodando em outro terminal):
    py seed.py
    py seed.py --url http://127.0.0.1:8000
    py seed.py --forcar      # cadastra mesmo que já existam documentos

Os arquivos são gerados em memória (nada é criado fora do storage/ da API).
Como o envio é feito pelo endpoint POST /documentos, o sistema.log fica com um
histórico real de UPLOAD.
"""
import argparse
import csv
import io
import struct
import sys
import zlib

import requests

# ----------------------------------------------------------------- geradores
def gerar_pdf(titulo: str, linhas: list[str]) -> bytes:
    """PDF mínimo e válido (1 página, texto). Arquivo binário de verdade."""

    def esc(texto: str) -> str:
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    partes = ["BT", "/F1 16 Tf", "72 780 Td", f"({esc(titulo)}) Tj", "/F1 11 Tf"]
    for linha in linhas:
        partes += ["0 -22 Td", f"({esc(linha)}) Tj"]
    partes.append("ET")
    stream = "\n".join(partes).encode("latin-1", errors="replace")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos = []
    for numero, objeto in enumerate(objetos, start=1):
        deslocamentos.append(len(saida))
        saida += f"{numero} 0 obj\n".encode() + objeto + b"\nendobj\n"

    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for deslocamento in deslocamentos:
        saida += f"{deslocamento:010d} 00000 n \n".encode()
    saida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    return bytes(saida)


def gerar_png(cor=(30, 90, 160), largura=96, altura=64) -> bytes:
    """PNG válido com um degradê. Segundo arquivo binário do conjunto."""
    linhas = bytearray()
    for y in range(altura):
        linhas.append(0)  # filtro "nenhum"
        for x in range(largura):
            linhas += bytes((min(255, cor[0] + x), min(255, cor[1] + y * 2), cor[2]))

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0))
        + bloco(b"IDAT", zlib.compress(bytes(linhas)))
        + bloco(b"IEND", b"")
    )


def gerar_txt(titulo: str, linhas: list[str]) -> bytes:
    return ("\n".join([titulo.upper(), "=" * len(titulo), *linhas]) + "\n").encode("utf-8")


def gerar_csv(cabecalho: list[str], registros: list[list]) -> bytes:
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(cabecalho)
    escritor.writerows(registros)
    return buffer.getvalue().encode("utf-8")


def gerar_xml(raiz: str, campos: dict[str, str]) -> bytes:
    itens = "\n".join(f"  <{chave}>{valor}</{chave}>" for chave, valor in campos.items())
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<{raiz}>\n{itens}\n</{raiz}>\n'.encode("utf-8")


# ------------------------------------------------------------------- dados
# Cada processo tem metadados próprios (modalidade, fornecedor, valores...) e
# uma lista de documentos. Há processos completos e incompletos de propósito,
# para demonstrar o checklist e o ZIP por processo (F16).
PROCESSOS = [
    {
        "numero": "0001/2026",
        "modalidade": "pregao_eletronico",
        "fornecedor": "Papelaria Central Ltda",
        "orgao": "Secretaria de Educação",
        "estimado": 48000.00,
        "contratado": 45200.00,
        "abertura": "2026-03-10T09:00:00",
        "homologacao": "2026-03-25T15:00:00",
        "situacao": "homologada",
        "docs": [
            ("edital", "licitacao", "pdf", "Edital do Pregão 0001/2026", "Edital de material de expediente"),
            ("proposta", "licitacao", "pdf", "Proposta Papelaria Central", "Proposta comercial vencedora"),
            ("ata", "licitacao", "txt", "Ata de julgamento 0001/2026", "Ata da sessão pública do pregão"),
            ("contrato", "contrato", "pdf", "Contrato 0001/2026", "Contrato de fornecimento de material"),
            ("nota_fiscal", "financeiro", "csv", "Nota fiscal 0001/2026", "Itens faturados da nota fiscal"),
        ],
    },
    {
        "numero": "0002/2026",
        "modalidade": "concorrencia",
        "fornecedor": "Construtora Horizonte S.A.",
        "orgao": "Secretaria de Obras",
        "estimado": 850000.00,
        "contratado": 812500.00,
        "abertura": "2026-04-02T10:00:00",
        "homologacao": "2026-05-06T16:30:00",
        "situacao": "homologada",
        "docs": [
            ("edital", "licitacao", "pdf", "Edital da Concorrência 0002/2026", "Reforma da escola municipal"),
            ("proposta", "licitacao", "pdf", "Proposta Construtora Horizonte", "Proposta de preços da obra"),
            ("ata", "licitacao", "txt", "Ata de julgamento 0002/2026", "Ata de classificação das propostas"),
            ("contrato", "contrato", "xml", "Contrato 0002/2026", "Contrato de execução de obra em XML"),
            ("documento_fornecedor", "fornecedor", "png", "Certidão negativa (digitalizada)", "Certidão do fornecedor digitalizada"),
        ],
    },
    {
        "numero": "0003/2026",
        "modalidade": "dispensa",
        "fornecedor": "Clínica Vida Saúde ME",
        "orgao": "Secretaria de Saúde",
        "estimado": 12000.00,
        "contratado": 11800.00,
        "abertura": "2026-05-15T08:30:00",
        "homologacao": "2026-05-20T11:00:00",
        "situacao": "homologada",
        "docs": [
            ("edital", "licitacao", "txt", "Aviso de dispensa 0003/2026", "Aviso de contratação direta"),
            ("cotacao", "licitacao", "pdf", "Cotação Clínica Vida Saúde", "Cotação de exames ocupacionais"),
            ("contrato", "contrato", "pdf", "Contrato 0003/2026", "Contrato de prestação de serviços"),
        ],
    },
    {
        "numero": "0004/2026",
        "modalidade": "pregao_eletronico",
        "fornecedor": "TecnoInfo Equipamentos Ltda",
        "orgao": "Secretaria de Administração",
        "estimado": 120000.00,
        "contratado": None,
        "abertura": "2026-09-20T09:00:00",
        "homologacao": None,
        "situacao": "em_andamento",
        "docs": [
            ("edital", "licitacao", "pdf", "Edital do Pregão 0004/2026", "Aquisição de computadores"),
            ("proposta", "licitacao", "pdf", "Proposta TecnoInfo", "Proposta para 40 computadores"),
        ],
    },
    {
        "numero": "0005/2026",
        "modalidade": "inexigibilidade",
        "fornecedor": "Editora Saber Jurídico",
        "orgao": "Procuradoria Municipal",
        "estimado": 9500.00,
        "contratado": 9500.00,
        "abertura": "2026-06-03T14:00:00",
        "homologacao": "2026-06-05T10:00:00",
        "situacao": "homologada",
        "docs": [
            ("documento_fornecedor", "fornecedor", "pdf", "Carta de exclusividade", "Declaração de fornecedor exclusivo"),
            ("contrato", "contrato", "txt", "Contrato 0005/2026", "Assinatura de periódico jurídico"),
        ],
    },
    {
        "numero": "0006/2026",
        "modalidade": "tomada_de_precos",
        "fornecedor": "Serviços Gerais Alfa Ltda",
        "orgao": "Secretaria de Administração",
        "estimado": 36000.00,
        "contratado": None,
        "abertura": "2026-07-08T09:30:00",
        "homologacao": None,
        "situacao": "cancelada",
        "docs": [
            ("edital", "licitacao", "pdf", "Edital Tomada de Preços 0006/2026", "Serviços de limpeza (cancelada)"),
        ],
    },
]


def montar_conteudo(extensao: str, titulo: str, processo: dict, tipo: str) -> bytes:
    resumo = [
        f"Processo: {processo['numero']}",
        f"Modalidade: {processo['modalidade']}",
        f"Fornecedor: {processo['fornecedor']}",
        f"Orgao: {processo['orgao']}",
        f"Situacao: {processo['situacao']}",
    ]
    if extensao == "pdf":
        return gerar_pdf(titulo, resumo)
    if extensao == "txt":
        return gerar_txt(titulo, resumo)
    if extensao == "csv":
        return gerar_csv(
            ["item", "descricao", "quantidade", "valor_unitario"],
            [[1, "Resma de papel A4", 200, 28.90], [2, "Caneta esferografica", 500, 1.75], [3, "Pasta suspensa", 300, 4.20]],
        )
    if extensao == "xml":
        return gerar_xml(
            "contrato",
            {
                "numero_processo": processo["numero"],
                "fornecedor": processo["fornecedor"],
                "modalidade": processo["modalidade"],
                "valor": f"{processo['contratado']:.2f}" if processo["contratado"] else "0.00",
            },
        )
    if extensao == "png":
        return gerar_png()
    raise ValueError(f"extensão sem gerador: {extensao}")


def nome_do_arquivo(processo: dict, tipo: str, extensao: str) -> str:
    numero = processo["numero"].replace("/", "-")
    return f"{tipo}_{numero}.{extensao}"


TIPOS_MIME = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "csv": "text/csv",
    "xml": "application/xml",
    "png": "image/png",
}


# ------------------------------------------------------------------ envio
def enviar(base_url: str, processo: dict, doc: tuple) -> bool:
    tipo, categoria, extensao, titulo, descricao = doc
    nome = nome_do_arquivo(processo, tipo, extensao)
    conteudo = montar_conteudo(extensao, titulo, processo, tipo)

    campos = {
        "categoria": categoria,
        "descricao": descricao,
        "numero_processo": processo["numero"],
        "tipo_documento": tipo,
        "modalidade": processo["modalidade"],
        "fornecedor": processo["fornecedor"],
        "orgao_responsavel": processo["orgao"],
        "valor_estimado": processo["estimado"],
        "valor_contratado": processo["contratado"],
        "data_abertura": processo["abertura"],
        "data_homologacao": processo["homologacao"],
        "situacao": processo["situacao"],
    }
    campos = {chave: valor for chave, valor in campos.items() if valor is not None}

    resposta = requests.post(
        f"{base_url}/documentos",
        files={"arquivo": (nome, conteudo, TIPOS_MIME[extensao])},
        data=campos,
        timeout=30,
    )

    if resposta.status_code == 201:
        print(f"  [ok] id={resposta.json()['id']:<3} {nome}")
        return True

    print(f"  [ERRO {resposta.status_code}] {nome}: {resposta.text}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Popula o Cofre Digital pela API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="endereço da API")
    parser.add_argument("--forcar", action="store_true", help="cadastra mesmo com documentos já existentes")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    try:
        existentes = requests.get(f"{base_url}/documentos", timeout=10).json()
    except requests.RequestException:
        print(f"Não consegui falar com a API em {base_url}.")
        print("Suba a API em outro terminal:  py -m uvicorn app.main:app --reload")
        return 1

    if existentes and not args.forcar:
        print(f"A API já tem {len(existentes)} documento(s) cadastrado(s).")
        print("Rodar o seed de novo duplicaria os dados. Use --forcar se for isso mesmo que quer.")
        return 1

    total = sucesso = 0
    for processo in PROCESSOS:
        print(f"\nProcesso {processo['numero']} ({processo['modalidade']}, {processo['situacao']})")
        for doc in processo["docs"]:
            total += 1
            sucesso += enviar(base_url, processo, doc)

    print(f"\n{sucesso}/{total} documentos cadastrados.")

    estatisticas = requests.get(f"{base_url}/documentos/estatisticas", timeout=10).json()
    print("\nResumo do cofre:")
    print(f"  total de documentos : {estatisticas['total_documentos']}")
    print(f"  por extensão        : {estatisticas['por_extensao']}")
    print(f"  por categoria       : {estatisticas['por_categoria']}")
    return 0 if sucesso == total else 1


if __name__ == "__main__":
    sys.exit(main())
