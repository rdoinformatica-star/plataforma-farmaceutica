"""Analise completa de um distribuidor, parametrizada pelo nome.

    python analise.py MILLENIUM
    python analise.py EMEFARMA > ../cache/emefarma.txt

Roda o conjunto inteiro: volume, YoY, curva ABC, churn de PDV, mix, cobertura,
cross-sell, white spot, preco vs distribuidores, crescimento vs estado,
cruzamento CNPJ x UF e perfil da carteira.
"""
import sys
from collections import defaultdict

import numpy as np

from vmd import Pack, fmt_brl, fmt_int, fmt_pct, ESCALA as S

ALVO = (sys.argv[1] if len(sys.argv) > 1 else "EMEFARMA").upper()
ANO_A, ANO_B = 2025, 2026
MESES = range(1, 8)          # janela fechada jan-jul

p = Pack()
fProv, fProd, fPdv, fMes = p.col["fProv"], p.col["fProd"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64)
fVal = p.col["fVal"].astype(np.int64)
pdvUf, pdvGrp, pdvTip, pdvCid = p.col["pdvUf"], p.col["pdvGrp"], p.col["pdvTip"], p.col["pdvCid"]
apres, dUf, dGrp, dTip, dCid = p.dic["prodApres"], p.dic["uf"], p.dic["grupo"], p.dic["tipo"], p.dic["cidade"]
pdvRazao = p.dic["pdvRazao"]
per, nap = p.periodos, len(apres)

IDS = p.idx_of("provNome", ALVO)
if not IDS:
    raise SystemExit(f"Nenhum distribuidor com '{ALVO}' em provNome.")

iA = p.janela(ANO_A, MESES)
iB = p.janela(ANO_B, MESES)
mA, mB = np.isin(fMes, iA), np.isin(fMes, iB)
m_alvo = np.isin(fProv, IDS)
mAa, mBa = m_alvo & mA, m_alvo & mB
uf_lin = pdvUf[fPdv]

def H(n, t):
    print("\n" + "=" * 100)
    print(f"{n}. {t}")
    print("=" * 100)

def agg(mask):
    return fUnd[mask].sum()/S, fVal[mask].sum()/S, len(np.unique(fPdv[mask])), len(np.unique(fProd[mask]))

print("#" * 100)
print(f"# ANALISE COMERCIAL - {ALVO}")
print(f"# base {p.hdr['gerado']} | {per[0]} a {per[-1]} | {fmt_int(p.hdr['nRows'])} linhas")
print("#" * 100)

# ---------------------------------------------------------------- 1
H(1, "IDENTIFICACAO E VOLUME")
for i in IDS:
    print(f"  idx {i:>4} | {p.dic['provNome'][i]:<22} | CNPJ {p.dic['provCnpj'][i]}")
u, v, npv, nsk = agg(m_alvo)
print(f"\n  TOTAL 19 meses: un {fmt_int(u)} | {fmt_brl(v)} | {npv} PDVs | {nsk} SKUs | preco medio R$ {v/u:,.2f}")
for i in IDS:
    u_, v_, np_, ns_ = agg(fProv == i)
    print(f"    {p.dic['provNome'][i]:<16} un {fmt_int(u_):>12} | {fmt_brl(v_):>16} | {np_:>5} PDVs | {ns_:>4} SKUs")

nprov = len(p.dic["provNome"])
rk = np.bincount(fProv, weights=fVal, minlength=nprov)/S
o = np.argsort(-rk)
print(f"\n  Ranking nacional por valor (19 meses):")
for i in IDS:
    print(f"    {p.dic['provNome'][i]:<16} {int(np.where(o == i)[0][0])+1}o de {nprov}")
print(f"  Share no sell-out Vitamedic: {fVal[m_alvo].sum()/fVal.sum()*100:.2f}% do valor")

# ---------------------------------------------------------------- 2
H(2, f"CRESCIMENTO YoY (jan-jul/{ANO_A} vs jan-jul/{ANO_B})")
def yoy(mask, rot):
    a, b = mask & mA, mask & mB
    ua, va, pa, sa = agg(a); ub, vb, pb, sb = agg(b)
    if va == 0 and vb == 0: return None
    print(f"\n  {rot}")
    print(f"    Unidades {fmt_int(ua):>12} -> {fmt_int(ub):>12}  {fmt_pct((ub/ua-1)*100) if ua else 'novo'}")
    print(f"    Valor    {fmt_brl(va):>16} -> {fmt_brl(vb):>16}  {fmt_pct((vb/va-1)*100) if va else 'novo'}")
    print(f"    PDVs     {pa:>12} -> {pb:>12}  {fmt_pct((pb/pa-1)*100) if pa else 'novo'}")
    print(f"    SKUs     {sa:>12} -> {sb:>12}")
    if pa and pb:
        print(f"    R$/PDV   {va/pa:>12,.0f} -> {vb/pb:>12,.0f}  {fmt_pct((vb/pb)/(va/pa)*100-100)}")
    return (vb/va-1)*100 if va else None

g_alvo = yoy(m_alvo, f"{ALVO} CONSOLIDADO")
for i in IDS:
    yoy(fProv == i, p.dic["provNome"][i])
ua, va = fUnd[mA].sum()/S, fVal[mA].sum()/S
ub, vb = fUnd[mB].sum()/S, fVal[mB].sum()/S
g_merc = (vb/va-1)*100
print(f"\n  BENCHMARK - TOTAL VITAMEDIC ({nprov} distribuidores)")
print(f"    Unidades {fmt_int(ua):>12} -> {fmt_int(ub):>12}  {fmt_pct((ub/ua-1)*100)}")
print(f"    Valor    {fmt_brl(va):>16} -> {fmt_brl(vb):>16}  {fmt_pct(g_merc)}")
if g_alvo is not None:
    print(f"\n  >>> VANTAGEM SOBRE O MERCADO: {g_alvo-g_merc:+.1f} pp em valor")

# ---------------------------------------------------------------- 3
H(3, "CRUZAMENTO CNPJ x UF DO PDV  (CNPJ nao e praca)")
for i in IDS:
    print(f"\n  {p.dic['provNome'][i]}")
    print(f"  {'UF':<6}{'valor A':>13}{'valor B':>13}{'YoY':>9}{'PDVs B':>8}")
    for uu in range(len(dUf)):
        a = (fProv == i) & (uf_lin == uu) & mA
        b = (fProv == i) & (uf_lin == uu) & mB
        va_, vb_ = fVal[a].sum()/S, fVal[b].sum()/S
        if va_ == 0 and vb_ == 0: continue
        yv = fmt_pct((vb_/va_-1)*100, 0) if va_ else "novo"
        print(f"  {dUf[uu]:<6}{va_:>13,.0f}{vb_:>13,.0f}{yv:>9}{len(np.unique(fPdv[b])):>8}")

print(f"\n  CONSOLIDADO POR ESTADO (todos os CNPJs)")
print(f"  {'UF':<6}{'valor A':>13}{'valor B':>13}{'YoY':>9}{'delta':>13}")
deltas = []
for uu in range(len(dUf)):
    a, b = m_alvo & (uf_lin == uu) & mA, m_alvo & (uf_lin == uu) & mB
    va_, vb_ = fVal[a].sum()/S, fVal[b].sum()/S
    if va_ == 0 and vb_ == 0: continue
    deltas.append((vb_-va_, dUf[uu], va_, vb_))
for dd, uf, va_, vb_ in sorted(deltas):
    print(f"  {uf:<6}{va_:>13,.0f}{vb_:>13,.0f}{(fmt_pct((vb_/va_-1)*100,0) if va_ else 'novo'):>9}{dd:>+13,.0f}")

# ---------------------------------------------------------------- 4
H(4, "CRESCIMENTO vs O PROPRIO ESTADO")
principais = [u for _, u, _, _ in sorted(deltas, key=lambda x: -max(x[2], x[3]))][:4]
for uf in principais:
    uu = dUf.index(uf)
    est = uf_lin == uu
    eA, eB = est & mA, est & mB
    xA, xB = eA & m_alvo, eB & m_alvo
    euA, evA, epA, _ = agg(eA); euB, evB, epB, _ = agg(eB)
    xuA, xvA, xpA, _ = agg(xA); xuB, xvB, xpB, _ = agg(xB)
    if xvA == 0 and xvB == 0: continue
    gE = (evB/evA-1)*100 if evA else 0
    gX = (xvB/xvA-1)*100 if xvA else None
    print(f"\n  --- {uf} ---")
    print(f"    Estado  {fmt_brl(evA):>16} -> {fmt_brl(evB):>16}  {fmt_pct(gE)}")
    print(f"    {ALVO:<8}{fmt_brl(xvA):>16} -> {fmt_brl(xvB):>16}  {fmt_pct(gX) if gX is not None else 'novo'}")
    if gX is not None:
        print(f"    >>> vantagem {gX-gE:+.1f} pp")
    print(f"    Share valor {xvA/evA*100:>8.2f}% -> {xvB/evB*100:>7.2f}%   ({xvB/evB*100-xvA/evA*100:+.2f} pp)")
    print(f"    Penetracao PDV {xpA/epA*100:>5.1f}% -> {xpB/epB*100:>5.1f}%   |  PDVs {xpA} -> {xpB}")
    r = np.bincount(fProv[eB], weights=fVal[eB], minlength=nprov)/S
    rA = np.bincount(fProv[eA], weights=fVal[eA], minlength=nprov)/S
    oB, oA = np.argsort(-r), np.argsort(-rA)
    print(f"    TOP 6 no estado: ", end="")
    print(" | ".join(f"{p.dic['provNome'][j][:16]} {r[j]/evB*100:.1f}%" for j in oB[:6]))
    for i in IDS:
        if r[i] > 0:
            print(f"      {p.dic['provNome'][i]}: {int(np.where(oA==i)[0][0])+1}o -> {int(np.where(oB==i)[0][0])+1}o")

# ---------------------------------------------------------------- 5
H(5, "CURVA ABC (valor jan-jul do ano B)")
vB = np.bincount(fProd[mBa], weights=fVal[mBa], minlength=nap)/S
uB = np.bincount(fProd[mBa], weights=fUnd[mBa], minlength=nap)/S
vA = np.bincount(fProd[mAa], weights=fVal[mAa], minlength=nap)/S
cob = defaultdict(set)
for pr, pd_ in zip(fProd[mBa], fPdv[mBa]): cob[pr].add(pd_)
npdvB = len(np.unique(fPdv[mBa]))
o = np.argsort(-vB); tot = vB.sum(); ac = 0
print(f"\n  PDVs ativos: {npdvB} | SKUs vendidos: {int((vB>0).sum())} de {nap}")
print(f"\n  {'#':<4}{'Apresentacao':<44}{'Valor':>12}{'%ac':>6}{'Unid':>10}{'YoY':>9}{'PDVs':>6}{'Cob%':>6}{'C':>3}")
nA_ = nB_ = nC_ = 0
for r, i in enumerate(o, 1):
    if vB[i] <= 0: break
    sh = vB[i]/tot*100; ac += sh
    c = "A" if ac <= 80 else ("B" if ac <= 95 else "C")
    nA_ += c == "A"; nB_ += c == "B"; nC_ += c == "C"
    if r <= 30:
        y = fmt_pct((vB[i]/vA[i]-1)*100, 0) if vA[i] > 0 else "novo"
        print(f"  {r:<4}{apres[i][:43]:<44}{vB[i]:>12,.0f}{ac:>6.1f}{uB[i]:>10,.0f}{y:>9}"
              f"{len(cob[i]):>6}{len(cob[i])/npdvB*100:>6.1f}{c:>3}")
print(f"\n  Curva: {nA_} A | {nB_} B | {nC_} C")
vs = np.sort(vB[vB > 0])[::-1]; cs = np.cumsum(vs)/vs.sum()*100
print(f"  Concentracao: top 5 SKUs = {cs[4]:.1f}% | top 10 = {cs[9]:.1f}%")

# ---------------------------------------------------------------- 6
H(6, "MOVIMENTACAO DE PDVs")
pA = set(np.unique(fPdv[mAa]).tolist()); pB = set(np.unique(fPdv[mBa]).tolist())
ret, perd, novo = pA & pB, pA - pB, pB - pA
vpA, vpB = defaultdict(float), defaultdict(float)
for k, x in zip(fPdv[mAa], fVal[mAa]): vpA[k] += x/S
for k, x in zip(fPdv[mBa], fVal[mBa]): vpB[k] += x/S
vr_a = sum(vpA[i] for i in ret); vr_b = sum(vpB[i] for i in ret)
v_pd = sum(vpA[i] for i in perd); v_nv = sum(vpB[i] for i in novo)
print(f"\n  PDVs {len(pA)} -> {len(pB)}   (saldo {len(novo)-len(perd):+d})")
print(f"  RETIDOS  {len(ret):>6} ({len(ret)/len(pA)*100:.1f}%)  {fmt_brl(vr_a)} -> {fmt_brl(vr_b)}  {fmt_pct((vr_b/vr_a-1)*100)}")
print(f"  PERDIDOS {len(perd):>6} ({len(perd)/len(pA)*100:.1f}%)  valiam {fmt_brl(v_pd)}   ticket {fmt_brl(v_pd/max(len(perd),1))}")
print(f"  NOVOS    {len(novo):>6}          geraram {fmt_brl(v_nv)}   ticket {fmt_brl(v_nv/max(len(novo),1))}")
pl = defaultdict(lambda: [0, 0.0])
for i in perd:
    k = dUf[pdvUf[i]]; pl[k][0] += 1; pl[k][1] += vpA[i]
print(f"\n  Perdidos por UF:")
for uf, (n, vv) in sorted(pl.items(), key=lambda x: -x[1][1])[:6]:
    print(f"    {uf}  {n:>5} PDVs  {fmt_brl(vv)}")
print(f"\n  TOP 15 PDVs perdidos:")
for i in sorted(perd, key=lambda x: -vpA[x])[:15]:
    print(f"    {pdvRazao[i][:44]:<45}{dUf[pdvUf[i]]:<4}{dCid[pdvCid[i]][:16]:<17}{vpA[i]:>11,.0f}")

# ---------------------------------------------------------------- 7
H(7, "MIX E COBERTURA")
mix = defaultdict(set)
for k, pr in zip(fPdv[mBa], fProd[mBa]): mix[k].add(pr)
tam = np.array([len(x) for x in mix.values()])
print(f"\n  Mix medio {tam.mean():.1f} SKUs | mediana {np.median(tam):.0f}")
totB_mix = sum(vpB.values())
for lo, hi, rot in ((1,1,"1 SKU"), (2,3,"2-3"), (4,9,"4-9"), (10,999,"10+")):
    ids = [k for k, x in mix.items() if lo <= len(x) <= hi]
    vv = sum(vpB[i] for i in ids)
    print(f"    {rot:<6}{len(ids):>6} PDVs ({len(ids)/len(tam)*100:>4.1f}%)  {fmt_brl(vv):>14} "
          f"({vv/totB_mix*100:>4.1f}% do valor)  R$/PDV {vv/max(len(ids),1):>8,.0f}")
print(f"\n  Ganho ao subir 10pp de cobertura nos 20 maiores SKUs:")
pot = 0
for i in o[:20]:
    if vB[i] <= 0: break
    rpp = vB[i]/len(cob[i]); g = rpp*(npdvB*0.10); pot += g
    print(f"    {apres[i][:42]:<43}{len(cob[i]):>6}{len(cob[i])/npdvB*100:>6.1f}%  R$/PDV {rpp:>7,.0f}  +{g:>10,.0f}")
print(f"  >>> TOTAL: {fmt_brl(pot)} em 7 meses (~{fmt_brl(pot/7*12)}/ano)")

anc = sorted(cob, key=lambda i: -len(cob[i]))[:2]
for a in anc:
    print(f"\n  CROSS-SELL a partir de {apres[a][:52]} ({len(cob[a])} PDVs):")
    fal = []
    for i in o[:25]:
        if i == a or vB[i] <= 0: continue
        nt = len(cob[a]) - len(cob[a] & cob[i])
        fal.append((nt*vB[i]/len(cob[i]), apres[i], nt))
    for potx, nm, nt in sorted(fal, reverse=True)[:5]:
        print(f"    falta em {nt:>5} PDVs | {nm[:44]:<45} potencial {fmt_brl(potx)}")

# ---------------------------------------------------------------- 8
H(8, "WHITE SPOT E PRECO vs OUTROS DISTRIBUIDORES (nas pracas do distribuidor)")
ufs_alvo = [dUf.index(x) for x in principais[:2]]
base = mB & np.isin(uf_lin, ufs_alvo)
mine, other = base & m_alvo, base & ~m_alvo
ve = np.bincount(fProd[mine], weights=fVal[mine], minlength=nap)/S
ue = np.bincount(fProd[mine], weights=fUnd[mine], minlength=nap)/S
vo = np.bincount(fProd[other], weights=fVal[other], minlength=nap)/S
uo = np.bincount(fProd[other], weights=fUnd[other], minlength=nap)/S
te, to = ve.sum(), vo.sum()
shm = te/(te+to)
print(f"\n  Praca {'+'.join(principais[:2])}: mercado {fmt_brl(te+to)} | {ALVO} {fmt_brl(te)} = {shm*100:.1f}% share")
gap = (ve+vo)*shm - ve
og = np.argsort(-gap); sg = 0
print(f"\n  MAIORES LACUNAS (share do SKU abaixo do share medio):")
print(f"  {'Apresentacao':<44}{'Mercado':>13}{'Meu':>11}{'Share':>7}{'Gap':>11}")
for i in og[:15]:
    if gap[i] <= 0: break
    sg += gap[i]
    print(f"  {apres[i][:43]:<44}{ve[i]+vo[i]:>13,.0f}{ve[i]:>11,.0f}{ve[i]/(ve[i]+vo[i])*100:>6.1f}%{gap[i]:>11,.0f}")
print(f"  >>> Gap somado: {fmt_brl(sg)} em 7 meses (~{fmt_brl(sg/7*12)}/ano)")

print(f"\n  PRECO POR SKU vs demais distribuidores da praca:")
print(f"  {'Apresentacao':<44}{'Un':>10}{'P.meu':>8}{'P.merc':>8}{'Dif':>8}")
fora = 0
for i in np.argsort(-ve)[:22]:
    if ue[i] < 200 or uo[i] < 200: continue
    pe, po = ve[i]/ue[i], vo[i]/uo[i]
    d = (pe/po-1)*100
    if abs(d) > 8: fora += 1
    print(f"  {apres[i][:43]:<44}{ue[i]:>10,.0f}{pe:>8.2f}{po:>8.2f}{d:>+7.1f}%")
print(f"  Preco medio geral: meu R$ {te/ue.sum():.2f} vs mercado R$ {to/uo.sum():.2f}"
      f"  ({(te/ue.sum())/(to/uo.sum())*100-100:+.1f}%)  |  SKUs fora de +-8%: {fora}")

# ---------------------------------------------------------------- 9
H(9, "PERFIL DA CARTEIRA E CONCENTRACAO")
tv, tn = defaultdict(float), defaultdict(set)
gv, gn = defaultdict(float), defaultdict(set)
for k, x in zip(fPdv[mBa], fVal[mBa]):
    tv[dTip[pdvTip[k]]] += x/S; tn[dTip[pdvTip[k]]].add(k)
    gv[dGrp[pdvGrp[k]]] += x/S; gn[dGrp[pdvGrp[k]]].add(k)
totB = fVal[mBa].sum()/S
print(f"\n  {'Tipo de PDV':<26}{'PDVs':>7}{'Valor':>14}{'%':>7}{'R$/PDV':>9}")
for t, vv in sorted(tv.items(), key=lambda x: -x[1]):
    print(f"  {t[:25]:<26}{len(tn[t]):>7}{vv:>14,.0f}{vv/totB*100:>6.1f}%{vv/len(tn[t]):>9,.0f}")
print(f"\n  {'Grupo/rede':<32}{'PDVs':>7}{'Valor':>13}{'%':>7}{'R$/PDV':>9}")
for g, vv in sorted(gv.items(), key=lambda x: -x[1])[:8]:
    print(f"  {g[:31]:<32}{len(gn[g]):>7}{vv:>13,.0f}{vv/totB*100:>6.1f}%{vv/len(gn[g]):>9,.0f}")
vs2 = np.sort(np.array(list(vpB.values())))[::-1]; cum = np.cumsum(vs2)/vs2.sum()*100
print(f"\n  Concentracao de PDV: ", end="")
print(" | ".join(f"top {k} = {cum[k-1]:.1f}%" for k in (10, 50, 100, 500) if k <= len(vs2)))

# ---------------------------------------------------------------- 10
H(10, "TENDENCIA - ultimos 8 meses")
print(f"  {'Mes':<9}{'Unidades':>11}{'Valor':>13}{'PDVs':>7}{'SKUs':>6}{'R$/PDV':>9}")
for mi in range(len(per)-8, len(per)):
    m = m_alvo & (fMes == mi)
    u_, v_, np_, ns_ = agg(m)
    print(f"  {per[mi][4:]}/{per[mi][:4]}{u_:>11,.0f}{v_:>13,.0f}{np_:>7}{ns_:>6}{v_/max(np_,1):>9,.0f}")
