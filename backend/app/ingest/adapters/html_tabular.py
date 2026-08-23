"""Leitor de relatorios em HTML com tabelas — dossies, dashboards customizados, etc.

Estes arquivos trazem numeros ja calculados (share, penetracao, variacao %),
organizados em tabelas de formatos diferentes dentro do mesmo arquivo, e nem
sempre em grao incremental (ex.: "7 meses acumulados"). Por isso NAO alimentam
fact_sales — misturaria grao com o motor de vendas (distribuidor x produto x
pdv x mes) e arriscaria duplicar ao reimportar um mes seguinte. Ficam
guardados em dossies_html, ligados ao distribuidor quando identificado, para
consulta — nao entram nos calculos de ABC/cobertura/estoque/mercado.
"""
import json
import re
import sqlite3
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

CODIGO = "html_tabular"
ROTULO = "Relatório HTML (tabelas de referência)"
DATA_SOURCE = "OUTROS"

# Mapa de aliases comuns -> nome padrao a procurar em dim_distribuidor
DISTRIBUIDORES_ALIASES = {
    "emefarma": "EMEFARMA",
    "millenium": "MILLENIUM",
    "millenio": "MILLENIUM",
    "raia": "RAIA",
    "drogasil": "DROGASIL",
}


def pontuar(path: Path, cabeca: bytes, ext: str) -> tuple[float, str]:
    """Detecta HTML com tabelas estruturadas (thead/tbody/tr/td)."""
    if ext not in {".html", ".htm"}:
        return 0.0, ""

    texto_lower = cabeca.lower()

    if (b"<table" in texto_lower and b"<thead" in texto_lower and
            b"<tbody" in texto_lower and b"<tr" in texto_lower and b"<td" in texto_lower):
        return 0.99, "tabela estruturada com <thead>, <tbody>, <tr>, <td>"

    if b"<table" in texto_lower and b"<tr" in texto_lower and b"<td" in texto_lower:
        return 0.95, "tabela com <tr> e <td>"

    if b"<table" in texto_lower:
        return 0.70, "contém <table> mas sem estrutura clara"

    return 0.0, ""


def params_sugeridos(path: Path, cabeca: bytes) -> dict:
    distribuidor = _detectar_distribuidor(path, cabeca)
    return {"distribuidor_nome": distribuidor} if distribuidor else {}


def _detectar_distribuidor(path: Path, cabeca: bytes) -> str | None:
    """Procura o nome do distribuidor no nome do arquivo, <title> ou <h1>/<h2>."""
    nome_arquivo = path.stem.lower()
    for alias, nome in DISTRIBUIDORES_ALIASES.items():
        if alias in nome_arquivo:
            return nome

    titulo_match = re.search(rb"<title>([^<]+)</title>", cabeca, re.IGNORECASE)
    if titulo_match:
        titulo = titulo_match.group(1).decode("utf-8", errors="ignore").lower()
        for alias, nome in DISTRIBUIDORES_ALIASES.items():
            if alias in titulo:
                return nome

    for match in re.finditer(rb"<h[12][^>]*>([^<]+)</h[12]>", cabeca, re.IGNORECASE):
        texto = match.group(1).decode("utf-8", errors="ignore").lower()
        for alias, nome in DISTRIBUIDORES_ALIASES.items():
            if alias in texto:
                return nome

    return None


class TableExtractor(HTMLParser):
    """Extrai TODAS as tabelas do documento, cada uma com seu proprio
    cabecalho/linhas, mais o titulo (heading mais proximo antes da tabela)."""

    def __init__(self):
        super().__init__()
        self.tables: list[dict] = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.in_thead = False
        self.ultimo_heading = None
        self._lendo_heading = False
        self._heading_buf = None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3"):
            self._lendo_heading = True
            self._heading_buf = StringIO()
        elif tag == "table":
            self.current_table = {
                "titulo": self.ultimo_heading, "headers": [], "rows": [],
            }
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tr":
            self.current_row = []
        elif tag in ("td", "th"):
            self.current_cell = StringIO()
        elif tag == "br" and self.current_cell:
            self.current_cell.write(" ")

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3") and self._lendo_heading:
            self.ultimo_heading = self._heading_buf.getvalue().strip() or None
            self._lendo_heading = False
            self._heading_buf = None
        elif tag == "table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tr":
            if self.current_row is not None and self.current_table is not None:
                if self.in_thead or not self.current_table["headers"]:
                    self.current_table["headers"] = self.current_row
                else:
                    self.current_table["rows"].append(self.current_row)
            self.current_row = None
        elif tag in ("td", "th"):
            if self.current_cell is not None and self.current_row is not None:
                self.current_row.append(self.current_cell.getvalue().strip())
            self.current_cell = None

    def handle_data(self, data):
        if self._lendo_heading and self._heading_buf is not None:
            self._heading_buf.write(data)
        elif self.current_cell is not None:
            self.current_cell.write(data)


def abrir(path: Path, params: dict, prog):
    """Extrai todas as tabelas do HTML; a gravacao guarda cada uma em
    dossies_html, sem tocar em fact_sales."""
    from ..base import Coluna, Lote

    prog.etapa("Lendo arquivo HTML", 0.1)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    prog.etapa("Extraindo tabelas", 0.3)
    parser = TableExtractor()
    parser.feed(html_content)

    tabelas = [t for t in parser.tables if t["rows"]]
    if not tabelas:
        raise ValueError("Nenhuma tabela com dados encontrada no arquivo HTML")

    prog.etapa("Preparando lote", 0.9)
    distribuidor_nome = params.get("distribuidor_nome")

    def gravar(con: sqlite3.Connection, import_id: int, prog):
        return _gravar_dossie(con, import_id, prog, tabelas, distribuidor_nome, path.name)

    total_linhas = sum(len(t["rows"]) for t in tabelas)
    maior = max(tabelas, key=lambda t: len(t["rows"]))
    colunas = [
        Coluna(nome=_limpar_coluna(h) or f"col_{i}",
               valores=[row[i] if i < len(row) else None for row in maior["rows"]])
        for i, h in enumerate(maior["headers"])
    ]

    lote = Lote(
        fonte=path.name,
        # Igual ao tamanho da maior tabela (as colunas do perfil vem dela) —
        # nao a soma de todas: tabelas diferentes tem colunas diferentes, e o
        # perfilador espera todas as colunas do mesmo tamanho de n_linhas.
        n_linhas=len(maior["rows"]),
        colunas=colunas,
        gravar=gravar,
        buscar_chaves=False,  # nao faz sentido checar duplicata entre tabelas de formatos diferentes
        avisos=[
            "Relatório de referência: os números aqui são cálculos já prontos "
            "do arquivo original (share, variação, penetração), em tabelas de "
            "formatos diferentes. Não entram no motor de ABC/cobertura/estoque/"
            "mercado — ficam disponíveis só para consulta.",
            f"{len(tabelas)} tabela(s) encontradas no arquivo, {total_linhas} "
            f"linhas ao todo (o perfil mostrado é só da maior).",
        ],
    )
    prog.etapa("Lote pronto", 1.0)
    return lote


def _gravar_dossie(con: sqlite3.Connection, import_id: int, prog,
                    tabelas: list[dict], distribuidor_nome: str | None,
                    nome_arquivo: str) -> int:
    prog.etapa("Identificando distribuidor", 0.1)

    distribuidor_id = None
    if distribuidor_nome:
        dist = con.execute(
            "SELECT id FROM dim_distribuidor WHERE upper(nome) LIKE ? LIMIT 1",
            (f"%{distribuidor_nome.upper()}%",),
        ).fetchone()
        if dist:
            distribuidor_id = dist[0]
            prog.log(f"Distribuidor identificado: {distribuidor_nome} (ID {distribuidor_id})")
        else:
            prog.log(f"Distribuidor '{distribuidor_nome}' detectado no arquivo, mas "
                      f"ainda não existe no cadastro (nenhum sell-out importado dele "
                      f"ainda). O dossiê fica salvo com o nome, sem vínculo por enquanto.")
    else:
        prog.log("Não foi possível identificar o distribuidor pelo nome do arquivo "
                  "ou pelo título do relatório.")

    prog.etapa("Gravando tabelas de referência", 0.5)
    for indice, tabela in enumerate(tabelas):
        con.execute(
            "INSERT INTO dossies_html(import_id, distribuidor_id,"
            " distribuidor_nome_detectado, arquivo_nome, tabela_indice,"
            " tabela_titulo, cabecalhos_json, linhas_json)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (import_id, distribuidor_id, distribuidor_nome, nome_arquivo, indice,
             tabela["titulo"], json.dumps(tabela["headers"], ensure_ascii=False),
             json.dumps(tabela["rows"], ensure_ascii=False)),
        )

    total_linhas = sum(len(t["rows"]) for t in tabelas)
    prog.log(f"{len(tabelas)} tabela(s) guardadas como referência, "
              f"{total_linhas} linhas ao todo.")
    prog.etapa("Pronto", 1.0)
    return total_linhas


def _limpar_coluna(nome: str) -> str:
    nome = re.sub(r'[^\w\s]', '', nome, flags=re.UNICODE)
    return '_'.join(nome.split()).lower()
