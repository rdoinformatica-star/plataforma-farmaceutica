"""Separa perda do DISTRIBUIDOR de perda da INDUSTRIA.

    python a10_perda_industria.py MILLENIUM EMEFARMA

Cruza as carteiras de dois ou mais distribuidores e identifica os PDVs perdidos
por todos eles ao mesmo tempo. Desses, separa:

  - quem sumiu da Vitamedic inteira  -> perda da industria, nao do distribuidor
  - quem seguiu comprando de outro   -> perda competitiva real

A distincao importa na reuniao: cobrar do distribuidor um PDV que nenhum
concorrente conseguiu segurar gera cobranca indevida e desgasta a relacao.
"""
import sys
from collections import defaultdict

import numpy as np

from vmd import Pack, fmt_brl, fmt_int, ESCALA as S

NOMES = [n.upper() for n in sys.argv[1:]] or ["MILLENIUM", "EMEFARMA"]

p = Pack()
fProv, fPdv, fMes = p.col["fProv"], p.col["fPdv"], p.col["fMes"]
fVal = p.col["fVal"].astype(np.int64)
pdvUf, pdvCid, razao = p.col["pdvUf"], p.col["pdvCid"], p.dic["pdvRazao"]
dUf, dCid = p.dic["uf"], p.dic["cidade"]

A = np.isin(fMes, p.janela(2025))
B = np.isin(fMes, p.janela(2026))

# val_a  = quanto o PDV comprou de Vitamedic de QUALQUER distribuidor em 25
#          (usar para dimensionar perda da INDUSTRIA)
val_a = defaultdict(float)
for k, v in zip(fPdv[A], fVal[A]):
    val_a[k] += v / S


def val_do_distribuidor(ids):
    """Quanto cada PDV comprou DESTE distribuidor em 25 (para perda do distribuidor)."""
    m = A & np.isin(fProv, ids)
    d = defaultdict(float)
    for k, v in zip(fPdv[m], fVal[m]):
        d[k] += v / S
    return d

print("=" * 96)
print(f"PERDA DO DISTRIBUIDOR  x  PERDA DA INDUSTRIA   ({' + '.join(NOMES)})")
print("  janela jan-jul/2025 -> jan-jul/2026")
print("=" * 96)

perdidos = []
for nome in NOMES:
    ids = p.idx_of("provNome", nome)
    if not ids:
        raise SystemExit(f"Distribuidor '{nome}' nao encontrado.")
    pa = set(np.unique(fPdv[A & np.isin(fProv, ids)]).tolist())
    pb = set(np.unique(fPdv[B & np.isin(fProv, ids)]).tolist())
    perd = pa - pb
    perdidos.append(perd)
    vd = val_do_distribuidor(ids)
    print(f"\n  {nome:<14} perdeu {len(perd):>6} PDVs"
          f"   valendo {fmt_brl(sum(vd[i] for i in perd))} para ele"
          f"   ({fmt_brl(sum(val_a[i] for i in perd))} de Vitamedic no total)")

ambos = set.intersection(*perdidos)
todos_b = set(np.unique(fPdv[B]).tolist())
todos_a = set(np.unique(fPdv[A]).tolist())

saiu = ambos - todos_b     # nao compraram Vitamedic de ninguem em 26
trocou = ambos & todos_b   # seguiram comprando, de outro distribuidor

print(f"\n  Perdidos por TODOS simultaneamente: {len(ambos)}")
print(f"    sumiram da Vitamedic inteira : {len(saiu):>5}  ({fmt_brl(sum(val_a[i] for i in saiu))})"
      f"  <- perda da INDUSTRIA")
print(f"    seguiram comprando de outro  : {len(trocou):>5}  ({fmt_brl(sum(val_a[i] for i in trocou))})"
      f"  <- perda COMPETITIVA")

print(f"\n  --- TOP 20 PDVs QUE SUMIRAM DA VITAMEDIC ---")
print(f"  {'PDV':<44}{'UF':<4}{'Cidade':<20}{'Valor 25':>11}")
for i in sorted(saiu, key=lambda x: -val_a[x])[:20]:
    print(f"  {razao[i][:43]:<44}{dUf[pdvUf[i]]:<4}{dCid[pdvCid[i]][:19]:<20}{val_a[i]:>11,.0f}")

print(f"\n  --- CIDADES COM MAIS PERDAS SIMULTANEAS ---")
cid = defaultdict(lambda: [0, 0.0])
for i in ambos:
    k = f"{dCid[pdvCid[i]]}/{dUf[pdvUf[i]]}"
    cid[k][0] += 1
    cid[k][1] += val_a[i]
for c, (n, v) in sorted(cid.items(), key=lambda x: -x[1][1])[:10]:
    print(f"    {c:<34}{n:>4} PDVs   {fmt_brl(v):>12}")

sumiram = todos_a - todos_b
print(f"\n  --- PANORAMA NACIONAL DA INDUSTRIA ---")
print(f"    PDVs compradores de Vitamedic: {fmt_int(len(todos_a))} (25) -> {fmt_int(len(todos_b))} (26)")
print(f"    Sumiram {fmt_int(len(sumiram))} PDVs, que valiam {fmt_brl(sum(val_a[i] for i in sumiram))}.")
