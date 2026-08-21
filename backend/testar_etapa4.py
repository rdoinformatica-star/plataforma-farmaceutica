"""Verificacao ponta a ponta da Etapa 4 (Estoque + DDE + Capital parado +
Mercado/IQVIA + Share + Preco).

Mesmo espirito das etapas anteriores: fala com a API rodando e confere contra
o oraculo recomputado ao vivo — nunca contra numeros congelados de relatorio.

Os oraculos desta etapa:
  - estoque: a propria fonte traz cobertura_dias. O teste recomputa a formula
    a partir das colunas cruas e confere contra a API E contra a origem;
  - mercado/share: recomputado direto de fact_market em SQL independente;
  - preco: replica a logica de engine/a05_preco.py (valor/unidades por SKU,
    cliente x demais distribuidores, com piso de volume).

Uso:  python backend/testar_etapa4.py
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000/api"
DB = RAIZ / "database" / "pharma.db"

INI, FIM = 202601, 202607

_ok = _falha = 0
_erros: list[str] = []


def checar(rotulo: str, condicao, obtido=None, esperado=None):
    global _ok, _falha
    if condicao:
        _ok += 1
        print(f"  OK    {rotulo}")
    else:
        _falha += 1
        extra = f" (obtido: {obtido!r}, esperado: {esperado!r})" if obtido is not None else ""
        print(f"  FALHA {rotulo}{extra}")
        _erros.append(rotulo + extra)


def chamar(metodo: str, rota: str, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        API + rota, data=dados, method=metodo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def secao(titulo: str):
    print(f"\n== {titulo} " + "=" * max(0, 58 - len(titulo)))


def perto(a, b, tol=0.01):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


# --------------------------------------------------------------------------
# 1. Perfil das fontes novas
# --------------------------------------------------------------------------
def teste_perfis(con):
    secao("Perfil das fontes (estoque e mercado)")

    st, p = chamar("GET", "/analytics/1/estoque/perfil")
    checar("perfil de estoque responde", st == 200, st, 200)
    checar("perfil de estoque disponivel para quem importou", p.get("disponivel") is True)

    linhas, com_pos = con.execute(
        "SELECT count(*), count(estoque_disp_un) FROM v_estoque WHERE client_id = 1"
    ).fetchone()
    checar("perfil conta as linhas de estoque corretamente",
           p["linhas"] == linhas, p["linhas"], linhas)
    checar("perfil separa linhas com e sem posicao fisica",
           p["com_posicao"] == com_pos and p["sem_posicao"] == linhas - com_pos,
           (p["com_posicao"], p["sem_posicao"]), (com_pos, linhas - com_pos))
    checar("perfil identifica que o estoque e uma foto unica",
           p["eh_foto"] is True)
    checar("perfil expoe filial sem posicao fisica (nao finge estoque zero)",
           any(f["tem_posicao_fisica"] is False for f in p["por_filial"]))
    checar("perfil liga filial do estoque ao distribuidor do sell-out",
           len(p["filiais_vinculadas"]) >= 1, p["filiais_vinculadas"])

    st, p2 = chamar("GET", "/analytics/2/estoque/perfil")
    checar("cliente sem estoque devolve indisponivel com motivo",
           st == 200 and p2.get("disponivel") is False and p2.get("motivo"),
           p2.get("disponivel"))

    st, m = chamar("GET", "/analytics/1/mercado/perfil")
    checar("perfil de mercado responde", st == 200, st, 200)
    n_iqvia = con.execute("SELECT count(*) FROM v_mercado").fetchone()[0]
    checar("perfil de mercado conta as linhas corretamente",
           m["linhas"] == n_iqvia, m["linhas"], n_iqvia)
    checar("perfil de mercado declara que NAO identifica distribuidor",
           m["identifica_distribuidor"] is False)
    n_prodid = con.execute("SELECT count(produto_id) FROM v_mercado").fetchone()[0]
    checar("perfil de mercado declara ausencia de chave com dim_product",
           m["tem_ligacao_com_dim_product"] == (n_prodid > 0),
           m["tem_ligacao_com_dim_product"], n_prodid > 0)
    checar("perfil de mercado deriva a janela YTD do periodo de referencia",
           m["janela_ytd"]["fim"] == m["periodo_ref"],
           m["janela_ytd"], m["periodo_ref"])


# --------------------------------------------------------------------------
# 2. DDE contra o oraculo da propria fonte
# --------------------------------------------------------------------------
def teste_dde(con):
    secao("DDE e cobertura de estoque (oraculo: a propria fonte)")

    # Oraculo recomputado das colunas cruas.
    oraculo = {}
    for pid, fil, ed, mv, cob in con.execute(
        """SELECT produto_id, filial, estoque_disp_un, media_venda_un, cobertura_dias
             FROM v_estoque WHERE client_id = 1 AND estoque_disp_un IS NOT NULL"""):
        dde = (ed / (mv / 30.0)) if (mv is not None and mv > 0) else None
        oraculo[(pid, fil)] = (dde, cob)

    st, r = chamar("GET", f"/analytics/1/estoque?periodo_ini={INI}&periodo_fim={FIM}&limite=2000")
    checar("posicao de estoque responde", st == 200, st, 200)
    itens = r["itens"]
    checar("posicao lista todos os SKUs com estoque",
           len(itens) == len(oraculo), len(itens), len(oraculo))

    div_api = div_origem = 0
    for i in itens:
        chave = (i["produto_id"], i["filial"])
        if chave not in oraculo:
            div_api += 1
            continue
        dde_calc, cob_origem = oraculo[chave]
        if not perto(i["dde_fonte"], dde_calc, 0.0001):
            div_api += 1
        # A origem so serve de conferencia quando ela propria e interpretavel
        # (cobertura negativa/infinita da origem nao entra).
        if (cob_origem is not None and cob_origem == cob_origem
                and cob_origem not in (float("inf"), float("-inf"))
                and cob_origem > 0 and i["dde_fonte"] is not None):
            if not perto(i["dde_fonte"], cob_origem, 0.0001):
                div_origem += 1
    checar("DDE da API bate com a formula recomputada", div_api == 0, div_api, 0)
    checar("DDE bate com o cobertura_dias que a propria fonte traz",
           div_origem == 0, div_origem, 0)

    checar("formula do DDE aparece no 'como foi calculado'",
           "DDE" in r["calculo"]["formula"] and "/" in r["calculo"]["formula"])
    checar("premissas do DDE citam que a media da fonte e mensal",
           any("MENSAL" in p or "mensal" in p for p in r["calculo"]["premissas"]))

    # Media de venda negativa nao pode virar DDE nem cair numa faixa.
    negativos = con.execute(
        """SELECT count(*) FROM v_estoque
            WHERE client_id = 1 AND estoque_disp_un IS NOT NULL AND media_venda_un < 0"""
    ).fetchone()[0]
    indef = [i for i in itens if i["classificacao"] == "INDEFINIDO"]
    checar("SKU com devolucao liquida fica INDEFINIDO, nao classificado",
           len(indef) == negativos, len(indef), negativos)
    checar("SKU INDEFINIDO nao carrega DDE numerico",
           all(i["dde"] is None for i in indef))

    # Sem venda -> pior faixa, nunca a melhor.
    sem_venda = [i for i in itens if i.get("motivo_dde_indefinido") == "sem_venda"]
    faixas = r["faixas"]
    pior = faixas[-1]["rotulo"]
    checar("SKU com estoque e sem venda cai na pior faixa",
           all(i["classificacao"] == pior for i in sem_venda),
           [i["classificacao"] for i in sem_venda], pior)


def teste_classificacao(con):
    secao("Classificacao de cobertura e faixas configuraveis")

    st, r = chamar("GET", f"/analytics/1/estoque?periodo_ini={INI}&periodo_fim={FIM}&limite=2000")
    itens = r["itens"]
    faixas = {f["rotulo"]: (f["de"], f["ate"]) for f in r["faixas"]}
    checar("faixas padrao sao as cinco combinadas",
           set(faixas) == {"SAUDAVEL", "ATENCAO", "ALTO", "CRITICO", "ZUMBI"},
           sorted(faixas))

    erradas = 0
    for i in itens:
        if i["dde"] is None:
            continue
        de, ate = faixas[i["classificacao"]]
        if not (i["dde"] >= de and (ate is None or i["dde"] < ate)):
            erradas += 1
    checar("todo SKU esta dentro da faixa que a API atribuiu", erradas == 0, erradas, 0)

    soma = sum(1 for i in itens)
    st, res = chamar("GET",
                     f"/analytics/1/estoque/resumo?periodo_ini={INI}&periodo_fim={FIM}")
    checar("resumo de estoque responde", st == 200, st, 200)
    checar("classes do resumo somam o total de SKUs com estoque",
           sum(c["skus"] for c in res["por_classe"]) == soma,
           sum(c["skus"] for c in res["por_classe"]), soma)

    valor_bd = con.execute(
        """SELECT coalesce(sum(estoque_disp_x100),0)/100.0 FROM v_estoque
            WHERE client_id = 1 AND estoque_disp_un IS NOT NULL""").fetchone()[0]
    checar("valor total do estoque bate com o banco",
           perto(res["valor_total"], valor_bd, 0.01), res["valor_total"], valor_bd)
    checar("resumo separa cobertura media simples da ponderada por valor",
           res["cobertura_media_dias"] is not None
           and res["cobertura_ponderada_dias"] is not None)


def teste_zumbi_capital(con):
    secao("Estoque zumbi e capital parado")

    st, z = chamar("GET",
                   f"/analytics/1/estoque/zumbi?periodo_ini={INI}&periodo_fim={FIM}"
                   f"&limite_dias=365&top_n=500")
    checar("estoque zumbi responde", st == 200, st, 200)
    checar("zumbi vem ordenado do maior valor para o menor",
           all(z["itens"][i]["valor_estoque"] >= z["itens"][i + 1]["valor_estoque"]
               for i in range(len(z["itens"]) - 1)))
    checar("todo item zumbi excede o limite (ou nao tem venda)",
           all(i["dde"] is None or i["dde"] > 365 for i in z["itens"]))
    checar("nenhum item INDEFINIDO entra no zumbi",
           all(i["classificacao"] != "INDEFINIDO" for i in z["itens"]))

    st, z2 = chamar("GET",
                    f"/analytics/1/estoque/zumbi?periodo_ini={INI}&periodo_fim={FIM}"
                    f"&limite_dias=180&top_n=500")
    checar("limite menor captura pelo menos tantos SKUs quanto o maior",
           z2["n_skus"] >= z["n_skus"], (z2["n_skus"], z["n_skus"]))

    st, c = chamar("GET",
                   f"/analytics/1/estoque/capital-parado?periodo_ini={INI}&periodo_fim={FIM}")
    checar("capital parado responde", st == 200, st, 200)
    f180 = next(f for f in c["faixas"] if f["acima_de_dias"] == 180)
    f365 = next(f for f in c["faixas"] if f["acima_de_dias"] == 365)
    checar("capital acima de 180 dias >= capital acima de 365 dias",
           f180["valor"] >= f365["valor"], (f180["valor"], f365["valor"]))
    checar("capital parado nunca excede o estoque total",
           f180["valor"] <= c["valor_total_estoque"] + 0.01,
           f180["valor"], c["valor_total_estoque"])
    checar("capital de 365 bate com o total do zumbi de 365",
           perto(f365["valor"], z["valor_total"], 0.01),
           f365["valor"], z["valor_total"])
    checar("premissa diz que e capital imobilizado, nao prejuizo",
           any("prejuizo" in p or "imobilizado" in p for p in c["calculo"]["premissas"]))


def teste_simulador():
    secao("Simulador de estoque")

    anterior = None
    for obj in (30, 60, 90, 120):
        st, s = chamar("GET",
                       f"/analytics/1/estoque/simulador?periodo_ini={INI}&periodo_fim={FIM}"
                       f"&objetivo_dias={obj}&top_n=500")
        checar(f"simulador responde para objetivo de {obj} dias", st == 200, st, 200)
        checar(f"objetivo de {obj} dias ecoa na resposta", s["objetivo_dias"] == obj)
        checar(f"capital liberavel ({obj}d) nao excede o estoque atual",
               s["capital_potencialmente_liberavel"] <= s["valor_estoque_atual"] + 0.01)
        if anterior is not None:
            checar(f"objetivo maior ({obj}d) libera menos capital que o anterior",
                   s["capital_potencialmente_liberavel"] <= anterior + 0.01,
                   s["capital_potencialmente_liberavel"], f"<= {anterior}")
        anterior = s["capital_potencialmente_liberavel"]

        if obj == 60:
            checar("simulador mostra estoque atual, objetivo e excesso por SKU",
                   all({"estoque_atual_un", "estoque_objetivo_un", "excesso_un"}
                       <= set(i) for i in s["itens"]))
            checar("excesso por SKU e coerente com atual - objetivo",
                   all(perto(i["excesso_un"],
                             max(0.0, i["estoque_atual_un"] - i["estoque_objetivo_un"]), 0.01)
                       for i in s["itens"] if not i["sem_giro"]))
            checar("simulador rotula como POTENCIALMENTE LIBERAVEL, nao garantido",
                   any("POTENCIALMENTE LIBERAVEL" in p.upper()
                       for p in s["calculo"]["premissas"]))
            checar("simulador declara a premissa de ritmo de venda",
                   any("ritmo" in p for p in s["calculo"]["premissas"]))
            checar("SKU sem giro vem marcado", any("sem_giro" in i for i in s["itens"]))

    st, e = chamar("GET",
                   f"/analytics/1/estoque/simulador?periodo_ini={INI}&periodo_fim={FIM}"
                   f"&objetivo_dias=0")
    checar("objetivo zero e recusado pela validacao", e is not None and st in (400, 422),
           st, "400/422")


def teste_matriz_estoque():
    secao("Matriz estoque x vendas")

    st, m = chamar("GET",
                   f"/analytics/1/estoque/matriz?periodo_ini={INI}&periodo_fim={FIM}")
    checar("matriz estoque x vendas responde", st == 200, st, 200)
    esperados = {"RUPTURA_POTENCIAL", "CAPITAL_CONCENTRADO", "EXCESSO", "BAIXA_PRIORIDADE"}
    checar("os quatro quadrantes existem",
           {q["quadrante"] for q in m["quadrantes"]} == esperados,
           {q["quadrante"] for q in m["quadrantes"]})
    checar("soma dos quadrantes bate com o total de itens",
           sum(q["skus"] for q in m["quadrantes"]) == len(m["itens"]),
           sum(q["skus"] for q in m["quadrantes"]), len(m["itens"]))
    checar("todo item recebeu um quadrante",
           all(i.get("quadrante") in esperados for i in m["itens"]))
    checar("ruptura e tratada como alerta a verificar, nao como certeza",
           any("nao mostra pedido" in p or "alerta a verificar" in p
               for p in m["calculo"]["premissas"]))


# --------------------------------------------------------------------------
# 3. Mercado, share e cliente vs mercado
# --------------------------------------------------------------------------
def teste_mercado_share(con):
    secao("Mercado e share (oraculo: SQL independente sobre fact_market)")

    st, r = chamar("GET", "/analytics/1/mercado")
    checar("resumo de mercado responde", st == 200, st, 200)
    un, un_a, val = con.execute(
        """SELECT coalesce(sum(un_ytd),0), coalesce(sum(un_ytd_ant),0),
                  coalesce(sum(valor_ytd_x100),0)/100.0 FROM v_mercado""").fetchone()
    checar("unidades YTD do mercado batem com o banco",
           perto(r["unidades_ytd"], un, 0.5), r["unidades_ytd"], un)
    checar("valor YTD do mercado bate com o banco",
           perto(r["valor_ytd"], val, 0.5), r["valor_ytd"], val)
    esperado_cresc = (un / un_a - 1) * 100 if un_a else None
    checar("crescimento do mercado em unidades bate com o recomputado",
           perto(r["cresc_unidades_pct"], esperado_cresc, 0.0001),
           r["cresc_unidades_pct"], esperado_cresc)

    st, s = chamar("GET", "/analytics/1/mercado/share")
    checar("share da industria responde", st == 200, st, 200)
    vmd, tot = con.execute(
        """SELECT coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd END),0),
                  coalesce(sum(un_ytd),0) FROM v_mercado""").fetchone()
    checar("share da industria bate com o recomputado",
           perto(s["share_pct"], vmd / tot * 100, 0.0001),
           s["share_pct"], vmd / tot * 100)
    checar("share declara escopo INDUSTRIA (nao distribuidor)",
           s["escopo"] == "INDUSTRIA_VITAMEDIC", s["escopo"])
    checar("share documenta numerador e denominador",
           "VITAMEDIC" in s["calculo"]["formula"] and "total" in s["calculo"]["formula"])
    checar("variacao de share vem em pontos percentuais",
           s["delta_share_pp"] is not None
           and perto(s["delta_share_pp"], s["share_pct"] - s["share_ant_pct"], 0.0001))

    st, sv = chamar("GET", "/analytics/1/mercado/share?base=valor")
    checar("share aceita base em valor", st == 200 and sv["base"] == "valor")
    st, sx = chamar("GET", "/analytics/1/mercado/share?base=inventada")
    checar("base de share invalida e recusada", st == 422, st, 422)

    # A limitacao central da etapa.
    st, sc = chamar("GET", "/analytics/1/mercado/share-cliente")
    checar("share do CLIENTE devolve indisponivel", sc["disponivel"] is False)
    checar("motivo explica que a IQVIA identifica laboratorio, nao distribuidor",
           "laboratorio" in sc["motivo"] and "distribuidor" in sc["motivo"])
    checar("cliente realmente nao aparece na base de mercado",
           sc["ocorrencias_do_nome_no_mercado"] == 0,
           sc["ocorrencias_do_nome_no_mercado"], 0)

    st, uf = chamar("GET", "/analytics/1/mercado/share?uf=RJ")
    vmd_rj, tot_rj = con.execute(
        """SELECT coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd END),0),
                  coalesce(sum(un_ytd),0) FROM v_mercado WHERE uf='RJ'""").fetchone()
    checar("filtro de UF no share bate com o recomputado",
           perto(uf["share_pct"], vmd_rj / tot_rj * 100, 0.0001),
           uf["share_pct"], vmd_rj / tot_rj * 100)
    checar("share por UF difere do nacional (o filtro tem efeito)",
           not perto(uf["share_pct"], s["share_pct"], 0.0001))


def teste_regional_ranking():
    secao("Analise regional e ranking de mercados")

    st, r = chamar("GET", "/analytics/1/mercado/regional&top_n=50".replace("&", "?", 1))
    checar("regional responde", st == 200, st, 200)
    checar("regional traz UF, mercado, share e crescimento",
           all({"uf", "mercado_un", "share_pct", "cresc_mercado_pct"} <= set(i)
               for i in r["itens"]))
    checar("regional ordenado por tamanho de mercado",
           all(r["itens"][i]["mercado_valor"] >= r["itens"][i + 1]["mercado_valor"]
               for i in range(len(r["itens"]) - 1)))
    checar("share por UF sempre entre 0 e 100",
           all(0 <= i["share_pct"] <= 100 for i in r["itens"]))

    st, k = chamar("GET", "/analytics/1/mercado/ranking?top_n=50")
    checar("ranking de mercados responde", st == 200, st, 200)
    checar("so entram mercados com presenca da industria",
           all(i["vitamedic_un"] > 0 for i in k["itens"]))
    checar("delta de share em p.p. e consistente",
           all(i["delta_share_pp"] is None
               or perto(i["delta_share_pp"], i["share_pct"] - i["share_ant_pct"], 0.0001)
               for i in k["itens"]))


def teste_cliente_vs_mercado(con):
    secao("Crescimento do cliente vs mercado")

    st, r = chamar("GET", "/analytics/1/mercado/vs-cliente")
    checar("cliente vs mercado responde", st == 200, st, 200)
    checar("comparacao disponivel para cliente com historico", r["disponivel"] is True)

    j = r["janela"]
    checar("janela do cliente e a mesma do mercado (nao a da tela)",
           j["ini"] == 202601 and j["fim"] == 202606 and j["ini_ant"] == 202501,
           j)

    val, un = con.execute(
        """SELECT coalesce(sum(valor),0), coalesce(sum(unidades),0)
             FROM v_vendas_mensal WHERE distribuidor_id IN (231,232)
              AND periodo BETWEEN 202601 AND 202606""").fetchone()
    checar("faturamento do cliente na janela bate com o banco",
           perto(r["cliente"]["valor"], val, 0.01), r["cliente"]["valor"], val)

    d = r["diferenca_valor_pp"]
    checar("diferenca em p.p. = cliente - mercado",
           perto(d, r["cliente"]["cresc_valor_pct"] - r["mercado"]["cresc_valor_pct"], 0.0001))

    # A regra de linguagem mais importante do item 14 do prompt.
    leitura = r["leitura_valor"] or ""
    if r["cliente"]["cresc_valor_pct"] is not None and r["cliente"]["cresc_valor_pct"] < 0:
        # A frase pode citar que o MERCADO cresceu; o que nao pode e atribuir
        # crescimento ao CLIENTE. Por isso a checagem e sobre o sujeito.
        checar("cliente em queda NAO e descrito como tendo crescido",
               not leitura.startswith("O cliente cresceu"), leitura)
        checar("leitura de queda diz que o cliente caiu",
               leitura.startswith("O cliente caiu")
               or leitura.startswith("O cliente apresentou queda"), leitura)
    checar("leitura fala em desempenho relativo e p.p.",
           "p.p." in leitura and "relativo" in leitura, leitura)
    checar("premissa avisa que os elos da cadeia sao diferentes",
           any("elos" in p.lower() or "Elos" in p for p in r["calculo"]["premissas"]))

    st, r2 = chamar("GET", "/analytics/2/mercado/vs-cliente")
    checar("comparacao funciona para o segundo cliente", st == 200, st, 200)
    if r2.get("disponivel"):
        checar("clientes diferentes tem crescimento diferente",
               not perto(r2["cliente"]["cresc_valor_pct"],
                         r["cliente"]["cresc_valor_pct"], 0.0001))


def teste_ponte(con):
    secao("Ponte produto do cliente x mercado")

    st, p = chamar("GET",
                   f"/analytics/1/mercado/ponte?periodo_ini=202601&periodo_fim=202606&top_n=500")
    checar("ponte responde", st == 200, st, 200)
    checar("ponte informa quantos SKUs ficaram sem correspondencia",
           p["n_sem_correspondencia"] > 0, p["n_sem_correspondencia"])
    checar("ponte expoe a cobertura do faturamento",
           p["cobertura_da_ponte_pct"] is not None and 0 <= p["cobertura_da_ponte_pct"] <= 100,
           p["cobertura_da_ponte_pct"])
    checar("cada SKU ligado declara por qual nivel casou",
           all(i["nivel_ligacao"] in ("apresentacao", "molecula") for i in p["itens"]))
    checar("soma dos niveis bate com o total de ligados",
           sum(n["skus"] for n in p["por_nivel"]) == p["n_ligados"],
           sum(n["skus"] for n in p["por_nivel"]), p["n_ligados"])
    checar("premissa avisa que o nivel molecula e mais amplo que o SKU",
           any("molecula" in x and "amplo" in x for x in p["calculo"]["premissas"]))
    checar("premissa avisa que a ponte e parcial",
           any("PARCIAL" in x for x in p["calculo"]["premissas"]))
    checar("share da ponte e rotulado como da industria",
           all("share_industria_pct" in i for i in p["itens"]))


# --------------------------------------------------------------------------
# 4. Preco e comparabilidade
# --------------------------------------------------------------------------
def teste_preco(con):
    secao("Preco (oraculo: logica de engine/a05_preco.py recomputada)")

    st, c = chamar("GET", "/analytics/1/preco/comparabilidade")
    checar("comparabilidade responde", st == 200, st, 200)
    par_iqvia = next(p for p in c["pares"] if "IQVIA" in p["para"])
    checar("sell-out x IQVIA marcado como NAO comparavel",
           par_iqvia["comparavel"] is False)
    checar("motivo cita elos diferentes da cadeia",
           "elo" in par_iqvia["motivo"].lower(), par_iqvia["motivo"][:60])
    par_peer = next(p for p in c["pares"] if "outros distribuidores" in p["para"])
    checar("cliente x outros distribuidores marcado como comparavel",
           par_peer["comparavel"] is True)
    tabelado = next(f for f in c["fontes"] if "tabelado" in f["fonte"])
    checar("preco tabelado declarado indisponivel (price_data vazia)",
           tabelado["disponivel"] is False)

    st, p = chamar("GET",
                   f"/analytics/1/preco?periodo_ini={INI}&periodo_fim={FIM}&uf=RJ&top_n=500")
    checar("preco vs concorrentes responde", st == 200, st, 200)

    # Oraculo: mesma conta, direto no banco.
    cli = {r[0]: (r[1], r[2]) for r in con.execute(
        """SELECT produto_id, coalesce(sum(unidades),0), coalesce(sum(valor),0)
             FROM v_vendas_mensal WHERE distribuidor_id IN (231,232)
              AND periodo BETWEEN ? AND ? AND uf='RJ' GROUP BY produto_id""",
        (INI, FIM))}
    out = {r[0]: (r[1], r[2]) for r in con.execute(
        """SELECT produto_id, coalesce(sum(unidades),0), coalesce(sum(valor),0)
             FROM v_vendas_mensal WHERE distribuidor_id NOT IN (231,232)
              AND periodo BETWEEN ? AND ? AND uf='RJ' GROUP BY produto_id""",
        (INI, FIM))}
    esperado = {}
    for pid, (un_c, val_c) in cli.items():
        un_o, val_o = out.get(pid, (0, 0))
        if un_c < 200 or un_o < 200:
            continue
        esperado[pid] = (val_c / un_c, val_o / un_o)

    checar("quantidade de SKUs comparaveis bate com o oraculo",
           p["n_comparaveis"] == len(esperado), p["n_comparaveis"], len(esperado))
    div = 0
    for i in p["itens"]:
        e = esperado.get(i["produto_id"])
        if not e or not perto(i["preco_cliente"], e[0], 0.0001) \
                or not perto(i["preco_outros"], e[1], 0.0001):
            div += 1
    checar("precos por SKU batem com o oraculo", div == 0, div, 0)
    checar("diferenca % coerente com os dois precos",
           all(perto(i["diferenca_pct"],
                     (i["preco_cliente"] / i["preco_outros"] - 1) * 100, 0.0001)
               for i in p["itens"] if i["preco_outros"]))
    checar("SKUs sem volume minimo ficam listados, nao sumidos",
           p["n_sem_volume"] > 0 and len(p["sem_volume"]) > 0)
    checar("premissa declara o piso de volume",
           any("unidades" in x and "fora" in x for x in p["calculo"]["premissas"]))
    checar("premissa avisa que preco nao explica venda sozinho",
           any("nao explica sozinha" in x for x in p["calculo"]["premissas"]))

    st, p2 = chamar("GET",
                    f"/analytics/1/preco?periodo_ini={INI}&periodo_fim={FIM}"
                    f"&uf=RJ&minimo_unidades=5000&top_n=500")
    checar("piso de volume maior reduz os SKUs comparaveis",
           p2["n_comparaveis"] <= p["n_comparaveis"],
           p2["n_comparaveis"], p["n_comparaveis"])

    st, e = chamar("GET",
                   f"/analytics/1/preco/evolucao?periodo_ini={INI}&periodo_fim={FIM}")
    checar("evolucao de preco responde", st == 200, st, 200)
    checar("serie tem um ponto por mes do periodo", len(e["serie"]) == 7, len(e["serie"]))
    checar("preco medio do mes = valor / unidades",
           all(x["preco_medio"] is None
               or perto(x["preco_medio"], x["valor"] / x["unidades"], 0.0001)
               for x in e["serie"]))

    st, v = chamar("GET", "/analytics/1/preco/varejo?uf=RJ&top_n=100")
    checar("preco de varejo IQVIA responde", st == 200, st, 200)
    checar("preco de varejo declara escopo de industria",
           v["escopo"] == "VAREJO_INDUSTRIA", v["escopo"])
    checar("indice vs lider coerente com os dois precos",
           all(perto(i["indice_vs_lider_pct"],
                     (i["preco_vitamedic"] / i["preco_lider"] - 1) * 100, 0.0001)
               for i in v["itens"] if i["preco_lider"]))
    checar("premissa do varejo avisa que nao se compara com sell-out",
           any("sell-out" in x for x in v["calculo"]["premissas"]))


# --------------------------------------------------------------------------
# 5. Multicliente, filtros, validacao e performance
# --------------------------------------------------------------------------
def teste_isolamento():
    secao("Isolamento multicliente e validacao de entrada")

    st, e1 = chamar("GET", "/analytics/1/estoque/perfil")
    st, e2 = chamar("GET", "/analytics/2/estoque/perfil")
    checar("estoque de um cliente nao aparece no outro",
           e1["disponivel"] is True and e2["disponivel"] is False)

    st, c1 = chamar("GET", "/analytics/1/mercado/vs-cliente")
    st, c2 = chamar("GET", "/analytics/2/mercado/vs-cliente")
    if c1.get("disponivel") and c2.get("disponivel"):
        checar("cada cliente tem o proprio faturamento na comparacao",
               not perto(c1["cliente"]["valor"], c2["cliente"]["valor"], 0.01))
        checar("o mercado e o mesmo para os dois (base compartilhada)",
               perto(c1["mercado"]["valor"], c2["mercado"]["valor"], 0.01))

    st, p1 = chamar("GET", f"/analytics/1/preco?periodo_ini={INI}&periodo_fim={FIM}")
    st, p2 = chamar("GET", f"/analytics/2/preco?periodo_ini={INI}&periodo_fim={FIM}")
    checar("preco medio difere entre clientes",
           not perto(p1["preco_medio_cliente"], p2["preco_medio_cliente"], 0.0001))

    st, _ = chamar("GET", "/analytics/999/estoque/perfil")
    checar("cliente inexistente devolve 404", st == 404, st, 404)
    st, _ = chamar("GET", "/analytics/1/estoque?periodo_ini=209913&periodo_fim=202607")
    checar("periodo invalido devolve 400", st == 400, st, 400)
    st, _ = chamar("GET", "/analytics/1/estoque?periodo_ini=202607&periodo_fim=202601")
    checar("periodo_fim antes de periodo_ini devolve 400", st == 400, st, 400)
    st, _ = chamar("GET",
                   f"/analytics/1/estoque?periodo_ini={INI}&periodo_fim={FIM}"
                   f"&base_velocidade=chute")
    checar("base_velocidade invalida e recusada", st == 422, st, 422)


def teste_filtros():
    secao("Filtros: filial, UF e base de velocidade")

    st, todos = chamar("GET",
                       f"/analytics/1/estoque/resumo?periodo_ini={INI}&periodo_fim={FIM}")
    st, rj = chamar("GET",
                    f"/analytics/1/estoque/resumo?periodo_ini={INI}&periodo_fim={FIM}"
                    f"&filial=Emefarma%20RJ")
    checar("filtro de filial responde", st == 200, st, 200)
    checar("filial nao traz mais SKUs que o total",
           rj["skus_com_estoque"] <= todos["skus_com_estoque"],
           rj["skus_com_estoque"], todos["skus_com_estoque"])

    st, fonte = chamar("GET",
                       f"/analytics/1/estoque?periodo_ini={INI}&periodo_fim={FIM}"
                       f"&base_velocidade=fonte&limite=2000")
    st, per = chamar("GET",
                     f"/analytics/1/estoque?periodo_ini={INI}&periodo_fim={FIM}"
                     f"&base_velocidade=periodo&limite=2000")
    checar("as duas bases de velocidade respondem",
           fonte["disponivel"] and per["disponivel"])
    checar("os dois DDE vem juntos na resposta",
           all({"dde_fonte", "dde_periodo"} <= set(i) for i in fonte["itens"]))
    difere = sum(1 for a, b in zip(fonte["itens"], per["itens"])
                 if not perto(a["dde"], b["dde"], 0.01))
    checar("trocar a base de velocidade muda o DDE de pelo menos um SKU",
           difere > 0, difere)

    st, m_nac = chamar("GET", "/analytics/1/mercado")
    st, m_rj = chamar("GET", "/analytics/1/mercado?uf=RJ")
    checar("filtro de UF reduz o mercado",
           m_rj["unidades_ytd"] < m_nac["unidades_ytd"],
           m_rj["unidades_ytd"], m_nac["unidades_ytd"])


def teste_performance():
    secao("Performance")

    t = time.time()
    for rota in (f"/analytics/1/estoque/resumo?periodo_ini={INI}&periodo_fim={FIM}",
                 f"/analytics/1/estoque/zumbi?periodo_ini={INI}&periodo_fim={FIM}",
                 f"/analytics/1/estoque/simulador?periodo_ini={INI}&periodo_fim={FIM}"):
        chamar("GET", rota)
    dt = time.time() - t
    checar(f"bateria de estoque responde rapido ({dt:.2f}s)", dt < 8.0, round(dt, 2), "<8s")

    t = time.time()
    for rota in ("/analytics/1/mercado", "/analytics/1/mercado/share",
                 "/analytics/1/mercado/regional", "/analytics/1/mercado/ranking"):
        chamar("GET", rota)
    dt = time.time() - t
    checar(f"bateria de mercado responde rapido ({dt:.2f}s)", dt < 8.0, round(dt, 2), "<8s")

    t = time.time()
    chamar("GET", f"/analytics/1/preco?periodo_ini={INI}&periodo_fim={FIM}")
    dt = time.time() - t
    checar(f"preco responde rapido ({dt:.2f}s)", dt < 8.0, round(dt, 2), "<8s")


def main():
    print("=" * 64)
    print("  VERIFICACAO DA ETAPA 4 — estoque, DDE, capital, mercado, share, preco")
    print("=" * 64)

    st, _ = chamar("GET", "/analytics/1/disponibilidade")
    if st != 200:
        print("\n  API nao respondeu. Suba o backend antes de rodar este teste.")
        return 1

    con = sqlite3.connect(DB)
    try:
        teste_perfis(con)
        teste_dde(con)
        teste_classificacao(con)
        teste_zumbi_capital(con)
        teste_simulador()
        teste_matriz_estoque()
        teste_mercado_share(con)
        teste_regional_ranking()
        teste_cliente_vs_mercado(con)
        teste_ponte(con)
        teste_preco(con)
        teste_isolamento()
        teste_filtros()
        teste_performance()
    finally:
        con.close()

    print("\n" + "=" * 64)
    print(f"  {_ok} passaram | {_falha} falharam")
    if _erros:
        print("\n  Falhas:")
        for e in _erros:
            print(f"   - {e}")
    print("=" * 64)
    return 1 if _falha else 0


if __name__ == "__main__":
    sys.exit(main())
