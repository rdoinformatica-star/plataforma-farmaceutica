"""Cruzamento CNPJ do EMEFARMA x UF do PDV - separa 'unidade ES' de 'vendas no estado ES'."""
import numpy as np
from vmd import Pack, fmt_pct

p = Pack()
S = 100.0
fProv, fPdv, fMes = p.col["fProv"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64); fVal = p.col["fVal"].astype(np.int64)
EME = p.idx_of("provNome", "EMEFARMA"); RJ_I, ES_I = EME
per = p.periodos
i25 = [per.index(f"2025{m:02d}") for m in range(1, 8)]
i26 = [per.index(f"2026{m:02d}") for m in range(1, 8)]
uf_lin = p.col["pdvUf"][fPdv]; dUf = p.dic["uf"]

print("=" * 88)
print("CRUZAMENTO: CNPJ do EMEFARMA  x  UF onde esta o PDV   (valor R$, jan-jul)")
print("=" * 88)

for idx, nome in ((RJ_I, "EMEFARMA RJ"), (ES_I, "EMEFARMA ES")):
    print(f"\n  {nome}  (CNPJ {p.dic['provCnpj'][idx]})")
    print(f"  {'UF do PDV':<12}{'valor 25':>13}{'valor 26':>13}{'YoY':>10}{'un 25':>11}{'un 26':>11}{'YoY un':>10}{'PDV 26':>8}")
    tot25 = tot26 = 0
    linhas = []
    for u in range(len(dUf)):
        a = (fProv == idx) & (uf_lin == u) & np.isin(fMes, i25)
        b = (fProv == idx) & (uf_lin == u) & np.isin(fMes, i26)
        v25 = fVal[a].sum()/S; v26 = fVal[b].sum()/S
        if v25 == 0 and v26 == 0: continue
        u25 = fUnd[a].sum()/S; u26 = fUnd[b].sum()/S
        npv = len(np.unique(fPdv[b]))
        linhas.append((max(v25, v26), dUf[u], v25, v26, u25, u26, npv))
        tot25 += v25; tot26 += v26
    for _, uf, v25, v26, u25, u26, npv in sorted(linhas, reverse=True):
        yv = fmt_pct((v26/v25-1)*100, 0) if v25 else "novo"
        yu = fmt_pct((u26/u25-1)*100, 0) if u25 else "novo"
        print(f"  {uf:<12}{v25:>13,.0f}{v26:>13,.0f}{yv:>10}{u25:>11,.0f}{u26:>11,.0f}{yu:>10}{npv:>8}")
    print(f"  {'TOTAL':<12}{tot25:>13,.0f}{tot26:>13,.0f}{fmt_pct((tot26/tot25-1)*100,0):>10}")

print("\n" + "=" * 88)
print("LEITURA CONSOLIDADA - por ESTADO (somando os dois CNPJs)")
print("=" * 88)
m_eme = np.isin(fProv, EME)
print(f"  {'UF do PDV':<12}{'valor 25':>13}{'valor 26':>13}{'YoY':>10}{'delta R$':>13}")
tot = []
for u in range(len(dUf)):
    a = m_eme & (uf_lin == u) & np.isin(fMes, i25)
    b = m_eme & (uf_lin == u) & np.isin(fMes, i26)
    v25 = fVal[a].sum()/S; v26 = fVal[b].sum()/S
    if v25 == 0 and v26 == 0: continue
    tot.append((v26-v25, dUf[u], v25, v26))
for d, uf, v25, v26 in sorted(tot, key=lambda x: x[0]):
    yv = fmt_pct((v26/v25-1)*100, 0) if v25 else "novo"
    print(f"  {uf:<12}{v25:>13,.0f}{v26:>13,.0f}{yv:>10}{d:>+13,.0f}")
tv25 = sum(x[2] for x in tot); tv26 = sum(x[3] for x in tot)
print(f"  {'TOTAL':<12}{tv25:>13,.0f}{tv26:>13,.0f}{fmt_pct((tv26/tv25-1)*100,1):>10}{tv26-tv25:>+13,.0f}")

# quanto da queda total vem de SP
sp = [x for x in tot if x[1] == "SP"][0]
print(f"\n  >>> A conta perdeu {tv26-tv25:,.0f} no total.")
print(f"  >>> Só SP responde por {sp[0]:,.0f}  ({sp[0]/(tv26-tv25)*100:.0f}% da queda).")
print(f"  >>> Excluindo SP, a conta variou {fmt_pct(((tv26-sp[3])/(tv25-sp[2])-1)*100,1)}.")
