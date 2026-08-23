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


def _curva_mercado(con: sqlite3.Connection, limite_a: float, limite_b: float,
                   uf: str | None) -> tuple[dict[str, dict], float]:
    """Curva ABC dos produtos VITAMEDIC no mercado (IQVIA), por apresentacao.

    So linhas eh_vitamedic=1: o universo tem que ser o mesmo do cliente (que
    so distribui Vitamedic). Comparar a curva do cliente com a do mercado
    INTEIRO — incluindo concorrentes que ele nao vende — nao responderia
    "estou em linha", responderia "a Vitamedic e pequena", que e outra coisa.

    Em VALOR, para casar com a curva do cliente, que tambem e por faturamento.
    """
    where, params = ["eh_vitamedic = 1"], []
    if uf is not None:
        where.append("uf = ?")
        params.append(uf)
    linhas = con.execute(
        f"""SELECT apresentacao, sum(valor_ytd_x100)/100.0 v, sum(un_ytd) u
              FROM v_mercado WHERE {' AND '.join(where)}
             GROUP BY apresentacao HAVING v > 0 ORDER BY v DESC""", params).fetchall()
    total = sum(r[1] for r in linhas)

    curva: dict[str, dict] = {}
    ac = 0.0
    for pos, (apres, valor, unidades) in enumerate(linhas, start=1):
        part = valor / total * 100 if total else 0.0
        ac += part
        curva[(apres or "").strip().upper()] = {
            "apresentacao": apres,
            "posicao": pos,
            "valor": valor,
            "unidades": float(unidades or 0),
            "participacao_pct": part,
            "acumulada_pct": ac,
            "classe": "A" if ac <= limite_a else ("B" if ac <= limite_b else "C"),
        }
    return curva, total


# Quanto pior a classe do cliente em relacao a do mercado, maior a distancia.
_ORDEM_CLASSE = {"A": 0, "B": 1, "C": 2}


def abc_vs_mercado(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                   *, limite_a: float = 80.0, limite_b: float = 95.0,
                   uf: str | None = None, top_n: int = 100) -> dict:
    """Compara a curva ABC do cliente com a curva ABC da Vitamedic no mercado.

    A pergunta: "o que e classe A para a Vitamedic no mercado tambem e classe A
    na minha carteira?". Onde o mercado diz A e o cliente entrega C, ha
    oportunidade — o produto vende naquela praca, mas nao por este distribuidor.

    Traz tambem o SHARE do cliente dentro da Vitamedic: quanto das vendas
    Vitamedic daquele produto na regiao passa por este distribuidor.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if uf is not None and not disp.tem_uf:
        return {"disponivel": False,
               "motivo": "Este cliente não tem UF de PDV resolvida nos dados importados."}
    if not con.execute("SELECT 1 FROM v_mercado LIMIT 1").fetchone():
        return {"disponivel": False,
               "motivo": "Nenhum arquivo de mercado (IQVIA) importado. Importe o "
                        "Dashboard de Mercado Relevante para liberar esta comparação."}

    abc = curva_abc(con, client_id, ini, fim, limite_a=limite_a, limite_b=limite_b,
                    uf=uf, com_cobertura=False)
    if not abc["disponivel"]:
        return abc

    curva_mkt, total_mkt = _curva_mercado(con, limite_a, limite_b, uf)
    if not curva_mkt:
        return {"disponivel": False,
               "motivo": (f"Sem dados de mercado Vitamedic para {uf}." if uf else
                          "Sem dados de mercado Vitamedic no arquivo importado.")}

    # A apresentacao do cadastro do cliente e a chave; e o mesmo criterio de
    # mercado.ponte_produtos (texto normalizado), e falha do mesmo jeito —
    # o que nao casa fica visivel, nao sumido.
    apres_por_id = dict(con.execute(
        "SELECT id, apresentacao FROM dim_product WHERE apresentacao IS NOT NULL"))

    itens, sem_match = [], []
    for i in abc["itens"]:
        chave = (apres_por_id.get(i["produto_id"]) or "").strip().upper()
        m = curva_mkt.get(chave)
        if not m:
            sem_match.append({"produto_id": i["produto_id"], "produto": i["produto"],
                              "faturamento": i["faturamento_atual"],
                              "classe_cliente": i["classe_abc"]})
            continue
        distancia = _ORDEM_CLASSE[i["classe_abc"]] - _ORDEM_CLASSE[m["classe"]]
        if distancia > 0:
            situacao = "OPORTUNIDADE"     # mercado valoriza mais do que o cliente
        elif distancia < 0:
            situacao = "ACIMA_DO_MERCADO"  # cliente valoriza mais do que o mercado
        else:
            situacao = "EM_LINHA"
        # Share DENTRO da Vitamedic: quanto da venda Vitamedic daquele produto
        # na regiao passa por este distribuidor. Nao e share de mercado total.
        share = (i["faturamento_atual"] / m["valor"] * 100) if m["valor"] else None
        itens.append({
            "produto_id": i["produto_id"], "produto": i["produto"],
            "faturamento_cliente": i["faturamento_atual"],
            "participacao_cliente_pct": i["participacao_pct"],
            "acumulada_cliente_pct": i["participacao_acumulada_pct"],
            "classe_cliente": i["classe_abc"],
            "valor_mercado": m["valor"],
            "participacao_mercado_pct": m["participacao_pct"],
            "acumulada_mercado_pct": m["acumulada_pct"],
            "classe_mercado": m["classe"],
            "posicao_mercado": m["posicao"],
            "distancia_classes": distancia,
            "situacao": situacao,
            "share_no_vitamedic_pct": share,
            "variacao_pct": i["variacao_pct"],
        })

    # Curva acumulada para o grafico: as duas séries no mesmo eixo de posição,
    # cada uma na SUA ordem (é a forma da curva que se compara, não produto a
    # produto — duas curvas com produtos diferentes nas mesmas posições).
    cliente_ord = sorted(abc["itens"], key=lambda x: -x["faturamento_atual"])
    curva_cliente_pts = [
        {"posicao": n, "acumulada_pct": i["participacao_acumulada_pct"]}
        for n, i in enumerate(cliente_ord, start=1)]
    mkt_ord = sorted(curva_mkt.values(), key=lambda x: x["posicao"])
    curva_mercado_pts = [
        {"posicao": m["posicao"], "acumulada_pct": m["acumulada_pct"]} for m in mkt_ord]

    def _contar(chave: str) -> dict:
        saida: dict[str, int] = {}
        for i in itens:
            saida[i[chave]] = saida.get(i[chave], 0) + 1
        return saida

    oportunidades = sorted(
        [i for i in itens if i["situacao"] == "OPORTUNIDADE"],
        key=lambda x: (-x["distancia_classes"], -x["valor_mercado"]))

    fat_ligado = sum(i["faturamento_cliente"] for i in itens)
    fat_sem = sum(i["faturamento"] for i in sem_match)
    total_cli = fat_ligado + fat_sem
    share_geral = (fat_ligado / total_mkt * 100) if total_mkt else None

    return {
        "disponivel": True,
        "uf": uf, "limite_a": limite_a, "limite_b": limite_b,
        "n_ligados": len(itens),
        "n_sem_correspondencia": len(sem_match),
        "cobertura_da_ponte_pct": (fat_ligado / total_cli * 100) if total_cli else None,
        "faturamento_cliente_ligado": fat_ligado,
        "valor_mercado_total": total_mkt,
        "share_no_vitamedic_pct": share_geral,
        "por_situacao": _contar("situacao"),
        "n_produtos_mercado": len(curva_mkt),
        "curva_cliente": curva_cliente_pts,
        "curva_mercado": curva_mercado_pts,
        "oportunidades": oportunidades[:top_n],
        "itens": sorted(itens, key=lambda x: -x["faturamento_cliente"])[:top_n],
        "sem_correspondencia": sorted(sem_match, key=lambda x: -x["faturamento"])[:top_n],
        "calculo": f.Calculo(
            formula=("duas curvas ABC pelo mesmo critério (valor acumulado, "
                     f"A até {limite_a}%, B até {limite_b}%): a do cliente sobre o "
                     "sell-out dele, a do mercado sobre as vendas Vitamedic do "
                     "IQVIA na mesma região. Ligação por apresentação. "
                     "share no Vitamedic = faturamento do cliente / valor Vitamedic "
                     "do produto na região."),
            valores={
                "produtos ligados": len(itens),
                "produtos sem correspondência": len(sem_match),
                "produtos Vitamedic no mercado": len(curva_mkt),
                "share do cliente no Vitamedic": (f"{share_geral:.2f}%"
                                                  if share_geral is not None else "n/d"),
                "oportunidades (mercado valoriza mais)": len(oportunidades),
                "recorte": uf or "país",
            },
            premissas=[
                _ELO_SELLOUT,
                "A curva do mercado usa SÓ produtos Vitamedic (eh_vitamedic=1), "
                "para o universo ser o mesmo do cliente. Não é a curva do mercado "
                "farmacêutico inteiro.",
                "As duas pontas medem coisas diferentes: o cliente é sell-out "
                "(distribuidor → PDV) e o IQVIA é PDV → consumidor. A comparação é "
                "de IMPORTÂNCIA RELATIVA de cada produto, não de volume absoluto.",
                "O share aqui é dentro da Vitamedic — quanto da venda Vitamedic "
                "daquele produto passa por este distribuidor. Não é participação "
                "no mercado farmacêutico.",
                "'Oportunidade' significa que o produto pesa mais na curva do "
                "mercado do que na do cliente. É um sinal para investigar, não uma "
                "meta: pode haver exclusividade, logística ou acordo comercial que "
                "o dado não mostra.",
                "A ligação por apresentação é parcial (os nomes divergem entre as "
                "fontes). O que não casa fica em 'sem_correspondencia'.",
                "O período do IQVIA é o do arquivo importado (YTD da foto), não o "
                "período selecionado na tela — os dois não são recortáveis do mesmo "
                "jeito. Compare formato de curva, não valores mês a mês.",
            ] + ([f"Recorte: só {uf}, nos dois lados da comparação."] if uf else []),
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
