"""Teste de robustez: a conclusao sobre preco depende do criterio de comparacao?

    python a11_robustez_preco.py

Compara o preco da Vitamedic contra duas referencias diferentes e verifica se as
conclusoes mudam:

  MEDIA PONDERADA de todos os concorrentes  -> pode enganar: concorrentes caros de
                                               baixo volume puxam a media para cima
  LIDER DE VOLUME                           -> e contra ele que o PDV compara

Motivo de existir: na primeira versao do dossie EMEFARMA o Biovarixon foi descrito
como "48% mais barato" usando a media ponderada, quando na verdade esta 24% ACIMA
da Teuto, que domina o volume. Este script mede quantos mercados invertem o sinal.
"""
import statistics as st
from collections import defaultdict

import iqvia as Q

UFS = ["RJ", "ES"]

d = Q.load("m24")
VITA = Q.vitamedic_labs(d)
ALVO = Q.ufs_idx(d, UFS)

mk = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0]))
for r in d["sku"]:
    if r[Q.UF] not in ALVO:
        continue
    a = mk[r[Q.MER]][r[Q.LAB]]
    a[0] += r[Q.U_YTD]; a[1] += r[Q.R_YTD]; a[2] += r[Q.U_YTDP]; a[3] += r[Q.R_YTDP]

rows = []
for mi, porlab in mk.items():
    if not (VITA & porlab.keys()):
        continue
    vu = vr = vup = cu = cr = cup = 0.0
    conc = []
    for li, (u, rr, up, rp) in porlab.items():
        if li in VITA:
            vu += u; vr += rr; vup += up
        else:
            cu += u; cr += rr; cup += up
            if u > 0:
                conc.append((u, d["labsFull"][li], rr / u))
    if vu <= 0 or cu <= 0:
        continue
    conc.sort(reverse=True)
    pv = vr / vu
    tot, totp = vu + cu, vup + cup
    sh = vu / tot * 100
    rows.append({
        "mer": d["mercados"][mi], "pv": pv,
        "pmed": cr / cu, "plid": conc[0][1 + 1], "lider": conc[0][1],
        "i_med": (pv / (cr / cu) - 1) * 100,
        "i_lid": (pv / conc[0][2] - 1) * 100,
        "sh": sh, "dsh": (sh - vup / totp * 100) if totp > 0 else None,
        "fat": vr, "merc": vr + cr,
    })


def pearson(pairs):
    xs = [a for a, b in pairs]; ys = [b for a, b in pairs]
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in pairs)
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** .5
    return num / den if den else 0


print("=" * 92)
print(f"ROBUSTEZ DA CONCLUSAO SOBRE PRECO - {'+'.join(UFS)}, IQVIA YTD jan-jun/26")
print(f"  n = {len(rows)} mercados relevantes com presenca Vitamedic")
print("=" * 92)

for rot, k in (("MEDIA ponderada dos concorrentes", "i_med"), ("LIDER de volume", "i_lid")):
    p_sh = pearson([(r[k], r["sh"]) for r in rows])
    p_ds = pearson([(r[k], r["dsh"]) for r in rows if r["dsh"] is not None])
    print(f"\n  Referencia: {rot}")
    print(f"    correlacao preco x share atual    : {p_sh:+.3f}")
    print(f"    correlacao preco x variacao share : {p_ds:+.3f}")

print("\n  --- FAIXAS DE PRECO vs LIDER ---")
faixas = [(-999, -20, "muito abaixo (< -20%)"), (-20, -5, "abaixo (-20% a -5%)"),
          (-5, 5, "na paridade (+-5%)"), (5, 20, "acima (+5% a +20%)"),
          (20, 999, "muito acima (> +20%)")]
print(f"  {'Faixa':<26}{'Merc':>6}{'Share medio':>13}{'dShare medio':>14}{'Faturamento':>14}")
for lo, hi, nome in faixas:
    g = [r for r in rows if lo <= r["i_lid"] < hi]
    if not g:
        continue
    ds = [x["dsh"] for x in g if x["dsh"] is not None]
    print(f"  {nome:<26}{len(g):>6}{st.mean(x['sh'] for x in g):>12.1f}%"
          f"{(st.mean(ds) if ds else 0):>+13.1f}pp{sum(x['fat'] for x in g):>14,.0f}")

print("\n  --- MERCADOS QUE INVERTEM O SINAL (media diz barato, lider diz caro) ---")
flip = [r for r in rows if (r["i_med"] < 0) != (r["i_lid"] < 0)]
flip.sort(key=lambda r: -r["merc"])
print(f"  {'Mercado':<46}{'vs media':>10}{'vs lider':>10}{'Mercado R$':>13}  Lider")
for r in flip[:15]:
    print(f"  {r['mer'][:45]:<46}{r['i_med']:>+9.0f}%{r['i_lid']:>+9.0f}%{r['merc']:>13,.0f}  {r['lider'][:20]}")
print(f"\n  {len(flip)} de {len(rows)} mercados invertem o sinal "
      f"({len(flip)/len(rows)*100:.0f}%).")
print("  >>> Use SEMPRE o lider de volume para decidir preco. A media so serve de contexto.")
