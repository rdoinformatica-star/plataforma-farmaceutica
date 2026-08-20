"""Recomputa da fonte os numeros afirmados nos dossies e compara.

    python verifica_dossies.py

Cada linha imprime OK ou DIVERGE. Serve para conferir antes de levar o relatorio
para uma reuniao.
"""
import numpy as np
from collections import defaultdict

from vmd import Pack, ESCALA as S

p = Pack()
fProv, fProd, fPdv, fMes = p.col["fProv"], p.col["fProd"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64)
fVal = p.col["fVal"].astype(np.int64)
uf_lin = p.col["pdvUf"][fPdv]
dUf = p.dic["uf"]
A, B = np.isin(fMes, p.janela(2025)), np.isin(fMes, p.janela(2026))

ok = div = 0


def chk(rot, calc, dito, tol=0.011):
    """tol = tolerancia relativa (1,1% cobre arredondamento de exibicao)."""
    global ok, div
    if dito == 0:
        bate = abs(calc) < 1e-9
    else:
        bate = abs(calc - dito) / abs(dito) <= tol
    if bate:
        ok += 1
        print(f"  OK      {rot:<52} {calc:>14,.2f}")
    else:
        div += 1
        print(f"  DIVERGE {rot:<52} calc {calc:>12,.2f}  dossie {dito:>12,.2f}")


def bloco(mask):
    return fUnd[mask].sum() / S, fVal[mask].sum() / S, len(np.unique(fPdv[mask]))


def estado(uf, ids=None):
    u = dUf.index(uf)
    m = uf_lin == u
    if ids is not None:
        m = m & np.isin(fProv, ids)
    return m


EME = p.idx_of("provNome", "EMEFARMA")
MIL = p.idx_of("provNome", "MILLENIUM")

print("=" * 84)
print("DOSSIE EMEFARMA")
print("=" * 84)
uA, vA, pA = bloco(np.isin(fProv, EME) & A)
uB, vB, pB = bloco(np.isin(fProv, EME) & B)
chk("unidades 7M/25", uA, 917_155)
chk("unidades 7M/26", uB, 777_406)
chk("valor 7M/25", vA, 3_286_300)
chk("valor 7M/26", vB, 3_167_160)
chk("variacao valor %", (vB / vA - 1) * 100, -3.6, 0.03)
chk("variacao unidades %", (uB / uA - 1) * 100, -15.2, 0.02)
chk("PDVs 7M/26", pB, 4_688)

for uf, sh_a, sh_b in (("RJ", 20.29, 24.38), ("ES", 5.48, 10.39)):
    ea, eb = estado(uf) & A, estado(uf) & B
    xa, xb = estado(uf, EME) & A, estado(uf, EME) & B
    chk(f"share {uf} 25 %", fVal[xa].sum() / fVal[ea].sum() * 100, sh_a, 0.01)
    chk(f"share {uf} 26 %", fVal[xb].sum() / fVal[eb].sum() * 100, sh_b, 0.01)

sp_a = fVal[estado("SP", EME) & A].sum() / S
sp_b = fVal[estado("SP", EME) & B].sum() / S
chk("delta SP", sp_b - sp_a, -301_836)
chk("ex-SP variacao %", ((vB - sp_b) / (vA - sp_a) - 1) * 100, 6.2, 0.02)

pdvA = set(np.unique(fPdv[np.isin(fProv, EME) & A]).tolist())
pdvB = set(np.unique(fPdv[np.isin(fProv, EME) & B]).tolist())
vpA = defaultdict(float)
m = np.isin(fProv, EME) & A
for k, v in zip(fPdv[m], fVal[m]):
    vpA[k] += v / S
chk("PDVs perdidos", len(pdvA - pdvB), 1_254)
chk("valor dos perdidos", sum(vpA[i] for i in pdvA - pdvB), 784_481)

print()
print("=" * 84)
print("DOSSIE MILLENIUM")
print("=" * 84)
uA, vA, pA = bloco(np.isin(fProv, MIL) & A)
uB, vB, pB = bloco(np.isin(fProv, MIL) & B)
chk("unidades 7M/25", uA, 1_299_672)
chk("unidades 7M/26", uB, 1_283_002)
chk("valor 7M/25", vA, 5_243_622)
chk("valor 7M/26", vB, 5_044_409)
chk("variacao valor %", (vB / vA - 1) * 100, -3.8, 0.03)
chk("PDVs 7M/26", pB, 5_198)

for uf, sh_a, sh_b in (("RJ", 30.65, 27.99), ("ES", 24.05, 40.54)):
    ea, eb = estado(uf) & A, estado(uf) & B
    xa, xb = estado(uf, MIL) & A, estado(uf, MIL) & B
    chk(f"share {uf} 25 %", fVal[xa].sum() / fVal[ea].sum() * 100, sh_a, 0.01)
    chk(f"share {uf} 26 %", fVal[xb].sum() / fVal[eb].sum() * 100, sh_b, 0.01)

rj_a = np.isin(fProv, MIL) & estado("RJ") & A
rj_b = np.isin(fProv, MIL) & estado("RJ") & B
va_rj, vb_rj = fVal[rj_a].sum() / S, fVal[rj_b].sum() / S
pa_rj, pb_rj = len(np.unique(fPdv[rj_a])), len(np.unique(fPdv[rj_b]))
chk("RJ valor 25", va_rj, 4_035_771)
chk("RJ valor 26", vb_rj, 2_994_760)
chk("RJ PDVs 25", pa_rj, 3_533)
chk("RJ PDVs 26", pb_rj, 3_576)
chk("RJ R$/PDV 25", va_rj / pa_rj, 1_142)
chk("RJ R$/PDV 26", vb_rj / pb_rj, 837)
chk("RJ queda R$/PDV %", ((vb_rj / pb_rj) / (va_rj / pa_rj) - 1) * 100, -26.7, 0.02)

es_a = np.isin(fProv, MIL) & estado("ES") & A
es_b = np.isin(fProv, MIL) & estado("ES") & B
chk("ES variacao valor %", (fVal[es_b].sum() / fVal[es_a].sum() - 1) * 100, 68.6, 0.02)

pdvA = set(np.unique(fPdv[np.isin(fProv, MIL) & A]).tolist())
pdvB = set(np.unique(fPdv[np.isin(fProv, MIL) & B]).tolist())
vpA = defaultdict(float)
m = np.isin(fProv, MIL) & A
for k, v in zip(fPdv[m], fVal[m]):
    vpA[k] += v / S
perd = pdvA - pdvB
chk("PDVs perdidos", len(perd), 922)
chk("valor dos perdidos", sum(vpA[i] for i in perd), 863_877)
chk("perdidos no RJ - valor", sum(vpA[i] for i in perd if dUf[p.col["pdvUf"][i]] == "RJ"), 800_058)

print()
print("=" * 84)
print("COMPARATIVO ENTRE AS DUAS CONTAS (RJ)")
print("=" * 84)
ea, eb = estado("RJ") & A, estado("RJ") & B
m_sh = fVal[estado("RJ", MIL) & A].sum() / fVal[ea].sum() * 100
e_sh = fVal[estado("RJ", EME) & A].sum() / fVal[ea].sum() * 100
m_sh2 = fVal[estado("RJ", MIL) & B].sum() / fVal[eb].sum() * 100
e_sh2 = fVal[estado("RJ", EME) & B].sum() / fVal[eb].sum() * 100
chk("vantagem MILLENIUM 25 (pp)", m_sh - e_sh, 10.36, 0.01)
chk("vantagem MILLENIUM 26 (pp)", m_sh2 - e_sh2, 3.61, 0.01)

print()
print("=" * 84)
print(f"RESULTADO: {ok} conferem | {div} divergem")
print("=" * 84)
