"""Mix de produtos por PDV.

Faixas de SKU por PDV identicas a engine/analise.py §7, a03_pdv_whitespot.py §4
e a04_cobertura_mix.py: 1 / 2-3 / 4-9 / 10+ (tuplas (lo,hi), confirmadas
identicas nos tres scripts). Aqui viram parametro, mesmo padrao da Etapa 2.

Tudo em grao bruto (v_vendas): mix por PDV so existe no nivel de PDV, que
agg_vendas_mensal nao preserva.
"""
import sqlite3
import statistics

from . import formulas as f
from . import periodo as pe
from .contexto import carregar

_ELO_SELLOUT = "Sell-out: venda do distribuidor para o PDV."
FAIXAS_PADRAO = [(1, 1, "1 SKU"), (2, 3, "2-3 SKUs"), (4, 9, "4-9 SKUs"), (10, 999999, "10+ SKUs")]


def _marca(n: int) -> str:
    return ",".join("?" * n)


def _mix_bruto(con: sqlite3.Connection, distribuidor_ids: list[int],
              ini: int, fim: int, *, uf: str | None = None) -> list[dict]:
    """Um registro por PDV: {pdv_id, faturamento, unidades, n_skus}."""
    if not distribuidor_ids:
        return []
    marca = _marca(len(distribuidor_ids))
    if uf is None:
        sql = (f"SELECT pdv_id, sum(valor), sum(unidades), count(DISTINCT produto_id)"
               f"  FROM v_vendas WHERE distribuidor_id IN ({marca})"
               f"   AND periodo BETWEEN ? AND ? GROUP BY pdv_id")
        params = list(distribuidor_ids) + [ini, fim]
    else:
        sql = (f"SELECT s.pdv_id, sum(s.valor), sum(s.unidades), count(DISTINCT s.produto_id)"
               f"  FROM v_vendas s JOIN dim_pdv d ON d.id = s.pdv_id"
               f" WHERE s.distribuidor_id IN ({marca}) AND s.periodo BETWEEN ? AND ?"
               f"   AND d.uf = ? GROUP BY s.pdv_id")
        params = list(distribuidor_ids) + [ini, fim, uf]
    return [{"pdv_id": p, "faturamento": v, "unidades": u, "n_skus": n}
            for p, v, u, n in con.execute(sql, params).fetchall()]


def mix_por_pdv(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                *, faixas: list[tuple[int, int, str]] | None = None,
                uf: str | None = None) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if uf is not None and not disp.tem_uf:
        return {"disponivel": False,
               "motivo": "Este cliente não tem UF de PDV resolvida nos dados importados."}

    faixas = faixas or FAIXAS_PADRAO
    pdvs = _mix_bruto(con, disp.distribuidor_ids, ini, fim, uf=uf)
    if not pdvs:
        return {"disponivel": False, "motivo": "Nenhum PDV comprador neste período."}

    total_pdvs = len(pdvs)
    total_valor = sum(p["faturamento"] for p in pdvs)
    mix_medio = statistics.mean(p["n_skus"] for p in pdvs)
    mix_mediano = statistics.median(p["n_skus"] for p in pdvs)

    resumo = []
    for lo, hi, rotulo in faixas:
        do_grupo = [p for p in pdvs if lo <= p["n_skus"] <= hi]
        n = len(do_grupo)
        valor = sum(p["faturamento"] for p in do_grupo)
        resumo.append({
            "faixa": rotulo, "sku_min": lo, "sku_max": hi if hi < 999999 else None,
            "n_pdvs": n, "pct_pdvs": round(n / total_pdvs * 100, 1) if total_pdvs else 0,
            "faturamento": round(valor, 2),
            "pct_faturamento": round(valor / total_valor * 100, 1) if total_valor else 0,
            "rs_por_pdv": round(valor / n, 2) if n else None,
        })

    premissas = [_ELO_SELLOUT,
                "SKUs distintos comprados do cliente no período, por PDV."]
    if uf is not None:
        premissas.append(f"Recorte: só PDVs do estado {uf}.")

    return {
        "disponivel": True, "total_pdvs": total_pdvs,
        "mix_medio": round(mix_medio, 2), "mix_mediano": mix_mediano,
        "resumo": resumo, "uf": uf,
        "calculo": f.Calculo(
            formula="Faixas de quantidade de SKUs distintos por PDV no período; "
                   "R$/PDV = faturamento da faixa / PDVs da faixa.",
            valores={"total_pdvs": total_pdvs, "mix_medio": round(mix_medio, 2),
                    "periodo": pe.Janela(ini, fim).rotulo},
            premissas=premissas,
        ).como_dict(),
    }


def monoproduto(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                *, uf: str | None = None, limite: int = 50) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}

    pdvs = _mix_bruto(con, disp.distribuidor_ids, ini, fim, uf=uf)
    mono = [p for p in pdvs if p["n_skus"] == 1]
    if not mono:
        return {"disponivel": True, "n_pdvs": 0, "faturamento": 0, "rs_por_pdv": None,
               "top_produtos": [], "itens": [],
               "calculo": f.Calculo(formula="PDVs com exatamente 1 SKU comprado no "
                                            "período.").como_dict()}

    ids = [p["pdv_id"] for p in mono]
    marca = _marca(len(ids))
    marca_dist = _marca(len(disp.distribuidor_ids))
    # produto unico de cada PDV monoproduto — junta com o grao bruto pra achar
    # QUAL produto e (o unico que aparece para aquele PDV no periodo).
    linhas = con.execute(
        f"SELECT pdv_id, produto_id FROM v_vendas"
        f" WHERE distribuidor_id IN ({marca_dist}) AND pdv_id IN ({marca})"
        f"   AND periodo BETWEEN ? AND ? GROUP BY pdv_id, produto_id",
        disp.distribuidor_ids + ids + [ini, fim]).fetchall()
    produto_do_pdv = dict(linhas)
    contagem_produto: dict[int, int] = {}
    for pid in produto_do_pdv.values():
        contagem_produto[pid] = contagem_produto.get(pid, 0) + 1
    top_ids = sorted(contagem_produto, key=lambda p: -contagem_produto[p])[:10]
    nomes = dict(con.execute(
        f"SELECT id, nome_canonico FROM dim_product WHERE id IN ({_marca(len(top_ids))})",
        top_ids).fetchall()) if top_ids else {}
    nomes_pdv = dict(con.execute(
        f"SELECT id, razao_social FROM dim_pdv WHERE id IN ({marca})", ids).fetchall())

    total_valor = sum(p["faturamento"] for p in mono)
    itens = sorted(
        [{"pdv_id": p["pdv_id"], "pdv": nomes_pdv.get(p["pdv_id"], f"PDV #{p['pdv_id']}"),
          "faturamento": p["faturamento"],
          "produto_id": produto_do_pdv.get(p["pdv_id"]),
          "produto": nomes.get(produto_do_pdv.get(p["pdv_id"]), "—")}
         for p in mono],
        key=lambda x: -x["faturamento"])[:limite]

    return {
        "disponivel": True, "n_pdvs": len(mono), "faturamento": round(total_valor, 2),
        "rs_por_pdv": round(total_valor / len(mono), 2),
        "top_produtos": [{"produto_id": pid, "produto": nomes.get(pid, f"produto #{pid}"),
                          "n_pdvs": contagem_produto[pid]} for pid in top_ids],
        "itens": itens,
        "calculo": f.Calculo(
            formula="PDVs que compraram exatamente 1 produto distinto no período. "
                   "'top_produtos' = quais produtos concentram esses PDVs monoproduto.",
            valores={"n_pdvs": len(mono), "faturamento": round(total_valor, 2)},
            premissas=[_ELO_SELLOUT],
        ).como_dict(),
    }


def detalhe_faixa(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                  *, sku_min: int, sku_max: int | None = None,
                  uf: str | None = None, limite: int = 200,
                  top_produtos: int = 15) -> dict:
    """Quem esta numa faixa de mix, e o que essa faixa compra.

    Generaliza monoproduto() para qualquer intervalo de SKUs: 1, 2-3, 4-9,
    10+ ou um recorte arbitrario. Devolve os PDVs (com nome, faturamento e
    quantos SKUs) e os produtos que mais concentram esses PDVs — que e a
    pergunta util: "os PDVs de 2-3 SKUs compram O QUE?".
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}
    if uf is not None and not disp.tem_uf:
        return {"disponivel": False,
               "motivo": "Este cliente não tem UF de PDV resolvida nos dados importados."}
    if sku_min < 1:
        raise ValueError("sku_min deve ser pelo menos 1.")
    teto = sku_max if sku_max is not None else 10**9
    if teto < sku_min:
        raise ValueError("sku_max nao pode ser menor que sku_min.")

    pdvs = _mix_bruto(con, disp.distribuidor_ids, ini, fim, uf=uf)
    if not pdvs:
        return {"disponivel": False, "motivo": "Nenhum PDV comprador neste período."}
    total_base = sum(p["faturamento"] for p in pdvs)

    grupo = [p for p in pdvs if sku_min <= p["n_skus"] <= teto]
    rotulo = f"{sku_min} SKU" if sku_min == teto else (
        f"{sku_min}+ SKUs" if sku_max is None else f"{sku_min}-{sku_max} SKUs")
    if not grupo:
        return {"disponivel": True, "faixa": rotulo, "sku_min": sku_min,
                "sku_max": sku_max, "uf": uf, "n_pdvs": 0, "faturamento": 0.0,
                "participacao_pct": 0.0, "rs_por_pdv": None, "top_produtos": [],
                "itens": [],
                "calculo": f.Calculo(
                    formula=f"PDVs com {rotulo} comprados no período.",
                    premissas=[_ELO_SELLOUT]).como_dict()}

    ids = [p["pdv_id"] for p in grupo]
    marca_dist = _marca(len(disp.distribuidor_ids))

    # Quais produtos esses PDVs compram, e em quantos deles cada um aparece.
    # Em lotes de 900 por causa do teto de variaveis do SQLite — a faixa 4-9
    # tem milhares de PDVs na base real.
    contagem: dict[int, int] = {}
    valor_prod: dict[int, float] = {}
    for i in range(0, len(ids), 900):
        lote = ids[i:i + 900]
        for pid, n_pdvs, valor in con.execute(
            f"SELECT produto_id, count(DISTINCT pdv_id), sum(valor) FROM v_vendas"
            f" WHERE distribuidor_id IN ({marca_dist}) AND pdv_id IN ({_marca(len(lote))})"
            f"   AND periodo BETWEEN ? AND ? GROUP BY produto_id",
            disp.distribuidor_ids + lote + [ini, fim]):
            contagem[pid] = contagem.get(pid, 0) + n_pdvs
            valor_prod[pid] = valor_prod.get(pid, 0.0) + (valor or 0.0)

    top_ids = sorted(contagem, key=lambda p: -contagem[p])[:top_produtos]
    nomes_prod = dict(con.execute(
        f"SELECT id, nome_canonico FROM dim_product WHERE id IN ({_marca(len(top_ids))})",
        top_ids).fetchall()) if top_ids else {}

    grupo.sort(key=lambda p: -p["faturamento"])
    mostrados = grupo[:limite]
    nomes_pdv: dict[int, str] = {}
    ufs_pdv: dict[int, str | None] = {}
    ids_mostrados = [p["pdv_id"] for p in mostrados]
    for i in range(0, len(ids_mostrados), 900):
        lote = ids_mostrados[i:i + 900]
        for pid, razao, u in con.execute(
            f"SELECT id, razao_social, uf FROM dim_pdv WHERE id IN ({_marca(len(lote))})", lote):
            nomes_pdv[pid] = razao
            ufs_pdv[pid] = u

    faturamento = sum(p["faturamento"] for p in grupo)
    itens = [{"pdv_id": p["pdv_id"],
              "pdv": nomes_pdv.get(p["pdv_id"], f"PDV #{p['pdv_id']}"),
              "uf": ufs_pdv.get(p["pdv_id"]),
              "faturamento": p["faturamento"], "unidades": p["unidades"],
              "n_skus": p["n_skus"]} for p in mostrados]

    return {
        "disponivel": True,
        "faixa": rotulo, "sku_min": sku_min, "sku_max": sku_max, "uf": uf,
        "n_pdvs": len(grupo),
        "faturamento": faturamento,
        "participacao_pct": (faturamento / total_base * 100) if total_base else 0.0,
        "rs_por_pdv": faturamento / len(grupo),
        "mix_medio": statistics.mean(p["n_skus"] for p in grupo),
        "n_mostrados": len(itens),
        "top_produtos": [{
            "produto_id": pid,
            "produto": nomes_prod.get(pid, f"produto #{pid}"),
            "n_pdvs": contagem[pid],
            "pct_da_faixa": contagem[pid] / len(grupo) * 100,
            "faturamento": valor_prod.get(pid, 0.0),
        } for pid in top_ids],
        "itens": itens,
        "calculo": f.Calculo(
            formula=(f"PDVs com {rotulo} distintos comprados no período. "
                     f"'top_produtos' = em quantos PDVs DA FAIXA cada produto "
                     f"aparece (não no total do cliente)."),
            valores={"faixa": rotulo, "PDVs na faixa": len(grupo),
                     "PDVs listados": len(itens),
                     "faturamento da faixa": round(faturamento, 2),
                     "R$ por PDV": round(faturamento / len(grupo), 2)},
            premissas=[
                _ELO_SELLOUT,
                "'Em quantos PDVs' conta PDVs da própria faixa — o percentual "
                "é sobre os PDVs da faixa, não sobre a base inteira.",
                f"A lista mostra os {limite} maiores por faturamento; a "
                f"contagem e o faturamento da faixa consideram todos os "
                f"{len(grupo)}.",
            ] + ([f"Recorte: só PDVs do estado {uf}."] if uf else []),
        ).como_dict(),
    }


def alto_mix(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
            *, minimo_skus: int = 10, uf: str | None = None, limite: int = 50) -> dict:
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return {"disponivel": False, "motivo": disp.motivo_indisponivel}

    pdvs = _mix_bruto(con, disp.distribuidor_ids, ini, fim, uf=uf)
    if not pdvs:
        return {"disponivel": False, "motivo": "Nenhum PDV comprador neste período."}
    total_valor_base = sum(p["faturamento"] for p in pdvs)

    alto = [p for p in pdvs if p["n_skus"] >= minimo_skus]
    faturamento = sum(p["faturamento"] for p in alto)
    ids = [p["pdv_id"] for p in alto]
    nomes = dict(con.execute(
        f"SELECT id, razao_social FROM dim_pdv WHERE id IN ({_marca(len(ids))})",
        ids).fetchall()) if ids else {}
    itens = sorted(
        [{"pdv_id": p["pdv_id"], "pdv": nomes.get(p["pdv_id"], f"PDV #{p['pdv_id']}"),
          "faturamento": p["faturamento"], "n_skus": p["n_skus"]} for p in alto],
        key=lambda x: -x["faturamento"])[:limite]

    return {
        "disponivel": True, "n_pdvs": len(alto),
        "faturamento": round(faturamento, 2),
        "participacao_pct": round(faturamento / total_valor_base * 100, 1) if total_valor_base else 0,
        "rs_por_pdv": round(faturamento / len(alto), 2) if alto else None,
        "itens": itens,
        "calculo": f.Calculo(
            formula=f"PDVs com {minimo_skus} SKUs distintos ou mais no período — "
                   f"\"PDVs estratégicos de alto mix\".",
            valores={"minimo_skus": minimo_skus, "n_pdvs": len(alto)},
            premissas=[_ELO_SELLOUT],
        ).como_dict(),
    }


def oportunidades_expansao(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                           *, faixas: list[tuple[int, int, str]] | None = None,
                           uf: str | None = None, limite: int = 30) -> dict:
    """PDV de mix baixo cujo faturamento ja iguala a media de R$/PDV da faixa
    seguinte — sinal de que ele ja compra num volume tipico de quem tem mais
    SKUs, so nao tem os SKUs ainda. Nao afirma que ele vai comprar: e uma
    leitura de similaridade com PDVs de mix maior, no mesmo periodo.
    """
    resumo = mix_por_pdv(con, client_id, ini, fim, faixas=faixas, uf=uf)
    if not resumo["disponivel"]:
        return resumo

    faixas_ord = faixas or FAIXAS_PADRAO
    rs_por_pdv_da_faixa = {r["faixa"]: r["rs_por_pdv"] for r in resumo["resumo"]}

    disp = carregar(con, client_id)
    pdvs = _mix_bruto(con, disp.distribuidor_ids, ini, fim, uf=uf)
    nomes = {}
    itens = []
    for idx in range(len(faixas_ord) - 1):
        lo, hi, rotulo = faixas_ord[idx]
        _, _, rotulo_seguinte = faixas_ord[idx + 1]
        alvo_rs = rs_por_pdv_da_faixa.get(rotulo_seguinte)
        if not alvo_rs:
            continue
        candidatos = [p for p in pdvs if lo <= p["n_skus"] <= hi and p["faturamento"] >= alvo_rs]
        for c in sorted(candidatos, key=lambda p: -p["faturamento"])[:limite]:
            itens.append({
                "pdv_id": c["pdv_id"], "n_skus_atual": c["n_skus"],
                "faixa_atual": rotulo, "faixa_referencia": rotulo_seguinte,
                "faturamento_atual": c["faturamento"],
                "rs_por_pdv_faixa_referencia": alvo_rs,
            })

    itens.sort(key=lambda i: -i["faturamento_atual"])
    itens = itens[:limite]
    if itens:
        ids = [i["pdv_id"] for i in itens]
        nomes = dict(con.execute(
            f"SELECT id, razao_social FROM dim_pdv WHERE id IN ({_marca(len(ids))})",
            ids).fetchall())
        for i in itens:
            i["pdv"] = nomes.get(i["pdv_id"], f"PDV #{i['pdv_id']}")

    return {
        "disponivel": True, "total": len(itens), "itens": itens,
        "calculo": f.Calculo(
            formula="PDV com mix baixo cujo faturamento no período já é maior ou "
                   "igual ao R$/PDV médio da faixa de mix seguinte.",
            premissas=[_ELO_SELLOUT,
                      "Isto é uma oportunidade a investigar, não uma previsão: "
                      "não afirma que o PDV vai comprar mais SKUs, só que ele já "
                      "fatura como PDVs que têm mais SKUs.",
                      "Compara com a média da faixa seguinte no mesmo período — "
                      "não é uma meta fixa do sistema."],
        ).como_dict(),
    }
