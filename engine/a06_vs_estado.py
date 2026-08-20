"""EMEFARMA vs o proprio estado: crescimento e share por UF."""
import numpy as np
from collections import defaultdict
from vmd import Pack, fmt_brl, fmt_int, fmt_pct

p = Pack()
S = 100.0
fProv, fProd, fPdv, fMes = p.col["fProv"], p.col["fProd"], p.col["fPdv"], p.col["fMes"]
fUnd = p.col["fUnd"].astype(np.int64); fVal = p.col["fVal"].astype(np.int64)
EME = p.idx_of("provNome", "EMEFARMA"); RJ_I, ES_I = EME
per = p.periodos
i25 = [per.index(f"2025{m:02d}") for m in range(1, 8)]
i26 = [per.index(f"2026{m:02d}") for m in range(1, 8)]
pdvUf = p.col["pdvUf"]; dUf = p.dic["uf"]
uf_de_linha = pdvUf[fPdv]          # UF do PDV em cada linha de fato

m25 = np.isin(fMes, i25); m26 = np.isin(fMes, i26)
m_eme = np.isin(fProv, EME)

def agg(mask):
    return fUnd[mask].sum()/S, fVal[mask].sum()/S, len(np.unique(fPdv[mask]))

print("=" * 92)
print("13. EMEFARMA vs O ESTADO - crescimento e share por UF (jan-jul/25 vs jan-jul/26)")
print("    'Estado' = todo o sell-out Vitamedic para PDVs daquela UF, por qualquer distribuidor.")
print("=" * 92)

for uf in ("RJ", "ES", "SP"):
    ui = dUf.index(uf)
    est = uf_de_linha == ui
    e25 = est & m25; e26 = est & m26                    # estado inteiro
    x25 = est & m25 & m_eme; x26 = est & m26 & m_eme    # EMEFARMA dentro do estado

    eu25, ev25, ep25 = agg(e25); eu26, ev26, ep26 = agg(e26)
    xu25, xv25, xp25 = agg(x25); xu26, xv26, xp26 = agg(x26)
    if xv25 == 0 and xv26 == 0:
        continue

    sh25 = xv25/ev25*100 if ev25 else 0
    sh26 = xv26/ev26*100 if ev26 else 0
    shu25 = xu25/eu25*100 if eu25 else 0
    shu26 = xu26/eu26*100 if eu26 else 0

    g_est_v = (ev26/ev25-1)*100; g_eme_v = (xv26/xv25-1)*100 if xv25 else None
    g_est_u = (eu26/eu25-1)*100; g_eme_u = (xu26/xu25-1)*100 if xu25 else None

    print(f"\n{'='*92}")
    print(f"  {uf}")
    print(f"{'='*92}")
    print(f"  {'':<26}{'jan-jul/25':>16}{'jan-jul/26':>16}{'variacao':>12}")
    print(f"  {'-'*68}")
    print(f"  {'ESTADO ' + uf + ' - valor':<26}{ev25:>16,.0f}{ev26:>16,.0f}{fmt_pct(g_est_v):>12}")
    print(f"  {'EMEFARMA no ' + uf + ' - valor':<26}{xv25:>16,.0f}{xv26:>16,.0f}{fmt_pct(g_eme_v):>12}")
    print(f"  {'>>> vantagem EMEFARMA':<26}{'':>16}{'':>16}{(g_eme_v-g_est_v):>+11.1f}pp")
    print()
    print(f"  {'ESTADO ' + uf + ' - unidades':<26}{eu25:>16,.0f}{eu26:>16,.0f}{fmt_pct(g_est_u):>12}")
    print(f"  {'EMEFARMA no ' + uf + ' - un.':<26}{xu25:>16,.0f}{xu26:>16,.0f}{fmt_pct(g_eme_u):>12}")
    print(f"  {'>>> vantagem EMEFARMA':<26}{'':>16}{'':>16}{(g_eme_u-g_est_u):>+11.1f}pp")
    print()
    print(f"  {'SHARE valor no estado':<26}{sh25:>15.2f}%{sh26:>15.2f}%{(sh26-sh25):>+11.2f}pp")
    print(f"  {'SHARE unidades':<26}{shu25:>15.2f}%{shu26:>15.2f}%{(shu26-shu25):>+11.2f}pp")
    print(f"  {'PDVs Vitamedic no estado':<26}{ep25:>16,}{ep26:>16,}{fmt_pct((ep26/ep25-1)*100):>12}")
    print(f"  {'PDVs do EMEFARMA':<26}{xp25:>16,}{xp26:>16,}{fmt_pct((xp26/xp25-1)*100):>12}")
    print(f"  {'Penetracao na base do est.':<26}{xp25/ep25*100:>15.1f}%{xp26/ep26*100:>15.1f}%")
    print(f"  {'N. de distribuidores ativos':<26}{len(np.unique(fProv[e25])):>16,}{len(np.unique(fProv[e26])):>16,}")

    # ranking do EMEFARMA dentro do estado
    nprov = len(p.dic["provNome"])
    r26 = np.bincount(fProv[e26], weights=fVal[e26], minlength=nprov)/S
    r25 = np.bincount(fProv[e25], weights=fVal[e25], minlength=nprov)/S
    o26 = np.argsort(-r26); o25 = np.argsort(-r25)
    idx = RJ_I if uf == "RJ" else (ES_I if uf == "ES" else None)
    print(f"\n  --- TOP 10 DISTRIBUIDORES VITAMEDIC NO {uf} (valor jan-jul/26) ---")
    print(f"  {'#':<4}{'Distribuidor':<30}{'Valor 26':>13}{'Share':>8}{'Valor 25':>13}{'YoY':>10}")
    for r, i in enumerate(o26[:10], 1):
        eh = "  <<<" if i in EME else ""
        yo = (r26[i]/r25[i]-1)*100 if r25[i] > 0 else None
        print(f"  {r:<4}{p.dic['provNome'][i][:29]:<30}{r26[i]:>13,.0f}{r26[i]/ev26*100:>7.1f}%{r25[i]:>13,.0f}{(fmt_pct(yo,0) if yo is not None else 'novo'):>10}{eh}")
    for i in EME:
        if r26[i] > 0:
            pos26 = int(np.where(o26 == i)[0][0])+1
            pos25 = int(np.where(o25 == i)[0][0])+1
            print(f"     {p.dic['provNome'][i]}: {pos25}o em 25  ->  {pos26}o em 26  "
                  f"({'subiu' if pos26 < pos25 else ('caiu' if pos26 > pos25 else 'manteve')} "
                  f"{abs(pos26-pos25)} posicoes)")

# ---- evolucao mensal do share no RJ ----
print("\n" + "=" * 92)
print("14. EVOLUCAO MENSAL DO SHARE DO EMEFARMA NO SEU ESTADO")
print("=" * 92)
for uf in ("RJ", "ES"):
    ui = dUf.index(uf); est = uf_de_linha == ui
    print(f"\n  --- {uf} ---")
    print(f"  {'Mes':<9}{'Estado R$':>13}{'EMEFARMA R$':>13}{'Share':>8}{'Share un.':>11}")
    for mi in range(len(per)):
        e = est & (fMes == mi); x = e & m_eme
        ev = fVal[e].sum()/S; xv = fVal[x].sum()/S
        eu = fUnd[e].sum()/S; xu = fUnd[x].sum()/S
        if ev == 0: continue
        print(f"  {per[mi][4:]}/{per[mi][:4]}{ev:>13,.0f}{xv:>13,.0f}{xv/ev*100:>7.1f}%{(xu/eu*100 if eu else 0):>10.1f}%")
