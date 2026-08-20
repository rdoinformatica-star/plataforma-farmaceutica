"""VITAMEDIC x industrias concorrentes na MESMA molecula/mercado relevante (RJ+ES).

Pergunta: o preco esta custando venda?
Metodo: para cada mercado relevante, compara preco VITAMEDIC x concorrentes e cruza
com a variacao de share (YTD jan-jun/26 vs jan-jun/25).
"""
from collections import defaultdict
import iqvia as Q

d = Q.load("m24")
sku = d["sku"]; ufs = d["ufs"]; apreMol = d["apreMol"]
mercados = d["mercados"]; moleculas = d["moleculas"]
labsFull = d["labsFull"]; labs = d["labs"]; labFullToG = d["labFullToG"]
VITA = Q.vitamedic_labs(d)
ALVO = {ufs.index("RJ"), ufs.index("ES")}

# ---- agrega por mercado relevante x fabricante ----
mk = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0]))  # [uYtd,rYtd,uYtdP,rYtdP]
for r in sku:
    if r[Q.UF] not in ALVO:
        continue
    a = mk[r[Q.MER]][r[Q.LAB]]
    a[0] += r[Q.U_YTD]; a[1] += r[Q.R_YTD]; a[2] += r[Q.U_YTDP]; a[3] += r[Q.R_YTDP]

linhas = []
for mi, porlab in mk.items():
    if not (VITA & porlab.keys()):
        continue
    vu = vr = vup = 0.0
    cu = cr = cup = 0.0
    concorrentes = []
    for li, (u, rr, up, rp) in porlab.items():
        if li in VITA:
            vu += u; vr += rr; vup += up
        else:
            cu += u; cr += rr; cup += up
            if u > 0:
                concorrentes.append((u, labsFull[li], rr / u))
    if vu <= 0 or cu <= 0:
        continue
    tot_u = vu + cu; tot_up = vup + cup
    pv = vr / vu                      # preco VITAMEDIC
    pc = cr / cu                      # preco medio ponderado dos concorrentes
    sh = vu / tot_u * 100
    shp = (vup / tot_up * 100) if tot_up > 0 else None
    dsh = (sh - shp) if shp is not None else None
    concorrentes.sort(reverse=True)
    lider = concorrentes[0] if concorrentes else None
    linhas.append({
        "mer": mercados[mi], "mol": moleculas[apreMol[[r[Q.APRE] for r in sku if r[Q.MER] == mi][0]]]
        if False else None,
        "vu": vu, "vr": vr, "pv": pv, "pc": pc,
        "idx": (pv / pc - 1) * 100, "sh": sh, "shp": shp, "dsh": dsh,
        "tot_u": tot_u, "tot_r": vr + cr,
        "lider": lider, "nconc": len(concorrentes),
    })

print("=" * 112)
print("15. VITAMEDIC x CONCORRENTES NA MESMA MOLECULA - RJ + ES  (YTD jan-jun/26 vs jan-jun/25)")
print("    Fonte: IQVIA Mercado Relevante. 'Indice' = preco VITAMEDIC vs media ponderada dos concorrentes.")
print("=" * 112)

linhas.sort(key=lambda x: -x["tot_r"])
print(f"\n{'Mercado relevante':<46}{'Merc.un':>10}{'Share':>7}{'ΔShare':>8}{'P.VITA':>8}{'P.Conc':>8}{'Indice':>8}{'Concorrente lider':<22}")
for L in linhas[:34]:
    lid = f"{L['lider'][1][:18]} {L['lider'][2]:.2f}" if L["lider"] else "-"
    dsh = f"{L['dsh']:+.1f}pp" if L["dsh"] is not None else "  n/d"
    print(f"{L['mer'][:45]:<46}{L['tot_u']:>10,.0f}{L['sh']:>6.1f}%{dsh:>8}"
          f"{L['pv']:>8.2f}{L['pc']:>8.2f}{L['idx']:>+7.0f}%  {lid:<22}")

# ---------- correlacao preco x share ----------
import statistics as st
print("\n" + "=" * 112)
print("16. O PRECO EXPLICA A PERFORMANCE? - agrupamento por faixa de indice de preco")
print("=" * 112)
faixas = [(-999, -20, "muito abaixo (< -20%)"), (-20, -5, "abaixo (-20% a -5%)"),
          (-5, 5, "na paridade (±5%)"), (5, 20, "acima (+5% a +20%)"), (20, 999, "muito acima (> +20%)")]
print(f"\n{'Faixa de preco vs concorrencia':<28}{'Mercados':>10}{'Share medio':>13}{'ΔShare medio':>14}{'Faturam. VITA':>15}")
for lo, hi, nome in faixas:
    g = [L for L in linhas if lo <= L["idx"] < hi]
    if not g:
        continue
    shm = st.mean(x["sh"] for x in g)
    ds = [x["dsh"] for x in g if x["dsh"] is not None]
    dsm = st.mean(ds) if ds else 0
    fat = sum(x["vr"] for x in g)
    print(f"{nome:<28}{len(g):>10}{shm:>12.1f}%{dsm:>+13.1f}pp{fat:>15,.0f}")

# correlacao de Pearson
pares = [(L["idx"], L["sh"]) for L in linhas]
pares_d = [(L["idx"], L["dsh"]) for L in linhas if L["dsh"] is not None]
def pearson(p):
    xs = [a for a, b in p]; ys = [b for a, b in p]
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a-mx)*(b-my) for a, b in p)
    den = (sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys)) ** .5
    return num/den if den else 0
print(f"\n  Correlacao (Pearson) indice de preco x share atual : {pearson(pares):+.3f}   (n={len(pares)})")
print(f"  Correlacao indice de preco x variacao de share      : {pearson(pares_d):+.3f}   (n={len(pares_d)})")

# ---------- casos criticos ----------
print("\n" + "=" * 112)
print("17. CASOS CRITICOS")
print("=" * 112)

caros = sorted([L for L in linhas if L["idx"] > 10 and L["vr"] > 3000], key=lambda x: -x["vr"])
print(f"\n  A) PRECO ACIMA DA CONCORRENCIA (>+10%) - risco de perder venda por preco: {len(caros)}")
print(f"  {'Mercado':<46}{'Share':>7}{'ΔShare':>8}{'P.VITA':>8}{'P.Conc':>8}{'Indice':>8}{'Fat.VITA':>11}")
for L in caros[:12]:
    dsh = f"{L['dsh']:+.1f}pp" if L["dsh"] is not None else "n/d"
    print(f"  {L['mer'][:45]:<46}{L['sh']:>6.1f}%{dsh:>8}{L['pv']:>8.2f}{L['pc']:>8.2f}{L['idx']:>+7.0f}%{L['vr']:>11,.0f}")

barato_perde = sorted([L for L in linhas if L["idx"] < -10 and (L["dsh"] or 0) < 0 and L["tot_r"] > 20000],
                      key=lambda x: x["dsh"] or 0)
print(f"\n  B) PRECO ABAIXO E MESMO ASSIM PERDENDO SHARE - problema NAO e preco: {len(barato_perde)}")
print(f"  {'Mercado':<46}{'Share':>7}{'ΔShare':>8}{'Indice':>8}{'Merc.R$':>12}")
for L in barato_perde[:12]:
    print(f"  {L['mer'][:45]:<46}{L['sh']:>6.1f}%{L['dsh']:>+7.1f}pp{L['idx']:>+7.0f}%{L['tot_r']:>12,.0f}")

barato_baixo = sorted([L for L in linhas if L["idx"] < -10 and L["sh"] < 5 and L["tot_r"] > 50000],
                      key=lambda x: -x["tot_r"])
print(f"\n  C) PRECO BEM ABAIXO E SHARE < 5% - mercado grande, preco competitivo, presenca minima: {len(barato_baixo)}")
print(f"  {'Mercado':<46}{'Share':>7}{'Indice':>8}{'Merc.R$':>12}{'VITA R$':>11}{'Lider':<20}")
for L in barato_baixo[:14]:
    lid = L["lider"][1][:18] if L["lider"] else "-"
    print(f"  {L['mer'][:45]:<46}{L['sh']:>6.1f}%{L['idx']:>+7.0f}%{L['tot_r']:>12,.0f}{L['vr']:>11,.0f}  {lid:<20}")
