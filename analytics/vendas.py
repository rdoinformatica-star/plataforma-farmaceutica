"""Composicoes de negocio sobre as formulas atomicas — resumo executivo,
ranking, evolucao, UF, PDV, concentracao, alertas.

Grao usado por funcao:
  - resumo, evolucao, ranking/variacao de produto, UF, concentracao de produto
    -> v_vendas_mensal (agregado, rapido: 373 mil linhas no arquivo real).
  - contagem exata de PDV, ranking/novos/sumidos de PDV, concentracao de PDV
    -> v_vendas (grao bruto), sempre filtrado por distribuidor_id + periodo,
    que sao o prefixo dos indices criados na Etapa 1 (ix_fs_dist_per).
"""
import sqlite3

from . import formulas as f
from . import periodo as pe
from .contexto import Disponibilidade, carregar

_ELO_SELLOUT = "Sell-out: venda do distribuidor para o PDV."


def _marca(n: int) -> str:
    return ",".join("?" * n)


def _brl(v: float) -> str:
    """Separador de milhar brasileiro (ponto), nao o americano de {:,.0f}."""
    return f"{v:,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _nome_produto(con: sqlite3.Connection, produto_id: int) -> str:
    r = con.execute("SELECT nome_canonico FROM dim_product WHERE id=?",
                    (produto_id,)).fetchone()
    return r[0] if r else f"produto #{produto_id}"


def contar_pdvs_distintos(con: sqlite3.Connection, distribuidor_ids: list[int],
                          ini: int, fim: int) -> int:
    if not distribuidor_ids:
        return 0
    sql = (f"SELECT count(DISTINCT pdv_id) FROM v_vendas"
           f" WHERE distribuidor_id IN ({_marca(len(distribuidor_ids))})"
           f"   AND periodo BETWEEN ? AND ?")
    return con.execute(sql, list(distribuidor_ids) + [ini, fim]).fetchone()[0]


def _comparacao(con, dist_ids, ini, fim, janela_cmp: pe.Janela, rotulo: str,
                periodo_min: int | None) -> dict:
    """periodo_min e o inicio real dos dados do cliente. Se a janela de
    comparacao comecar antes disso, ela esta so PARCIALMENTE coberta — comparar
    um periodo completo com um incompleto infla o crescimento de forma
    artificial (ex.: "ultimo ano" perto do inicio dos dados). Nesse caso a
    comparacao nao e calculada, e o motivo fica explicito no calculo.
    """
    cobertura_completa = periodo_min is None or janela_cmp.ini >= periodo_min
    atual_v, atual_u, _, _ = f.faturamento_unidades(con, dist_ids, ini, fim)

    if cobertura_completa:
        ant_v, ant_u, _, _ = f.faturamento_unidades(con, dist_ids, janela_cmp.ini, janela_cmp.fim)
        cresc_v = f.crescimento_pct(atual_v, ant_v)
        cresc_u = f.crescimento_pct(atual_u, ant_u)
        premissas = [f"Período atual: {pe.Janela(ini, fim).rotulo}.",
                    f"Período de comparação: {janela_cmp.rotulo}.",
                    "Quando o período de comparação não teve nenhuma venda, "
                    "o crescimento não é calculado — o produto/cliente é "
                    "tratado como \"novo\", nunca como crescimento infinito."]
    else:
        ant_v = ant_u = cresc_v = cresc_u = None
        premissas = [
            f"Período atual: {pe.Janela(ini, fim).rotulo}.",
            f"Comparação NÃO calculada: o período de comparação ({janela_cmp.rotulo}) "
            f"começaria antes de {pe.periodo_label(periodo_min)}, que é o início dos "
            f"dados disponíveis para este cliente. Comparar um período completo com "
            f"um incompleto infla a variação artificialmente, então o sistema prefere "
            f"não mostrar um número a mostrar um número errado.",
        ]

    return {
        "rotulo": rotulo,
        "comparacao_valida": cobertura_completa,
        "periodo_atual": {"ini": ini, "fim": fim, "label": pe.Janela(ini, fim).rotulo},
        "periodo_anterior": {"ini": janela_cmp.ini, "fim": janela_cmp.fim,
                             "label": janela_cmp.rotulo},
        "faturamento_atual": atual_v, "faturamento_anterior": ant_v,
        "faturamento_variacao_pct": cresc_v,
        "faturamento_variacao_rs": None if not ant_v else atual_v - ant_v,
        "unidades_atual": atual_u, "unidades_anterior": ant_u,
        "unidades_variacao_pct": cresc_u,
        "calculo": f.Calculo(
            formula="(faturamento_atual / faturamento_anterior - 1) x 100",
            valores={"faturamento_atual": round(atual_v, 2),
                    "faturamento_anterior": None if ant_v is None else round(ant_v, 2),
                    "resultado_pct": None if cresc_v is None else round(cresc_v, 2)},
            premissas=premissas,
        ).como_dict(),
    }


def resumo_executivo(con: sqlite3.Connection, client_id: int, ini: int, fim: int) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel,
               "disponibilidade": disp.__dict__}

    dist_ids = disp.distribuidor_ids
    valor, unidades, _, n_produtos = f.faturamento_unidades(con, dist_ids, ini, fim)
    n_pdvs = contar_pdvs_distintos(con, dist_ids, ini, fim)

    cmp_anterior = _comparacao(con, dist_ids, ini, fim, pe.janela_anterior(ini, fim),
                               "período anterior", disp.periodo_min)

    # YoY so e oferecido se a janela de ha-1-ano tocar os dados disponiveis; se
    # nao tocar em nada (cliente cujo historico nem chega la), nem mostramos o
    # botao. Se tocar so parcialmente, _comparacao mostra o motivo em vez do numero.
    janela_ya = pe.janela_ano_anterior(ini, fim)
    cmp_ano_anterior = None
    if disp.periodo_min is None or janela_ya.fim >= disp.periodo_min:
        cmp_ano_anterior = _comparacao(con, dist_ids, ini, fim, janela_ya,
                                       "mesmo período do ano anterior (YoY)", disp.periodo_min)

    return {
        "disponivel": True,
        "cliente": disp.cliente_nome,
        "periodo": {"ini": ini, "fim": fim, "label": pe.Janela(ini, fim).rotulo},
        "faturamento": valor,
        "unidades": unidades,
        "n_produtos": n_produtos,
        "n_pdvs": n_pdvs,
        "comparacao_periodo_anterior": cmp_anterior,
        "comparacao_ano_anterior": cmp_ano_anterior,
        "calculo": f.Calculo(
            formula="SOMA(valor) e SOMA(unidades) das vendas do(s) distribuidor(es) "
                   "vinculados ao cliente, no período selecionado.",
            valores={"distribuidores": dist_ids, "periodo": pe.Janela(ini, fim).rotulo,
                    "faturamento": round(valor, 2), "unidades": unidades,
                    "pdvs_distintos": n_pdvs},
            premissas=[_ELO_SELLOUT,
                      "PDVs contam uma vez cada, mesmo comprando vários produtos "
                      "ou em vários meses do período."],
        ).como_dict(),
    }


def evolucao_mensal(con: sqlite3.Connection, client_id: int, metrica: str,
                    ini: int, fim: int) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    dist_ids = disp.distribuidor_ids
    marca = _marca(len(dist_ids))

    if metrica == "pdvs":
        linhas = con.execute(
            f"SELECT periodo, count(DISTINCT pdv_id) AS v FROM v_vendas"
            f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?"
            f" GROUP BY periodo ORDER BY periodo", dist_ids + [ini, fim]).fetchall()
    else:
        campo = {"faturamento": "sum(valor)", "unidades": "sum(unidades)",
                 "skus": "count(DISTINCT produto_id)"}[metrica]
        linhas = con.execute(
            f"SELECT periodo, {campo} AS v FROM v_vendas_mensal"
            f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?"
            f" GROUP BY periodo ORDER BY periodo", dist_ids + [ini, fim]).fetchall()

    serie = [{"periodo": p, "label": pe.periodo_label(p), "valor": v} for p, v in linhas]
    return {
        "disponivel": True, "metrica": metrica, "serie": serie,
        "calculo": f.Calculo(
            formula=f"Agrupamento mensal de '{metrica}' entre "
                   f"{pe.periodo_label(ini)} e {pe.periodo_label(fim)}.",
            premissas=[_ELO_SELLOUT],
        ).como_dict(),
    }


_ORDENACOES = {
    "faturamento": "faturamento_atual DESC",
    "unidades": "unidades_atual DESC",
    "crescimento": "variacao_pct DESC NULLS LAST",
    "queda": "variacao_pct ASC NULLS LAST",
}


def ranking_produtos(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                     *, ordenar: str = "faturamento", limite: int = 20,
                     offset: int = 0) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    dist_ids = disp.distribuidor_ids
    marca = _marca(len(dist_ids))
    janela_ant = pe.janela_anterior(ini, fim)
    # Se a janela de comparacao comecar antes do inicio real dos dados, ela e
    # so PARCIAL — comparar um periodo cheio com um incompleto infla a variacao
    # de cada produto artificialmente. Nesse caso a variacao fica None para
    # todo mundo, em vez de um numero enganoso.
    comparacao_valida = disp.periodo_min is None or janela_ant.ini >= disp.periodo_min

    atuais = con.execute(
        f"SELECT produto_id, sum(valor) v, sum(unidades) u FROM v_vendas_mensal"
        f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?"
        f" GROUP BY produto_id", dist_ids + [ini, fim]).fetchall()
    anteriores = dict(con.execute(
        f"SELECT produto_id, sum(valor) FROM v_vendas_mensal"
        f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?"
        f" GROUP BY produto_id", dist_ids + [janela_ant.ini, janela_ant.fim]).fetchall()
    ) if comparacao_valida else {}

    total_periodo = sum(v for _, v, _ in atuais)
    nomes = dict(con.execute(
        f"SELECT id, nome_canonico FROM dim_product WHERE id IN "
        f"({_marca(len(atuais))})", [p for p, _, _ in atuais]).fetchall()) if atuais else {}

    linhas = []
    for produto_id, valor, unidades in atuais:
        ant = anteriores.get(produto_id, 0.0) if comparacao_valida else None
        linhas.append({
            "produto_id": produto_id,
            "produto": nomes.get(produto_id, f"produto #{produto_id}"),
            "faturamento_atual": valor, "unidades_atual": unidades,
            "faturamento_anterior": ant if ant is not None else 0.0,
            "variacao_pct": f.crescimento_pct(valor, ant) if ant is not None else None,
            "participacao_pct": f.participacao_pct(valor, total_periodo),
        })

    reverso = ordenar in ("faturamento", "unidades", "crescimento")
    chave = {"faturamento": lambda r: r["faturamento_atual"],
             "unidades": lambda r: r["unidades_atual"],
             "crescimento": lambda r: (r["variacao_pct"] is not None, r["variacao_pct"]),
             "queda": lambda r: (r["variacao_pct"] is not None, r["variacao_pct"])}
    linhas.sort(key=chave.get(ordenar, chave["faturamento"]), reverse=reverso)

    premissas = [_ELO_SELLOUT]
    if not comparacao_valida:
        premissas.append(
            f"Variação NÃO calculada: o período de comparação ({janela_ant.rotulo}) "
            f"começaria antes de {pe.periodo_label(disp.periodo_min)}, início dos "
            f"dados disponíveis. Todo produto aparece como \"novo\" neste caso, não "
            f"porque tenha surgido agora, mas porque não há como comparar.")

    return {
        "disponivel": True, "total": len(linhas), "ordenar": ordenar,
        "comparacao_valida": comparacao_valida,
        "itens": linhas[offset:offset + limite],
        "calculo": f.Calculo(
            formula="Participação = faturamento do produto / faturamento total "
                   "do cliente no período. Variação = vs. período anterior "
                   f"de mesma duração ({janela_ant.rotulo}).",
            valores={"faturamento_total_periodo": round(total_periodo, 2)},
            premissas=premissas,
        ).como_dict(),
    }


def variacao_produtos(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                      *, direcao: str = "crescimento",
                      limite_crescimento_pct: float = 10.0,
                      limite_atencao_pct: float = -10.0,
                      limite_queda_pct: float = -20.0,
                      limite_critica_pct: float = -35.0) -> dict:
    """direcao='crescimento': produtos acima de limite_crescimento_pct.
    direcao='queda': produtos abaixo de limite_atencao_pct, classificados em
    ATENCAO / QUEDA / QUEDA_CRITICA pelos limites (todos configuraveis).
    """
    ranking = ranking_produtos(con, client_id, ini, fim, ordenar="faturamento", limite=100000)
    if not ranking["disponivel"]:
        return ranking
    if not ranking.get("comparacao_valida", True):
        # Sem periodo anterior integralmente coberto, "crescimento"/"queda" nao
        # tem base de comparacao valida — melhor voltar vazio e explicar do que
        # marcar todo o catalogo como "novo".
        return {
            "disponivel": True, "direcao": direcao,
            "limites": {}, "itens": [],
            "calculo": f.Calculo(
                formula="Sem base de comparação válida neste período.",
                premissas=ranking["calculo"]["premissas"],
            ).como_dict(),
        }

    def classificar(pct):
        if pct is None:
            return None
        if pct <= limite_critica_pct:
            return "QUEDA_CRITICA"
        if pct <= limite_queda_pct:
            return "QUEDA"
        if pct <= limite_atencao_pct:
            return "ATENCAO"
        return None

    itens = []
    for r in ranking["itens"]:
        pct = r["variacao_pct"]
        if direcao == "crescimento":
            eh_novo = r["faturamento_anterior"] == 0 and r["faturamento_atual"] > 0
            if (pct is not None and pct >= limite_crescimento_pct) or eh_novo:
                itens.append({**r, "classificacao": "NOVO" if eh_novo else "CRESCIMENTO",
                             "faturamento_variacao_rs": r["faturamento_atual"] - r["faturamento_anterior"]})
        else:
            classe = classificar(pct)
            if classe:
                itens.append({**r, "classificacao": classe,
                             "faturamento_variacao_rs": r["faturamento_atual"] - r["faturamento_anterior"]})

    itens.sort(key=lambda r: r["variacao_pct"] if r["variacao_pct"] is not None else 0,
              reverse=(direcao == "crescimento"))

    limites = ({"crescimento_pct": limite_crescimento_pct} if direcao == "crescimento"
              else {"atencao_pct": limite_atencao_pct, "queda_pct": limite_queda_pct,
                    "critica_pct": limite_critica_pct})
    return {
        "disponivel": True, "direcao": direcao, "limites": limites,
        "itens": itens,
        "calculo": f.Calculo(
            formula=("Produtos com variação >= limite de crescimento, ou sem "
                    "venda no período anterior e com venda agora (\"novo\")."
                    if direcao == "crescimento" else
                    "Produtos classificados por faixa de queda: ATENÇÃO, QUEDA "
                    "ou QUEDA CRÍTICA, conforme os limites configurados."),
            valores=limites,
            premissas=["Limites configuráveis — os valores acima são os usados "
                      "nesta consulta, não um padrão fixo no sistema."],
        ).como_dict(),
    }


def analise_uf(con: sqlite3.Connection, client_id: int, ini: int, fim: int) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if not disp.tem_uf:
        return {"disponivel": False,
               "motivo": "Este cliente não tem UF de PDV resolvida nos dados importados."}

    dist_ids = disp.distribuidor_ids
    marca = _marca(len(dist_ids))
    janela_ant = pe.janela_anterior(ini, fim)
    comparacao_valida = disp.periodo_min is None or janela_ant.ini >= disp.periodo_min

    atuais = con.execute(
        f"SELECT uf, sum(valor) v, sum(unidades) u FROM v_vendas_mensal"
        f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ? AND uf IS NOT NULL"
        f" GROUP BY uf", dist_ids + [ini, fim]).fetchall()
    anteriores = dict(con.execute(
        f"SELECT uf, sum(valor) FROM v_vendas_mensal"
        f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ? AND uf IS NOT NULL"
        f" GROUP BY uf", dist_ids + [janela_ant.ini, janela_ant.fim]).fetchall()
    ) if comparacao_valida else {}
    total = sum(v for _, v, _ in atuais)

    itens = [{
        "uf": uf, "faturamento": v, "unidades": u,
        "participacao_pct": f.participacao_pct(v, total),
        "variacao_pct": (f.crescimento_pct(v, anteriores.get(uf, 0.0))
                        if comparacao_valida else None),
    } for uf, v, u in atuais]
    itens.sort(key=lambda r: r["faturamento"], reverse=True)

    premissas = [_ELO_SELLOUT]
    if not comparacao_valida:
        premissas.append(
            f"Variação NÃO calculada: o período de comparação ({janela_ant.rotulo}) "
            f"começaria antes de {pe.periodo_label(disp.periodo_min)}, início dos "
            f"dados disponíveis.")

    return {
        "disponivel": True, "itens": itens, "comparacao_valida": comparacao_valida,
        "calculo": f.Calculo(
            formula="UF do ponto de venda (não o CNPJ do faturador, que pode "
                   "atender outro estado).",
            valores={"faturamento_total_periodo": round(total, 2)},
            premissas=premissas,
        ).como_dict(),
    }


def ranking_pdvs(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                 *, visao: str = "ranking", limite: int = 20, offset: int = 0) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    dist_ids = disp.distribuidor_ids
    marca = _marca(len(dist_ids))
    janela_ant = pe.janela_anterior(ini, fim)
    # Mesma regra das outras analises: um periodo de comparacao so parcialmente
    # coberto pelos dados produz numeros enganosos (um PDV que comprou antes do
    # inicio dos dados pareceria "novo" sem ser).
    comparacao_valida = disp.periodo_min is None or janela_ant.ini >= disp.periodo_min
    aviso_cobertura = (
        f"\"{visao.capitalize()}\" NÃO calculado: o período de comparação "
        f"({janela_ant.rotulo}) começaria antes de "
        f"{pe.periodo_label(disp.periodo_min)}, início dos dados disponíveis."
    ) if not comparacao_valida else None

    if visao in ("novos", "sumidos"):
        if not comparacao_valida:
            return {"disponivel": True, "visao": visao, "total": 0, "itens": [],
                   "calculo": f.Calculo(formula="Sem base de comparação válida.",
                                       premissas=[aviso_cobertura]).como_dict()}
        atuais = {r[0] for r in con.execute(
            f"SELECT DISTINCT pdv_id FROM v_vendas"
            f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?",
            dist_ids + [ini, fim])}
        anteriores = {r[0] for r in con.execute(
            f"SELECT DISTINCT pdv_id FROM v_vendas"
            f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?",
            dist_ids + [janela_ant.ini, janela_ant.fim])}
        alvo_ids = list((atuais - anteriores) if visao == "novos" else (anteriores - atuais))
        alvo_ids = [i for i in alvo_ids if i is not None]
        nomes = dict(con.execute(
            f"SELECT id, razao_social FROM dim_pdv WHERE id IN ({_marca(len(alvo_ids))})",
            alvo_ids).fetchall()) if alvo_ids else {}
        itens = [{"pdv_id": i, "pdv": nomes.get(i, f"PDV #{i}")} for i in alvo_ids]
        return {
            "disponivel": True, "visao": visao, "total": len(itens),
            "itens": itens[offset:offset + limite],
            "calculo": f.Calculo(
                formula=("PDVs com venda no período atual e nenhuma no período "
                        "anterior." if visao == "novos" else
                        "PDVs com venda no período anterior e nenhuma no atual."),
                valores={"periodo_atual": pe.Janela(ini, fim).rotulo,
                        "periodo_anterior": janela_ant.rotulo},
                premissas=[_ELO_SELLOUT,
                          "Um PDV \"sumido\" pode ter migrado para outro "
                          "distribuidor, não necessariamente parado de comprar "
                          "Vitamedic — ver perda do distribuidor vs. da "
                          "indústria (Etapa 3)."],
            ).como_dict(),
        }

    atuais = con.execute(
        f"SELECT pdv_id, sum(valor) v, sum(unidades) u, count(DISTINCT produto_id) n"
        f"  FROM v_vendas WHERE distribuidor_id IN ({marca})"
        f"   AND periodo BETWEEN ? AND ? GROUP BY pdv_id",
        dist_ids + [ini, fim]).fetchall()
    anteriores = dict(con.execute(
        f"SELECT pdv_id, sum(valor) FROM v_vendas WHERE distribuidor_id IN ({marca})"
        f"   AND periodo BETWEEN ? AND ? GROUP BY pdv_id",
        dist_ids + [janela_ant.ini, janela_ant.fim]).fetchall()
    ) if comparacao_valida else {}
    total = sum(v for _, v, _, _ in atuais)
    ids = [p for p, _, _, _ in atuais]
    nomes = dict(con.execute(
        f"SELECT id, razao_social FROM dim_pdv WHERE id IN ({_marca(len(ids))})",
        ids).fetchall()) if ids else {}

    linhas = [{
        "pdv_id": pdv_id, "pdv": nomes.get(pdv_id, f"PDV #{pdv_id}"),
        "faturamento": v, "unidades": u, "n_skus": n,
        "participacao_pct": f.participacao_pct(v, total),
        "variacao_pct": (f.crescimento_pct(v, anteriores.get(pdv_id, 0.0))
                        if comparacao_valida else None),
    } for pdv_id, v, u, n in atuais]
    linhas.sort(key=lambda r: r["faturamento"], reverse=True)

    premissas = [_ELO_SELLOUT]
    if aviso_cobertura:
        premissas.append(aviso_cobertura)

    return {
        "disponivel": True, "visao": "ranking", "total": len(linhas),
        "comparacao_valida": comparacao_valida,
        "itens": linhas[offset:offset + limite],
        "calculo": f.Calculo(
            formula="Faturamento por PDV no período; participação sobre o "
                   "total de todos os PDVs do cliente.",
            valores={"faturamento_total_periodo": round(total, 2),
                    "n_pdvs": len(linhas)},
            premissas=premissas,
        ).como_dict(),
    }


def concentracao(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                 *, contexto: str = "produtos") -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    dist_ids = disp.distribuidor_ids
    marca = _marca(len(dist_ids))

    if contexto == "pdvs":
        valores = [r[0] for r in con.execute(
            f"SELECT sum(valor) v FROM v_vendas WHERE distribuidor_id IN ({marca})"
            f" AND periodo BETWEEN ? AND ? GROUP BY pdv_id ORDER BY v DESC",
            dist_ids + [ini, fim])]
    else:
        valores = [r[0] for r in con.execute(
            f"SELECT sum(valor) v FROM v_vendas_mensal WHERE distribuidor_id IN ({marca})"
            f" AND periodo BETWEEN ? AND ? GROUP BY produto_id ORDER BY v DESC",
            dist_ids + [ini, fim])]

    total = sum(valores)
    faixas = []
    for n in (5, 10, 20):
        if n > len(valores):
            continue
        soma_n = sum(valores[:n])
        faixas.append({"top": n, "valor": soma_n,
                       "percentual": f.participacao_pct(soma_n, total),
                       "n_elementos": min(n, len(valores))})

    return {
        "disponivel": True, "contexto": contexto,
        "n_total_elementos": len(valores), "faturamento_total": total,
        "faixas": faixas,
        "calculo": f.Calculo(
            formula=f"SOMA dos {contexto} ordenados por faturamento decrescente, "
                   f"acumulado até a posição N, dividido pelo total.",
            premissas=[_ELO_SELLOUT],
        ).como_dict(),
    }


def alertas(con: sqlite3.Connection, client_id: int, ini: int, fim: int) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}

    itens = []
    cresc = variacao_produtos(con, client_id, ini, fim, direcao="crescimento")
    for r in cresc["itens"][:5]:
        cor = "azul" if r["classificacao"] == "NOVO" else "verde"
        texto = (f"Produto novo: {r['produto']} (R$ {_brl(r['faturamento_atual'])})"
                if r["classificacao"] == "NOVO" else
                f"{r['produto']} cresceu {r['variacao_pct']:.0f}%")
        itens.append({"tipo": cor, "categoria": "PRODUTO", "texto": texto,
                      "produto_id": r["produto_id"], "valor_pct": r["variacao_pct"]})

    queda = variacao_produtos(con, client_id, ini, fim, direcao="queda")
    for r in queda["itens"][:5]:
        itens.append({
            "tipo": "vermelho" if r["classificacao"] in ("QUEDA", "QUEDA_CRITICA") else "amarelo",
            "categoria": "PRODUTO",
            "texto": f"{r['produto']} caiu {abs(r['variacao_pct']):.0f}% "
                    f"({r['classificacao'].replace('_', ' ').title()})",
            "produto_id": r["produto_id"], "valor_pct": r["variacao_pct"],
        })

    # Produtos que desapareceram: tinham venda no periodo anterior, zero agora.
    # So verifica se o periodo anterior estiver integralmente coberto pelos
    # dados — senao um produto pareceria ter sumido so porque o mes dele nao
    # foi importado.
    dist_ids = disp.distribuidor_ids
    marca = _marca(len(dist_ids))
    janela_ant = pe.janela_anterior(ini, fim)
    if disp.periodo_min is None or janela_ant.ini >= disp.periodo_min:
        prod_atuais = {r[0] for r in con.execute(
            f"SELECT DISTINCT produto_id FROM v_vendas_mensal"
            f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?",
            dist_ids + [ini, fim])}
        prod_anteriores_rows = con.execute(
            f"SELECT produto_id, sum(valor) FROM v_vendas_mensal"
            f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?"
            f" GROUP BY produto_id", dist_ids + [janela_ant.ini, janela_ant.fim]).fetchall()
        sumidos = [(pid, v) for pid, v in prod_anteriores_rows if pid not in prod_atuais]
        sumidos.sort(key=lambda x: x[1], reverse=True)
        for pid, v in sumidos[:3]:
            itens.append({"tipo": "vermelho", "categoria": "PRODUTO",
                          "texto": f"{_nome_produto(con, pid)} parou de vender "
                                  f"(tinha R$ {_brl(v)} no período anterior)",
                          "produto_id": pid, "valor_pct": None})

    return {
        "disponivel": True, "itens": itens, "n_total": len(itens),
        "calculo": f.Calculo(
            formula="Deriva de produtos/variação e produtos/queda desta mesma "
                   "consulta — não é um cálculo à parte.",
            premissas=["Mostra até 5 maiores altas, 5 maiores quedas e 3 "
                      "produtos que pararam de vender, por relevância de valor."],
        ).como_dict(),
    }
