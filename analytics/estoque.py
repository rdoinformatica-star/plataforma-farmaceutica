"""Inteligencia de estoque: DDE, cobertura, capital parado, simulacao.

Fonte: fact_inventory (v_estoque) — export .xlsx do proprio distribuidor, uma
linha por SKU x filial. E uma FOTO de uma data, nao uma serie historica: nao
da para calcular evolucao de estoque nem giro historico com uma foto so.

Achados da base real que mudam o que da para calcular (documentados aqui
porque nenhum deles era assumivel de antemao):

  - So o cliente que importou estoque tem esta analise. Nao ha estoque
    "do mercado" nem estoque inferido de sell-out.

  - Nem toda filial traz posicao fisica. No export de 20/08/2026 a filial RJ
    veio com estoque completo e a ES so com media de venda (sinal de operacao
    cross-dock a partir do CD do RJ). Linhas sem posicao ficam fora dos
    calculos de DDE/capital e aparecem contadas em "sem_posicao" — nunca
    somadas como estoque zero, que faria o capital parado parecer menor do
    que e.

  - A propria fonte ja traz cobertura_dias. Conferido em 127/127 linhas:
        cobertura_dias = estoque_disp_un / media_venda_un * 30
    Ou seja: media_venda_un e MENSAL e a fonte usa mes comercial de 30 dias.
    Por isso a media da fonte e dividida por 30 (e nao por 30,44) quando
    convertida para venda diaria — para bater exatamente com o numero que o
    distribuidor ve no proprio sistema.

  - O valor do estoque (estoque_disp_x100) e o campo autoritativo. O
    custo_rep_x100 vem arredondado em centavos na origem, entao
    un x custo_rep diverge do valor em ate ~0,3%. Capital parado usa sempre
    o valor, nunca un x custo.
"""
import sqlite3
from typing import Any

from .formulas import Calculo
from .periodo import contar_meses

# Mes comercial da fonte. Ver docstring: e o divisor que reproduz o
# cobertura_dias do proprio distribuidor.
DIAS_MES = 30.0

# (limite_inferior, limite_superior_exclusivo, rotulo). None = sem teto.
FAIXAS_PADRAO: list[tuple[float, float | None, str]] = [
    (0, 60, "SAUDAVEL"),
    (60, 120, "ATENCAO"),
    (120, 180, "ALTO"),
    (180, 365, "CRITICO"),
    (365, None, "ZUMBI"),
]

def _acima_de(item: dict, dias: float) -> bool:
    """Conta como 'estoque acima de N dias'. SKU sem venda entra (cobertura
    infinita e o caso extremo de estoque parado). SKU com devolucao liquida
    NAO entra: o DDE dele e indefinido, e empurra-lo para o lado do estoque
    parado inflaria o capital parado com um numero que a base nao sustenta.
    """
    if item["dde"] is not None:
        return item["dde"] > dias
    return item.get("motivo_dde_indefinido") == "sem_venda"


_INDISP_SEM_ESTOQUE = (
    "Este cliente nao possui arquivo de estoque importado. Importe o export "
    "de estoque do distribuidor para liberar DDE, capital parado e simulacao."
)


def _sem(motivo: str) -> dict:
    return {"disponivel": False, "motivo": motivo}


INDEFINIDO = "INDEFINIDO"


def _classificar(dias: float | None, faixas, motivo: str | None = None) -> str:
    """Sem venda -> DDE infinito. E o pior caso possivel (estoque que nao
    gira), entao cai na ultima faixa — nunca vira 'saudavel' por divisao por
    zero, e nunca vira Infinity no JSON.

    Media de venda negativa (devolucao liquida maior que a venda no periodo
    da origem) nao produz DDE com sentido: a propria fonte devolve cobertura
    negativa nesses casos (-2901 dias num SKU real). Fica INDEFINIDO em vez
    de ser empurrado para uma ponta ou outra da escala.
    """
    if motivo == "devolucao_liquida":
        return INDEFINIDO
    if dias is None:
        return faixas[-1][2]
    for ini, fim, rotulo in faixas:
        if dias >= ini and (fim is None or dias < fim):
            return rotulo
    return faixas[-1][2]


def _validar_faixas(faixas) -> list[tuple[float, float | None, str]]:
    if not faixas:
        raise ValueError("E preciso pelo menos uma faixa de cobertura.")
    norm = []
    for f in faixas:
        if len(f) != 3:
            raise ValueError("Cada faixa e (inicio, fim, rotulo); fim=None e 'sem teto'.")
        ini, fim, rotulo = f
        if fim is not None and fim <= ini:
            raise ValueError(f"Faixa invalida: fim ({fim}) deve ser maior que inicio ({ini}).")
        norm.append((float(ini), None if fim is None else float(fim), str(rotulo)))
    return norm


def _filiais_do_cliente(con: sqlite3.Connection, client_id: int) -> dict[str, int]:
    """Liga a filial do arquivo de estoque ao distribuidor do sell-out, por
    nome normalizado ('Emefarma RJ' -> 'EMEFARMA RJ'). Sem isso a velocidade
    de venda usada no DDE seria a do cliente inteiro (RJ+ES) contra um estoque
    que e so de uma praca — o que subestimaria o DDE.
    """
    filiais = [r[0] for r in con.execute(
        "SELECT DISTINCT filial FROM v_estoque WHERE client_id = ? AND filial IS NOT NULL",
        (client_id,))]
    dists = con.execute(
        "SELECT id, nome FROM dim_distribuidor WHERE client_id = ?", (client_id,)).fetchall()
    mapa = {}
    for f in filiais:
        alvo = f.strip().upper()
        for did, nome in dists:
            if (nome or "").strip().upper() == alvo:
                mapa[f] = did
                break
    return mapa


def perfil(con: sqlite3.Connection, client_id: int) -> dict:
    """O que existe de estoque para este cliente, antes de qualquer calculo."""
    total = con.execute(
        "SELECT count(*) FROM v_estoque WHERE client_id = ?", (client_id,)).fetchone()[0]
    if not total:
        return _sem(_INDISP_SEM_ESTOQUE)

    linha = con.execute(
        """SELECT count(*), count(estoque_disp_un), count(estoque_disp_x100),
                  count(media_venda_un), count(DISTINCT produto_id),
                  count(DISTINCT data_ref), min(data_ref), max(data_ref)
             FROM v_estoque WHERE client_id = ?""", (client_id,)).fetchone()
    n, com_un, com_valor, com_media, n_prod, n_datas, dmin, dmax = linha

    por_filial = []
    for f, nn, cu, cv, cm in con.execute(
        """SELECT filial, count(*), count(estoque_disp_un),
                  count(estoque_disp_x100), count(media_venda_un)
             FROM v_estoque WHERE client_id = ? GROUP BY filial ORDER BY filial""",
            (client_id,)):
        por_filial.append({
            "filial": f, "linhas": nn, "com_posicao": cu,
            "com_valor": cv, "com_media_venda": cm,
            "tem_posicao_fisica": cu > 0,
        })

    vinculo = _filiais_do_cliente(con, client_id)
    return {
        "disponivel": True,
        "linhas": n,
        "produtos": n_prod,
        "com_posicao": com_un,
        "sem_posicao": n - com_un,
        "com_valor": com_valor,
        "com_media_venda": com_media,
        "data_ref": dmax,
        "n_datas": n_datas,
        "eh_foto": n_datas <= 1,
        "por_filial": por_filial,
        "filiais_vinculadas": {k: v for k, v in vinculo.items()},
        "calculo": Calculo(
            formula="perfil = contagem direta das linhas de v_estoque do cliente",
            valores={"linhas": n, "com posicao fisica": com_un,
                     "sem posicao fisica": n - com_un, "data da foto": dmax},
            premissas=[
                "O estoque e uma foto de uma data, nao uma serie historica: "
                "nao da para calcular evolucao nem giro historico com ela.",
                "Linhas sem posicao fisica (estoque nulo na origem) sao contadas "
                "a parte e ficam fora de DDE e capital — nao viram estoque zero.",
            ] + ([] if n_datas <= 1 else
                 [f"Ha {n_datas} datas de foto; os calculos usam a mais recente ({dmax})."]),
        ).como_dict(),
    }


def velocidade_venda(con: sqlite3.Connection, distribuidor_ids: list[int],
                     ini: int, fim: int, *, produto_id: int | None = None) -> dict:
    """Velocidade media de venda no periodo selecionado, a partir do sell-out.

    E a alternativa "calculada" a media que vem no arquivo de estoque: usa a
    janela que o usuario escolheu, nao os ultimos 4 meses fixos da origem.
    """
    if not distribuidor_ids:
        return _sem("Cliente sem distribuidor vinculado.")
    marca = ",".join("?" * len(distribuidor_ids))
    where = [f"distribuidor_id IN ({marca})", "periodo BETWEEN ? AND ?"]
    params: list = list(distribuidor_ids) + [ini, fim]
    if produto_id is not None:
        where.append("produto_id = ?")
        params.append(produto_id)
    unidades = con.execute(
        f"SELECT coalesce(sum(unidades),0) FROM v_vendas_mensal WHERE {' AND '.join(where)}",
        params).fetchone()[0]

    meses = contar_meses(ini, fim)
    dias = meses * DIAS_MES
    return {
        "disponivel": True,
        "unidades": float(unidades),
        "meses": meses,
        "dias": dias,
        "un_por_mes": float(unidades) / meses if meses else 0.0,
        "un_por_dia": float(unidades) / dias if dias else 0.0,
        "calculo": Calculo(
            formula="velocidade diaria = unidades vendidas no periodo / (meses x 30)",
            valores={"unidades no periodo": round(float(unidades), 2),
                     "meses": meses, "dias considerados": dias,
                     "unidades/mes": round(float(unidades) / meses, 2) if meses else 0,
                     "unidades/dia": round(float(unidades) / dias, 2) if dias else 0},
            premissas=[
                f"Periodo usado: {ini} a {fim} ({meses} meses) — o mesmo "
                f"selecionado na tela, nao uma media arbitraria.",
                "Mes comercial de 30 dias, para bater com a cobertura que a "
                "propria fonte de estoque calcula.",
                "Unidades de sell-out (distribuidor -> PDV), que e o que "
                "consome o estoque do distribuidor.",
            ],
        ).como_dict(),
    }


def posicao(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
            faixas=None, base_velocidade: str = "fonte",
            filial: str | None = None, classe: str | None = None,
            limite: int = 500) -> dict:
    """Tabela principal de estoque: SKU, posicao, velocidade, DDE, classe, valor.

    base_velocidade:
      "fonte"     — usa media_venda_un do proprio arquivo (media da origem,
                    ultimos meses do sistema do distribuidor). Reproduz o
                    cobertura_dias que o distribuidor ve.
      "periodo"   — usa a velocidade calculada do sell-out na janela
                    selecionada. Responde "e no ritmo DESTE periodo?".
    Os dois DDE vem na resposta; base_velocidade so define qual classifica.

    classe filtra pela faixa de cobertura (SAUDAVEL, ATENCAO, ... , INDEFINIDO).
    O filtro e aplicado DEPOIS de classificar e ANTES do limite — senao a faixa
    so listaria o que coubesse nos N SKUs mais caros, e uma faixa inteira poderia
    aparecer vazia so por nao ter entrado no corte.
    """
    if base_velocidade not in ("fonte", "periodo"):
        raise ValueError("base_velocidade deve ser 'fonte' ou 'periodo'.")
    fx = _validar_faixas(faixas or FAIXAS_PADRAO)

    p = perfil(con, client_id)
    if not p["disponivel"]:
        return p
    if p["com_posicao"] == 0:
        return _sem(
            "O arquivo de estoque deste cliente nao trouxe posicao fisica em "
            "nenhuma filial (so media de venda). DDE e capital parado ficam "
            "indisponiveis — nao ha estoque para dividir.")

    data_ref = p["data_ref"]
    vinculo = _filiais_do_cliente(con, client_id)

    where = ["e.client_id = ?", "e.data_ref = ?", "e.estoque_disp_un IS NOT NULL"]
    params: list = [client_id, data_ref]
    if filial is not None:
        where.append("e.filial = ?")
        params.append(filial)

    # Sem LIMIT no SQL: a classe so existe depois de calcular o DDE, e cortar
    # antes faria o filtro de faixa enxergar so os SKUs mais caros. A foto de
    # estoque e pequena (centenas de linhas), entao ler tudo e barato.
    linhas = con.execute(
        f"""SELECT e.produto_id, e.filial, pr.apresentacao,
                   e.estoque_total_un, e.estoque_disp_un, e.estoque_disp_x100,
                   e.custo_rep_x100, e.media_venda_un, e.cobertura_dias
              FROM v_estoque e
              LEFT JOIN dim_product pr ON pr.id = e.produto_id
             WHERE {' AND '.join(where)}
             ORDER BY e.estoque_disp_x100 DESC""", params).fetchall()

    # Velocidade do periodo, por produto e por filial (cada filial tem o
    # sell-out do seu proprio distribuidor).
    vel_periodo: dict[tuple[int, str], float] = {}
    meses = contar_meses(ini, fim)
    dias_periodo = meses * DIAS_MES
    for fil, did in vinculo.items():
        for prod, un in con.execute(
            """SELECT produto_id, coalesce(sum(unidades),0) FROM v_vendas_mensal
                WHERE distribuidor_id = ? AND periodo BETWEEN ? AND ?
                GROUP BY produto_id""", (did, ini, fim)):
            vel_periodo[(prod, fil)] = float(un) / dias_periodo if dias_periodo else 0.0

    itens = []
    for (pid, fil, apres, e_tot, e_disp, e_val_x100, custo_x100,
         mv_un, cob_fonte) in linhas:
        e_disp = float(e_disp)
        valor = (e_val_x100 or 0) / 100.0

        # Media negativa = devolucao liquida maior que a venda. Nao vira DDE.
        mv = float(mv_un) if mv_un is not None else None
        vd_fonte = (mv / DIAS_MES) if (mv is not None and mv > 0) else None
        dde_fonte = (e_disp / vd_fonte) if vd_fonte else None

        vd_bruta = vel_periodo.get((pid, fil))
        vd_per = vd_bruta if (vd_bruta or 0) > 0 else None
        dde_per = (e_disp / vd_per) if vd_per else None

        if base_velocidade == "fonte":
            dde, mv_ref = dde_fonte, mv
        else:
            dde, mv_ref = dde_per, vd_bruta
        motivo_dde = None
        if dde is None:
            motivo_dde = ("devolucao_liquida" if (mv_ref is not None and mv_ref < 0)
                          else "sem_venda")
        itens.append({
            "produto_id": pid,
            "produto": apres or f"produto {pid}",
            "filial": fil,
            "estoque_total_un": float(e_tot) if e_tot is not None else None,
            "estoque_disp_un": e_disp,
            "valor_estoque": valor,
            "custo_reposicao": (custo_x100 or 0) / 100.0 if custo_x100 else None,
            "media_venda_mes_fonte": float(mv_un) if mv_un else None,
            "venda_dia_fonte": vd_fonte,
            "venda_dia_periodo": vd_per,
            "dde_fonte": dde_fonte,
            "dde_periodo": dde_per,
            "dde": dde,
            "cobertura_dias_origem": (None if cob_fonte is None or cob_fonte != cob_fonte
                                      or cob_fonte in (float("inf"), float("-inf"))
                                      else float(cob_fonte)),
            "classificacao": _classificar(dde, fx, motivo_dde),
            "sem_venda": motivo_dde == "sem_venda",
            "motivo_dde_indefinido": motivo_dde,
        })

    n_antes = len(itens)
    if classe:
        alvo = classe.strip().upper()
        rotulos = {r for _, _, r in fx} | {INDEFINIDO}
        if alvo not in rotulos:
            raise ValueError(
                f"Classe '{classe}' nao existe. Use uma de: {', '.join(sorted(rotulos))}.")
        itens = [i for i in itens if i["classificacao"] == alvo]
    itens = itens[:limite]

    return {
        "disponivel": True,
        "data_ref": data_ref,
        "base_velocidade": base_velocidade,
        "filial": filial,
        "classe": classe,
        "n_total_sem_filtro": n_antes,
        "itens": itens,
        "faixas": [{"de": a, "ate": b, "rotulo": r} for a, b, r in fx],
        "calculo": Calculo(
            formula=("DDE = estoque disponivel (un) / venda media diaria (un/dia); "
                     "venda diaria da fonte = media_venda_un / 30; "
                     "venda diaria do periodo = unidades do sell-out / (meses x 30)"),
            valores={"data da foto": data_ref, "SKUs listados": len(itens),
                     "base de velocidade": base_velocidade,
                     "periodo do sell-out": f"{ini}-{fim}"},
            premissas=[
                "Estoque disponivel (nao o total) — e o que a propria fonte usa "
                "no cobertura_dias dela; conferido em 127/127 linhas.",
                "media_venda_un do arquivo e MENSAL; dividida por 30 vira diaria.",
                "SKU sem venda no periodo fica com DDE indefinido e cai na pior "
                "faixa: estoque que nao gira e o pior caso, nao o melhor.",
                "A velocidade do periodo usa o sell-out do distribuidor da mesma "
                "filial — nao mistura pracas.",
            ],
        ).como_dict(),
    }


def resumo(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
           faixas=None, base_velocidade: str = "fonte",
           filial: str | None = None) -> dict:
    """Cards do dashboard de estoque."""
    fx = _validar_faixas(faixas or FAIXAS_PADRAO)
    pos = posicao(con, client_id, ini, fim, faixas=fx,
                  base_velocidade=base_velocidade, filial=filial, limite=1000000)
    if not pos["disponivel"]:
        return pos

    itens = pos["itens"]
    valor_total = sum(i["valor_estoque"] for i in itens)
    com_dde = [i for i in itens if i["dde"] is not None]
    cob_media = (sum(i["dde"] for i in com_dde) / len(com_dde)) if com_dde else None
    # Cobertura ponderada por valor: mais fiel ao capital do que a media simples.
    peso = sum(i["valor_estoque"] for i in com_dde)
    cob_ponderada = (sum(i["dde"] * i["valor_estoque"] for i in com_dde) / peso
                     if peso else None)

    def acima(dias: float) -> tuple[int, float]:
        sel = [i for i in itens if _acima_de(i, dias)]
        return len(sel), sum(i["valor_estoque"] for i in sel)

    n180, v180 = acima(180)
    n365, v365 = acima(365)
    n_indef = sum(1 for i in itens if i["classificacao"] == INDEFINIDO)

    por_classe: dict[str, dict] = {r: {"classe": r, "skus": 0, "valor": 0.0}
                                   for _, _, r in fx}
    for i in itens:
        c = por_classe.setdefault(i["classificacao"],
                                  {"classe": i["classificacao"], "skus": 0, "valor": 0.0})
        c["skus"] += 1
        c["valor"] += i["valor_estoque"]

    return {
        "disponivel": True,
        "data_ref": pos["data_ref"],
        "valor_total": valor_total,
        "skus_com_estoque": len(itens),
        "skus_sem_venda": sum(1 for i in itens if i.get("motivo_dde_indefinido") == "sem_venda"),
        "skus_dde_indefinido": n_indef,
        "cobertura_media_dias": cob_media,
        "cobertura_ponderada_dias": cob_ponderada,
        "skus_acima_180": n180, "valor_acima_180": v180,
        "skus_acima_365": n365, "valor_acima_365": v365,
        "por_classe": list(por_classe.values()),
        "calculo": Calculo(
            formula=("valor total = soma do estoque disponivel R$; "
                     "cobertura ponderada = soma(DDE x valor) / soma(valor)"),
            valores={"SKUs com estoque": len(itens),
                     "valor total": round(valor_total, 2),
                     "valor acima de 180 dias": round(v180, 2),
                     "valor acima de 365 dias": round(v365, 2),
                     "SKUs com DDE indefinido": n_indef},
            premissas=[
                "Valor do estoque = campo de valor da origem (custo de "
                "reposicao), nao preco de venda: e capital imobilizado, nao "
                "receita perdida.",
                "SKU sem venda entra em 'acima de' — estoque que nao gira e o "
                "caso mais grave, nao pode sumir da conta.",
                "SKU com devolucao liquida (media de venda negativa na origem) "
                "fica com DDE INDEFINIDO e fora das faixas — a fonte devolve "
                "cobertura negativa nesses casos, que nao e interpretavel.",
                "Media ponderada por valor aparece junto da simples porque a "
                "simples da o mesmo peso a um SKU de R$ 50 e a um de R$ 80 mil.",
            ],
        ).como_dict(),
    }


def zumbi(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
          limite_dias: float = 365, faixas=None,
          base_velocidade: str = "fonte", filial: str | None = None,
          top_n: int = 50) -> dict:
    """SKUs com cobertura acima do limite, do maior estoque para o menor."""
    pos = posicao(con, client_id, ini, fim, faixas=faixas or FAIXAS_PADRAO,
                  base_velocidade=base_velocidade, filial=filial, limite=1000000)
    if not pos["disponivel"]:
        return pos

    sel = [i for i in pos["itens"] if _acima_de(i, limite_dias)]
    sel.sort(key=lambda i: i["valor_estoque"], reverse=True)
    total = sum(i["valor_estoque"] for i in sel)
    return {
        "disponivel": True,
        "limite_dias": limite_dias,
        "n_skus": len(sel),
        "valor_total": total,
        "itens": sel[:top_n],
        "calculo": Calculo(
            formula=f"estoque zumbi = SKUs com DDE > {limite_dias} dias (ou sem venda)",
            valores={"SKUs": len(sel), "valor imobilizado": round(total, 2),
                     "limite usado": limite_dias},
            premissas=[
                "Limite configuravel — nao e uma regra fixa do sistema.",
                "SKU sem nenhuma venda no periodo entra na lista: cobertura "
                "infinita e o caso extremo de estoque parado.",
                "E um indicador de capital imobilizado, nao uma instrucao de "
                "descarte: pode haver sazonalidade, compra recente ou "
                "obrigacao contratual que o dado nao mostra.",
            ],
        ).como_dict(),
    }


def capital_parado(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
                   limites: tuple[float, ...] = (180, 365),
                   base_velocidade: str = "fonte",
                   filial: str | None = None) -> dict:
    """Capital associado a estoque acima de cada limite de cobertura."""
    pos = posicao(con, client_id, ini, fim, base_velocidade=base_velocidade,
                  filial=filial, limite=1000000)
    if not pos["disponivel"]:
        return pos
    itens = pos["itens"]
    if not any(i["valor_estoque"] for i in itens):
        return _sem(
            "O arquivo de estoque nao trouxe valor financeiro. Capital parado "
            "indisponivel — da para ver cobertura em dias, mas nao em R$.")

    total = sum(i["valor_estoque"] for i in itens)
    faixas = []
    for lim in limites:
        sel = [i for i in itens if _acima_de(i, lim)]
        v = sum(i["valor_estoque"] for i in sel)
        faixas.append({
            "acima_de_dias": lim, "skus": len(sel), "valor": v,
            "pct_do_estoque": (v / total * 100) if total else None,
        })
    return {
        "disponivel": True,
        "valor_total_estoque": total,
        "faixas": faixas,
        "calculo": Calculo(
            formula="capital parado (>N dias) = soma do valor dos SKUs com DDE > N",
            valores={"valor total do estoque": round(total, 2),
                     **{f"acima de {f['acima_de_dias']:.0f} dias": round(f["valor"], 2)
                        for f in faixas}},
            premissas=[
                "Valor a custo de reposicao, como vem da origem.",
                "E capital imobilizado hoje, nao prejuizo: o produto continua "
                "vendavel; o custo e o dinheiro parado, nao a perda dele.",
            ],
        ).como_dict(),
    }


def simulador(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
              objetivo_dias: float = 60, base_velocidade: str = "fonte",
              filial: str | None = None, top_n: int = 50) -> dict:
    """Quanto de estoque excede um objetivo de cobertura, e quanto capital
    isso representa. Deliberadamente chamado de "potencialmente liberavel".
    """
    if objetivo_dias <= 0:
        raise ValueError("objetivo_dias deve ser maior que zero.")
    pos = posicao(con, client_id, ini, fim, base_velocidade=base_velocidade,
                  filial=filial, limite=1000000)
    if not pos["disponivel"]:
        return pos

    itens = []
    excesso_valor = 0.0
    atual_valor = 0.0
    for i in pos["itens"]:
        atual_valor += i["valor_estoque"]
        if i["classificacao"] == INDEFINIDO:
            # Devolucao liquida: nao ha ritmo de venda para projetar objetivo.
            continue
        vd = i["venda_dia_fonte"] if base_velocidade == "fonte" else i["venda_dia_periodo"]
        if not vd:
            # Sem venda: todo o estoque excede qualquer objetivo. Contabiliza,
            # mas marca — extrapolar "liberacao" de item sem giro e frageil.
            exc_un = i["estoque_disp_un"]
            exc_val = i["valor_estoque"]
            objetivo_un = 0.0
            sem_giro = True
        else:
            objetivo_un = vd * objetivo_dias
            exc_un = max(0.0, i["estoque_disp_un"] - objetivo_un)
            unit = (i["valor_estoque"] / i["estoque_disp_un"]) if i["estoque_disp_un"] else 0.0
            exc_val = exc_un * unit
            sem_giro = False
        if exc_un <= 0:
            continue
        excesso_valor += exc_val
        itens.append({
            "produto_id": i["produto_id"], "produto": i["produto"],
            "filial": i["filial"],
            "estoque_atual_un": i["estoque_disp_un"],
            "estoque_objetivo_un": objetivo_un,
            "excesso_un": exc_un,
            "valor_estoque": i["valor_estoque"],
            "excesso_valor": exc_val,
            "dde": i["dde"], "sem_giro": sem_giro,
        })
    itens.sort(key=lambda x: x["excesso_valor"], reverse=True)

    return {
        "disponivel": True,
        "objetivo_dias": objetivo_dias,
        "valor_estoque_atual": atual_valor,
        "capital_potencialmente_liberavel": excesso_valor,
        "pct_do_estoque": (excesso_valor / atual_valor * 100) if atual_valor else None,
        "n_skus_com_excesso": len(itens),
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula=("estoque objetivo (un) = venda media diaria x objetivo_dias; "
                     "excesso (un) = estoque atual - estoque objetivo; "
                     "capital = excesso (un) x valor unitario do estoque"),
            valores={"objetivo (dias)": objetivo_dias,
                     "estoque atual (R$)": round(atual_valor, 2),
                     "capital potencialmente liberavel (R$)": round(excesso_valor, 2),
                     "SKUs com excesso": len(itens),
                     "base de velocidade": base_velocidade},
            premissas=[
                "POTENCIALMENTE LIBERAVEL — nao e dinheiro garantidamente "
                "recuperavel. Depende de conseguir vender ou devolver o excesso.",
                "Premissa central: a venda futura segue o ritmo medido. "
                "Sazonalidade, ruptura de concorrente ou campanha mudam isso.",
                "Nao considera lote minimo de compra, validade, nem acordo "
                "comercial de recompra — nenhum desses dados esta na base.",
                "SKU sem giro entra com o estoque inteiro como excesso e vem "
                "marcado 'sem_giro': e o caso menos defensavel da lista.",
            ],
        ).como_dict(),
    }


def matriz_estoque_vendas(con: sqlite3.Connection, client_id: int, ini: int, fim: int, *,
                          base_velocidade: str = "fonte", filial: str | None = None,
                          _pos: dict | None = None) -> dict:
    """Cruza cobertura (DDE) com faturamento do periodo, em 4 quadrantes.

    Corte pela mediana de cada eixo dentro do recorte atual — o mesmo criterio
    da matriz de cobertura da Etapa 3, para as duas telas se lerem igual.
    """
    pos = _pos if _pos is not None else posicao(
        con, client_id, ini, fim, base_velocidade=base_velocidade,
        filial=filial, limite=1000000)
    if not pos["disponivel"]:
        return pos

    dists = list(_filiais_do_cliente(con, client_id).values())
    fat: dict[int, float] = {}
    if dists:
        marca = ",".join("?" * len(dists))
        for pid, v in con.execute(
            f"""SELECT produto_id, coalesce(sum(valor),0) FROM v_vendas_mensal
                 WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?
                 GROUP BY produto_id""", dists + [ini, fim]):
            fat[pid] = float(v)

    itens = [dict(i, faturamento=fat.get(i["produto_id"], 0.0))
             for i in pos["itens"] if i["classificacao"] != INDEFINIDO]
    if not itens:
        return _sem("Sem SKUs com estoque para cruzar com vendas.")

    def mediana(vals: list[float]) -> float:
        s = sorted(vals)
        n = len(s)
        if n == 0:
            return 0.0
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    # SKU sem venda tem DDE indefinido; para o corte, trata como o maior DDE.
    ddes = [i["dde"] for i in itens if i["dde"] is not None]
    med_dde = mediana(ddes) if ddes else 0.0
    med_fat = mediana([i["faturamento"] for i in itens])

    QUADRANTES = {
        ("alta", "baixo"): ("RUPTURA_POTENCIAL",
                            "alta venda com pouca cobertura — vale checar risco de ruptura"),
        ("alta", "alto"): ("CAPITAL_CONCENTRADO",
                           "alta venda com muita cobertura — capital concentrado em item que gira"),
        ("baixa", "alto"): ("EXCESSO",
                            "baixa venda com muita cobertura — atencao a excesso"),
        ("baixa", "baixo"): ("BAIXA_PRIORIDADE",
                             "baixa venda e pouca cobertura — baixa prioridade"),
    }
    for i in itens:
        eixo_fat = "alta" if i["faturamento"] >= med_fat else "baixa"
        dde_i = i["dde"] if i["dde"] is not None else float("inf")
        eixo_dde = "alto" if dde_i >= med_dde else "baixo"
        q, desc = QUADRANTES[(eixo_fat, eixo_dde)]
        i["quadrante"] = q
        i["quadrante_descricao"] = desc

    resumo_q: dict[str, dict] = {}
    for q, desc in QUADRANTES.values():
        resumo_q[q] = {"quadrante": q, "descricao": desc, "skus": 0,
                       "valor_estoque": 0.0, "faturamento": 0.0}
    for i in itens:
        r = resumo_q[i["quadrante"]]
        r["skus"] += 1
        r["valor_estoque"] += i["valor_estoque"]
        r["faturamento"] += i["faturamento"]

    itens.sort(key=lambda x: x["valor_estoque"], reverse=True)
    return {
        "disponivel": True,
        "mediana_dde": med_dde,
        "mediana_faturamento": med_fat,
        "quadrantes": list(resumo_q.values()),
        "itens": itens,
        "calculo": Calculo(
            formula=("eixo X = DDE (dias de cobertura); eixo Y = faturamento do "
                     "periodo; corte pela mediana de cada eixo no recorte atual"),
            valores={"mediana de DDE (dias)": round(med_dde, 1),
                     "mediana de faturamento (R$)": round(med_fat, 2),
                     "SKUs classificados": len(itens)},
            premissas=[
                "'Risco potencial de ruptura' e um alerta a verificar, nao uma "
                "previsao: o dado mostra cobertura baixa com venda alta, nao "
                "mostra pedido em transito, lote a caminho nem prazo de reposicao.",
                "A mediana e do recorte atual — mudar filial ou periodo move o "
                "corte, entao o quadrante e relativo, nao absoluto.",
                "SKU sem venda no periodo conta como cobertura maxima no corte.",
            ],
        ).como_dict(),
    }
