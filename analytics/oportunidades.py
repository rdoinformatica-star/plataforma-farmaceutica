"""Matriz de oportunidades — junta ABC, cobertura e mix num score unico.

Esta etapa so estabelece a estrutura (Oportunidade/Potencial/Impacto/
Facilidade/Prioridade/Premissa/Fonte) e um score determinístico simples —
a inteligencia estrategica completa (priorizacao entre alavancas que se
sobrepoem, plano de acao) fica para uma etapa futura, como o proprio prompt
pede.

Toda oportunidade nasce rotulada FATO: o texto descreve o que os dados
mostram (classe, variacao, cobertura), nunca uma causa ("caiu por problema
comercial" seria HIPOTESE, e o sistema nao afirma isso).
"""
import sqlite3

from . import abc, cobertura, mix
from . import formulas as f
from .contexto import carregar
from .vendas import alertas as alertas_vendas

# Facilidade por tipo de oportunidade — tabela fixa e documentada (nao e
# pedido configuravel pelo prompt, so os PESOS do score sao). 0-100, quanto
# maior mais facil de executar.
_FACILIDADE_POR_TIPO = {
    "COBERTURA": 70,       # execucao direta de distribuicao em PDV ja carteira
    "MIX": 55,             # depende de relacionamento comercial no PDV
    "ABC_QUEDA": 35,        # exige investigar causa antes de agir
    "CONCENTRACAO": 30,     # mudanca estrutural de portfolio/carteira
}


def _normalizar(valores: list[float]) -> list[float]:
    """Min-max para 0-100 dentro do proprio conjunto. Uma unica oportunidade
    ou todas iguais -> 100 (nao ha o que comparar)."""
    if not valores:
        return []
    lo, hi = min(valores), max(valores)
    if hi == lo:
        return [100.0 for _ in valores]
    return [(v - lo) / (hi - lo) * 100 for v in valores]


# Cada tipo de oportunidade age sobre um produto ou sobre um PDV. Sao acoes
# diferentes, para times diferentes — por isso a tela separa as duas listas.
_ESCOPO_POR_TIPO = {
    "ABC_QUEDA": "PRODUTO",
    "COBERTURA": "PRODUTO",
    "CONCENTRACAO": "PRODUTO",
    "MIX": "PDV",
}


def matriz_oportunidades(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                         *, peso_potencial: float = 40.0, peso_impacto: float = 35.0,
                         peso_facilidade: float = 25.0, incremento_pp: float = 10.0,
                         uf: str | None = None, escopo: str | None = None,
                         top_n: int = 30) -> dict:
    """escopo: None traz tudo, 'PRODUTO' ou 'PDV' filtra.

    O filtro é aplicado ANTES de normalizar potencial e impacto — senão o
    score de uma oportunidade de PDV dependeria de quais produtos entraram na
    mesma consulta, e mudar o filtro reordenaria a lista sem nada ter mudado
    no negócio.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if uf is not None and not disp.tem_uf:
        return {"disponivel": False,
               "motivo": "Este cliente não tem UF de PDV resolvida nos dados importados."}
    if escopo is not None and escopo not in ("PRODUTO", "PDV"):
        return {"disponivel": False,
               "motivo": "escopo deve ser 'PRODUTO', 'PDV' ou vazio."}

    soma_pesos = peso_potencial + peso_impacto + peso_facilidade
    if soma_pesos <= 0:
        return {"disponivel": False, "motivo": "Pesos inválidos (soma tem que ser > 0)."}
    p_pot, p_imp, p_fac = (peso_potencial / soma_pesos, peso_impacto / soma_pesos,
                           peso_facilidade / soma_pesos)

    total_periodo, _, _, _ = f.faturamento_unidades(con, disp.distribuidor_ids, ini, fim)

    candidatas: list[dict] = []

    # 1) ABC classe A em queda — FATO, sem causa atribuida.
    curva = abc.curva_abc(con, client_id, ini, fim, uf=uf, com_cobertura=False)
    if curva["disponivel"]:
        for i in curva["itens"]:
            if i["classe_abc"] == "A" and i["variacao_pct"] is not None and i["variacao_pct"] < 0:
                candidatas.append({
                    "tipo": "ABC_QUEDA",
                    "oportunidade": f"{i['produto']} é classe A e caiu "
                                    f"{abs(i['variacao_pct']):.1f}% no período.",
                    "fonte": "Curva ABC × crescimento",
                    "potencial_bruto": abs(i["faturamento_atual"] * i["variacao_pct"] / 100),
                    "impacto_bruto": i["participacao_pct"] or 0,
                    "premissa": "FATO: classe e variação vêm direto dos dados. Não "
                               "afirma a causa da queda.",
                    "referencia_id": i["produto_id"],
                })

    # 2) Cobertura baixa + faturamento alto (quadrante PRIORITARIO).
    # Um cobertura_produtos() so, reusado nas duas chamadas abaixo — cada uma
    # sozinha pagaria de novo a contagem de PDV por produto (grao bruto).
    _cob_base = cobertura.cobertura_produtos(con, client_id, ini, fim, uf=uf, limite=100000)
    matriz_cob = cobertura.matriz_cobertura_faturamento(con, client_id, ini, fim,
                                                        uf=uf, _cob=_cob_base)
    if matriz_cob["disponivel"]:
        potencial = cobertura.potencial_cobertura(con, client_id, ini, fim,
                                                  incremento_pp=incremento_pp,
                                                  uf=uf, _cob=_cob_base)
        ganhos = {g["produto_id"]: g["potencial_estimado"]
                 for g in potencial.get("itens", [])} if potencial["disponivel"] else {}
        for i in matriz_cob["itens"]:
            if i["quadrante"] == "PRIORITARIO":
                candidatas.append({
                    "tipo": "COBERTURA",
                    "oportunidade": f"{i['produto']} tem faturamento acima da mediana "
                                    f"mas cobertura de só {i['cobertura_pct']:.1f}% "
                                    f"da carteira.",
                    "fonte": "Matriz cobertura × faturamento",
                    "potencial_bruto": ganhos.get(i["produto_id"], i["faturamento_atual"] * incremento_pp / 100),
                    "impacto_bruto": i["participacao_pct"] or 0,
                    "premissa": "POTENCIAL ESTIMADO — não é venda garantida. Premissa: "
                               "PDV novo compra como a média atual do produto.",
                    "referencia_id": i["produto_id"],
                })

    # 3) Expansao de mix.
    expansao = mix.oportunidades_expansao(con, client_id, ini, fim, uf=uf)
    if expansao["disponivel"]:
        for i in expansao["itens"][:20]:
            gap = i["rs_por_pdv_faixa_referencia"] - i["faturamento_atual"]
            candidatas.append({
                "tipo": "MIX",
                "oportunidade": f"{i['pdv']} já fatura como um PDV de "
                                f"'{i['faixa_referencia']}', mas só compra "
                                f"'{i['faixa_atual']}'.",
                "fonte": "Oportunidades de expansão de mix",
                "potencial_bruto": max(gap, 0),
                "impacto_bruto": (i["faturamento_atual"] / total_periodo * 100
                                  if total_periodo else 0),
                "premissa": "Leitura de similaridade com PDVs de mix maior — não "
                           "afirma que o PDV vai comprar mais SKUs.",
                "referencia_id": i["pdv_id"],
            })

    # 4) Concentracao excessiva (top 5 produtos > 50% do faturamento).
    if curva["disponivel"] and curva["itens"]:
        top5_pct = sum(i["participacao_pct"] or 0 for i in
                       sorted(curva["itens"], key=lambda x: -x["faturamento_atual"])[:5])
        if top5_pct > 50:
            candidatas.append({
                "tipo": "CONCENTRACAO",
                "oportunidade": f"Os 5 maiores produtos concentram "
                                f"{top5_pct:.1f}% do faturamento do período.",
                "fonte": "Concentração de produtos",
                "potencial_bruto": total_periodo * 0.05,
                "impacto_bruto": top5_pct,
                "premissa": "FATO de concentração. Não afirma que a carteira "
                           "precisa diversificar — é um dado para avaliar risco.",
                "referencia_id": None,
            })

    # Contagem por escopo antes do filtro, para a tela poder dizer quantas
    # existem do outro lado sem uma segunda consulta.
    por_escopo = {"PRODUTO": 0, "PDV": 0}
    for c in candidatas:
        por_escopo[_ESCOPO_POR_TIPO.get(c["tipo"], "PRODUTO")] += 1
    if escopo is not None:
        candidatas = [c for c in candidatas
                      if _ESCOPO_POR_TIPO.get(c["tipo"], "PRODUTO") == escopo]

    if not candidatas:
        return {"disponivel": True, "itens": [], "total": 0,
               "uf": uf, "escopo": escopo, "por_escopo": por_escopo,
               "calculo": f.Calculo(
                   formula="Nenhuma oportunidade passou nos critérios desta consulta.",
               ).como_dict()}

    potenciais_norm = _normalizar([c["potencial_bruto"] for c in candidatas])
    impactos_norm = _normalizar([c["impacto_bruto"] for c in candidatas])

    itens = []
    for c, pot_n, imp_n in zip(candidatas, potenciais_norm, impactos_norm):
        facilidade = _FACILIDADE_POR_TIPO.get(c["tipo"], 50)
        score = p_pot * pot_n + p_imp * imp_n + p_fac * facilidade
        prioridade = "Alta" if score >= 70 else ("Média" if score >= 40 else "Baixa")
        itens.append({
            "tipo": c["tipo"], "oportunidade": c["oportunidade"], "fonte": c["fonte"],
            "escopo": _ESCOPO_POR_TIPO.get(c["tipo"], "PRODUTO"),
            "potencial_estimado": round(c["potencial_bruto"], 2),
            "impacto_pct": round(c["impacto_bruto"], 2),
            "facilidade": facilidade, "score": round(score, 1),
            "prioridade": prioridade, "premissa": c["premissa"],
            "rotulo": "FATO", "referencia_id": c["referencia_id"],
        })
    itens.sort(key=lambda i: -i["score"])
    itens = itens[:top_n]

    return {
        "disponivel": True, "total": len(itens), "itens": itens,
        "uf": uf, "escopo": escopo, "por_escopo": por_escopo,
        "pesos": {"potencial": round(p_pot * 100, 1), "impacto": round(p_imp * 100, 1),
                 "facilidade": round(p_fac * 100, 1)},
        "calculo": f.Calculo(
            formula="score = peso_potencial×potencial_norm + peso_impacto×impacto_norm "
                   "+ peso_facilidade×facilidade. potencial/impacto normalizados 0-100 "
                   "dentro das oportunidades encontradas nesta consulta; facilidade vem "
                   "de uma tabela fixa por tipo de oportunidade.",
            valores={"pesos_pedidos": {"potencial": peso_potencial, "impacto": peso_impacto,
                                       "facilidade": peso_facilidade},
                    "facilidade_por_tipo": _FACILIDADE_POR_TIPO},
            premissas=[
                "Cada oportunidade nasce como FATO (o que os dados mostram), nunca "
                "com causa atribuída — a causa seria HIPÓTESE.",
                "Potenciais de tipos diferentes NÃO devem ser somados sem descontar "
                "sobreposição (um PDV pode aparecer em cobertura e em mix ao mesmo "
                "tempo). Esta etapa ainda não resolve a sobreposição entre alavancas.",
                "Esta é a estrutura inicial da matriz de oportunidades — a "
                "priorização estratégica completa é de uma etapa futura.",
                "Potencial e impacto são normalizados DENTRO do escopo filtrado: "
                "os scores de produto e de PDV não são comparáveis entre si, "
                "porque cada lista tem sua própria escala.",
            ],
        ).como_dict(),
    }


def alertas_expandidos(con: sqlite3.Connection, client_id: int, ini: int, fim: int) -> dict:
    """vendas.alertas() (Etapa 2, intocado) + os tipos novos desta etapa."""
    base = alertas_vendas(con, client_id, ini, fim)
    if not base["disponivel"]:
        return base

    itens = list(base["itens"])

    matriz_cob = cobertura.matriz_cobertura_faturamento(con, client_id, ini, fim)
    if matriz_cob["disponivel"]:
        prioritarios = [i for i in matriz_cob["itens"] if i["quadrante"] == "PRIORITARIO"]
        for i in sorted(prioritarios, key=lambda x: -x["faturamento_atual"])[:3]:
            itens.append({
                "tipo": "amarelo", "categoria": "COBERTURA",
                "texto": f"{i['produto']}: alto faturamento, cobertura de só "
                        f"{i['cobertura_pct']:.1f}%",
                "produto_id": i["produto_id"], "valor_pct": i["cobertura_pct"],
            })

    expansao = mix.oportunidades_expansao(con, client_id, ini, fim, limite=3)
    if expansao["disponivel"]:
        for i in expansao["itens"]:
            itens.append({
                "tipo": "azul", "categoria": "MIX",
                "texto": f"{i['pdv']}: potencial de expansão de mix "
                        f"({i['faixa_atual']} → {i['faixa_referencia']})",
                "produto_id": None, "valor_pct": None,
            })

    curva = abc.curva_abc(con, client_id, ini, fim, uf=uf, com_cobertura=False)
    if curva["disponivel"] and curva["itens"]:
        top5_pct = sum(i["participacao_pct"] or 0 for i in
                       sorted(curva["itens"], key=lambda x: -x["faturamento_atual"])[:5])
        if top5_pct > 50:
            itens.append({
                "tipo": "roxo", "categoria": "CONCENTRACAO",
                "texto": f"Concentração excessiva: os 5 maiores produtos somam "
                        f"{top5_pct:.1f}% do faturamento",
                "produto_id": None, "valor_pct": top5_pct,
            })

    return {"disponivel": True, "itens": itens, "n_total": len(itens),
           "calculo": f.Calculo(
               formula="Alertas da Etapa 2 (produto/crescimento/queda) + alertas "
                      "novos desta etapa (cobertura baixa, expansão de mix, "
                      "concentração excessiva).",
           ).como_dict()}
