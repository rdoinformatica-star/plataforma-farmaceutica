"""EMEFARMA - cobertura de SKU, cross-sell, grupos, concentracao e diagnostico do ES."""
import numpy as np
from collections import defaultdict
from vmd import Pack, fmt_brl, fmt_int, fmt_pct

p = Pack()
S = 100.0
fProv, fProd, fPdv, fMes = p.col["fProv"], p.col["fProd"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64); fVal = p.col["fVal"].astype(np.int64)
EME = p.idx_of("provNome", "EMEFARMA"); RJ, ES = EME
per = p.periodos
i2025 = [per.index(f"2025{m:02d}") for m in range(1, 8)]
i2026 = [per.index(f"2026{m:02d}") for m in range(1, 8)]
apres = p.dic["prodApres"]
pdvUf, pdvGrp, pdvTip = p.col["pdvUf"], p.col["pdvGrp"], p.col["pdvTip"]
dUf, dGrp, dTip = p.dic["uf"], p.dic["grupo"], p.dic["tipo"]

m_eme = np.isin(fProv, EME)
m26 = m_eme & np.isin(fMes, i2026)
m25 = m_eme & np.isin(fMes, i2025)
nap = len(apres)

# ---------- 6. COBERTURA: oportunidade dentro da propria base ----------
print("=" * 80)
print("6. COBERTURA DE SKU NA BASE ATUAL - o cross-sell mais barato que existe")
print("=" * 80)

pdvs26 = np.unique(fPdv[m26]); n_pdv = len(pdvs26)
cob = defaultdict(set)
for pr, pd_ in zip(fProd[m26], fPdv[m26]): cob[pr].add(pd_)
v26 = np.bincount(fProd[m26], weights=fVal[m26], minlength=nap) / S

# receita media por PDV que ja compra o SKU -> potencial se ampliar cobertura
print(f"\n  Base ativa EMEFARMA jan-jul/26: {n_pdv} PDVs")
print(f"\n  {'Apresentacao':<42}{'PDVs':>6}{'Cob%':>7}{'R$/PDV':>9}{'Valor 26':>11}{'+10pp cob':>11}")
ordem = np.argsort(-v26)
pot_total = 0
for i in ordem[:22]:
    if v26[i] <= 0: break
    np_ = len(cob[i]); c = np_ / n_pdv * 100
    rpp = v26[i] / np_
    ganho = rpp * (n_pdv * 0.10)     # ganho ao subir 10 pontos de cobertura
    pot_total += ganho
    print(f"  {apres[i][:41]:<42}{np_:>6}{c:>6.1f}%{rpp:>9,.0f}{v26[i]:>11,.0f}{ganho:>11,.0f}")
print(f"\n  >>> Subir 10pp de cobertura nos 22 SKUs acima = +{fmt_brl(pot_total)} em 7 meses "
      f"(~{fmt_brl(pot_total/7*12)}/ano)")

# ---------- 7. CROSS-SELL: pares ----------
print("\n" + "=" * 80)
print("7. CROSS-SELL - SKUs ancora e o que falta junto")
print("=" * 80)
mix = defaultdict(set)
for pd_, pr in zip(fPdv[m26], fProd[m26]): mix[pd_].add(pr)

# top 5 SKUs por numero de PDVs = ancoras
ancoras = sorted(cob.keys(), key=lambda i: -len(cob[i]))[:5]
for a in ancoras:
    base = cob[a]
    print(f"\n  ANCORA: {apres[a][:60]}  ({len(base)} PDVs)")
    faltam = []
    for i in ordem[:30]:
        if i == a or v26[i] <= 0: continue
        tem = len(base & cob[i])
        nao_tem = len(base) - tem
        rpp = v26[i] / max(len(cob[i]), 1)
        faltam.append((nao_tem * rpp, apres[i], nao_tem, tem / len(base) * 100))
    faltam.sort(reverse=True)
    for pot, nome, nt, pen in faltam[:5]:
        print(f"     falta em {nt:>5} PDVs ({100-pen:>4.0f}% da base) | {nome[:44]:<45} potencial {fmt_brl(pot)}")

# ---------- 8. GRUPOS / TIPO ----------
print("\n" + "=" * 80)
print("8. PERFIL DA CARTEIRA - grupos e tipo de PDV (jan-jul/26)")
print("=" * 80)
gv = defaultdict(float); gn = defaultdict(set)
tv = defaultdict(float); tn = defaultdict(set)
for pd_, v in zip(fPdv[m26], fVal[m26]):
    gv[dGrp[pdvGrp[pd_]]] += v / S; gn[dGrp[pdvGrp[pd_]]].add(pd_)
    tv[dTip[pdvTip[pd_]]] += v / S; tn[dTip[pdvTip[pd_]]].add(pd_)
tot26 = fVal[m26].sum() / S
print(f"\n  {'Grupo/rede':<38}{'PDVs':>7}{'Valor 26':>13}{'%':>7}{'R$/PDV':>9}")
for g, v in sorted(gv.items(), key=lambda x: -x[1])[:12]:
    print(f"  {g[:37]:<38}{len(gn[g]):>7}{v:>13,.0f}{v/tot26*100:>6.1f}%{v/len(gn[g]):>9,.0f}")
print(f"\n  {'Tipo de PDV':<38}{'PDVs':>7}{'Valor 26':>13}{'%':>7}")
for t, v in sorted(tv.items(), key=lambda x: -x[1]):
    print(f"  {t[:37]:<38}{len(tn[t]):>7}{v:>13,.0f}{v/tot26*100:>6.1f}%")

# ---------- 9. CONCENTRACAO ----------
print("\n" + "=" * 80)
print("9. CONCENTRACAO DE RISCO")
print("=" * 80)
valpdv = defaultdict(float)
for pd_, v in zip(fPdv[m26], fVal[m26]): valpdv[pd_] += v / S
vs = np.sort(np.array(list(valpdv.values())))[::-1]
cum = np.cumsum(vs) / vs.sum() * 100
for k in (10, 50, 100, 500):
    if k <= len(vs): print(f"  Top {k:>4} PDVs = {cum[k-1]:>5.1f}% do valor")
vsku = np.sort(v26[v26 > 0])[::-1]; csku = np.cumsum(vsku) / vsku.sum() * 100
print(f"  Top   5 SKUs = {csku[4]:>5.1f}% do valor  |  Top 10 SKUs = {csku[9]:.1f}%")

# ---------- 10. ES: DIAGNOSTICO ----------
print("\n" + "=" * 80)
print("10. DIAGNOSTICO EMEFARMA ES  (-41,7% em unidades)")
print("=" * 80)
es25 = (fProv == ES) & np.isin(fMes, i2025); es26 = (fProv == ES) & np.isin(fMes, i2026)
u25 = np.bincount(fProd[es25], weights=fUnd[es25], minlength=nap) / S
u26 = np.bincount(fProd[es26], weights=fUnd[es26], minlength=nap) / S
ve25 = np.bincount(fProd[es25], weights=fVal[es25], minlength=nap) / S
ve26 = np.bincount(fProd[es26], weights=fVal[es26], minlength=nap) / S
delta = u26 - u25
ordd = np.argsort(delta)
print(f"\n  --- MAIORES QUEDAS EM UNIDADES (ES) ---")
print(f"  {'Apresentacao':<44}{'Un 25':>10}{'Un 26':>10}{'Delta':>10}{'R$ perdido':>12}")
for i in ordd[:12]:
    if delta[i] >= 0: break
    print(f"  {apres[i][:43]:<44}{u25[i]:>10,.0f}{u26[i]:>10,.0f}{delta[i]:>10,.0f}{ve26[i]-ve25[i]:>12,.0f}")
print(f"\n  --- MAIORES ALTAS EM UNIDADES (ES) ---")
for i in ordd[::-1][:6]:
    if delta[i] <= 0: break
    print(f"  {apres[i][:43]:<44}{u25[i]:>10,.0f}{u26[i]:>10,.0f}{delta[i]:>+10,.0f}{ve26[i]-ve25[i]:>+12,.0f}")

# preco medio ES vs RJ
for nome, idx in (("RJ", RJ), ("ES", ES)):
    a = (fProv == idx) & np.isin(fMes, i2025); b = (fProv == idx) & np.isin(fMes, i2026)
    pa = fVal[a].sum()/fUnd[a].sum(); pb = fVal[b].sum()/fUnd[b].sum()
    print(f"\n  Preco medio {nome}: R$ {pa:,.2f} (25) -> R$ {pb:,.2f} (26)   {fmt_pct((pb/pa-1)*100)}")

# ---------- 11. TENDENCIA RECENTE ----------
print("\n" + "=" * 80)
print("11. TENDENCIA - ultimos 6 meses fechados")
print("=" * 80)
print(f"  {'Mes':<9}{'Unidades':>11}{'Valor':>13}{'PDVs':>7}{'SKUs':>6}{'Mix':>6}{'R$/PDV':>9}")
for mi in range(len(per) - 6, len(per)):
    m = m_eme & (fMes == mi)
    u = fUnd[m].sum()/S; v = fVal[m].sum()/S
    npv = len(np.unique(fPdv[m])); nsk = len(np.unique(fProd[m]))
    mixm = len(fProd[m]) / max(npv, 1)
    print(f"  {per[mi][4:]}/{per[mi][:4]}{u:>11,.0f}{v:>13,.0f}{npv:>7}{nsk:>6}{mixm:>6.1f}{v/npv:>9,.0f}")
