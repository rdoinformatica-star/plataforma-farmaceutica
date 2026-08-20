"""EMEFARMA - visao geral: identificacao, volume, evolucao mensal, share."""
import numpy as np
from vmd import Pack, fmt_brl, fmt_int, fmt_pct, periodo_label

p = Pack()
print("Base gerada em:", p.hdr["gerado"], "| ultimo mes fechado:", p.hdr["ultimoFechado"])
print("Periodos:", p.periodos[0], "->", p.periodos[-1], f"({len(p.periodos)} meses)")
print("Linhas de fato:", fmt_int(p.hdr["nRows"]))

# ---- 1. localizar EMEFARMA entre os distribuidores (provNome) ----
hits = p.idx_of("provNome", "EMEFARMA")
print("\n=== DISTRIBUIDORES 'EMEFARMA' ENCONTRADOS ===")
for i in hits:
    print(f"  idx {i:>4} | {p.dic['provNome'][i]:<20} | CNPJ {p.dic['provCnpj'][i]}")

fProv = p.col["fProv"]
fUnd = p.col["fUnd"].astype(np.int64)
fVal = p.col["fVal"].astype(np.int64)
fMes = p.col["fMes"]
fProd = p.col["fProd"]
fPdv = p.col["fPdv"]

mask = np.isin(fProv, hits)
print(f"\nLinhas de fato do EMEFARMA: {fmt_int(mask.sum())}")

# valor: descobrir escala (centavos?) checando ticket medio
tot_und = fUnd[mask].sum()
tot_val = fVal[mask].sum()
print(f"Unidades totais (19 meses): {fmt_int(tot_und)}")
print(f"Valor bruto somado:        {fmt_int(tot_val)}")
print(f"Preco medio implicito (se valor em R$): R$ {tot_val/tot_und:,.2f}")
print(f"Preco medio implicito (se valor em centavos): R$ {tot_val/tot_und/100:,.2f}")

# ---- 2. evolucao mensal ----
print("\n=== EVOLUCAO MENSAL EMEFARMA (consolidado RJ+ES) ===")
print(f"{'Mes':<9}{'Unidades':>12}{'Valor R$':>16}{'PDVs':>8}{'SKUs':>7}{'Var.Un%':>10}")
mes_und, mes_val, mes_pdv, mes_sku = [], [], [], []
sub_mes, sub_und, sub_val, sub_pdv, sub_prod = fMes[mask], fUnd[mask], fVal[mask], fPdv[mask], fProd[mask]
for mi, per in enumerate(p.periodos):
    m = sub_mes == mi
    u = int(sub_und[m].sum())
    v = int(sub_val[m].sum())
    npdv = len(np.unique(sub_pdv[m]))
    nsku = len(np.unique(sub_prod[m]))
    mes_und.append(u); mes_val.append(v); mes_pdv.append(npdv); mes_sku.append(nsku)
    var = ((u / mes_und[mi-1] - 1) * 100) if mi > 0 and mes_und[mi-1] else None
    print(f"{periodo_label(per):<9}{fmt_int(u):>12}{fmt_int(v):>16}{npdv:>8}{nsku:>7}{(fmt_pct(var) if var is not None else '-'):>10}")

# ---- 3. EMEFARMA RJ vs ES ----
print("\n=== EMEFARMA RJ vs ES ===")
for i in hits:
    m = fProv == i
    u = int(fUnd[m].sum()); v = int(fVal[m].sum())
    npdv = len(np.unique(fPdv[m])); nsku = len(np.unique(fProd[m]))
    print(f"  {p.dic['provNome'][i]:<15} un={fmt_int(u):>12}  val={fmt_int(v):>14}  PDVs={npdv:>6}  SKUs={nsku:>4}")

# ---- 4. share do EMEFARMA no total VITAMEDIC ----
tot_und_geral = int(fUnd.sum()); tot_val_geral = int(fVal.sum())
print("\n=== SHARE EMEFARMA NO SELL-OUT TOTAL VITAMEDIC ===")
print(f"  Unidades: {fmt_int(tot_und)} de {fmt_int(tot_und_geral)}  =  {tot_und/tot_und_geral*100:.2f}%")
print(f"  Valor:    {fmt_int(tot_val)} de {fmt_int(tot_val_geral)}  =  {tot_val/tot_val_geral*100:.2f}%")

# ---- 5. ranking do EMEFARMA entre todos os distribuidores ----
nprov = len(p.dic["provNome"])
prov_und = np.bincount(fProv, weights=fUnd, minlength=nprov)
ordem = np.argsort(-prov_und)
print("\n=== TOP 20 DISTRIBUIDORES (unidades, 19 meses) ===")
print(f"{'#':<4}{'Distribuidor':<32}{'Unidades':>14}{'Share':>9}")
for r, i in enumerate(ordem[:20], 1):
    marca = " <<<" if i in hits else ""
    print(f"{r:<4}{p.dic['provNome'][i][:31]:<32}{fmt_int(prov_und[i]):>14}{prov_und[i]/tot_und_geral*100:>8.2f}%{marca}")

for i in hits:
    pos = int(np.where(ordem == i)[0][0]) + 1
    print(f"\n  -> {p.dic['provNome'][i]} ocupa a posicao {pos} de {nprov} distribuidores")
