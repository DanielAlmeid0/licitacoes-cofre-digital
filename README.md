# Cofre Digital - Licitações e Compras

API em FastAPI para armazenar, organizar e recuperar documentos de processos de licitação e compras, com metadados em JSON, logs, backup e exportações.

## Integrantes

- José Yago
- Lorhann De Oliveira
- Daniel Almeida

Disciplina: Desenvolvimento De Software Para Persistencia | Professor: Francisco Victor Da Silva Pinheiro

## Objetivo

Oferecer um "cofre" de documentos (editais, propostas, contratos, atas, cotações, notas fiscais e documentos de fornecedores) com cadastro, consulta, integridade por hash, backup/restauração e relatórios por processo.

## Requisitos e bibliotecas

- Python 3.11+ (_confirmar a versão usada_)
- FastAPI, Uvicorn, Pydantic, PyYAML, python-multipart (_conferir com o requirements.txt_)

## Instalação

    git clone <url-do-repositorio>
    cd licitacoes-cofre-digital
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

## Execução

    uvicorn app.main:app --reload

Swagger: http://127.0.0.1:8000/docs

Para popular dados de demonstração (com a API rodando):

    python seed.py

O seed cadastra 18 documentos, em 5 extensões, 4 categorias e 6 processos.

## Estrutura

    app/
      main.py                # aplicação e registro das rotas
      models.py              # modelos Pydantic e tipos de documento
      routes/
        documentos.py        # CRUD, filtros, estatísticas, integridade
        processos.py         # documentos, ZIP e checklist por processo (F16)
        exportacao.py        # exportação CSV e XML
        backup.py            # backup, download e restauração
      services/
        json_repository.py   # leitura/escrita atômica dos metadados
        hash_service.py      # hash conforme o config.yaml
    storage/
      documentos/            # arquivos físicos
      metadata/              # documentos.json
      backups/               # ZIPs de backup
      logs/sistema.log       # log do sistema
    seed.py

## Metadados do domínio

Cada documento tem: nome do arquivo, tipo de documento (edital, proposta, contrato, ata, cotacao, nota_fiscal, documento_fornecedor, entre outros), categoria, número do processo, valor contratado, tipo MIME, descrição e hash de integridade.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/documentos` | Upload com metadados (400 arquivo vazio, 413 acima do limite, 422 metadados inválidos) |
| GET | `/documentos` | Lista com filtros (categoria, extensao, numero_processo, tipo_documento, modalidade, orgao_responsavel, fornecedor, situacao, nome_arquivo) |
| GET | `/documentos/{id}` | Consulta de um documento |
| GET | `/documentos/{id}/download` | Download do arquivo |
| GET | `/documentos/{id}/integridade` | Confere o hash de um documento |
| PUT | `/documentos/{id}` | Atualiza metadados (revalida o documento inteiro) |
| DELETE | `/documentos/{id}` | Remove documento |
| GET | `/documentos/estatisticas` | Totais por extensão, categoria, modalidade e situação; valor contratado somado por processo |
| GET | `/integridade` | Verifica o hash de todos os documentos |
| GET | `/processos` | Lista os processos cadastrados |
| GET | `/processos/{numero_processo}/documentos` | Documentos do processo (F16) |
| GET | `/processos/{numero_processo}/zip` | ZIP com os arquivos do processo (F16) |
| GET | `/processos/{numero_processo}/checklist` | Documentos presentes e faltantes por modalidade (extra) |
| GET | `/exportar/csv` | Exportação CSV |
| GET | `/exportar/xml` | Exportação XML agrupada por processo |
| POST | `/backup` | Cria backup |
| GET | `/backups` | Lista backups |
| GET | `/backups/{nome}` | Baixa um backup (404 se não existir) |
| POST | `/backups/{nome}/restaurar` | Restaura um backup |

O número do processo aceita barra, por exemplo `/processos/0001/2026/zip`.

## F16 - Documentos por processo

Agrupa os documentos pelo número do processo. `GET /processos/0001/2026/zip` baixa um ZIP com todos os arquivos do processo.

O checklist (`/processos/0004/2026/checklist`) compara os tipos presentes com os esperados para a modalidade do processo e lista os faltantes:

- Pregão eletrônico, concorrência e tomada de preços: edital, proposta, ata e contrato.
- Dispensa: cotação e contrato.
- Inexigibilidade: documento do fornecedor e contrato.

## Backup e restauração

- O nome do backup inclui data e segundos (`backup_2026-10-08_040710.zip`) e ganha contador se houver colisão.
- A restauração valida os metadados do ZIP antes de alterar qualquer coisa; backup corrompido retorna 422 e nada muda.
- Entradas com `../` dentro do ZIP são bloqueadas.
- Decisão de projeto: a restauração substitui o `documentos.json` pelo do backup. Documentos cadastrados depois do backup somem da lista, mas o arquivo físico permanece na pasta.

## Logs

Os eventos ficam em `storage/logs/sistema.log` (UPLOAD, CONSULTA, BACKUP_CRIADO, BACKUP_NAO_ENCONTRADO, BACKUP_RESTAURADO, entre outros). Recurso não encontrado é `WARNING`; inconsistência (como arquivo físico ausente) e falhas são `ERROR`.

## Validações e tratamento de erros

- Upload recusa arquivo vazio (400), acima de `upload.tamanho_maximo_mb` (413) e metadados inválidos (422) sem gravar o arquivo. Nomes com `../` são limpos.
- O PUT revalida o documento inteiro; `null` em campo obrigatório ou valor negativo retornam 422.
- A gravação do `documentos.json` usa arquivo temporário e `os.replace`. JSON inválido gera `RepositorioError` e resposta 500 com log `ERRO_REPOSITORIO`.
- O diretório de metadados e o algoritmo de hash vêm do `config.yaml`.

## Exemplos

    curl -X POST http://127.0.0.1:8000/backup
    curl -OJ http://127.0.0.1:8000/processos/0001/2026/zip