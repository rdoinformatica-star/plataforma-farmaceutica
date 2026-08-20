"""Adaptador do Mercado Relevante (IQVIA).

Mede o elo PDV -> consumidor. O preco daqui NAO e comparavel com o do sell-out
(distribuidor -> PDV): sao pontos diferentes da cadeia. Por isso a fonte e
gravada com natureza_elo = PDV_CONSUMIDOR e a interface exibe o aviso.

Um share baixo aqui nao e falha do distribuidor — e espaco de mercado.

As posicoes das colunas vem do proprio engine/iqvia.py. Nao duplicamos os
numeros: se o formato mudar, muda num lugar so.
"""
from pathlib import Path

import numpy as np

from .. import engine_bridge
from ..base import Lote, procurar
from ..profiler import Coluna

CODIGO = "iqvia_mercado"
ROTULO = "Mercado Relevante (IQVIA)"
DATA_SOURCE = "IQVIA"

_MARCA = b'id="__model_json__"'


def pontuar(path: Path, cabeca: bytes, ext: str) -> tuple[float, str]:
    if ext not in {".html", ".htm"}:
        return 0.0, ""
    if _MARCA in cabeca or procurar(path, _MARCA) >= 0:
        return 0.99, 'bloco <script id="__model_json__"> encontrado — base IQVIA'
    return 0.0, ""


def params_sugeridos(path: Path, cabeca: bytes) -> dict:
    return {"aba": "m24", "abas_disponiveis": ["m24", "m5"],
            "aba_descricao": {"m24": "ultimos 24 meses",
                              "m5": "5 anos (MAT junho)"}}


def _rotulo(tabela, i):
    try:
        j = int(i)
    except (TypeError, ValueError):
        return None
    return tabela[j] if tabela is not None and 0 <= j < len(tabela) else None


def abrir(path: Path, params: dict, prog) -> Lote:
    aba = params.get("aba", "m24")
    sha = params.get("_sha", "")
    prog.etapa("Lendo a base de mercado", 0.10)
    d = engine_bridge.carregar_iqvia(path, aba, sha, log=prog.log)
    K = engine_bridge.constantes_iqvia()
    vit = engine_bridge.labs_vitamedic(d)

    linhas = d.get("sku") or []
    n = len(linhas)
    prog.log(f"{n:,} linhas de mercado na aba {aba}.".replace(",", "."))

    mercados = d.get("mercados", [])
    apres = d.get("apres", [])
    ufs = d.get("ufs", [])
    canais = d.get("canais", [])
    tipos = d.get("tipos", [])
    labs_full = d.get("labsFull", [])
    labs = d.get("labs", [])
    lab_para_grupo = d.get("labFullToG", [])
    moleculas = d.get("moleculas", [])
    apre_mol = d.get("apreMol", [])

    periodos = d.get("periods") or []
    periodo_ref = None
    if periodos:
        # rotulos vem como '2026/07'
        try:
            periodo_ref = int(str(periodos[-1]).replace("/", "").replace("-", "")[:6])
        except ValueError:
            periodo_ref = None

    def _col(pos):
        return [r[pos] if len(r) > pos else None for r in linhas]

    i_mer, i_apre, i_uf = _col(K["MER"]), _col(K["APRE"]), _col(K["UF"])
    i_canal, i_tipo, i_lab = _col(K["CANAL"]), _col(K["TIPO"]), _col(K["LAB"])

    t_mer = [_rotulo(mercados, i) for i in i_mer]
    t_apre = [_rotulo(apres, i) for i in i_apre]
    t_uf = [_rotulo(ufs, i) for i in i_uf]
    t_canal = [_rotulo(canais, i) for i in i_canal]
    t_tipo = [_rotulo(tipos, i) for i in i_tipo]
    t_labfull = [_rotulo(labs_full, i) for i in i_lab]
    t_labgrp = [_rotulo(labs, _rotulo(lab_para_grupo, i)) if lab_para_grupo else None
                for i in i_lab]
    t_mol = [_rotulo(moleculas, _rotulo(apre_mol, i)) if apre_mol else None
             for i in i_apre]
    eh_vit = [1 if i in vit else 0 for i in i_lab]

    def _num(pos):
        out = []
        for r in linhas:
            v = r[pos] if len(r) > pos else None
            try:
                out.append(float(v) if v is not None else None)
            except (TypeError, ValueError):
                out.append(None)
        return out

    def _cent(pos):
        return [None if v is None else int(round(v * 100)) for v in _num(pos)]

    un_atual, un_ant = _num(K["U_CUR"]), _num(K["U_PRV"])
    un_ytd, un_ytd_ant = _num(K["U_YTD"]), _num(K["U_YTDP"])
    v_atual, v_ant = _cent(K["R_CUR"]), _cent(K["R_PRV"])
    v_ytd, v_ytd_ant = _cent(K["R_YTD"]), _cent(K["R_YTDP"])

    def gravar(con, import_id, p):
        p.etapa("Gravando os dados de mercado", 0.70)
        sql = (
            "INSERT INTO fact_market(import_id, aba, periodo_ref, mercado,"
            " apresentacao, molecula, uf, canal, tipo, lab_full, lab_grupo,"
            " eh_vitamedic, un_atual, valor_atual_x100, un_ant, valor_ant_x100,"
            " un_ytd, valor_ytd_x100, un_ytd_ant, valor_ytd_ant_x100)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        dados = [
            (import_id, aba, periodo_ref, t_mer[i], t_apre[i], t_mol[i], t_uf[i],
             t_canal[i], t_tipo[i], t_labfull[i], t_labgrp[i], eh_vit[i],
             un_atual[i], v_atual[i], un_ant[i], v_ant[i],
             un_ytd[i], v_ytd[i], un_ytd_ant[i], v_ytd_ant[i])
            for i in range(n)
        ]
        con.execute("BEGIN")
        for ini in range(0, n, 50_000):
            if p.cancelado():
                raise InterruptedError("Importacao cancelada pelo usuario.")
            con.executemany(sql, dados[ini:ini + 50_000])
            # Fecha a transacao ANTES de reportar: o SQLite aceita um escritor
            # por vez, e o progresso e escrito por outra conexao.
            con.execute("COMMIT")
            p.linhas(min(ini + 50_000, n), n)
            p.etapa(f"Gravando mercado: {min(ini + 50_000, n):,} de {n:,}"
                    .replace(",", "."), 0.70 + 0.20 * (min(ini + 50_000, n) / n))
            con.execute("BEGIN")
        con.execute("COMMIT")
        return n

    def _obj(lista):
        return np.asarray(lista, dtype=object)

    def _flt(lista):
        return np.asarray([np.nan if v is None else v for v in lista], dtype=np.float64)

    colunas = [
        Coluna("Mercado relevante", _obj(t_mer)),
        Coluna("Apresentacao", _obj(t_apre)),
        Coluna("Molecula", _obj(t_mol)),
        Coluna("UF", _obj(t_uf)),
        Coluna("Canal", _obj(t_canal)),
        Coluna("Tipo", _obj(t_tipo)),
        Coluna("Laboratorio", _obj(t_labfull)),
        Coluna("Unidades (mes atual)", _flt(un_atual)),
        Coluna("Valor R$ (mes atual)", _flt(_num(K["R_CUR"]))),
        Coluna("Unidades (acumulado ano)", _flt(un_ytd)),
        Coluna("Valor R$ (acumulado ano)", _flt(_num(K["R_YTD"]))),
    ]

    return Lote(
        fonte="IQVIA",
        n_linhas=n,
        colunas=colunas,
        gravar=gravar,
        entidades={
            "mercados": len(mercados), "apresentacoes": len(apres),
            "ufs": len(ufs), "laboratorios": len(labs_full),
            "linhas_vitamedic": sum(eh_vit),
        },
        periodo={"min": periodo_ref, "max": periodo_ref,
                 "granularidade": "mes" if aba == "m24" else "ano movel"},
        avisos=[
            "Esta base mede a venda do PDV para o consumidor (varejo). O preco "
            "dela NAO e comparavel com o preco do sell-out, que e do distribuidor "
            "para o PDV."
        ],
        limitacoes=[
            "Share baixo aqui nao e falha do distribuidor: mede a participacao da "
            "industria no varejo, incluindo o que outros distribuidores e a venda "
            "direta entregam. E espaco de mercado, nao perda de execucao.",
            "A ligacao entre a apresentacao do IQVIA e o produto do sell-out nao e "
            "automatica: os dois usam nomes diferentes. Confirme o mapeamento de "
            "fontes antes de cruzar as duas bases.",
        ],
    )
