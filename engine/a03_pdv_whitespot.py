"""EMEFARMA - PDV, churn, mix, white spots e concorrencia regional."""
import numpy as np
from collections import defaultdict
from vmd import Pack, fmt_brl, fmt_int, fmt_pct

p = Pack()
S = 100.0
fProv, fProd, fPdv, fMes = p.col["fProv"], p.col["fProd"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64)
fVal = p.col["fVal"].astype(np.int64)

EME = p.idx_of("provNome", "EMEFARMA"); RJ, ES = EME
per = p.periodos
i2025 = [per.index(f"2025{m:02d}") for m in range(1, 8)]
i2026 = [per.index(f"2026{m:02d}") for m in range(1, 8)]

apres, produto, marca = p.dic["prodApres"], p.dic["produto"], p.dic["marca"]
pdvUf, pdvGrp, pdvTip = p.col["pdvUf"], p.col["pdvGrp"], p.col["pdvTip"]
pdvRazao, pdvCid = p.dic["pdvRazao"], p.col["pdvCid"]
dUf, dGrp, dTip, dCid = p.dic["uf"], p.dic["grupo"], p.dic["tipo"], p.dic["cidade"]

m_eme = np.isin(fProv, EME)
m25 = m_eme & np.isin(fMes, i2025)
m26 = m_eme & np.isin(fMes, i2026)

print("=" * 80)
print("3. BASE DE PDVs - CHURN, NOVOS E RETIDOS  (jan-jul/25 vs jan-jul/26)")
print("=" * 80)

pdv25 = set(np.unique(fPdv[m25]).tolist())
pdv26 = set(np.unique(fPdv[m26]).tolist())
retidos = pdv25 & pdv26
perdidos = pdv25 - pdv26
novos = pdv26 - pdv25

# valor por PDV em cada janela
val25 = defaultdict(float); val26 = defaultdict(float)
for pd_, v in zip(fPdv[m25], fVal[m25]): val25[pd_] += v / S
for pd_, v in zip(fPdv[m26], fVal[m26]): val26[pd_] += v / S

v_ret25 = sum(val25[i] for i in retidos); v_ret26 = sum(val26[i] for i in retidos)
v_perd = sum(val25[i] for i in perdidos)
v_novo = sum(val26[i] for i in novos)

print(f"\n  PDVs 2025: {len(pdv25):>6}      PDVs 2026: {len(pdv26):>6}")
print(f"  RETIDOS  : {len(retidos):>6}  ({len(retidos)/len(pdv25)*100:.1f}% da base 25)  "
      f"valor 25 {fmt_brl(v_ret25)} -> 26 {fmt_brl(v_ret26)}  {fmt_pct((v_ret26/v_ret25-1)*100)}")
print(f"  PERDIDOS : {len(perdidos):>6}  ({len(perdidos)/len(pdv25)*100:.1f}% da base 25)  "
      f"valeram {fmt_brl(v_perd)} em 2025  <== RECUPERAVEL")
print(f"  NOVOS    : {len(novos):>6}                       geraram {fmt_brl(v_novo)} em 2026")
print(f"\n  Saldo liquido de PDVs: {len(novos)-len(perdidos):+d}")
print(f"  Ticket medio PDV perdido: {fmt_brl(v_perd/len(perdidos))} | PDV novo: {fmt_brl(v_novo/len(novos))}")

# perdidos por UF
print("\n  --- PDVs PERDIDOS POR UF ---")
pl = defaultdict(lambda: [0, 0.0])
for i in perdidos:
    uf = dUf[pdvUf[i]]
    pl[uf][0] += 1; pl[uf][1] += val25[i]
for uf, (n, v) in sorted(pl.items(), key=lambda x: -x[1][1])[:8]:
    print(f"    {uf}  {n:>5} PDVs   {fmt_brl(v):>14} perdidos em 2025")

print("\n  --- TOP 25 PDVs PERDIDOS (maior valor em 2025, zero em 2026) ---")
top_perd = sorted(perdidos, key=lambda i: -val25[i])[:25]
print(f"    {'PDV':<42}{'UF':<4}{'Cidade':<18}{'Valor 2025':>13}")
for i in top_perd:
    print(f"    {pdvRazao[i][:41]:<42}{dUf[pdvUf[i]]:<4}{dCid[pdvCid[i]][:17]:<18}{val25[i]:>13,.0f}")

# ---------- MIX POR PDV ----------
print("\n" + "=" * 80)
print("4. MIX (SKUs por PDV) - potencial de cross-selling")
print("=" * 80)
mix26 = defaultdict(set)
for pd_, pr in zip(fPdv[m26], fProd[m26]): mix26[pd_].add(pr)
tam = np.array([len(v) for v in mix26.values()])
print(f"\n  Mix medio por PDV (jan-jul/26): {tam.mean():.1f} SKUs   mediana: {np.median(tam):.0f}")
print(f"  PDVs com 1 SKU apenas: {(tam==1).sum()} ({(tam==1).sum()/len(tam)*100:.1f}%)")
print(f"  PDVs com 2-3 SKUs    : {((tam>=2)&(tam<=3)).sum()} ({((tam>=2)&(tam<=3)).sum()/len(tam)*100:.1f}%)")
print(f"  PDVs com 4-9 SKUs    : {((tam>=4)&(tam<=9)).sum()} ({((tam>=4)&(tam<=9)).sum()/len(tam)*100:.1f}%)")
print(f"  PDVs com 10+ SKUs    : {(tam>=10).sum()} ({(tam>=10).sum()/len(tam)*100:.1f}%)")

faixas = [(1,1),(2,3),(4,9),(10,999)]
print(f"\n  {'Faixa de mix':<16}{'PDVs':>8}{'Valor 26':>15}{'R$/PDV':>11}")
for lo, hi in faixas:
    ids = [k for k, v in mix26.items() if lo <= len(v) <= hi]
    v = sum(val26[i] for i in ids)
    print(f"  {f'{lo}-{hi if hi<999 else '+'} SKUs':<16}{len(ids):>8}{v:>15,.0f}{v/max(len(ids),1):>11,.0f}")

# ---------- WHITE SPOT: RJ/ES ----------
print("\n" + "=" * 80)
print("5. WHITE SPOT - o que os concorrentes vendem em RJ/ES e o EMEFARMA nao")
print("=" * 80)

# universo de PDVs em RJ e ES
uf_rj = dUf.index("RJ"); uf_es = dUf.index("ES")
pdv_rjes = np.where(np.isin(pdvUf, [uf_rj, uf_es]))[0]
set_rjes = set(pdv_rjes.tolist())

m_rjes26 = np.isin(fMes, i2026) & np.isin(fPdv, pdv_rjes)
m_out26 = m_rjes26 & ~np.isin(fProv, EME)      # concorrentes na mesma praca
m_eme26 = m_rjes26 & np.isin(fProv, EME)

nap = len(apres)
v_out = np.bincount(fProd[m_out26], weights=fVal[m_out26], minlength=nap) / S
v_eme = np.bincount(fProd[m_eme26], weights=fVal[m_eme26], minlength=nap) / S
tot_out, tot_eme = v_out.sum(), v_eme.sum()

print(f"\n  Mercado VITAMEDIC em RJ+ES (jan-jul/26): {fmt_brl(tot_out + tot_eme)}")
print(f"    EMEFARMA        : {fmt_brl(tot_eme)}  ({tot_eme/(tot_out+tot_eme)*100:.1f}% share)")
print(f"    Outros distrib. : {fmt_brl(tot_out)}  ({tot_out/(tot_out+tot_eme)*100:.1f}%)")

share = np.divide(v_eme, v_eme + v_out, out=np.zeros(nap), where=(v_eme + v_out) > 0)
share_medio = tot_eme / (tot_out + tot_eme)
# gap = quanto o EMEFARMA deixaria de faturar por estar abaixo do proprio share medio
gap = (v_eme + v_out) * share_medio - v_eme
ordem = np.argsort(-gap)

print(f"\n  Share medio do EMEFARMA em RJ+ES: {share_medio*100:.1f}%")
print(f"  --- APRESENTACOES COM MAIOR GAP (share abaixo da media do proprio EMEFARMA) ---")
print(f"  {'Apresentacao':<44}{'Mercado RJ/ES':>14}{'EMEFARMA':>11}{'Share':>7}{'Gap R$':>11}")
soma_gap = 0
for i in ordem[:25]:
    if gap[i] <= 0: break
    merc = v_eme[i] + v_out[i]
    soma_gap += gap[i]
    print(f"  {apres[i][:43]:<44}{merc:>14,.0f}{v_eme[i]:>11,.0f}{share[i]*100:>6.1f}%{gap[i]:>11,.0f}")
print(f"\n  >>> Gap somado das 25 maiores: {fmt_brl(soma_gap)} em 7 meses "
      f"(~{fmt_brl(soma_gap/7*12)}/ano) apenas para igualar o share medio")
