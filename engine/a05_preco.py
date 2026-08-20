"""EMEFARMA - preco medio por SKU vs concorrentes na mesma praca (RJ+ES)."""
import numpy as np
from vmd import Pack, fmt_brl, fmt_pct

p = Pack()
S = 100.0
fProv, fProd, fPdv, fMes = p.col["fProv"], p.col["fProd"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64); fVal = p.col["fVal"].astype(np.int64)
EME = p.idx_of("provNome", "EMEFARMA")
per = p.periodos
i2026 = [per.index(f"2026{m:02d}") for m in range(1, 8)]
apres = p.dic["prodApres"]; pdvUf = p.col["pdvUf"]; dUf = p.dic["uf"]
nap = len(apres)

pdv_rjes = np.where(np.isin(pdvUf, [dUf.index("RJ"), dUf.index("ES")]))[0]
base = np.isin(fMes, i2026) & np.isin(fPdv, pdv_rjes)
m_eme = base & np.isin(fProv, EME)
m_out = base & ~np.isin(fProv, EME)

ue = np.bincount(fProd[m_eme], weights=fUnd[m_eme], minlength=nap) / S
ve = np.bincount(fProd[m_eme], weights=fVal[m_eme], minlength=nap) / S
uo = np.bincount(fProd[m_out], weights=fUnd[m_out], minlength=nap) / S
vo = np.bincount(fProd[m_out], weights=fVal[m_out], minlength=nap) / S

print("=" * 96)
print("12. PRECO MEDIO POR SKU - EMEFARMA vs DEMAIS DISTRIBUIDORES (RJ+ES, jan-jul/26)")
print("    Preco = valor de sell-out / unidades. Reflete o preco praticado ao PDV.")
print("=" * 96)
print(f"\n{'Apresentacao':<43}{'Un EME':>9}{'P.EME':>8}{'P.Mercado':>11}{'Dif%':>8}{'Valor EME':>11}")

ordem = np.argsort(-ve)
caro, barato = [], []
for i in ordem[:32]:
    if ue[i] < 200 or uo[i] < 200:
        continue
    pe = ve[i] / ue[i]; po = vo[i] / uo[i]
    dif = (pe / po - 1) * 100
    flag = ""
    if dif > 8:
        flag = "  CARO"; caro.append((i, dif, ve[i]))
    elif dif < -8:
        flag = "  BARATO"; barato.append((i, dif, ve[i]))
    print(f"{apres[i][:42]:<43}{ue[i]:>9,.0f}{pe:>8,.2f}{po:>11,.2f}{dif:>+7.1f}%{ve[i]:>11,.0f}{flag}")

pe_tot = ve.sum() / ue.sum(); po_tot = vo.sum() / uo.sum()
print(f"\n  PRECO MEDIO GERAL  EMEFARMA: R$ {pe_tot:,.2f}   |   MERCADO RJ/ES: R$ {po_tot:,.2f}   "
      f"({(pe_tot/po_tot-1)*100:+.1f}%)")

print(f"\n  SKUs em que o EMEFARMA esta ACIMA do mercado (>+8%): {len(caro)}")
for i, d, v in sorted(caro, key=lambda x: -x[2])[:8]:
    print(f"    {apres[i][:52]:<53} {d:+6.1f}%   valor {v:,.0f}")
print(f"\n  SKUs em que o EMEFARMA esta ABAIXO do mercado (<-8%) - munição comercial: {len(barato)}")
for i, d, v in sorted(barato, key=lambda x: -x[2])[:8]:
    print(f"    {apres[i][:52]:<53} {d:+6.1f}%   valor {v:,.0f}")
