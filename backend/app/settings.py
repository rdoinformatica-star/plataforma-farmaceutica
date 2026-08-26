"""Caminhos e limites do sistema.

Nao se chama config.py de proposito: engine/config.py entra no sys.path global
quando a ponte com o motor antigo e carregada, e os dois nomes colidiriam.
"""
from pathlib import Path

APP = Path(__file__).resolve().parent
BACKEND = APP.parent
RAIZ = BACKEND.parent

DADOS = RAIZ / "dados"
ENGINE_DIR = RAIZ / "engine"
CACHE = RAIZ / "cache"
RELATORIOS = RAIZ / "relatorios"
DATABASE = RAIZ / "database"
IMPORTS = RAIZ / "imports"
IMPORTS_TMP = IMPORTS / "tmp"

DB_PATH = DATABASE / "pharma.db"
SCHEMA_SQL = DATABASE / "schema.sql"
SEED_SQL = DATABASE / "seed.sql"
SCHEMA_POSTGRES_SQL = DATABASE / "schema_postgres.sql"
SEED_POSTGRES_SQL = DATABASE / "seed_postgres.sql"

VERSAO = "4.0.0-etapa4"
ETAPA = 4

# Pastas que o seletor de disco pode navegar. Qualquer caminho fora daqui e
# recusado, mesmo que o usuario digite na URL.
RAIZES_PERMITIDAS = [DADOS, RELATORIOS, IMPORTS]

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
BLOCO_HASH = 1024 * 1024
EXTENSOES_SUPORTADAS = {".html", ".htm", ".xlsx", ".xls", ".csv", ".txt", ".tsv"}

# Limites de resposta: nenhuma tela recebe milhoes de linhas.
LIMITE_PADRAO = 50
LIMITE_MAXIMO = 500

for _p in (CACHE, IMPORTS, IMPORTS_TMP, DATABASE):
    _p.mkdir(parents=True, exist_ok=True)
