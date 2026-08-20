"""Escrita das dimensoes e carga em massa dos fatos.

A regra de ouro das dimensoes: a chave natural e sempre TEXTUAL. Os arquivos de
origem identificam produto e PDV por indice posicional, e esse indice muda de uma
versao do export para a outra — usar o indice duplicaria toda a base na
reimportacao seguinte.
"""
import numpy as np

from ..core.texto import chave as chave_texto
from ..core.texto import ean13, normalizar

BLOCO = 250_000
COMMIT_A_CADA = 4  # blocos


def _ids_por_chave(con, tabela: str, chaves: list[str]) -> dict[str, int]:
    """Le os ids de volta em lotes. executemany nao devolve RETURNING."""
    mapa: dict[str, int] = {}
    unicas = list(dict.fromkeys(chaves))
    for i in range(0, len(unicas), 900):
        pedaco = unicas[i:i + 900]
        marca = ",".join("?" * len(pedaco))
        for k, v in con.execute(
            f"SELECT chave_natural, id FROM {tabela} WHERE chave_natural IN ({marca})",
            pedaco,
        ):
            mapa[k] = v
    return mapa


def upsert_produtos_texto(con, nomes: list[str], eans: list[str | None],
                          import_id: int) -> list[int]:
    """Produtos vindos de fonte tabular. Devolve o id de cada LINHA, na ordem."""
    chaves = [(e if e else chave_texto(n)) for n, e in zip(nomes, eans)]
    vistos: dict[str, tuple] = {}
    for k, n, e in zip(chaves, nomes, eans):
        vistos.setdefault(k, (k, str(n).strip(), e, str(n).strip(), import_id))
    con.executemany(
        "INSERT OR IGNORE INTO dim_product"
        "(chave_natural, nome_canonico, ean, apresentacao, primeiro_import_id)"
        " VALUES (?,?,?,?,?)", list(vistos.values()))
    mapa = _ids_por_chave(con, "dim_product", chaves)
    return [mapa[k] for k in chaves]


def upsert_produtos_vmd(con, apresentacoes, eans, fccs, produtos, marcas,
                        prod_pro, prod_mar, import_id: int) -> np.ndarray:
    """Dimensao de produto do sell-out. Devolve array indice_do_arquivo -> id.

    A chave e o EAN quando existe. Alem de ser estavel entre versoes do arquivo,
    e o que permite reconhecer o mesmo produto na planilha de estoque, que so
    traz o codigo de barras.
    """
    def _rot(tabela, i):
        return tabela[i] if tabela is not None and i < len(tabela) else None

    linhas, chaves = [], []
    for i, apre in enumerate(apresentacoes):
        ean = ean13(_rot(eans, i))
        k = ean or chave_texto(apre)
        chaves.append(k)
        base = _rot(produtos, int(prod_pro[i])) if prod_pro is not None else None
        marca = _rot(marcas, int(prod_mar[i])) if prod_mar is not None else None
        linhas.append((k, str(apre).strip(), ean, _rot(fccs, i),
                       str(apre).strip(), base, marca, import_id))
    con.executemany(
        "INSERT OR IGNORE INTO dim_product"
        "(chave_natural, nome_canonico, ean, codigo_interno, apresentacao,"
        " produto_base, marca, primeiro_import_id) VALUES (?,?,?,?,?,?,?,?)", linhas)
    mapa = _ids_por_chave(con, "dim_product", chaves)
    return np.fromiter((mapa[k] for k in chaves), dtype=np.int64, count=len(chaves))


def upsert_distribuidores(con, nomes, cnpjs, import_id: int) -> np.ndarray:
    linhas, chaves = [], []
    for i, nome in enumerate(nomes):
        cnpj = None
        if cnpjs is not None and i < len(cnpjs):
            from ..core.texto import so_digitos
            cnpj = so_digitos(cnpjs[i]) or None
        k = cnpj or chave_texto(nome)
        chaves.append(k)
        linhas.append((k, str(nome).strip(), cnpj, import_id))
    con.executemany(
        "INSERT OR IGNORE INTO dim_distribuidor"
        "(chave_natural, nome, cnpj, primeiro_import_id) VALUES (?,?,?,?)", linhas)
    mapa = _ids_por_chave(con, "dim_distribuidor", chaves)
    return np.fromiter((mapa[k] for k in chaves), dtype=np.int64, count=len(chaves))


def upsert_pdvs(con, razoes, cnpjs, col: dict, dic: dict,
                import_id: int) -> tuple[np.ndarray, int]:
    """PDVs do sell-out.

    A chave e o CNPJ do PDV. Cair para razao|uf|cidade funde lojas distintas da
    mesma rede na mesma cidade — no arquivo real isso apagaria mais de 20 mil
    PDVs e falsearia churn e cobertura.
    """
    from ..core.texto import so_digitos

    def _rot(nome_dic, nome_col, i):
        tabela, idx = dic.get(nome_dic), col.get(nome_col)
        if tabela is None or idx is None or i >= len(idx):
            return None
        j = int(idx[i])
        return tabela[j] if 0 <= j < len(tabela) else None

    linhas, chaves = [], []
    for i, razao in enumerate(razoes):
        cnpj = so_digitos(cnpjs[i]) if cnpjs is not None and i < len(cnpjs) else ""
        uf = _rot("uf", "pdvUf", i)
        cidade = _rot("cidade", "pdvCid", i)
        k = cnpj or f"{chave_texto(razao)}|{normalizar(uf)}|{chave_texto(cidade)}"
        chaves.append(k)
        linhas.append((k, str(razao).strip(), cnpj or None, uf, cidade,
                       _rot("grupo", "pdvGrp", i), _rot("bandeira", "pdvBan", i),
                       _rot("rede", "pdvRed", i), _rot("tipo", "pdvTip", i),
                       import_id))

    colisoes = len(chaves) - len(set(chaves))
    con.executemany(
        "INSERT OR IGNORE INTO dim_pdv"
        "(chave_natural, razao_social, cnpj, uf, cidade, grupo, bandeira, rede,"
        " tipo, primeiro_import_id) VALUES (?,?,?,?,?,?,?,?,?,?)", linhas)
    mapa = _ids_por_chave(con, "dim_pdv", chaves)
    return np.fromiter((mapa[k] for k in chaves), dtype=np.int64, count=len(chaves)), colisoes


# ─────────────────────────── carga em massa ────────────────────────────

INSERT_VENDAS = (
    "INSERT INTO fact_sales"
    "(import_id, distribuidor_id, produto_id, pdv_id, periodo,"
    " unidades_x100, valor_x100) VALUES (?,?,?,?,?,?,?)")

INDICES_VENDAS = (
    "CREATE INDEX IF NOT EXISTS ix_fs_dist_per"
    " ON fact_sales(distribuidor_id, periodo, produto_id)",
    "CREATE INDEX IF NOT EXISTS ix_fs_prod_per ON fact_sales(produto_id, periodo)",
    "CREATE INDEX IF NOT EXISTS ix_fs_pdv_per  ON fact_sales(pdv_id, periodo)",
)


def gravar_em_blocos(con, sql: str, matriz: np.ndarray, prog,
                     rotulo: str = "Gravando") -> int:
    """executemany em blocos, com commit periodico e progresso.

    Sem isto, 6,8 milhoes de inserts numa transacao unica incham o WAL e o
    usuario fica olhando uma barra parada por minutos.
    """
    total = int(matriz.shape[0])
    escritas = 0
    con.execute("BEGIN")
    for bloco, ini in enumerate(range(0, total, BLOCO)):
        if prog.cancelado():
            con.execute("COMMIT")
            raise InterruptedError("Importacao cancelada pelo usuario.")
        pedaco = matriz[ini:ini + BLOCO]
        con.executemany(sql, pedaco.tolist())
        escritas += len(pedaco)
        if bloco % COMMIT_A_CADA == 0:
            # Reportar sempre FORA da transacao: o SQLite aceita um escritor por
            # vez e o progresso vai por outra conexao.
            con.execute("COMMIT")
            prog.linhas(escritas, total)
            prog.etapa(f"{rotulo}: {escritas:,} de {total:,}".replace(",", "."),
                       0.40 + 0.45 * (escritas / max(total, 1)))
            con.execute("BEGIN")
    con.execute("COMMIT")
    prog.linhas(escritas, total)
    return escritas


def materializar_resumo_mensal(con, import_id: int, prog) -> int:
    """Monta o resumo mensal a partir do grao bruto ja carregado."""
    prog.etapa("Montando o resumo mensal", 0.97)
    prog.log("Montando o resumo mensal para as telas de visao geral...")
    con.execute("DELETE FROM agg_vendas_mensal WHERE import_id = ?", (import_id,))
    con.execute(
        "INSERT INTO agg_vendas_mensal"
        "(import_id, distribuidor_id, produto_id, uf, periodo,"
        " unidades_x100, valor_x100, n_pdvs)"
        " SELECT s.import_id, s.distribuidor_id, s.produto_id, v.uf, s.periodo,"
        "        sum(s.unidades_x100), sum(s.valor_x100), count(DISTINCT s.pdv_id)"
        "   FROM fact_sales s LEFT JOIN dim_pdv v ON v.id = s.pdv_id"
        "  WHERE s.import_id = ?"
        "  GROUP BY s.distribuidor_id, s.produto_id, v.uf, s.periodo", (import_id,))
    n = con.execute("SELECT count(*) FROM agg_vendas_mensal WHERE import_id = ?",
                    (import_id,)).fetchone()[0]
    prog.log(f"Resumo mensal pronto: {n:,} linhas.".replace(",", "."))
    return n


def criar_indices(con, comandos, prog) -> None:
    for i, sql in enumerate(comandos):
        nome = sql.split("ix_")[1].split()[0] if "ix_" in sql else f"indice {i+1}"
        prog.etapa(f"Criando indice {i+1} de {len(comandos)} ({nome})",
                   0.86 + 0.12 * (i / max(len(comandos), 1)))
        prog.log(f"Criando indice {nome}...")
        con.execute(sql)
