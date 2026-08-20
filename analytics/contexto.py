"""O que existe para um cliente — a base do requisito "nunca inventar dado que
nao existe". Toda tela do dashboard consulta isto primeiro.
"""
import sqlite3
from dataclasses import dataclass, field

from .vinculo import distribuidores_do_cliente


@dataclass
class Disponibilidade:
    client_id: int
    cliente_nome: str
    distribuidor_ids: list[int]
    tem_distribuidor_vinculado: bool
    tem_sellout: bool
    tem_iqvia: bool
    tem_estoque: bool
    tem_uf: bool
    tem_pdv: bool
    periodo_min: int | None
    periodo_max: int | None
    n_produtos: int
    n_pdvs: int
    motivo_indisponivel: str | None = field(default=None)


def carregar(con: sqlite3.Connection, client_id: int) -> Disponibilidade:
    cliente = con.execute(
        "SELECT id, nome FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not cliente:
        raise ValueError(f"Cliente {client_id} nao existe.")
    cid, nome = cliente

    dist_ids = distribuidores_do_cliente(con, client_id)
    if not dist_ids:
        return Disponibilidade(
            cid, nome, [], False, False, False, False, False, False,
            None, None, 0, 0,
            motivo_indisponivel=(
                f"Nenhum distribuidor da base corresponde ao nome '{nome}'. "
                f"Importe o sell-out (se ainda nao importou) ou confira se o "
                f"nome do cliente bate com o nome do distribuidor no arquivo."
            ),
        )

    marca = ",".join("?" * len(dist_ids))
    linha = con.execute(
        f"SELECT min(periodo), max(periodo), count(DISTINCT produto_id) "
        f"  FROM v_vendas_mensal WHERE distribuidor_id IN ({marca})",
        dist_ids,
    ).fetchone()
    pmin, pmax, n_produtos = linha
    tem_sellout = pmin is not None

    n_pdvs = con.execute(
        f"SELECT count(DISTINCT pdv_id) FROM v_vendas "
        f" WHERE distribuidor_id IN ({marca})", dist_ids,
    ).fetchone()[0] if tem_sellout else 0

    tem_uf = tem_sellout and con.execute(
        f"SELECT count(*) FROM v_vendas_mensal "
        f" WHERE distribuidor_id IN ({marca}) AND uf IS NOT NULL LIMIT 1",
        dist_ids,
    ).fetchone()[0] > 0

    tem_iqvia = con.execute(
        "SELECT count(*) FROM v_mercado WHERE eh_vitamedic = 1 LIMIT 1"
    ).fetchone()[0] > 0

    tem_estoque = con.execute(
        "SELECT count(*) FROM v_estoque WHERE client_id = ? LIMIT 1",
        (client_id,),
    ).fetchone()[0] > 0

    return Disponibilidade(
        cid, nome, dist_ids, True, tem_sellout, tem_iqvia, tem_estoque,
        tem_uf, tem_sellout and n_pdvs > 0, pmin, pmax,
        n_produtos or 0, n_pdvs,
        motivo_indisponivel=None if tem_sellout else (
            f"'{nome}' foi encontrado na base de distribuidores, mas ainda "
            f"nao ha sell-out importado com dados dele nesta janela."
        ),
    )
