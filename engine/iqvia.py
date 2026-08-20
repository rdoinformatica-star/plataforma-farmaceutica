"""Leitor da base IQVIA Mercado Relevante (dados de mercado/concorrencia).

Diferente do sell-out: aqui o payload e JSON puro, sem compressao, no bloco
<script type="application/json" id="__model_json__">.

Duas abas:
  m24 - 24 meses (o mais recente termina em jun/2026)
  m5  - 5 anos MAT junho

Layout de cada linha de 'sku' (documentado no proprio JS do dashboard):
  [mer, apre, uf, canal, tipo, labFull, uL, rL, uP, rP, uYtd, rYtd, uYtdP, rYtdP]

  'L'   = ultimo periodo (mes)      'P'    = periodo anterior
  'Ytd' = acumulado do ano          'YtdP' = acumulado do ano anterior
  u = unidades, r = R$

Atencao: o preco daqui e de VAREJO ao consumidor. O preco do sell-out e do
distribuidor para o PDV. Sao elos diferentes da cadeia - nao compare os dois.
"""
import io
import json
import os
import re

import config

# posicoes na linha de sku
MER, APRE, UF, CANAL, TIPO, LAB = 0, 1, 2, 3, 4, 5
U_CUR, R_CUR, U_PRV, R_PRV = 6, 7, 8, 9
U_YTD, R_YTD, U_YTDP, R_YTDP = 10, 11, 12, 13


def load(aba="m24"):
    """Carrega uma aba do modelo, com cache em JSON para acelerar reexecucoes."""
    cache = os.path.join(config.CACHE, f"iqvia_{aba}.json")
    if os.path.exists(cache):
        with io.open(cache, encoding="utf-8") as fh:
            return json.load(fh)

    config.exigir(config.MERCADO_HTML, "Dashboard de Mercado Relevante")
    print(f"Lendo a base IQVIA (aba {aba}) - so acontece na primeira execucao...")
    with io.open(config.MERCADO_HTML, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    m = re.search(
        r'<script type="application/json" id="__model_json__">(.*?)</script>', src, re.S
    )
    if not m:
        raise SystemExit("Bloco __model_json__ nao encontrado no HTML de mercado.")
    model = json.loads(m.group(1))
    d = model[aba]
    d["_meta"] = model.get("meta", {})
    with io.open(cache, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    return d


def vitamedic_labs(d):
    """Indices de labFull que pertencem ao grupo VITAMEDIC."""
    g = d["labs"].index("VITAMEDIC")
    return {i for i, gi in enumerate(d["labFullToG"]) if gi == g}


def ufs_idx(d, siglas):
    """Converte siglas de UF nos indices usados pela base."""
    return {d["ufs"].index(s) for s in siglas if s in d["ufs"]}


def fmt(v, c=0):
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")
