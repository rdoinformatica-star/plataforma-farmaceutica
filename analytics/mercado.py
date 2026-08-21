"""Inteligencia de mercado (IQVIA): tamanho, crescimento, share e regiao.

O QUE ESTA FONTE E — e o que ela NAO e. Isto define todo o modulo:

  A base IQVIA identifica LABORATORIO (VITAMEDIC, EMS, CIMED, GEOLAB...),
  nunca o distribuidor. Conferido na base real: 'EMEFARMA' e 'MILLENIUM'
  aparecem ZERO vezes em lab_full/lab_grupo.

  Consequencia direta, e a limitacao mais importante da Etapa 4:
  >>> Share do CLIENTE (distribuidor) no mercado nao e calculavel. <<<
  O que da para calcular e o share da INDUSTRIA (VITAMEDIC) no varejo.
  Sao coisas diferentes e o modulo nunca troca uma pela outra —
  share_do_cliente() existe justamente para devolver indisponivel com o
  motivo, em vez de deixar a interface inventar um numero parecido.

  Elo da cadeia: IQVIA mede PDV -> consumidor (varejo). O sell-out mede
  distribuidor -> PDV. Preco e share dos dois nao se comparam entre si.

GRANULARIDADE REAL (conferida, nao assumida):
  - uma unica foto: periodo_ref 202606, aba 'm24';
  - nao ha serie mensal — a evolucao vem em colunas (atual/anterior/ytd/
    ytd anterior), nao em linhas. Por isso "share ao longo do tempo" so
    tem dois pontos comparaveis (YTD atual x YTD do ano anterior), e o
    modulo diz isso em vez de desenhar uma linha que nao existe;
  - un_atual/valor_atual = mes corrente (jun/2026);
  - un_ytd/valor_ytd     = acumulado do ano (jan-jun/2026);
  - un_ytd_ant           = mesmo acumulado do ano anterior (jan-jun/2025);
  - produto_id NAO e preenchido: nao ha chave ligando o mercado ao
    dim_product. A ponte com os SKUs do cliente e por texto e parcial —
    ver ponte_produtos().
"""
import sqlite3

from .formulas import Calculo, crescimento_pct
from .periodo import contar_meses

# Janela que o YTD do IQVIA cobre nesta foto. Derivado de periodo_ref, nao
# fixado a mao: se a proxima carga vier com outro mes, isto acompanha.
_INDISP_SEM_IQVIA = (
    "Nao ha base de mercado (IQVIA) importada. Share, crescimento de mercado "
    "e analise regional de mercado ficam indisponiveis."
)


def _sem(motivo: str) -> dict:
    return {"disponivel": False, "motivo": motivo}


def _tem_iqvia(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT count(*) FROM v_mercado LIMIT 1").fetchone()[0] > 0


def _janela_ytd(periodo_ref: int) -> tuple[int, int, int, int]:
    """(ini, fim, ini_ant, fim_ant) do YTD que a foto representa.
    202606 -> (202601, 202606, 202501, 202506).
    """
    ano, mes = divmod(periodo_ref, 100)
    return ano * 100 + 1, periodo_ref, (ano - 1) * 100 + 1, (ano - 1) * 100 + mes


def _filtros(uf=None, mercado=None, molecula=None, canal=None,
             lab_grupo=None) -> tuple[list[str], list]:
    where, params = [], []
    for col, val in (("uf", uf), ("mercado", mercado), ("molecula", molecula),
                     ("canal", canal), ("lab_grupo", lab_grupo)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(val)
    return where, params


def perfil(con: sqlite3.Connection) -> dict:
    """Perfil da fonte de mercado — o que existe antes de calcular share."""
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)

    linha = con.execute(
        """SELECT count(*), count(DISTINCT aba), count(DISTINCT periodo_ref),
                  min(periodo_ref), max(periodo_ref),
                  count(DISTINCT mercado), count(DISTINCT molecula),
                  count(DISTINCT apresentacao), count(DISTINCT uf),
                  count(DISTINCT canal), count(DISTINCT tipo),
                  count(DISTINCT lab_full), count(DISTINCT lab_grupo),
                  sum(eh_vitamedic), count(produto_id)
             FROM v_mercado""").fetchone()
    (n, n_aba, n_per, pmin, pmax, n_merc, n_mol, n_apre, n_uf, n_can,
     n_tipo, n_lab, n_grp, n_vmd, n_prodid) = linha

    ini, fim, ini_ant, fim_ant = _janela_ytd(pmax)
    metricas = []
    for rot, col in (("unidades do mes", "un_atual"), ("valor do mes", "valor_atual_x100"),
                     ("unidades do mes anterior", "un_ant"),
                     ("unidades YTD", "un_ytd"), ("valor YTD", "valor_ytd_x100"),
                     ("unidades YTD ano anterior", "un_ytd_ant")):
        preenchidas = con.execute(f"SELECT count({col}) FROM v_mercado").fetchone()[0]
        metricas.append({"metrica": rot, "coluna": col, "linhas_preenchidas": preenchidas})

    return {
        "disponivel": True,
        "linhas": n,
        "abas": n_aba,
        "periodos": n_per,
        "periodo_ref": pmax,
        "eh_foto_unica": n_per <= 1,
        "janela_ytd": {"ini": ini, "fim": fim, "ini_ant": ini_ant, "fim_ant": fim_ant},
        "dimensoes": {
            "mercados": n_merc, "moleculas": n_mol, "apresentacoes": n_apre,
            "ufs": n_uf, "canais": n_can, "tipos": n_tipo,
            "laboratorios": n_lab, "grupos_de_laboratorio": n_grp,
        },
        "linhas_vitamedic": n_vmd,
        "produto_id_preenchido": n_prodid,
        "tem_ligacao_com_dim_product": n_prodid > 0,
        "identifica_distribuidor": False,
        "calculo": Calculo(
            formula="perfil = contagem de linhas e de valores distintos por dimensao em v_mercado",
            valores={"linhas": n, "periodo de referencia": pmax,
                     "janela YTD": f"{ini}-{fim} vs {ini_ant}-{fim_ant}",
                     "linhas VITAMEDIC": n_vmd,
                     "linhas com produto_id": n_prodid},
            premissas=[
                "A fonte identifica LABORATORIO, nunca distribuidor: nao da "
                "para isolar o cliente dentro do mercado.",
                "Elo da cadeia: PDV -> consumidor (varejo). O sell-out e "
                "distribuidor -> PDV. Preco e share nao se comparam entre as duas.",
                f"Foto unica ({pmax}): a evolucao vem em colunas (mes, mes "
                f"anterior, YTD, YTD anterior), nao em serie mensal.",
                "produto_id nao vem preenchido: a ligacao com os SKUs do "
                "cliente e por texto e parcial (ver ponte de produtos).",
            ],
        ).como_dict(),
    }


def resumo(con: sqlite3.Connection, *, uf=None, mercado=None, molecula=None,
           canal=None) -> dict:
    """Tamanho e crescimento do mercado no recorte pedido."""
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    where, params = _filtros(uf, mercado, molecula, canal)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""
    r = con.execute(
        f"""SELECT coalesce(sum(un_ytd),0), coalesce(sum(valor_ytd_x100),0)/100.0,
                   coalesce(sum(un_ytd_ant),0), coalesce(sum(valor_ytd_ant_x100),0)/100.0,
                   coalesce(sum(un_atual),0), coalesce(sum(valor_atual_x100),0)/100.0,
                   coalesce(sum(un_ant),0), coalesce(sum(valor_ant_x100),0)/100.0,
                   count(*)
              FROM v_mercado{filtro}""", params).fetchone()
    un, val, un_a, val_a, un_m, val_m, un_ma, val_ma, linhas = r
    if not linhas:
        return _sem("Nenhuma linha de mercado neste recorte.")

    pref = con.execute("SELECT max(periodo_ref) FROM v_mercado").fetchone()[0]
    ini, fim, ini_ant, fim_ant = _janela_ytd(pref)
    return {
        "disponivel": True,
        "recorte": {"uf": uf, "mercado": mercado, "molecula": molecula, "canal": canal},
        "linhas": linhas,
        "unidades_ytd": float(un), "valor_ytd": float(val),
        "unidades_ytd_ant": float(un_a), "valor_ytd_ant": float(val_a),
        "cresc_unidades_pct": crescimento_pct(float(un), float(un_a)),
        "cresc_valor_pct": crescimento_pct(float(val), float(val_a)),
        "unidades_mes": float(un_m), "valor_mes": float(val_m),
        "cresc_mes_valor_pct": crescimento_pct(float(val_m), float(val_ma)),
        "janela": {"ini": ini, "fim": fim, "ini_ant": ini_ant, "fim_ant": fim_ant},
        "calculo": Calculo(
            formula="crescimento do mercado = (YTD atual / YTD ano anterior - 1) x 100",
            valores={"valor YTD": round(float(val), 2),
                     "valor YTD ano anterior": round(float(val_a), 2),
                     "unidades YTD": round(float(un), 0),
                     "janela": f"{ini}-{fim} vs {ini_ant}-{fim_ant}",
                     "linhas somadas": linhas},
            premissas=[
                f"Janela fixa da foto: {ini}-{fim} contra {ini_ant}-{fim_ant}. "
                f"Nao acompanha o seletor de periodo da tela porque a fonte "
                f"nao traz serie mensal.",
                "Valor de mercado a preco de varejo (PDV -> consumidor).",
            ],
        ).como_dict(),
    }


def share_industria(con: sqlite3.Connection, *, uf=None, mercado=None,
                    molecula=None, canal=None, base: str = "unidades") -> dict:
    """Share da VITAMEDIC (industria) no mercado do recorte.

    NAO e o share do cliente/distribuidor — ver share_do_cliente().
    """
    if base not in ("unidades", "valor"):
        raise ValueError("base deve ser 'unidades' ou 'valor'.")
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    where, params = _filtros(uf, mercado, molecula, canal)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""

    cur = "un_ytd" if base == "unidades" else "valor_ytd_x100"
    ant = "un_ytd_ant" if base == "unidades" else "valor_ytd_ant_x100"
    div = 1.0 if base == "unidades" else 100.0
    r = con.execute(
        f"""SELECT coalesce(sum(CASE WHEN eh_vitamedic=1 THEN {cur} END),0)/{div},
                   coalesce(sum({cur}),0)/{div},
                   coalesce(sum(CASE WHEN eh_vitamedic=1 THEN {ant} END),0)/{div},
                   coalesce(sum({ant}),0)/{div}, count(*)
              FROM v_mercado{filtro}""", params).fetchone()
    vmd, tot, vmd_a, tot_a, linhas = r
    if not linhas or not tot:
        return _sem("Nenhuma linha de mercado neste recorte — share indisponivel.")

    share = vmd / tot * 100
    share_ant = (vmd_a / tot_a * 100) if tot_a else None
    return {
        "disponivel": True,
        "escopo": "INDUSTRIA_VITAMEDIC",
        "base": base,
        "recorte": {"uf": uf, "mercado": mercado, "molecula": molecula, "canal": canal},
        "vitamedic": float(vmd), "mercado_total": float(tot),
        "share_pct": share,
        "share_ant_pct": share_ant,
        "delta_share_pp": (share - share_ant) if share_ant is not None else None,
        "calculo": Calculo(
            formula=f"share = VITAMEDIC ({base}, YTD) / mercado total ({base}, YTD) x 100",
            valores={"VITAMEDIC": round(float(vmd), 2),
                     "mercado total": round(float(tot), 2),
                     "share": f"{share:.2f}%",
                     "share ano anterior": (f"{share_ant:.2f}%" if share_ant is not None else "n/d"),
                     "linhas": linhas},
            premissas=[
                "ESTE E O SHARE DA INDUSTRIA (VITAMEDIC) no varejo, nao o "
                "share do distribuidor: a fonte nao identifica distribuidor.",
                "Numerador: linhas marcadas como VITAMEDIC. Denominador: todas "
                "as linhas do mesmo recorte (mercado x UF x canal), incluindo "
                "concorrentes.",
                "Variacao em pontos percentuais (p.p.), nunca em porcentagem "
                "de porcentagem.",
            ],
        ).como_dict(),
    }


def share_do_cliente(con: sqlite3.Connection, client_id: int) -> dict:
    """Existe de proposito: responde POR QUE o share do cliente nao sai.

    Sem isto a interface tenderia a mostrar o share da industria com o rotulo
    do cliente — que e o erro mais caro que este modulo poderia cometer.
    """
    nome = con.execute("SELECT nome FROM clients WHERE id = ?", (client_id,)).fetchone()
    nome = nome[0] if nome else f"cliente {client_id}"
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    ocorrencias = con.execute(
        "SELECT count(*) FROM v_mercado WHERE upper(lab_full) LIKE ? OR upper(lab_grupo) LIKE ?",
        (f"%{nome.upper()}%", f"%{nome.upper()}%")).fetchone()[0]
    return {
        "disponivel": False,
        "motivo": (
            f"Share de '{nome}' no mercado nao e calculavel com esta base. "
            f"A IQVIA identifica laboratorio (industria), nao distribuidor — "
            f"'{nome}' aparece em {ocorrencias} linhas do mercado. Alem disso "
            f"os dois lados medem elos diferentes: IQVIA e venda do PDV ao "
            f"consumidor; o sell-out do cliente e venda do distribuidor ao PDV. "
            f"O que esta disponivel e o share da industria (VITAMEDIC) no "
            f"mercado dos produtos que o cliente distribui."
        ),
        "alternativa": "share_industria",
        "ocorrencias_do_nome_no_mercado": ocorrencias,
    }


def ranking_mercados(con: sqlite3.Connection, *, uf=None, canal=None,
                     top_n: int = 30, minimo_unidades: float = 0) -> dict:
    """Mercados onde a VITAMEDIC atua, do maior share para o menor."""
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    where, params = _filtros(uf, None, None, canal)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""
    linhas = con.execute(
        f"""SELECT mercado,
                   coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd END),0) vmd,
                   coalesce(sum(un_ytd),0) tot,
                   coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd_ant END),0) vmd_a,
                   coalesce(sum(un_ytd_ant),0) tot_a,
                   coalesce(sum(valor_ytd_x100),0)/100.0 val
              FROM v_mercado{filtro}
             GROUP BY mercado""", params).fetchall()

    itens = []
    for mercado, vmd, tot, vmd_a, tot_a, val in linhas:
        if vmd <= 0 or tot <= 0 or tot < minimo_unidades:
            continue
        s = vmd / tot * 100
        s_a = (vmd_a / tot_a * 100) if tot_a else None
        itens.append({
            "mercado": mercado, "vitamedic_un": float(vmd), "mercado_un": float(tot),
            "mercado_valor": float(val), "share_pct": s, "share_ant_pct": s_a,
            "delta_share_pp": (s - s_a) if s_a is not None else None,
            "cresc_mercado_un_pct": crescimento_pct(float(tot), float(tot_a)),
            "cresc_vitamedic_un_pct": crescimento_pct(float(vmd), float(vmd_a)),
        })
    itens.sort(key=lambda x: x["mercado_valor"], reverse=True)
    return {
        "disponivel": True,
        "recorte": {"uf": uf, "canal": canal},
        "n_mercados": len(itens),
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula="por mercado: share = VITAMEDIC un YTD / total un YTD x 100",
            valores={"mercados com presenca VITAMEDIC": len(itens),
                     "minimo de unidades": minimo_unidades},
            premissas=[
                "So entram mercados onde a VITAMEDIC tem unidades > 0 — nos "
                "demais o share seria zero e nao diria nada.",
                "Share da industria, nao do distribuidor.",
            ],
        ).como_dict(),
    }


def regional(con: sqlite3.Connection, *, mercado=None, molecula=None,
             canal=None, top_n: int = 30) -> dict:
    """Mercado, share da industria e crescimento por UF."""
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    where, params = _filtros(None, mercado, molecula, canal)
    where.append("uf IS NOT NULL")
    filtro = " WHERE " + " AND ".join(where)
    itens = []
    for uf, vmd, tot, vmd_a, tot_a, val in con.execute(
        f"""SELECT uf,
                   coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd END),0),
                   coalesce(sum(un_ytd),0),
                   coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd_ant END),0),
                   coalesce(sum(un_ytd_ant),0),
                   coalesce(sum(valor_ytd_x100),0)/100.0
              FROM v_mercado{filtro} GROUP BY uf""", params):
        if tot <= 0:
            continue
        s = vmd / tot * 100
        s_a = (vmd_a / tot_a * 100) if tot_a else None
        itens.append({
            "uf": uf, "mercado_un": float(tot), "mercado_valor": float(val),
            "vitamedic_un": float(vmd), "share_pct": s, "share_ant_pct": s_a,
            "delta_share_pp": (s - s_a) if s_a is not None else None,
            "cresc_mercado_pct": crescimento_pct(float(tot), float(tot_a)),
        })
    itens.sort(key=lambda x: x["mercado_valor"], reverse=True)
    return {
        "disponivel": True,
        "recorte": {"mercado": mercado, "molecula": molecula, "canal": canal},
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula="por UF: share = VITAMEDIC un YTD / total un YTD x 100",
            valores={"UFs com mercado": len(itens)},
            premissas=[
                "UF do mercado IQVIA e a praca de venda ao consumidor.",
                "Share da industria, nao do distribuidor.",
            ],
        ).como_dict(),
    }


def cliente_vs_mercado(con: sqlite3.Connection, client_id: int,
                       distribuidor_ids: list[int], *, uf=None,
                       mercado=None, molecula=None) -> dict:
    """Crescimento do cliente x crescimento do mercado, em pontos percentuais.

    Comparabilidade: o mercado so tem UMA janela (o YTD da foto). Entao o
    cliente e medido exatamente na mesma janela — nao no periodo escolhido na
    tela. Comparar jan-jul do cliente com jan-jun do mercado daria uma
    diferenca que e artefato de calendario, nao de desempenho.
    """
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    if not distribuidor_ids:
        return _sem("Cliente sem distribuidor vinculado.")

    pref = con.execute("SELECT max(periodo_ref) FROM v_mercado").fetchone()[0]
    ini, fim, ini_ant, fim_ant = _janela_ytd(pref)

    disp = con.execute(
        f"""SELECT min(periodo), max(periodo) FROM v_vendas_mensal
             WHERE distribuidor_id IN ({','.join('?' * len(distribuidor_ids))})""",
        distribuidor_ids).fetchone()
    pmin, pmax = disp
    if pmin is None:
        return _sem("Cliente sem sell-out importado.")
    if pmin > ini_ant:
        return _sem(
            f"Comparacao cliente x mercado indisponivel: o mercado compara "
            f"{ini}-{fim} contra {ini_ant}-{fim_ant}, mas o sell-out do cliente "
            f"comeca em {pmin}. Sem o ano anterior completo a comparacao seria "
            f"entre janelas diferentes.")

    marca = ",".join("?" * len(distribuidor_ids))
    cond_uf = " AND uf = ?" if uf else ""

    def soma(a: int, b: int) -> tuple[float, float]:
        p = list(distribuidor_ids) + [a, b] + ([uf] if uf else [])
        r = con.execute(
            f"""SELECT coalesce(sum(valor),0), coalesce(sum(unidades),0)
                  FROM v_vendas_mensal
                 WHERE distribuidor_id IN ({marca})
                   AND periodo BETWEEN ? AND ?{cond_uf}""", p).fetchone()
        return float(r[0]), float(r[1])

    val_c, un_c = soma(ini, fim)
    val_ca, un_ca = soma(ini_ant, fim_ant)
    merc = resumo(con, uf=uf, mercado=mercado, molecula=molecula)
    if not merc["disponivel"]:
        return merc

    g_cli_val = crescimento_pct(val_c, val_ca)
    g_cli_un = crescimento_pct(un_c, un_ca)
    g_mer_val = merc["cresc_valor_pct"]
    g_mer_un = merc["cresc_unidades_pct"]

    def leitura(gc, gm) -> str | None:
        """Frase factual. Nunca diz que 'cresceu' quem caiu."""
        if gc is None or gm is None:
            return None
        d = gc - gm
        if gc >= 0 and gm >= 0:
            base = "O cliente cresceu"
        elif gc >= 0 > gm:
            base = "O cliente cresceu enquanto o mercado caiu"
        elif gc < 0 <= gm:
            base = "O cliente caiu enquanto o mercado cresceu"
        else:
            base = "O cliente apresentou queda nominal"
        if d > 0:
            return f"{base}, com desempenho relativo superior ao mercado ({d:+.1f} p.p.)."
        if d < 0:
            return f"{base}, com desempenho relativo inferior ao mercado ({d:+.1f} p.p.)."
        return f"{base}, em linha com o mercado (0,0 p.p.)."

    return {
        "disponivel": True,
        "janela": {"ini": ini, "fim": fim, "ini_ant": ini_ant, "fim_ant": fim_ant},
        "recorte": {"uf": uf, "mercado": mercado, "molecula": molecula},
        "cliente": {
            "valor": val_c, "valor_ant": val_ca, "cresc_valor_pct": g_cli_val,
            "unidades": un_c, "unidades_ant": un_ca, "cresc_unidades_pct": g_cli_un,
        },
        "mercado": {
            "valor": merc["valor_ytd"], "valor_ant": merc["valor_ytd_ant"],
            "cresc_valor_pct": g_mer_val,
            "unidades": merc["unidades_ytd"], "unidades_ant": merc["unidades_ytd_ant"],
            "cresc_unidades_pct": g_mer_un,
        },
        "diferenca_valor_pp": (g_cli_val - g_mer_val)
                              if (g_cli_val is not None and g_mer_val is not None) else None,
        "diferenca_unidades_pp": (g_cli_un - g_mer_un)
                                 if (g_cli_un is not None and g_mer_un is not None) else None,
        "leitura_valor": leitura(g_cli_val, g_mer_val),
        "leitura_unidades": leitura(g_cli_un, g_mer_un),
        "calculo": Calculo(
            formula=("diferenca (p.p.) = crescimento do cliente (%) - "
                     "crescimento do mercado (%)"),
            valores={"janela": f"{ini}-{fim} vs {ini_ant}-{fim_ant}",
                     "cliente (valor)": f"{g_cli_val:+.1f}%" if g_cli_val is not None else "n/d",
                     "mercado (valor)": f"{g_mer_val:+.1f}%" if g_mer_val is not None else "n/d",
                     "cliente (unidades)": f"{g_cli_un:+.1f}%" if g_cli_un is not None else "n/d",
                     "mercado (unidades)": f"{g_mer_un:+.1f}%" if g_mer_un is not None else "n/d"},
            premissas=[
                f"Janela imposta pela fonte de mercado ({ini}-{fim} vs "
                f"{ini_ant}-{fim_ant}); o cliente foi medido na mesma janela, "
                f"nao no periodo selecionado na tela.",
                "Elos diferentes: o cliente e medido em venda ao PDV; o mercado, "
                "em venda ao consumidor. A COMPARACAO E DE RITMO DE CRESCIMENTO, "
                "nao de tamanho — os valores absolutos nao sao somaveis nem "
                "divisiveis entre si.",
                "Comparar em unidades e mais seguro que em valor: preco de "
                "varejo e preco de distribuidor sobem por motivos diferentes.",
                "Diferenca em pontos percentuais (p.p.).",
            ],
        ).como_dict(),
    }


def ponte_produtos(con: sqlite3.Connection, distribuidor_ids: list[int],
                   ini: int, fim: int, *, uf=None, top_n: int = 50) -> dict:
    """Liga os SKUs do cliente ao mercado IQVIA correspondente.

    A base nao traz chave: produto_id de v_mercado nao e preenchido e os nomes
    divergem entre as fontes ('LORASLIV 10MG 12CPD VTC' no cadastro x
    'LORASLIV CPR 10.0 MG  X 12' no mercado). A ligacao aqui e por texto
    normalizado e e PARCIAL de proposito — o que nao casa aparece em
    'sem_correspondencia' em vez de ser silenciosamente descartado.
    """
    if not _tem_iqvia(con):
        return _sem(_INDISP_SEM_IQVIA)
    if not distribuidor_ids:
        return _sem("Cliente sem distribuidor vinculado.")

    marca = ",".join("?" * len(distribuidor_ids))
    vendas = con.execute(
        f"""SELECT s.produto_id, p.apresentacao,
                   coalesce(sum(s.valor),0), coalesce(sum(s.unidades),0)
              FROM v_vendas_mensal s
              LEFT JOIN dim_product p ON p.id = s.produto_id
             WHERE s.distribuidor_id IN ({marca}) AND s.periodo BETWEEN ? AND ?
             GROUP BY s.produto_id
             ORDER BY 3 DESC""", list(distribuidor_ids) + [ini, fim]).fetchall()

    where, params = _filtros(uf)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""

    def _agrega(coluna: str) -> dict[str, dict]:
        saida: dict[str, dict] = {}
        for chave, mercado, vmd, tot, vmd_a, tot_a in con.execute(
            f"""SELECT {coluna}, min(mercado),
                       coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd END),0),
                       coalesce(sum(un_ytd),0),
                       coalesce(sum(CASE WHEN eh_vitamedic=1 THEN un_ytd_ant END),0),
                       coalesce(sum(un_ytd_ant),0)
                  FROM v_mercado{filtro} GROUP BY {coluna}""", params):
            if chave:
                saida[chave.strip().upper()] = {
                    "rotulo": chave, "mercado": mercado, "vitamedic_un": float(vmd),
                    "mercado_un": float(tot), "vitamedic_un_ant": float(vmd_a),
                    "mercado_un_ant": float(tot_a),
                }
        return saida

    por_apres = _agrega("apresentacao")
    por_mol = _agrega("molecula")
    # Molecula mais longa primeiro: 'DIPIRONA MONOIDRATADA' antes de 'DIPIRONA'.
    mols = sorted(por_mol, key=len, reverse=True)

    ligados, sem = [], []
    for pid, apres, valor, unidades in vendas:
        chave = (apres or "").strip().upper()
        m = por_apres.get(chave)
        nivel = "apresentacao"
        if not m or m["mercado_un"] <= 0:
            achou = next((k for k in mols if k in chave), None)
            m = por_mol.get(achou) if achou else None
            nivel = "molecula"
        if not m or m["mercado_un"] <= 0:
            sem.append({"produto_id": pid, "produto": apres or f"produto {pid}",
                        "faturamento": float(valor)})
            continue
        s = m["vitamedic_un"] / m["mercado_un"] * 100
        s_a = (m["vitamedic_un_ant"] / m["mercado_un_ant"] * 100
               if m["mercado_un_ant"] else None)
        ligados.append({
            "produto_id": pid, "produto": apres, "mercado": m["mercado"],
            "nivel_ligacao": nivel, "referencia_mercado": m["rotulo"],
            "faturamento_cliente": float(valor), "unidades_cliente": float(unidades),
            "mercado_un": m["mercado_un"], "vitamedic_un": m["vitamedic_un"],
            "share_industria_pct": s, "share_industria_ant_pct": s_a,
            "delta_share_pp": (s - s_a) if s_a is not None else None,
        })

    fat_lig = sum(i["faturamento_cliente"] for i in ligados)
    fat_sem = sum(i["faturamento"] for i in sem)
    total = fat_lig + fat_sem
    por_nivel = {
        n: {"nivel": n,
            "skus": sum(1 for i in ligados if i["nivel_ligacao"] == n),
            "faturamento": sum(i["faturamento_cliente"] for i in ligados
                               if i["nivel_ligacao"] == n)}
        for n in ("apresentacao", "molecula")
    }
    return {
        "disponivel": True,
        "n_ligados": len(ligados),
        "n_sem_correspondencia": len(sem),
        "por_nivel": list(por_nivel.values()),
        "faturamento_ligado": fat_lig,
        "faturamento_sem_correspondencia": fat_sem,
        "cobertura_da_ponte_pct": (fat_lig / total * 100) if total else None,
        "itens": sorted(ligados, key=lambda x: x["faturamento_cliente"], reverse=True)[:top_n],
        "sem_correspondencia": sorted(sem, key=lambda x: x["faturamento"], reverse=True)[:top_n],
        "calculo": Calculo(
            formula=("ligacao em 2 niveis: 1) apresentacao identica (exata); "
                     "2) molecula contida no nome do produto (mais ampla). "
                     "Cada SKU informa por qual nivel entrou."),
            valores={"SKUs ligados": len(ligados),
                     "por apresentacao": por_nivel["apresentacao"]["skus"],
                     "por molecula": por_nivel["molecula"]["skus"],
                     "SKUs sem correspondencia": len(sem),
                     "faturamento coberto pela ponte": round(fat_lig, 2),
                     "cobertura da ponte": (f"{fat_lig / total * 100:.1f}%"
                                            if total else "n/d")},
            premissas=[
                "A ponte e PARCIAL: a base nao tem chave entre as duas fontes "
                "(produto_id do mercado vem vazio) e os nomes divergem. O que "
                "nao casa fica listado, nao sumido.",
                "Nivel 'molecula' e mais amplo que o SKU: compara o produto do "
                "cliente com o mercado da molecula inteira, somando outras "
                "dosagens e embalagens. Serve de contexto competitivo, nao de "
                "share do SKU.",
                "Marcas cujo nome nao contem a molecula (ex.: nomes de fantasia) "
                "nao casam automaticamente e ficam de fora — por isso a "
                "cobertura da ponte e sempre mostrada junto do resultado.",
                "O share mostrado por SKU e da INDUSTRIA naquele mercado, nao "
                "do cliente: e o contexto competitivo do produto que ele "
                "distribui, nao a fatia dele.",
                "Quanto menor a cobertura da ponte, menos representativa e a "
                "leitura de mercado para a carteira deste cliente.",
            ],
        ).como_dict(),
    }
