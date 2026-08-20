"""Cobertura comercial.

Cobertura = PDVs que compraram o produto / PDVs que compraram QUALQUER coisa
do cliente no periodo. Formula identica a engine/analise.py §7 (variavel
`cob`/`npdvB`) e a engine/a04_cobertura_mix.py §6 — o universo NAO e a base
nacional nem a UF (a menos que explicitamente filtrado): e a carteira ativa
do proprio cliente no periodo.

pdvs_por_produto() usa o grao bruto (v_vendas), nunca agg_vendas_mensal: somar
o n_pdvs por linha do agregado entre varios meses super-contaria um PDV que
comprou em mais de um mes (mesma ressalva ja documentada em vendas.py).
"""
import sqlite3
import statistics

from . import formulas as f
from . import periodo as pe
from . import vendas
from .contexto import carregar

_ELO_SELLOUT = "Sell-out: venda do distribuidor para o PDV."


def _marca(n: int) -> str:
    return ",".join("?" * n)


def pdvs_por_produto(con: sqlite3.Connection, distribuidor_ids: list[int],
                     ini: int, fim: int, *, uf: str | None = None) -> dict[int, int]:
    """{produto_id: PDVs distintos que compraram esse produto no periodo}."""
    if not distribuidor_ids:
        return {}
    marca = _marca(len(distribuidor_ids))
    if uf is None:
        sql = (f"SELECT produto_id, count(DISTINCT pdv_id) FROM v_vendas"
               f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?"
               f" GROUP BY produto_id")
        params = list(distribuidor_ids) + [ini, fim]
    else:
        sql = (f"SELECT s.produto_id, count(DISTINCT s.pdv_id) FROM v_vendas s"
               f" JOIN dim_pdv d ON d.id = s.pdv_id"
               f" WHERE s.distribuidor_id IN ({marca}) AND s.periodo BETWEEN ? AND ?"
               f"   AND d.uf = ?"
               f" GROUP BY s.produto_id")
        params = list(distribuidor_ids) + [ini, fim, uf]
    return dict(con.execute(sql, params).fetchall())


def cobertura_produtos(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                       *, uf: str | None = None, limite: int = 100,
                       offset: int = 0) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if uf is not None and not disp.tem_uf:
        return {"disponivel": False,
               "motivo": "Este cliente não tem UF de PDV resolvida nos dados importados."}

    dist_ids = disp.distribuidor_ids
    base_pdvs = vendas.contar_pdvs_distintos(con, dist_ids, ini, fim, uf=uf)
    if base_pdvs == 0:
        return {"disponivel": False,
               "motivo": "Nenhum PDV comprador neste período — não há base para calcular cobertura."}

    ranking = vendas.ranking_produtos(con, client_id, ini, fim, ordenar="faturamento",
                                      limite=100000, uf=uf)
    compradores = pdvs_por_produto(con, dist_ids, ini, fim, uf=uf)

    itens = []
    for r in ranking["itens"]:
        n_compradores = compradores.get(r["produto_id"], 0)
        itens.append({
            **r,
            "pdvs_compradores": n_compradores,
            "pdvs_base": base_pdvs,
            "cobertura_pct": round(n_compradores / base_pdvs * 100, 4),
        })
    itens.sort(key=lambda r: r["faturamento_atual"], reverse=True)

    premissas = [
        _ELO_SELLOUT,
        "PDVs_base = todos os PDVs que compraram QUALQUER produto do cliente no "
        "período — não é a base nacional nem todos os PDVs do estado.",
    ]
    if uf is not None:
        premissas.append(f"Recorte: só PDVs do estado {uf}.")

    return {
        "disponivel": True, "pdvs_base": base_pdvs, "uf": uf,
        "total": len(itens), "itens": itens[offset:offset + limite],
        "calculo": f.Calculo(
            formula="Cobertura = PDVs compradores do produto / PDVs base do cliente "
                   "no período.",
            valores={"pdvs_base": base_pdvs, "periodo": pe.Janela(ini, fim).rotulo},
            premissas=premissas,
        ).como_dict(),
    }


def matriz_cobertura_faturamento(con: sqlite3.Connection, client_id: int,
                                 ini: int, fim: int, *, uf: str | None = None,
                                 _cob: dict | None = None) -> dict:
    """4 quadrantes por mediana de faturamento e de cobertura do proprio recorte.

    _cob: resultado de cobertura_produtos() ja calculado, para quem compoe
    varias analises na mesma consulta (oportunidades.py) nao pagar a mesma
    contagem de PDV por produto mais de uma vez. Uso interno — nao expor na rota.
    """
    cob = _cob if _cob is not None else cobertura_produtos(con, client_id, ini, fim,
                                                            uf=uf, limite=100000)
    if not cob["disponivel"]:
        return cob
    itens = [i for i in cob["itens"] if i["faturamento_atual"] > 0]
    if len(itens) < 4:
        return {"disponivel": False,
               "motivo": "Poucos produtos com venda neste período para montar a "
                        "matriz (mínimo 4)."}

    med_fat = statistics.median(i["faturamento_atual"] for i in itens)
    med_cob = statistics.median(i["cobertura_pct"] for i in itens)

    def quadrante(i):
        alto_fat = i["faturamento_atual"] >= med_fat
        alta_cob = i["cobertura_pct"] >= med_cob
        if alto_fat and not alta_cob:
            return "PRIORITARIO"
        if alto_fat and alta_cob:
            return "CONSOLIDADO"
        if not alto_fat and alta_cob:
            return "INVESTIGAR_PRODUTIVIDADE"
        return "BAIXA_PRIORIDADE"

    for i in itens:
        i["quadrante"] = quadrante(i)

    contagem = {q: sum(1 for i in itens if i["quadrante"] == q) for q in
               ("PRIORITARIO", "CONSOLIDADO", "INVESTIGAR_PRODUTIVIDADE", "BAIXA_PRIORIDADE")}

    return {
        "disponivel": True, "itens": itens, "resumo": contagem,
        "mediana_faturamento": med_fat, "mediana_cobertura_pct": med_cob,
        "calculo": f.Calculo(
            formula="Quadrante por mediana de faturamento e de cobertura entre os "
                   "produtos com venda no período selecionado (não é um limite fixo "
                   "do sistema — recalcula a cada consulta).",
            valores={"mediana_faturamento": round(med_fat, 2),
                    "mediana_cobertura_pct": round(med_cob, 2), "n_produtos": len(itens)},
            premissas=["PRIORITARIO = faturamento acima da mediana e cobertura "
                      "abaixo — produto relevante que ainda não chegou na maior "
                      "parte da carteira.",
                      "CONSOLIDADO = acima da mediana nos dois — já maduro.",
                      "INVESTIGAR_PRODUTIVIDADE = cobertura alta mas faturamento "
                      "baixo — vende para muitos PDVs, mas pouco por PDV.",
                      "BAIXA_PRIORIDADE = abaixo da mediana nos dois."],
        ).como_dict(),
    }


def potencial_cobertura(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                        *, incremento_pp: float = 10.0, top_n: int = 20,
                        minimo_pdvs_compradores: int = 5,
                        uf: str | None = None, _cob: dict | None = None) -> dict:
    """Reproduz a formula do oraculo (engine/analise.py §7 e a04 §6):
    rpp = valor_do_SKU / PDVs_que_ja_compram; ganho = rpp * (PDVs_base * incremento_pp/100).

    minimo_pdvs_compradores e uma defesa que a Etapa 2 me ensinou a ter: com
    poucos compradores o R$/PDV medio e ruido estatistico, nao uma media
    confiavel — produtos abaixo do piso aparecem separados, sem numero.

    _cob: mesma ideia do parametro homonimo em matriz_cobertura_faturamento —
    reusa um cobertura_produtos() ja calculado. Uso interno.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}

    cob = _cob if _cob is not None else cobertura_produtos(con, client_id, ini, fim,
                                                            uf=uf, limite=100000)
    if not cob["disponivel"]:
        return cob

    candidatos = sorted(
        [i for i in cob["itens"] if i["faturamento_atual"] > 0],
        key=lambda i: -i["faturamento_atual"])[:top_n]

    n_meses = pe.contar_meses(ini, fim)
    base_pdvs = cob["pdvs_base"]
    pdvs_incremento = base_pdvs * incremento_pp / 100

    estimados, sem_dado = [], []
    total = 0.0
    for i in candidatos:
        if i["pdvs_compradores"] < minimo_pdvs_compradores:
            sem_dado.append({"produto_id": i["produto_id"], "produto": i["produto"],
                             "pdvs_compradores": i["pdvs_compradores"]})
            continue
        rpp = i["faturamento_atual"] / i["pdvs_compradores"]
        ganho = rpp * pdvs_incremento
        total += ganho
        estimados.append({
            "produto_id": i["produto_id"], "produto": i["produto"],
            "faturamento_atual": i["faturamento_atual"],
            "pdvs_compradores": i["pdvs_compradores"],
            "cobertura_pct": i["cobertura_pct"],
            "rs_por_pdv": round(rpp, 2),
            "potencial_estimado": round(ganho, 2),
        })

    return {
        "disponivel": True,
        "incremento_pp": incremento_pp, "top_n": top_n, "pdvs_base": base_pdvs,
        "pdvs_incremento": round(pdvs_incremento, 1),
        "potencial_estimado_total": round(total, 2),
        "potencial_estimado_anual": round(total / n_meses * 12, 2),
        "itens": estimados, "sem_dado_suficiente": sem_dado,
        "calculo": f.Calculo(
            formula="POTENCIAL ESTIMADO (não é venda garantida) = R$/PDV do produto "
                   "× (PDVs da base × incremento em pontos percentuais / 100). "
                   "R$/PDV = faturamento do produto / PDVs que já compram.",
            valores={"pdvs_base": base_pdvs,
                    "pdvs_incremento": round(pdvs_incremento, 1),
                    "periodo": pe.Janela(ini, fim).rotulo,
                    "meses_no_periodo": n_meses},
            premissas=[
                "Premissa central: o PDV incremental compra como a média atual do "
                "produto — otimista para PDVs pequenos, conservadora para os grandes.",
                f"Produtos com menos de {minimo_pdvs_compradores} PDVs compradores "
                f"ficam de fora da conta (R$/PDV pouco confiável com amostra tão "
                f"pequena) — aparecem em 'sem_dado_suficiente'.",
                "Os potenciais dos produtos NÃO devem ser somados a outros "
                "potenciais (ex.: potencial de mix) sem descontar sobreposição — "
                "PDVs recuperados podem aparecer em mais de uma conta.",
                "Projeção linear simples (total do período ÷ meses × 12), sem "
                "ajuste de sazonalidade.",
            ],
        ).como_dict(),
    }
