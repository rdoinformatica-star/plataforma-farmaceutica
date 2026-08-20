"""EMEFARMA - analise estrategica profunda (escala corrigida /100)."""
import numpy as np
from vmd import Pack, fmt_brl, fmt_int, fmt_pct, periodo_label

p = Pack()
S = 100.0  # unidades e valores estao armazenados x100

fProv, fProd, fPdv = p.col["fProv"], p.col["fProd"], p.col["fPdv"]
fMes = p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64)
fVal = p.col["fVal"].astype(np.int64)

EME = p.idx_of("provNome", "EMEFARMA")           # [230 RJ, 231 ES]
RJ, ES = EME[0], EME[1]
per = p.periodos
nper = len(per)

# janelas YoY limpas: jan-jul
i2025 = [per.index(f"2025{m:02d}") for m in range(1, 8)]
i2026 = [per.index(f"2026{m:02d}") for m in range(1, 8)]

apres = p.dic["prodApres"]
produto = p.dic["produto"]
marca = p.dic["marca"]
prodMar, prodPro = p.col["prodMar"], p.col["prodPro"]
pdvUf, pdvGrp, pdvTip, pdvCid = p.col["pdvUf"], p.col["pdvGrp"], p.col["pdvTip"], p.col["pdvCid"]

m_eme = np.isin(fProv, EME)

print("=" * 78)
print("EMEFARMA - PAINEL EXECUTIVO  (sell-out distribuidor -> PDV)")
print("=" * 78)

def bloco(mask, titulo):
    u = fUnd[mask].sum() / S
    v = fVal[mask].sum() / S
    print(f"\n{titulo}")
    print(f"  Unidades: {fmt_int(u)}   Valor: {fmt_brl(v)}   Preco medio: R$ {v/u:,.2f}")
    return u, v

bloco(m_eme, "TOTAL EMEFARMA (jan/25 - jul/26, 19 meses)")
bloco(fProv == RJ, "EMEFARMA RJ")
bloco(fProv == ES, "EMEFARMA ES")

# ---------- 1. YoY jan-jul ----------
print("\n" + "=" * 78)
print("1. CRESCIMENTO YoY  (jan-jul/2025  vs  jan-jul/2026)")
print("=" * 78)

def yoy(mask, rotulo):
    a = mask & np.isin(fMes, i2025)
    b = mask & np.isin(fMes, i2026)
    ua, va = fUnd[a].sum()/S, fVal[a].sum()/S
    ub, vb = fUnd[b].sum()/S, fVal[b].sum()/S
    pa = len(np.unique(fPdv[a])); pb = len(np.unique(fPdv[b]))
    sa = len(np.unique(fProd[a])); sb = len(np.unique(fProd[b]))
    du = (ub/ua-1)*100 if ua else None
    dv = (vb/va-1)*100 if va else None
    dp = (pb/pa-1)*100 if pa else None
    print(f"\n  {rotulo}")
    print(f"    Unidades : {fmt_int(ua):>12} -> {fmt_int(ub):>12}   {fmt_pct(du)}")
    print(f"    Valor    : {fmt_brl(va):>16} -> {fmt_brl(vb):>16}   {fmt_pct(dv)}")
    print(f"    PDVs     : {pa:>12} -> {pb:>12}   {fmt_pct(dp)}")
    print(f"    SKUs     : {sa:>12} -> {sb:>12}")
    print(f"    Un/PDV   : {ua/pa:>12,.0f} -> {ub/pb:>12,.0f}   {fmt_pct((ub/pb)/(ua/pa)*100-100)}")
    print(f"    R$/PDV   : {va/pa:>12,.0f} -> {vb/pb:>12,.0f}")
    return du, dv

yoy(m_eme, "EMEFARMA CONSOLIDADO")
yoy(fProv == RJ, "EMEFARMA RJ")
yoy(fProv == ES, "EMEFARMA ES")

# mercado total como referencia
a_all = np.isin(fMes, i2025); b_all = np.isin(fMes, i2026)
ua, ub = fUnd[a_all].sum()/S, fUnd[b_all].sum()/S
va, vb = fVal[a_all].sum()/S, fVal[b_all].sum()/S
print(f"\n  BENCHMARK - TOTAL VITAMEDIC (todos os 547 distribuidores)")
print(f"    Unidades : {fmt_int(ua):>12} -> {fmt_int(ub):>12}   {fmt_pct((ub/ua-1)*100)}")
print(f"    Valor    : {fmt_brl(va):>16} -> {fmt_brl(vb):>16}   {fmt_pct((vb/va-1)*100)}")

# ---------- 2. CURVA ABC POR APRESENTACAO ----------
print("\n" + "=" * 78)
print("2. CURVA ABC - APRESENTACOES NO EMEFARMA (base: valor jan-jul/26)")
print("=" * 78)

m26 = m_eme & np.isin(fMes, i2026)
m25 = m_eme & np.isin(fMes, i2025)
nap = len(apres)
v26 = np.bincount(fProd[m26], weights=fVal[m26], minlength=nap) / S
u26 = np.bincount(fProd[m26], weights=fUnd[m26], minlength=nap) / S
v25 = np.bincount(fProd[m25], weights=fVal[m25], minlength=nap) / S
u25 = np.bincount(fProd[m25], weights=fUnd[m25], minlength=nap) / S

# PDVs distintos por apresentacao em 26
pdv26 = {}
for prod, pdv in zip(fProd[m26], fPdv[m26]):
    pdv26.setdefault(prod, set()).add(pdv)
npdv_total26 = len(np.unique(fPdv[m26]))

ordem = np.argsort(-v26)
tot = v26.sum()
acum = 0.0
print(f"\n  PDVs ativos EMEFARMA jan-jul/26: {npdv_total26}")
print(f"\n{'#':<4}{'Apresentacao':<44}{'Valor 26':>13}{'%':>6}{'Ac%':>6}{'Un 26':>10}{'YoY val':>10}{'PDVs':>6}{'Cob%':>6}{'C':>3}")
linhas = []
for r, i in enumerate(ordem, 1):
    if v26[i] <= 0:
        break
    share = v26[i]/tot*100
    acum += share
    curva = "A" if acum <= 80 else ("B" if acum <= 95 else "C")
    yv = (v26[i]/v25[i]-1)*100 if v25[i] > 0 else None
    np_ = len(pdv26.get(i, ()))
    cob = np_/npdv_total26*100
    linhas.append((i, v26[i], share, acum, u26[i], yv, np_, cob, curva))
    if r <= 45:
        yvs = fmt_pct(yv, 0) if yv is not None else "NOVO"
        print(f"{r:<4}{apres[i][:43]:<44}{v26[i]:>13,.0f}{share:>6.1f}{acum:>6.1f}{u26[i]:>10,.0f}{yvs:>10}{np_:>6}{cob:>6.0f}{curva:>3}")

nA = sum(1 for l in linhas if l[8] == "A")
nB = sum(1 for l in linhas if l[8] == "B")
nC = sum(1 for l in linhas if l[8] == "C")
print(f"\n  Resumo: {nA} apresentacoes classe A (80% do valor) | {nB} classe B | {nC} classe C")
print(f"  Total de apresentacoes com venda em 26: {len(linhas)} de {nap} do portfolio VITAMEDIC")

import pickle, os, config
with open(os.path.join(config.CACHE, "abc.pkl"), "wb") as _fh:
    pickle.dump({"linhas": linhas, "apres": apres, "npdv_total26": npdv_total26}, _fh)
