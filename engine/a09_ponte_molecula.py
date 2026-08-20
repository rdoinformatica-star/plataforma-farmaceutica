"""Ponte: SKUs do distribuidor  x  posicao da VITAMEDIC na mesma molecula (IQVIA).

    python a09_ponte_molecula.py MILLENIUM
    python a09_ponte_molecula.py EMEFARMA

Responde: o preco da industria contra as concorrentes esta custando venda ao distribuidor?

Atencao: o share e o preco daqui sao da INDUSTRIA no varejo (PDV -> consumidor).
O preco do sell-out e do distribuidor -> PDV. Elos diferentes, nao comparar entre si.
"""
import sys
from collections import defaultdict

import numpy as np

import iqvia as Q
from vmd import Pack, ESCALA as S

ALVO = (sys.argv[1] if len(sys.argv) > 1 else "EMEFARMA").upper()
UFS = ["RJ", "ES"]

# SKU do sell-out -> mercado relevante do IQVIA (mapeamento manual; nomes divergem)
MAPA = {
    "DIPIRONA MONOIDRATADA MG CPR 1.0 G  X 10":            "DIPIRONA 1G COM C/10",
    "DIPIRONA MONOIDRATADA MG CPR 20X10 500.0 MG":         "DIPIRONA MONOIDRATADA 500MG COM C/20X10",
    "LORASLIV CPR 10.0 MG  X 12":                          "LORASLIV 10MG COM C/ 1X12",
    "CLORIDRATO DE FEXOFENADINA MG SUSP ORAL 6.0 MG 60.0 ML X 1 /": "FEXOFENADINA 60ML",
    "IVERMECTINA MG CPR 6.0 MG  X 4":                      "IVERMECTINA 6MG COM C/ 01X04 GENERICO",
    "IVERMECTINA MG CPR 6.0 MG  X 8":                      "IVERMECTINA 6MG COM C/ 125X4 GENERICO",
    "BESILATO DE ANLODIPINO MG CPR 5.0 MG  X 30":          "BESILATO DE ANLODIPINO 5MG COM C/2X15 GEN",
    "BESILATO DE ANLODIPINO MG CPR 10.0 MG  X 30":         "BESILATO DE ANLODIPINO 10MG COM C/3X10 GEN",
    "FLUCONAZOL MG CAPSULAS 150.0 MG  X 2":                "FLUCONAZOL 150MG CAP C/ 1X2 GEN",
    "FLUCONID CAPSULAS 150.0 MG  X 2":                     "FLUCONID 150MG CAP C/ 1X2",
    "FOSFATO SODICO PREDNISOLONA MG SOLUCAO 3.0":          "FOSFATO SODICO DE PREDNISOLONA 3MG/ML SOL OR 60ML",
    "LORATADINA MG CPR 10.0 MG  X 12":                     "LORATADINA 10MG COM C/ 1X12",
    "IBUPROFENO 600 MG CPR 600.0 MG  X 20":                "IBUPROFENO 600MG COM C/ 2X10",
    "MALEA ENALAPRIL MG CPR 10.0 MG  X 30":                "MALEATO DE ENALAPRIL 10MG COMP C/ 3X10 GENERICO",
    "NIMESULIDA MG CPR 100.0 MG  X 12":                    "NIMESULIDA 100MG COM C/1X12 GENERICO",
    "NIMELIT CPR 100.0 MG  X 12":                          "NIMELIT 100MG COM C/ 1X12",
    "HEPATOVIT FLAC ABACAXI 10.0 ML X 60":                 "HEPATOVIT ABACAXI 10ML C/ 60 FLACONETES",
    "ALGY-FLANDERIL CPR 600.0 MG  X 20":                   "ALGY-FLANDERIL 600MG COM C/ 2X10",
    "ALGY-FLANDERIL CPR 300.0 MG  X 20":                   "ALGY-FLANDERIL 300MG COM C/ 2X10",
    "ENERGRIP C CPR EFE LARA 1.0 G  X 10":                 "ENERGRIP C 1G COM EFERV C/10",
    "DORALEX CPR 1.0 G  X 10":                             "DORALEX 1G COM C/10",
    "ATENOLOL MG CPR 25.0 MG  X 30":                       "ATENOLOL 25MG COM C/2X15",
    "ATENOLOL MG CPR 50.0 MG  X 30":                       "ATENOLOL 50MG COM C/2X15",
    "VERTIZAN CPR 2X25 10.0 MG  X 50":                     "VERTIZAN 10MG COM 2X25",
    "LIMP LENT KS350+120GEL 470.0 ML X 1":                 "LIMP LENT SOLUCAO 470ML",
    "BUTACID CPR REVEST 200.0 MG  X 20":                   "BUTACID 200MG COM REV C/ 2X10",
    "CLORIDRATO DE METFORMINA MG CPR 500.0 MG  X":         "CLORIDRATO DE METFORMINA 500MG COM BL 3X10",
    "BIOVARIXON CPR REVEST 900.0 MG  X 30 /100":           "BIOVARIXON 900+100MG COM REV C/ 3X10",
    "BIOVARIXON CPR REVEST 450.0 MG  X 60 /50":            "BIOVARIXON 450MG+50MG X 60",
}

# ---- faturamento do distribuidor por apresentacao (sell-out, jan-jul ano B) ----
p = Pack()
ids = p.idx_of("provNome", ALVO)
if not ids:
    raise SystemExit(f"Distribuidor '{ALVO}' nao encontrado.")
mB = np.isin(p.col["fMes"], p.janela(2026)) & np.isin(p.col["fProv"], ids)
apres = p.dic["prodApres"]
fat = np.bincount(p.col["fProd"][mB], weights=p.col["fVal"][mB].astype(np.int64),
                  minlength=len(apres)) / S

# ---- posicao da VITAMEDIC por mercado relevante (IQVIA) ----
d = Q.load("m24")
VITA = Q.vitamedic_labs(d)
alvo_uf = Q.ufs_idx(d, UFS)

mk = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0]))
for r in d["sku"]:
    if r[Q.UF] not in alvo_uf:
        continue
    a = mk[r[Q.MER]][r[Q.LAB]]
    a[0] += r[Q.U_YTD]; a[1] += r[Q.R_YTD]; a[2] += r[Q.U_YTDP]; a[3] += r[Q.R_YTDP]

info = {}
for mi, porlab in mk.items():
    if not (VITA & porlab.keys()):
        continue
    vu = vr = vup = cu = cr = cup = 0.0
    conc = []
    for li, (u, rr, up, rp) in porlab.items():
        if li in VITA:
            vu += u; vr += rr; vup += up
        else:
            cu += u; cr += rr; cup += up
            if u > 0:
                conc.append((u, d["labsFull"][li], rr / u))
    if vu <= 0 or cu <= 0:
        continue
    conc.sort(reverse=True)
    tot, totp = vu + cu, vup + cup
    pv = vr / vu
    info[d["mercados"][mi]] = {
        "pv": pv, "plider": conc[0][2], "lider": conc[0][1],
        "idx_lider": (pv / conc[0][2] - 1) * 100,
        "share": vu / tot * 100,
        "dshare": (vu / tot * 100 - vup / totp * 100) if totp > 0 else None,
        "merc": vr + cr, "nconc": len(conc),
        "n_baratos": sum(1 for c in conc if c[2] < pv),
    }

# ---- junta ----
linhas = []
for i, nome in enumerate(apres):
    if fat[i] <= 0:
        continue
    chave = next((k for k in MAPA if nome.startswith(k)), None)
    if not chave:
        continue
    I = info.get(MAPA[chave])
    if I:
        linhas.append((fat[i], nome, I))
linhas.sort(reverse=True)

print("=" * 118)
print(f"PONTE MOLECULA - {ALVO}  x  posicao da VITAMEDIC em {'+'.join(UFS)} (IQVIA, YTD jan-jun/26)")
print("=" * 118)
print(f"\n{'SKU no distribuidor':<44}{'R$ distr':>10}{'Share':>8}{'dShare':>9}"
      f"{'P.Vita':>8}{'P.lider':>8}{'vs lider':>9}{'+baratos':>10}  Lider")
for fa, nome, I in linhas:
    ds = f"{I['dshare']:+.1f}pp" if I["dshare"] is not None else "n/d"
    print(f"{nome[:43]:<44}{fa:>10,.0f}{I['share']:>7.1f}%{ds:>9}"
          f"{I['pv']:>8.2f}{I['plider']:>8.2f}{I['idx_lider']:>+8.0f}%"
          f"{I['n_baratos']:>4}/{I['nconc']:<5} {I['lider'][:18]}")

print("\n" + "=" * 118)
print("VEREDITO - o preco da industria explica a performance?")
print("=" * 118)
tot = pesa = naoe = 0.0
for fa, nome, I in linhas:
    ds = I["dshare"] or 0
    caro, perde = I["idx_lider"] > 10, ds < -1
    if caro and perde:
        v = "PRECO PESA - cara vs lider e perdendo share"; pesa += fa
    elif caro:
        v = "cara, mas ganhando share -> a marca sustenta o premio"
    elif perde:
        v = "NAO E PRECO - competitiva e perdendo share (execucao/distribuicao)"; naoe += fa
    else:
        v = "saudavel - competitiva e estavel ou ganhando"
    tot += fa
    print(f"  {nome[:42]:<43} share {I['share']:>5.1f}% {ds:>+6.1f}pp  vs lider {I['idx_lider']:>+5.0f}%   {v}")

print(f"\n  Faturamento coberto: R$ {tot:,.0f}")
print(f"    PRECO pesa            : R$ {pesa:,.0f}  ({pesa/tot*100:.0f}%)")
print(f"    NAO e preco           : R$ {naoe:,.0f}  ({naoe/tot*100:.0f}%)")
print(f"    saudavel              : R$ {tot-pesa-naoe:,.0f}  ({(tot-pesa-naoe)/tot*100:.0f}%)")
