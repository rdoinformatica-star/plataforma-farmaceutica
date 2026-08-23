"""Liga clients a dim_distribuidor — a peca que faltava para "selecionar um
cliente" filtrar alguma coisa.

O sell-out e um arquivo NACIONAL (547 distribuidores). "Cliente" aqui nao e
dono de uma importacao — e o distribuidor que o KAM gerencia dentro dela.
engine/analise.py ja resolve isso manualmente: p.idx_of("provNome", ALVO), que
e "a in v.upper()" (vmd.py:76) — substring, sem distincao de maiusculas.

Esta funcao automatiza exatamente o mesmo criterio (generalizado para tambem
ignorar acento, via core.texto.normalizar), para nao inventar uma heuristica
nova e continuar comparavel ao oraculo. Nunca desfaz um vinculo ja feito
(WHERE client_id IS NULL) — chamar de novo e seguro.
"""
import sqlite3

from backend.app.core.audit import registrar
from backend.app.core.texto import normalizar


def resolver_vinculos(con: sqlite3.Connection, client_id: int | None = None) -> dict:
    """Roda apos toda importacao de sell-out e apos criar/editar um cliente —
    assim o vinculo se auto-corrige nao importa a ordem em que as duas coisas
    aconteceram. Devolve um resumo para log/depuracao.
    """
    sql_clientes = "SELECT id, nome, nome_norm FROM clients WHERE ativo = 1"
    params: tuple = ()
    if client_id is not None:
        sql_clientes += " AND id = ?"
        params = (client_id,)
    clientes = con.execute(sql_clientes, params).fetchall()

    livres = con.execute(
        "SELECT id, nome FROM dim_distribuidor WHERE client_id IS NULL"
    ).fetchall()
    livres_norm = [(row[0], normalizar(row[1])) for row in livres]

    vinculados: dict[str, list[int]] = {}
    ambiguos: list[str] = []
    for cid, nome, nome_norm in clientes:
        if len(nome_norm) < 3:
            # Nome curto demais para casar por substring sem risco de falso
            # positivo (ex.: cliente chamado "SP" casaria com qualquer nome
            # que contivesse "SP"). Fica sem vinculo automatico.
            continue
        achados = [did for did, dnome in livres_norm if nome_norm in dnome]
        if not achados:
            continue
        con.executemany(
            "UPDATE dim_distribuidor SET client_id = ? WHERE id = ?",
            [(cid, did) for did in achados],
        )
        for did, dnome in [(d, n) for d, n in livres_norm if d in achados]:
            registrar(
                con, "DISTRIBUIDOR_VINCULADO_CLIENTE",
                f"Distribuidor vinculado ao cliente '{nome}' (nome corresponde).",
                "dim_distribuidor", did, {"client_id": cid},
            )
        vinculados[nome] = achados
        livres_norm = [(d, n) for d, n in livres_norm if d not in achados]

    return {"vinculados": vinculados, "n_total": sum(len(v) for v in vinculados.values())}


def distribuidores_do_cliente(con: sqlite3.Connection, client_id: int) -> list[int]:
    return [r[0] for r in con.execute(
        "SELECT id FROM dim_distribuidor WHERE client_id = ?", (client_id,))]


def auto_criar_clientes_novos(con: sqlite3.Connection) -> dict:
    """Encontra distribuidores sem client_id e cria clientes novos automaticamente.
    Roda APÓS resolver_vinculos(), so restam distribuidores que nao casaram com
    clientes existentes. Devolve resumo de clientes criados."""

    orfaos = con.execute(
        "SELECT id, nome FROM dim_distribuidor WHERE client_id IS NULL"
    ).fetchall()

    criados: list[str] = []
    for dist_id, dist_nome in orfaos:
        # Cria cliente novo com mesmo nome do distribuidor
        con.execute(
            "INSERT INTO clients(nome, nome_norm, ativo) VALUES (?, ?, 1)",
            (dist_nome, normalizar(dist_nome))
        )
        client_id = con.lastrowid

        # Vincula distribuidor ao cliente novo
        con.execute(
            "UPDATE dim_distribuidor SET client_id = ? WHERE id = ?",
            (client_id, dist_id)
        )

        registrar(
            con, "CLIENTE_CRIADO_AUTOMATICO",
            f"Cliente novo criado automaticamente ao importar distribuidores sem cadastro.",
            "clients", client_id, {"nome": dist_nome, "distribuidor_id": dist_id},
        )
        criados.append(dist_nome)

    return {"criados": criados, "n_total": len(criados)}
