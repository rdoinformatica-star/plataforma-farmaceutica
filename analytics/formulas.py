"""Formulas atomicas de performance comercial.

Uma unica fonte de verdade para cada calculo — nada de reescrever "crescimento"
dentro de cada endpoint. Cada funcao devolve o valor E o "calculo" (formula em
texto, os numeros usados), para alimentar o "Ver como foi calculado" da
interface sem round-trip extra.

Todas trabalham sobre v_vendas_mensal (grao distribuidor x produto x UF x mes,
373 mil linhas no arquivo real) — nunca sobre fact_sales bruto (6,8 milhoes de
linhas), exceto as que precisam de granularidade de PDV (essas ficam em
vendas.py, que usa v_vendas).
"""
import sqlite3
from dataclasses import dataclass, field
from typing import Any

ESCALA_NOTA = (
    "unidades e valor vem de agg_vendas_mensal, materializado a partir do "
    "grao bruto (distribuidor x produto x pdv x mes) na carga do sell-out."
)


@dataclass
class Calculo:
    """O que aparece no drawer 'Ver como foi calculado'."""
    formula: str
    valores: dict[str, Any] = field(default_factory=dict)
    premissas: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {"formula": self.formula, "valores": self.valores,
                "premissas": self.premissas}


def _marca(n: int) -> str:
    return ",".join("?" * n)


def faturamento_unidades(con: sqlite3.Connection, distribuidor_ids: list[int],
                         ini: int, fim: int, *, produto_id: int | None = None,
                         uf: str | None = None) -> tuple[float, float, int, int]:
    """(valor, unidades, n_pdvs, n_produtos) no periodo. n_pdvs aqui vem da
    soma de n_pdvs por linha do agregado — e uma aproximacao por cima (um
    mesmo PDV em dois produtos conta duas vezes); para contagem exata de PDV
    distinto, use vendas.contar_pdvs_distintos (precisa do grao bruto).
    """
    if not distribuidor_ids:
        return 0.0, 0.0, 0, 0
    where = [f"distribuidor_id IN ({_marca(len(distribuidor_ids))})",
             "periodo BETWEEN ? AND ?"]
    params: list = list(distribuidor_ids) + [ini, fim]
    if produto_id is not None:
        where.append("produto_id = ?")
        params.append(produto_id)
    if uf is not None:
        where.append("uf = ?")
        params.append(uf)
    sql = (f"SELECT coalesce(sum(valor),0), coalesce(sum(unidades),0),"
           f"       count(DISTINCT produto_id)"
           f"  FROM v_vendas_mensal WHERE {' AND '.join(where)}")
    valor, unidades, n_produtos = con.execute(sql, params).fetchone()
    return float(valor), float(unidades), 0, int(n_produtos)


def crescimento_pct(atual: float, anterior: float) -> float | None:
    """(atual/anterior - 1) * 100. None quando a base e zero — rotulado
    'novo' pelo chamador, nunca Infinity. Formula identica a engine/analise.py
    (yoy(), linha final: (vb/va-1)*100 if va else None).
    """
    if anterior == 0:
        return None
    return (atual / anterior - 1) * 100


def participacao_pct(parte: float, todo: float) -> float | None:
    """Participacao = parte / todo. None quando o todo e zero (contexto vazio)."""
    if todo == 0:
        return None
    return parte / todo * 100
