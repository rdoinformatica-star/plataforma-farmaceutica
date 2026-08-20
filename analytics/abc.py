"""Curva ABC.

Classificacao por valor acumulado, identica a engine/analise.py §5: produtos
ordenados por faturamento decrescente, classe A ate `limite_a`% acumulado,
B ate `limite_b`%, C dai em diante. O motor original usa 80/95 fixos no
codigo — aqui viram parametro, com o mesmo padrao.

Reusa vendas.ranking_produtos() (que ja calcula faturamento, participacao,
variacao e o guarda-corpo de "comparacao_valida" da Etapa 2) e so empilha a
banda ABC por cima — nao recalcula nada que ja exista.
"""
import sqlite3

from . import cobertura
from . import formulas as f
from . import periodo as pe
from . import vendas
from .contexto import carregar

_ELO_SELLOUT = "Sell-out: venda do distribuidor para o PDV."


def curva_abc(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
             *, limite_a: float = 80.0, limite_b: float = 95.0,
             uf: str | None = None, com_cobertura: bool = True) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if limite_a <= 0 or limite_b <= limite_a or limite_b > 100:
        return {"disponivel": False,
               "motivo": f"Limites inválidos: A={limite_a}, B={limite_b} "
                        f"(precisa ser 0 < limite_a < limite_b <= 100)."}

    ranking = vendas.ranking_produtos(con, client_id, ini, fim, ordenar="faturamento",
                                      limite=100000, uf=uf)
    if not ranking["disponivel"]:
        return ranking

    itens = [i for i in ranking["itens"] if i["faturamento_atual"] > 0]
    total = sum(i["faturamento_atual"] for i in itens)

    compradores = {}
    if com_cobertura and itens:
        dist_ids = disp.distribuidor_ids
        compradores = cobertura.pdvs_por_produto(con, dist_ids, ini, fim, uf=uf)
        base_pdvs = vendas.contar_pdvs_distintos(con, dist_ids, ini, fim, uf=uf)
    else:
        base_pdvs = 0

    ac = 0.0
    n_a = n_b = n_c = 0
    fat_a = fat_b = fat_c = 0.0
    for i in itens:
        participacao = i["faturamento_atual"] / total * 100 if total else 0.0
        ac += participacao
        if ac <= limite_a:
            classe = "A"
        elif ac <= limite_b:
            classe = "B"
        else:
            classe = "C"
        i["classe_abc"] = classe
        i["participacao_acumulada_pct"] = round(ac, 4)
        if com_cobertura:
            n_comp = compradores.get(i["produto_id"], 0)
            i["pdvs_compradores"] = n_comp
            i["cobertura_pct"] = round(n_comp / base_pdvs * 100, 2) if base_pdvs else None
        if classe == "A":
            n_a += 1; fat_a += i["faturamento_atual"]
        elif classe == "B":
            n_b += 1; fat_b += i["faturamento_atual"]
        else:
            n_c += 1; fat_c += i["faturamento_atual"]

    n_total = len(itens)
    resumo = {
        "A": {"n_produtos": n_a, "pct_produtos": round(n_a / n_total * 100, 1) if n_total else 0,
             "faturamento": round(fat_a, 2), "pct_faturamento": round(fat_a / total * 100, 1) if total else 0},
        "B": {"n_produtos": n_b, "pct_produtos": round(n_b / n_total * 100, 1) if n_total else 0,
             "faturamento": round(fat_b, 2), "pct_faturamento": round(fat_b / total * 100, 1) if total else 0},
        "C": {"n_produtos": n_c, "pct_produtos": round(n_c / n_total * 100, 1) if n_total else 0,
             "faturamento": round(fat_c, 2), "pct_faturamento": round(fat_c / total * 100, 1) if total else 0},
    }

    premissas = [_ELO_SELLOUT,
                "Classificação feita sobre o faturamento do próprio cliente no "
                "período — não é participação de mercado nem ranking nacional."]
    if uf is not None:
        premissas.append(f"Recorte: só PDVs do estado {uf}.")

    return {
        "disponivel": True, "n_total_produtos": n_total,
        "faturamento_total": round(total, 2),
        "limite_a": limite_a, "limite_b": limite_b, "uf": uf,
        "resumo": resumo, "itens": itens,
        "calculo": f.Calculo(
            formula=f"Produtos ordenados por faturamento decrescente; classe A até "
                   f"{limite_a}% do valor acumulado, B até {limite_b}%, C depois.",
            valores={"limite_a": limite_a, "limite_b": limite_b,
                    "faturamento_total": round(total, 2), "n_produtos": n_total},
            premissas=premissas,
        ).como_dict(),
    }


def abc_crescimento(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                    *, limite_a: float = 80.0, limite_b: float = 95.0,
                    limite_crescimento_pct: float = 10.0,
                    limite_queda_pct: float = -10.0, uf: str | None = None) -> dict:
    """Cruza a classe ABC com a variacao (ja calculada e guardada pela Etapa 2)
    em 3 faixas: crescendo / estavel / caindo.
    """
    abc = curva_abc(con, client_id, ini, fim, limite_a=limite_a, limite_b=limite_b,
                    uf=uf, com_cobertura=False)
    if not abc["disponivel"]:
        return abc

    # ranking_produtos ja marca comparacao_valida=False globalmente quando o
    # historico nao cobre — aqui so refletimos o mesmo estado, sem recalcular.
    ranking_bruto = vendas.ranking_produtos(con, client_id, ini, fim, limite=1, uf=uf)
    comparacao_valida = ranking_bruto.get("comparacao_valida", True)

    def faixa(pct):
        if pct is None:
            return "SEM_HISTORICO" if not comparacao_valida else "NOVO"
        if pct >= limite_crescimento_pct:
            return "CRESCENDO"
        if pct <= limite_queda_pct:
            return "CAINDO"
        return "ESTAVEL"

    matriz = {c: {"CRESCENDO": [], "ESTAVEL": [], "CAINDO": [], "NOVO": [], "SEM_HISTORICO": []}
             for c in ("A", "B", "C")}
    for i in abc["itens"]:
        f_ = faixa(i["variacao_pct"])
        matriz[i["classe_abc"]][f_].append({
            "produto_id": i["produto_id"], "produto": i["produto"],
            "faturamento_atual": i["faturamento_atual"], "variacao_pct": i["variacao_pct"],
        })

    contagem = {c: {f_: len(v) for f_, v in faixas.items()} for c, faixas in matriz.items()}

    return {
        "disponivel": True, "comparacao_valida": comparacao_valida,
        "contagem": contagem, "matriz": matriz,
        "calculo": f.Calculo(
            formula="Cada produto entra na classe ABC (por faturamento) e na faixa "
                   "de variação (por crescimento vs. período anterior).",
            valores={"limite_crescimento_pct": limite_crescimento_pct,
                    "limite_queda_pct": limite_queda_pct},
            premissas=([f"Recorte: só PDVs do estado {uf}."] if uf else []) + [
                "FATO: a classe e a variação vêm direto dos dados. Não afirma causa "
                "— um produto A em queda é um fato, não diz por que caiu.",
            ] + (["Sem período de comparação válido: todo produto aparece como "
                  "SEM_HISTORICO, não porque não tenha variação real."]
                 if not comparacao_valida else []),
        ).como_dict(),
    }
