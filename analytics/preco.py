"""Analise de preco — e, principalmente, de COMPARABILIDADE de preco.

A regra que organiza este modulo inteiro: preco so se compara dentro do mesmo
elo da cadeia e da mesma fonte.

  sell-out (VMD1) : distribuidor -> PDV. Preco = valor / unidades.
  IQVIA           : PDV -> consumidor (varejo). Preco = valor / unidades.

Os dois medem transacoes diferentes, com margens diferentes no meio. Dividir
um pelo outro produz um "indice" que parece informacao e nao e. Por isso:

  - preco_vs_concorrentes() compara o cliente com OUTROS DISTRIBUIDORES, na
    mesma fonte, no mesmo SKU e na mesma praca — comparacao legitima;
  - preco_varejo_iqvia() devolve o preco de varejo isolado, rotulado;
  - comparabilidade() existe para responder "posso comparar os dois?" com
    NAO e o motivo, em vez de deixar a interface fazer a conta errada.

A tabela price_data existe no schema mas esta vazia na base real: nenhuma
fonte de preco tabelado (PMC/PF) foi importada. Nada aqui depende dela.
"""
import sqlite3

from .formulas import Calculo, crescimento_pct
from .periodo import contar_meses

# Piso de volume para uma media de preco significar alguma coisa. Mesmo
# criterio do engine (a05_preco.py usa 200 unidades de cada lado).
MINIMO_UNIDADES = 200


def _sem(motivo: str) -> dict:
    return {"disponivel": False, "motivo": motivo}


def _marca(n: int) -> str:
    return ",".join("?" * n)


def comparabilidade(con: sqlite3.Connection) -> dict:
    """Inventario das fontes de preco e o que pode ser comparado com o que."""
    tem_sellout = con.execute("SELECT count(*) FROM v_vendas_mensal LIMIT 1").fetchone()[0] > 0
    tem_iqvia = con.execute("SELECT count(*) FROM v_mercado LIMIT 1").fetchone()[0] > 0
    n_tabelado = con.execute("SELECT count(*) FROM price_data").fetchone()[0]

    fontes = [
        {"fonte": "Sell-out do distribuidor", "disponivel": tem_sellout,
         "elo": "distribuidor -> PDV", "unidade": "R$ por unidade vendida",
         "periodo": "mensal, segue o seletor da tela",
         "produto": "SKU (apresentacao) do cadastro do cliente",
         "observacao": "preco praticado ao PDV; e o preco que o cliente controla"},
        {"fonte": "IQVIA (mercado)", "disponivel": tem_iqvia,
         "elo": "PDV -> consumidor (varejo)", "unidade": "R$ por unidade vendida",
         "periodo": "foto unica: mes e acumulado do ano",
         "produto": "apresentacao/mercado da IQVIA, sem chave com o cadastro",
         "observacao": "preco de varejo da industria; inclui a margem do PDV"},
        {"fonte": "Preco tabelado (PMC/PF)", "disponivel": n_tabelado > 0,
         "elo": "tabela oficial", "unidade": "R$ por unidade",
         "periodo": "n/d", "produto": "n/d",
         "observacao": "nenhuma fonte de preco tabelado importada"},
    ]
    pares = [
        {"de": "Sell-out do cliente", "para": "Sell-out de outros distribuidores",
         "comparavel": tem_sellout,
         "motivo": ("Mesma fonte, mesmo elo, mesmo SKU e mesma praca — "
                    "comparacao legitima." if tem_sellout else
                    "Sem sell-out importado.")},
        {"de": "Sell-out do cliente", "para": "IQVIA (varejo)", "comparavel": False,
         "motivo": ("Elos diferentes da cadeia: o sell-out e a venda do "
                    "distribuidor ao PDV; a IQVIA e a venda do PDV ao "
                    "consumidor, ja com a margem do varejo dentro. A razao "
                    "entre os dois mede margem de canal, nao competitividade "
                    "de preco — e a base nao tem como separar as duas coisas.")},
        {"de": "Qualquer fonte", "para": "Preco tabelado", "comparavel": False,
         "motivo": "Nenhuma fonte de preco tabelado importada."},
    ]
    return {
        "disponivel": True,
        "fontes": fontes,
        "pares": pares,
        "calculo": Calculo(
            formula="inventario de fontes; comparabilidade decidida pelo elo da cadeia",
            valores={"fontes disponiveis": sum(1 for f in fontes if f["disponivel"]),
                     "linhas de preco tabelado": n_tabelado},
            premissas=[
                "Preco so se compara dentro do mesmo elo e da mesma fonte.",
                "A negativa aqui e deliberada: sem ela a interface tenderia a "
                "dividir um preco pelo outro e chamar o resultado de indice.",
            ],
        ).como_dict(),
    }


def preco_vs_concorrentes(con: sqlite3.Connection, distribuidor_ids: list[int],
                          ini: int, fim: int, *, uf: str | None = None,
                          minimo_unidades: float = MINIMO_UNIDADES,
                          top_n: int = 50, limite_alerta_pct: float = 8.0) -> dict:
    """Preco do cliente x preco dos demais distribuidores, por SKU.

    Mesma fonte, mesmo elo. O recorte de praca (uf) importa: um SKU pode ser
    caro no RJ e barato no ES, e a media nacional esconderia os dois.
    """
    if not distribuidor_ids:
        return _sem("Cliente sem distribuidor vinculado.")
    marca = _marca(len(distribuidor_ids))
    cond_uf = " AND uf = ?" if uf else ""
    par_uf = [uf] if uf else []

    cliente = {}
    for pid, un, val in con.execute(
        f"""SELECT produto_id, coalesce(sum(unidades),0), coalesce(sum(valor),0)
              FROM v_vendas_mensal
             WHERE distribuidor_id IN ({marca}) AND periodo BETWEEN ? AND ?{cond_uf}
             GROUP BY produto_id""", list(distribuidor_ids) + [ini, fim] + par_uf):
        cliente[pid] = (float(un), float(val))

    outros = {}
    for pid, un, val in con.execute(
        f"""SELECT produto_id, coalesce(sum(unidades),0), coalesce(sum(valor),0)
              FROM v_vendas_mensal
             WHERE distribuidor_id NOT IN ({marca}) AND periodo BETWEEN ? AND ?{cond_uf}
             GROUP BY produto_id""", list(distribuidor_ids) + [ini, fim] + par_uf):
        outros[pid] = (float(un), float(val))

    nomes = dict(con.execute("SELECT id, apresentacao FROM dim_product"))
    itens, sem_volume = [], []
    for pid, (un_c, val_c) in cliente.items():
        un_o, val_o = outros.get(pid, (0.0, 0.0))
        if un_c < minimo_unidades or un_o < minimo_unidades:
            sem_volume.append({
                "produto_id": pid, "produto": nomes.get(pid, f"produto {pid}"),
                "unidades_cliente": un_c, "unidades_outros": un_o,
                "motivo": (f"volume abaixo de {minimo_unidades:.0f} unidades em "
                           f"um dos lados — media de preco nao confiavel"),
            })
            continue
        p_c, p_o = val_c / un_c, val_o / un_o
        dif = (p_c / p_o - 1) * 100 if p_o else None
        itens.append({
            "produto_id": pid, "produto": nomes.get(pid, f"produto {pid}"),
            "preco_cliente": p_c, "preco_outros": p_o,
            "diferenca_pct": dif,
            "unidades_cliente": un_c, "unidades_outros": un_o,
            "faturamento_cliente": val_c,
            "posicao": (None if dif is None else
                        "ACIMA" if dif > limite_alerta_pct else
                        "ABAIXO" if dif < -limite_alerta_pct else "EM_LINHA"),
        })
    itens.sort(key=lambda x: x["faturamento_cliente"], reverse=True)

    un_c_tot = sum(i["unidades_cliente"] for i in itens)
    un_o_tot = sum(i["unidades_outros"] for i in itens)
    val_c_tot = sum(i["preco_cliente"] * i["unidades_cliente"] for i in itens)
    val_o_tot = sum(i["preco_outros"] * i["unidades_outros"] for i in itens)
    return {
        "disponivel": True,
        "uf": uf,
        "minimo_unidades": minimo_unidades,
        "limite_alerta_pct": limite_alerta_pct,
        "n_comparaveis": len(itens),
        "n_sem_volume": len(sem_volume),
        "preco_medio_cliente": (val_c_tot / un_c_tot) if un_c_tot else None,
        "preco_medio_outros": (val_o_tot / un_o_tot) if un_o_tot else None,
        "itens": itens[:top_n],
        "sem_volume": sem_volume[:top_n],
        "calculo": Calculo(
            formula=("preco = valor / unidades (sell-out); "
                     "diferenca % = (preco do cliente / preco dos outros - 1) x 100"),
            valores={"SKUs comparaveis": len(itens),
                     "SKUs sem volume minimo": len(sem_volume),
                     "piso de volume": minimo_unidades,
                     "praca": uf or "todas",
                     "periodo": f"{ini}-{fim}"},
            premissas=[
                "Mesma fonte e mesmo elo (distribuidor -> PDV) nos dois lados: "
                "o que torna a comparacao legitima.",
                f"SKU com menos de {minimo_unidades:.0f} unidades de qualquer um "
                f"dos lados fica de fora e aparece listado — media de preco "
                f"sobre volume baixo e ruido.",
                "Preco medio ponderado por unidades, nao media simples de precos.",
                "Diferenca de preco nao explica sozinha ganho ou perda de "
                "venda: mix de PDV, prazo e bonificacao tambem entram e nao "
                "estao nesta base.",
            ],
        ).como_dict(),
    }


def evolucao_preco(con: sqlite3.Connection, distribuidor_ids: list[int],
                   ini: int, fim: int, *, produto_id: int | None = None,
                   uf: str | None = None) -> dict:
    """Preco medio do cliente mes a mes, no recorte pedido."""
    if not distribuidor_ids:
        return _sem("Cliente sem distribuidor vinculado.")
    marca = _marca(len(distribuidor_ids))
    where = [f"distribuidor_id IN ({marca})", "periodo BETWEEN ? AND ?"]
    params: list = list(distribuidor_ids) + [ini, fim]
    if produto_id is not None:
        where.append("produto_id = ?")
        params.append(produto_id)
    if uf is not None:
        where.append("uf = ?")
        params.append(uf)

    serie = []
    for periodo, un, val in con.execute(
        f"""SELECT periodo, coalesce(sum(unidades),0), coalesce(sum(valor),0)
              FROM v_vendas_mensal WHERE {' AND '.join(where)}
             GROUP BY periodo ORDER BY periodo""", params):
        serie.append({"periodo": periodo, "unidades": float(un), "valor": float(val),
                      "preco_medio": (float(val) / float(un)) if un else None})
    if not serie:
        return _sem("Sem vendas neste recorte para calcular preco.")

    com_preco = [p for p in serie if p["preco_medio"] is not None]
    primeiro = com_preco[0]["preco_medio"] if com_preco else None
    ultimo = com_preco[-1]["preco_medio"] if com_preco else None
    return {
        "disponivel": True,
        "produto_id": produto_id, "uf": uf,
        "serie": serie,
        "preco_inicial": primeiro, "preco_final": ultimo,
        "variacao_pct": crescimento_pct(ultimo, primeiro) if (primeiro and ultimo) else None,
        "calculo": Calculo(
            formula="preco medio do mes = valor do mes / unidades do mes",
            valores={"meses": len(serie), "periodo": f"{ini}-{fim}",
                     "preco no primeiro mes": round(primeiro, 4) if primeiro else "n/d",
                     "preco no ultimo mes": round(ultimo, 4) if ultimo else "n/d"},
            premissas=[
                "Preco medio realizado, nao preco de tabela: muda com mix de "
                "produto, desconto e bonificacao dentro do proprio mes.",
                "Variacao ponta a ponta (primeiro x ultimo mes), nao tendencia "
                "ajustada — dois pontos, nao uma regressao.",
            ],
        ).como_dict(),
    }


def preco_varejo_iqvia(con: sqlite3.Connection, *, uf=None, mercado=None,
                       molecula=None, top_n: int = 30,
                       minimo_unidades: float = MINIMO_UNIDADES) -> dict:
    """Preco de varejo por mercado: VITAMEDIC x lider concorrente.

    Isolado de proposito do preco de sell-out — os dois nunca sao divididos
    um pelo outro neste modulo.
    """
    tem = con.execute("SELECT count(*) FROM v_mercado LIMIT 1").fetchone()[0] > 0
    if not tem:
        return _sem("Nao ha base de mercado (IQVIA) importada. Preco de varejo indisponivel.")

    where, params = [], []
    for col, val in (("uf", uf), ("mercado", mercado), ("molecula", molecula)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(val)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""

    por_mercado: dict[str, dict] = {}
    for merc, lab, vmd, un, val in con.execute(
        f"""SELECT mercado, lab_grupo, eh_vitamedic,
                   coalesce(sum(un_ytd),0), coalesce(sum(valor_ytd_x100),0)/100.0
              FROM v_mercado{filtro}
             GROUP BY mercado, lab_grupo, eh_vitamedic""", params):
        d = por_mercado.setdefault(merc, {"vmd_un": 0.0, "vmd_val": 0.0, "conc": []})
        if vmd:
            d["vmd_un"] += float(un)
            d["vmd_val"] += float(val)
        elif un:
            d["conc"].append((float(un), lab, float(val) / float(un)))

    itens = []
    for merc, d in por_mercado.items():
        if d["vmd_un"] < minimo_unidades or not d["conc"]:
            continue
        p_vmd = d["vmd_val"] / d["vmd_un"]
        d["conc"].sort(reverse=True)
        un_lider, lab_lider, p_lider = d["conc"][0]
        mais_baratos = sum(1 for u, _, p in d["conc"] if p < p_vmd)
        itens.append({
            "mercado": merc, "preco_vitamedic": p_vmd,
            "lider": lab_lider, "preco_lider": p_lider,
            "indice_vs_lider_pct": ((p_vmd / p_lider - 1) * 100) if p_lider else None,
            "concorrentes": len(d["conc"]),
            "concorrentes_mais_baratos": mais_baratos,
            "unidades_vitamedic": d["vmd_un"],
        })
    itens.sort(key=lambda x: x["unidades_vitamedic"], reverse=True)
    return {
        "disponivel": True,
        "escopo": "VAREJO_INDUSTRIA",
        "recorte": {"uf": uf, "mercado": mercado, "molecula": molecula},
        "n_mercados": len(itens),
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula=("preco de varejo = valor YTD / unidades YTD; "
                     "indice vs lider = (preco VITAMEDIC / preco do lider - 1) x 100"),
            valores={"mercados analisados": len(itens),
                     "piso de unidades": minimo_unidades,
                     "recorte": uf or "nacional"},
            premissas=[
                "PRECO DE VAREJO (PDV -> consumidor), da INDUSTRIA. Nao e o "
                "preco do distribuidor e nao se compara com o do sell-out.",
                "Lider = concorrente com mais unidades no mercado, nao o de "
                "maior preco.",
                "Preco medio por unidade da apresentacao; mercados com "
                "embalagens de tamanhos diferentes misturam unidades diferentes.",
            ],
        ).como_dict(),
    }
