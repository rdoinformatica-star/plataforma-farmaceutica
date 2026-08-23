"""Sugestao de combos, ajuste de preco e escoamento de estoque.

Tres perguntas comerciais que se cruzam:

  1. Que produtos fazem sentido vender juntos?
  2. Que produtos precisam de ajuste de preco para ficarem competitivos?
  3. Como escoar o estoque parado do cliente sem so dar desconto?

A liga entre as tres e a AFINIDADE observada: quais produtos os mesmos PDVs
ja compram juntos. Isso vem do dado (co-ocorrencia real no sell-out), nao de
uma tabela de "produtos que combinam" escrita a mao — que seria opiniao
disfarcada de analise.

Sobre "uso continuo": nao existe flag de cronico na base. O que existe e
RECORRENCIA — em quantos meses do periodo o PDV medio recompra aquele SKU.
Um anti-hipertensivo e recomprado quase todo mes; um antigripal nao. A
recorrencia e medida, nao assumida, e vem explicita em cada combo.

Nenhuma sugestao daqui e uma previsao de venda. Sao pares que a base mostra
que andam juntos, com o tamanho do estoque parado ao lado — a decisao
comercial (e o desconto) continua sendo do usuario.
"""
import sqlite3
from collections import defaultdict

from . import estoque as estoque_mod
from . import preco as preco_mod
from .contexto import carregar
from .formulas import Calculo
from .periodo import contar_meses

# Foco da consulta. Muda QUAIS produtos entram como "carga" do combo —
# nunca muda a forma de calcular a afinidade.
FOCOS = ("geral", "criticos", "zumbi", "misto", "giro_rapido")

# Piso de PDVs em comum para um par virar sugestao. Abaixo disso a afinidade
# e coincidencia: 2 PDVs comprarem os mesmos 2 produtos nao e um padrao.
MIN_PDVS_PAR = 15

# Lift = quantas vezes mais provavel comprar B dado que comprou A, contra a
# taxa geral de B. Abaixo de 1 os produtos se evitam; 1,2 e o piso para o
# par dizer alguma coisa alem do acaso.
MIN_LIFT = 1.2


def _sem(motivo: str) -> dict:
    return {"disponivel": False, "motivo": motivo}


def _cesta_por_pdv(con: sqlite3.Connection, dist_ids: list[int], ini: int, fim: int,
                   uf: str | None) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Devolve (pdv -> produtos comprados, produto -> meses com venda).

    Le o grao bruto uma vez so e monta as duas estruturas juntas: as duas
    varreriam a mesma tabela, e ela tem milhoes de linhas.
    """
    marca = ",".join("?" * len(dist_ids))
    filtro = " AND pdv_id IN (SELECT id FROM dim_pdv WHERE uf = ?)" if uf else ""
    params = list(dist_ids) + [ini, fim] + ([uf] if uf else [])

    cesta: dict[int, set[int]] = defaultdict(set)
    meses: dict[int, set[int]] = defaultdict(set)
    for pdv_id, produto_id, periodo in con.execute(
        f"SELECT pdv_id, produto_id, periodo FROM v_vendas"
        f" WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?{filtro}",
        params):
        if pdv_id is not None:
            cesta[pdv_id].add(produto_id)
        meses[produto_id].add(periodo)
    return cesta, meses


def _recorrencia(con: sqlite3.Connection, dist_ids: list[int], ini: int, fim: int,
                 uf: str | None) -> dict[int, float]:
    """Em quantos meses do periodo o PDV medio recompra cada SKU, em 0-1.

    Perto de 1 = recompra quase todo mes (perfil de uso continuo).
    Perto de 0 = compra pontual, sazonal ou de giro esporadico.
    """
    n_meses = contar_meses(ini, fim) or 1
    marca = ",".join("?" * len(dist_ids))
    filtro = " AND pdv_id IN (SELECT id FROM dim_pdv WHERE uf = ?)" if uf else ""
    params = list(dist_ids) + [ini, fim] + ([uf] if uf else [])
    saida: dict[int, float] = {}
    for produto_id, n_pares, n_pdvs in con.execute(
        f"""SELECT produto_id, count(*), count(DISTINCT pdv_id) FROM (
                SELECT DISTINCT produto_id, pdv_id, periodo FROM v_vendas
                 WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?{filtro}
            ) GROUP BY produto_id""", params):
        if n_pdvs:
            # media de meses distintos por PDV, normalizada pelo periodo
            saida[produto_id] = min(1.0, (n_pares / n_pdvs) / n_meses)
    return saida


def afinidade(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
              uf: str | None = None, min_pdvs: int = MIN_PDVS_PAR,
              min_lift: float = MIN_LIFT, top_n: int = 100) -> dict:
    """Pares de produtos que os mesmos PDVs compram juntos, com lift.

    lift(A,B) = P(B | comprou A) / P(B). Acima de 1 os dois andam juntos mais
    do que o acaso explicaria; abaixo de 1 se evitam (tipico de produtos que
    competem entre si — mesma molecula, dosagens diferentes).
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return _sem(disp.motivo_indisponivel)
    if uf is not None and not disp.tem_uf:
        return _sem("Este cliente nao tem UF de PDV resolvida nos dados importados.")

    cesta, _ = _cesta_por_pdv(con, disp.distribuidor_ids, ini, fim, uf)
    if not cesta:
        return _sem("Nenhum PDV comprador neste periodo.")

    total_pdvs = len(cesta)
    freq: dict[int, int] = defaultdict(int)
    par: dict[tuple[int, int], int] = defaultdict(int)
    for produtos in cesta.values():
        ordenados = sorted(produtos)
        for p in ordenados:
            freq[p] += 1
        # PDV com mix enorme geraria milhares de pares e dominaria a contagem;
        # na base real o teto de mix e ~30 SKUs, entao nao ha corte artificial.
        for i, a in enumerate(ordenados):
            for b in ordenados[i + 1:]:
                par[(a, b)] += 1

    nomes = dict(con.execute("SELECT id, nome_canonico FROM dim_product"))
    pares = []
    for (a, b), n_ambos in par.items():
        if n_ambos < min_pdvs:
            continue
        # lift simetrico: P(A e B) / (P(A) x P(B))
        p_a, p_b = freq[a] / total_pdvs, freq[b] / total_pdvs
        p_ab = n_ambos / total_pdvs
        lift = p_ab / (p_a * p_b) if p_a and p_b else 0.0
        if lift < min_lift:
            continue
        pares.append({
            "produto_a_id": a, "produto_a": nomes.get(a, f"produto {a}"),
            "produto_b_id": b, "produto_b": nomes.get(b, f"produto {b}"),
            "pdvs_ambos": n_ambos,
            "pdvs_a": freq[a], "pdvs_b": freq[b],
            "confianca_a_para_b": n_ambos / freq[a] * 100 if freq[a] else 0.0,
            "confianca_b_para_a": n_ambos / freq[b] * 100 if freq[b] else 0.0,
            "lift": lift,
        })
    pares.sort(key=lambda x: (-x["lift"], -x["pdvs_ambos"]))

    return {
        "disponivel": True, "uf": uf,
        "total_pdvs": total_pdvs,
        "n_pares": len(pares),
        "itens": pares[:top_n],
        "calculo": Calculo(
            formula=("lift(A,B) = P(A e B) / (P(A) x P(B)), sobre PDVs distintos. "
                     "confianca(A->B) = PDVs com os dois / PDVs com A."),
            valores={"PDVs na base": total_pdvs, "pares acima do piso": len(pares),
                     "piso de PDVs em comum": min_pdvs, "lift minimo": min_lift},
            premissas=[
                "Co-ocorrencia NAO e causa: os dois produtos aparecerem no mesmo "
                "PDV nao prova que um puxa o outro. Pode ser o perfil da loja.",
                f"Pares com menos de {min_pdvs} PDVs em comum ficam de fora — "
                f"abaixo disso a afinidade e coincidencia.",
                "Lift abaixo de 1 (produtos que se evitam) nao entra na lista: "
                "costuma ser canibalizacao entre dosagens da mesma molecula.",
                "A janela e a selecionada na tela; PDV que comprou A em janeiro e "
                "B em julho conta como 'ambos' — nao e cesta do mesmo pedido.",
            ] + ([f"Recorte: so PDVs do estado {uf}."] if uf else []),
        ).como_dict(),
    }


def _perfil_estoque(con: sqlite3.Connection, client_id: int, ini: int,
                    fim: int) -> dict[int, dict]:
    """Estoque por produto, agregando filiais. Vazio se o cliente nao importou
    estoque — os combos continuam funcionando, so perdem a camada de escoamento."""
    pos = estoque_mod.posicao(con, client_id, ini, fim, limite=1000000)
    if not pos.get("disponivel"):
        return {}
    por_produto: dict[int, dict] = {}
    for i in pos["itens"]:
        d = por_produto.setdefault(i["produto_id"], {
            "estoque_un": 0.0, "valor": 0.0, "dde": None, "classificacao": None})
        d["estoque_un"] += i["estoque_disp_un"]
        d["valor"] += i["valor_estoque"]
        # Entre filiais fica o PIOR caso: e o que define o risco de vencimento.
        if i["dde"] is not None and (d["dde"] is None or i["dde"] > d["dde"]):
            d["dde"] = i["dde"]
        ordem = ["SAUDAVEL", "ATENCAO", "ALTO", "CRITICO", "ZUMBI", "INDEFINIDO"]
        atual, novo = d["classificacao"], i["classificacao"]
        if atual is None or (novo in ordem and atual in ordem
                             and ordem.index(novo) > ordem.index(atual)):
            d["classificacao"] = novo
    return por_produto


def sugerir_combos(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
                   foco: str = "geral", uf: str | None = None,
                   max_acompanhantes: int = 2, top_n: int = 20,
                   min_pdvs: int = MIN_PDVS_PAR, min_lift: float = MIN_LIFT) -> dict:
    """Monta combos: um produto PUXADOR (alta cobertura, gira) + acompanhantes.

    O acompanhante e escolhido por afinidade real com o puxador, e o foco
    decide que tipo de acompanhante interessa:

      geral       -> maior lift, seja qual for o estoque
      criticos    -> acompanhantes com DDE 180-365 dias
      zumbi       -> acompanhantes com DDE > 365 dias ou sem giro
      misto       -> puxador saudavel + acompanhante parado (o pacote que
                     escoa capital sem so dar desconto)
      giro_rapido -> so produtos de giro alto dos dois lados, para volume

    O puxador e sempre o de MAIOR cobertura do par: e ele que ja esta no PDV
    e serve de porta de entrada.
    """
    if foco not in FOCOS:
        raise ValueError(f"foco invalido: {foco}. Use um de: {', '.join(FOCOS)}.")

    af = afinidade(con, client_id, ini, fim, uf=uf, min_pdvs=min_pdvs,
                   min_lift=min_lift, top_n=100000)
    if not af.get("disponivel"):
        return af

    disp = carregar(con, client_id)
    estoque = _perfil_estoque(con, client_id, ini, fim)
    recorr = _recorrencia(con, disp.distribuidor_ids, ini, fim, uf)
    tem_estoque = bool(estoque)
    if foco in ("criticos", "zumbi", "misto") and not tem_estoque:
        return _sem(
            f"O foco '{foco}' depende do arquivo de estoque do cliente, que ainda "
            f"nao foi importado. Os focos 'geral' e 'giro_rapido' funcionam so com "
            f"sell-out.")

    ALVO_CLASSE = {"criticos": {"CRITICO"}, "zumbi": {"ZUMBI"},
                   "misto": {"CRITICO", "ZUMBI", "ALTO"}}
    LEVES = {"SAUDAVEL", "ATENCAO"}

    def parado(pid: int) -> bool:
        c = (estoque.get(pid) or {}).get("classificacao")
        return c in {"ALTO", "CRITICO", "ZUMBI"}

    # Um acompanhante por puxador nao basta (o usuario pediu pacotes); junta
    # os pares por puxador e escolhe os melhores acompanhantes de cada um.
    por_puxador: dict[int, list[dict]] = defaultdict(list)
    for p in af["itens"]:
        # Puxador = o de maior alcance; e ele que abre a porta do PDV.
        if p["pdvs_a"] >= p["pdvs_b"]:
            puxador, acomp = ("a", "b")
        else:
            puxador, acomp = ("b", "a")
        pid_pux, pid_ac = p[f"produto_{puxador}_id"], p[f"produto_{acomp}_id"]

        if foco in ALVO_CLASSE:
            classe_ac = (estoque.get(pid_ac) or {}).get("classificacao")
            if classe_ac not in ALVO_CLASSE[foco]:
                continue
            if foco == "misto":
                # O pacote misto so faz sentido se o puxador NAO estiver parado
                # tambem — senao e so juntar dois problemas.
                if (estoque.get(pid_pux) or {}).get("classificacao") not in LEVES:
                    continue
        elif foco == "giro_rapido":
            if tem_estoque and (parado(pid_pux) or parado(pid_ac)):
                continue
            # sem estoque importado, "giro rapido" cai na recorrencia observada
            if not tem_estoque and recorr.get(pid_ac, 0) < 0.3:
                continue

        est_ac = estoque.get(pid_ac, {})
        por_puxador[pid_pux].append({
            "produto_id": pid_ac,
            "produto": p[f"produto_{acomp}"],
            "pdvs_ambos": p["pdvs_ambos"],
            "cobertura_pdvs": p[f"pdvs_{acomp}"],
            "lift": p["lift"],
            "confianca_pct": p[f"confianca_{puxador}_para_{acomp}"],
            "recorrencia": recorr.get(pid_ac),
            "uso_continuo": (recorr.get(pid_ac) or 0) >= 0.5,
            "dde": est_ac.get("dde"),
            "classe_estoque": est_ac.get("classificacao"),
            "estoque_un": est_ac.get("estoque_un"),
            "estoque_valor": est_ac.get("valor"),
            "_pux_pdvs": p[f"pdvs_{puxador}"],
            "_pux_nome": p[f"produto_{puxador}"],
        })

    combos = []
    for pid_pux, acomps in por_puxador.items():
        acomps.sort(key=lambda x: (-x["lift"], -x["pdvs_ambos"]))
        escolhidos = acomps[:max_acompanhantes]
        est_pux = estoque.get(pid_pux, {})
        capital = sum(a["estoque_valor"] or 0.0 for a in escolhidos)
        combos.append({
            "puxador_id": pid_pux,
            "puxador": escolhidos[0]["_pux_nome"],
            "puxador_cobertura_pdvs": escolhidos[0]["_pux_pdvs"],
            "puxador_dde": est_pux.get("dde"),
            "puxador_classe_estoque": est_pux.get("classificacao"),
            "puxador_recorrencia": recorr.get(pid_pux),
            "acompanhantes": [
                {k: v for k, v in a.items() if not k.startswith("_")}
                for a in escolhidos],
            "n_acompanhantes": len(escolhidos),
            "lift_medio": sum(a["lift"] for a in escolhidos) / len(escolhidos),
            "capital_parado_no_combo": capital,
            "tem_uso_continuo": any(a["uso_continuo"] for a in escolhidos),
        })

    # Ordena por capital destravado quando o foco e escoamento; por forca da
    # associacao quando e prospeccao pura.
    if foco in ("criticos", "zumbi", "misto"):
        combos.sort(key=lambda c: (-c["capital_parado_no_combo"], -c["lift_medio"]))
    else:
        combos.sort(key=lambda c: (-c["lift_medio"], -c["puxador_cobertura_pdvs"]))

    ROTULO_FOCO = {
        "geral": "todos os pares acima do piso de afinidade",
        "criticos": "acompanhantes com estoque critico (DDE 180-365 dias)",
        "zumbi": "acompanhantes com estoque zumbi (DDE acima de 365 dias)",
        "misto": "puxador saudavel + acompanhante de estoque parado",
        "giro_rapido": "so produtos de giro alto dos dois lados",
    }
    return {
        "disponivel": True, "foco": foco, "uf": uf,
        "tem_estoque": tem_estoque,
        "total": len(combos),
        "capital_parado_alcancado": sum(c["capital_parado_no_combo"] for c in combos),
        "itens": combos[:top_n],
        "calculo": Calculo(
            formula=("puxador = produto de maior cobertura do par; acompanhante = "
                     "maior lift com ele dentro do foco escolhido. "
                     "recorrencia = meses distintos com compra por PDV / meses do "
                     "periodo (proxy de uso continuo)."),
            valores={"foco": ROTULO_FOCO[foco],
                     "combos montados": len(combos),
                     "PDVs na base": af["total_pdvs"],
                     "capital parado alcancado": round(
                         sum(c["capital_parado_no_combo"] for c in combos), 2),
                     "estoque importado": "sim" if tem_estoque else "nao"},
            premissas=[
                "Nao e previsao de venda: sao pares que a base mostra que andam "
                "juntos, com o estoque parado ao lado. O desconto e a decisao "
                "comercial continuam com o usuario.",
                "'Uso continuo' e medido por RECORRENCIA (recompra mes a mes), nao "
                "por classificacao terapeutica — a base nao tem essa flag.",
                "O puxador e o produto de maior cobertura do par, nao "
                "necessariamente o de maior faturamento.",
                "Entre filiais, o DDE do combo usa o PIOR caso — e ele que define "
                "risco de vencimento.",
                "Combos diferentes podem repetir o mesmo acompanhante: o capital "
                "parado alcancado NAO e a soma simples dos combos.",
            ] + ([f"Recorte: so PDVs do estado {uf}."] if uf else []),
        ).como_dict(),
    }


def ajuste_preco(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
                 uf: str | None = None, limite_alerta_pct: float = 8.0,
                 top_n: int = 30) -> dict:
    """Onde o preco do cliente esta acima dos outros distribuidores, e quanto
    cairia para chegar a paridade.

    So sugere ajuste para BAIXO e so onde ha volume dos dois lados. Produto
    caro que ja ganha share nao vira sugestao — preco alto com performance boa
    e margem, nao problema.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return _sem(disp.motivo_indisponivel)

    comp = preco_mod.preco_vs_concorrentes(
        con, disp.distribuidor_ids, ini, fim, uf=uf, top_n=100000,
        limite_alerta_pct=limite_alerta_pct)
    if not comp.get("disponivel"):
        return comp

    estoque = _perfil_estoque(con, client_id, ini, fim)
    itens = []
    for i in comp["itens"]:
        dif = i["diferenca_pct"]
        if dif is None or i["posicao"] != "ACIMA":
            continue
        # Ajuste para paridade: preco_alvo / preco_atual - 1, em %.
        ajuste = (i["preco_outros"] / i["preco_cliente"] - 1) * 100
        est = estoque.get(i["produto_id"], {})
        # Receita cedida se o volume atual for mantido ao preco novo. E o
        # custo do ajuste — nao a "perda", porque o objetivo e ganhar volume.
        custo = i["unidades_cliente"] * (i["preco_cliente"] - i["preco_outros"])
        itens.append({
            "produto_id": i["produto_id"], "produto": i["produto"],
            "preco_cliente": i["preco_cliente"],
            "preco_outros": i["preco_outros"],
            "diferenca_pct": dif,
            "ajuste_sugerido_pct": ajuste,
            "preco_alvo": i["preco_outros"],
            "unidades_cliente": i["unidades_cliente"],
            "faturamento_cliente": i["faturamento_cliente"],
            "receita_cedida_no_volume_atual": custo,
            "dde": est.get("dde"),
            "classe_estoque": est.get("classificacao"),
            "estoque_valor": est.get("valor"),
            "prioridade": ("ALTA" if est.get("classificacao") in {"CRITICO", "ZUMBI"}
                           else "MEDIA" if dif > limite_alerta_pct * 2 else "BAIXA"),
        })
    itens.sort(key=lambda x: (-x["diferenca_pct"], -x["faturamento_cliente"]))

    return {
        "disponivel": True, "uf": uf,
        "limite_alerta_pct": limite_alerta_pct,
        "n_produtos": len(itens),
        "n_sem_volume": len(comp.get("sem_volume", [])),
        "receita_cedida_total": sum(i["receita_cedida_no_volume_atual"] for i in itens),
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula=("ajuste = preco medio dos outros distribuidores / preco do "
                     "cliente - 1. receita cedida = unidades atuais x (preco atual "
                     "- preco alvo)."),
            valores={"produtos acima do mercado": len(itens),
                     "limite para considerar 'acima'": f"{limite_alerta_pct}%",
                     "produtos sem volume suficiente": len(comp.get("sem_volume", [])),
                     "receita cedida no volume atual": round(
                         sum(i["receita_cedida_no_volume_atual"] for i in itens), 2)},
            premissas=[
                "Preco medio = faturamento / unidades no periodo. Nao e tabela de "
                "preco: mistura condicoes comerciais, bonificacao e mix de embalagem.",
                "A comparacao e com os DEMAIS distribuidores da mesma base, no mesmo "
                "elo (sell-out). Nao e preco de varejo nem preco de fabrica.",
                "A 'receita cedida' assume volume constante — e o custo do ajuste no "
                "cenario em que nada mais muda, nao uma projecao. O objetivo do "
                "ajuste e justamente mudar o volume.",
                "Produto abaixo do mercado nao entra: a tela sugere reducao, nao "
                "aumento. Subir preco tem risco que o dado sozinho nao mede.",
                "Prioridade ALTA marca produto caro E com estoque parado — ali o "
                "ajuste ataca dois problemas de uma vez.",
            ] + ([f"Recorte: so PDVs do estado {uf}."] if uf else []),
        ).como_dict(),
    }


_MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
          "jul", "ago", "set", "out", "nov", "dez"]

# Kit exige afinidade mais forte que o combo par-a-par: um kit e um
# compromisso maior (3+ produtos juntos tem que fazer sentido entre TODOS os
# pares, nao so cada um com um produto central).
MIN_LIFT_KIT = 1.5


def kits_tematicos(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
                   uf: str | None = None, min_lift: float = MIN_LIFT_KIT,
                   min_pdvs: int = MIN_PDVS_PAR, tamanho_min: int = 3,
                   tamanho_max: int = 6, top_n: int = 15) -> dict:
    """Kits de produtos que a base mostra sendo comprados juntos como GRUPO —
    o mais proximo de um "combo pronto" (tipo "combo inverno", "combo
    imunidade") que da para provar com dado: todo par dentro do kit tem
    afinidade forte entre si, nao so cada produto com um puxador central
    (que e o que sugerir_combos() ja faz, em formato estrela).

    ESTE SISTEMA NAO TENTA ADIVINHAR O TEMA. Chamar um grupo de "combo
    inverno" a partir do nome dos produtos seria opiniao disfarcada de dado —
    a base nao tem essa marcacao. Em vez disso, mostra QUANDO o kit vende
    mais (mes do ano, sobre todo o historico do cliente) para o usuario
    reconhecer o padrao com o proprio conhecimento de negocio.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return _sem(disp.motivo_indisponivel)
    if uf is not None and not disp.tem_uf:
        return _sem("Este cliente nao tem UF de PDV resolvida nos dados importados.")

    af = afinidade(con, client_id, ini, fim, uf=uf, min_pdvs=min_pdvs,
                   min_lift=min_lift, top_n=100000)
    if not af.get("disponivel"):
        return af
    if not af["itens"]:
        return _sem(
            f"Nenhum par de produtos com lift >= {min_lift} e pelo menos "
            f"{min_pdvs} PDVs em comum neste período — sem base para montar kits.")

    # Adjacencia: produto -> {produto vizinho: lift}. So pares que passaram
    # no piso de afinidade() entram aqui.
    adj: dict[int, dict[int, float]] = defaultdict(dict)
    nomes: dict[int, str] = {}
    for p in af["itens"]:
        a, b = p["produto_a_id"], p["produto_b_id"]
        adj[a][b] = p["lift"]
        adj[b][a] = p["lift"]
        nomes[a] = p["produto_a"]
        nomes[b] = p["produto_b"]

    def afinidade_media(grupo: set[int]) -> float:
        pares = [(x, y) for x in grupo for y in grupo if x < y]
        return sum(adj[x][y] for x, y in pares) / len(pares) if pares else 0.0

    # Cliques gulosas: cada produto (do mais conectado ao menos) vira semente
    # e cresce enquanto houver um vizinho ligado a TODOS os membros atuais —
    # sempre escolhendo o de maior afinidade media com o grupo, nao o primeiro.
    cliques: list[set[int]] = []
    for semente in sorted(adj, key=lambda p: -len(adj[p])):
        grupo = {semente}
        while len(grupo) < tamanho_max:
            candidatos = [p for p in adj[semente]
                         if p not in grupo and all(p in adj[m] for m in grupo)]
            if not candidatos:
                break
            melhor = max(candidatos,
                        key=lambda p: sum(adj[m][p] for m in grupo) / len(grupo))
            grupo.add(melhor)
        if len(grupo) >= tamanho_min:
            cliques.append(grupo)

    # Deduplica: cliques que compartilham a maioria dos produtos sao o mesmo
    # kit visto de sementes diferentes. Mede por Jaccard; fica so o maior/
    # mais forte de cada familia.
    cliques.sort(key=lambda c: (-len(c), -afinidade_media(c)))
    finais: list[set[int]] = []
    for c in cliques:
        if any(len(c & f) / len(c | f) > 0.5 for f in finais):
            continue
        finais.append(c)
    finais = finais[:top_n]

    periodo_min, periodo_max = disp.periodo_min, disp.periodo_max
    n_anos = ((periodo_max // 100) - (periodo_min // 100) + 1
             if periodo_min and periodo_max else 0)
    marca_dist = ",".join("?" * len(disp.distribuidor_ids))

    kits = []
    for grupo in finais:
        ids = list(grupo)
        marca = ",".join("?" * len(ids))

        # Sazonalidade sobre TODO o historico do cliente — o periodo
        # selecionado na tela costuma ser curto demais para dizer algo sobre
        # sazonalidade (precisa de mais de uma volta do calendario).
        por_mes = {int(m): float(v) for m, v in con.execute(
            f"""SELECT periodo % 100, sum(valor) FROM v_vendas_mensal
                 WHERE distribuidor_id IN ({marca_dist}) AND produto_id IN ({marca})
                   AND periodo BETWEEN ? AND ?
                 GROUP BY periodo % 100""",
            disp.distribuidor_ids + ids + [periodo_min, periodo_max])}
        total_historico = sum(por_mes.values())
        picos = sorted(por_mes, key=lambda m: -por_mes[m])[:3] if por_mes else []

        # Faturamento no periodo selecionado (o que esta na tela agora).
        fat_periodo = con.execute(
            f"""SELECT coalesce(sum(valor),0) FROM v_vendas_mensal
                 WHERE distribuidor_id IN ({marca_dist}) AND produto_id IN ({marca})
                   AND periodo BETWEEN ? AND ?""",
            disp.distribuidor_ids + ids + [ini, fim]).fetchone()[0]

        kits.append({
            "produtos": sorted(
                [{"produto_id": pid, "produto": nomes[pid]} for pid in ids],
                key=lambda x: x["produto"]),
            "tamanho": len(ids),
            "afinidade_media": afinidade_media(grupo),
            "faturamento_periodo_selecionado": float(fat_periodo),
            "faturamento_total_historico": total_historico,
            "picos_mes": picos,
            "picos_mes_nome": [_MESES[m - 1] for m in picos],
            "distribuicao_por_mes": [
                {"mes": m, "mes_nome": _MESES[m - 1], "valor": por_mes.get(m, 0.0)}
                for m in range(1, 13)],
        })

    kits.sort(key=lambda k: -k["afinidade_media"])

    return {
        "disponivel": True,
        "uf": uf,
        "n_kits": len(kits),
        "n_anos_historico": n_anos,
        "periodo_historico": {"min": periodo_min, "max": periodo_max},
        "itens": kits,
        "calculo": Calculo(
            formula=(f"kit = conjunto de {tamanho_min}+ produtos onde TODO par "
                     f"tem lift >= {min_lift} entre si (nao so cada um com um "
                     "produto central); sazonalidade = faturamento do kit somado "
                     "por mes-do-ano, sobre todo o historico disponivel do cliente."),
            valores={"kits encontrados": len(kits), "lift minimo exigido": min_lift,
                     "tamanho do kit": f"{tamanho_min} a {tamanho_max} produtos",
                     "historico usado p/ sazonalidade": f"{periodo_min}-{periodo_max}",
                     "anos de historico": n_anos},
            premissas=[
                "NAO TENTA ADIVINHAR UM TEMA. O sistema não sabe se um kit é "
                "\"combo inverno\" ou \"combo imunidade\" — a base não tem essa "
                "marcação. Mostra os produtos e QUANDO vendem mais; nomear o "
                "padrão é do usuário, com o conhecimento de negócio que o "
                "dado sozinho não tem.",
                "Co-ocorrência não é causa: produtos no mesmo kit podem estar "
                "juntos por perfil da loja, não por uma relação real entre eles.",
                f"Com {n_anos} ano(s) de histórico, um \"pico\" de mês pode ser "
                f"um evento pontual (campanha, ruptura de concorrente), não "
                f"sazonalidade de verdade — sazonalidade confiável pede pelo "
                f"menos 2 voltas do calendário.",
                "Kits que compartilham a maioria dos produtos entre si são "
                "unificados (fica só o maior/mais forte), para não repetir "
                "essencialmente o mesmo grupo com nomes diferentes.",
                "Exige afinidade mais forte que os combos par-a-par "
                f"(lift >= {min_lift} vs. {MIN_LIFT} do combo comum): um "
                "compromisso de 3+ produtos juntos precisa de uma base mais "
                "sólida que um par só.",
            ] + ([f"Recorte: só PDVs do estado {uf}."] if uf else []),
        ).como_dict(),
    }
