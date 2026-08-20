"""Verificacao ponta a ponta da Etapa 3 (Curva ABC + Cobertura + Mix +
Matriz de Oportunidades).

Mesmo espirito de testar_etapa1.py/testar_etapa2.py: fala com a API rodando e
confere contra o oraculo (engine/, recomputado ao vivo — nunca contra os
numeros congelados do dossie, que e de uma versao anterior do arquivo).
Pressupoe que testar_etapa1.py --completo ja rodou nesta base.

Uso:  python backend/testar_etapa3.py
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000/api"
DB = RAIZ / "database" / "pharma.db"

_ok = _falha = 0
_erros: list[str] = []


def checar(rotulo: str, condicao, obtido=None, esperado=None):
    global _ok, _falha
    if condicao:
        _ok += 1
        print(f"  OK    {rotulo}")
    else:
        _falha += 1
        extra = f" (obtido: {obtido!r}, esperado: {esperado!r})" if obtido is not None else ""
        print(f"  FALHA {rotulo}{extra}")
        _erros.append(rotulo + extra)


def chamar(metodo: str, rota: str, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        API + rota, data=dados, method=metodo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def secao(titulo: str):
    print(f"\n== {titulo} " + "=" * max(0, 58 - len(titulo)))


def obter_cliente_id(nome: str) -> int | None:
    _, clientes = chamar("GET", "/clientes")
    for c in clientes:
        if c["nome"] == nome:
            return c["id"]
    return None


def main():
    print("=" * 64)
    print("  PHARMA INTELLIGENCE — verificacao da Etapa 3")
    print("=" * 64)

    try:
        chamar("GET", "/health")
    except Exception:
        print("\nA API nao esta respondendo em http://127.0.0.1:8000")
        print("Suba o servidor antes (iniciar.bat) e rode de novo.")
        return 2

    cid_eme = obter_cliente_id("EMEFARMA")
    cid_mil = obter_cliente_id("MILLENIUM")
    if not cid_eme or not cid_mil:
        print("\nEMEFARMA/MILLENIUM nao encontrados. Rode primeiro:")
        print("  python backend/testar_etapa1.py --completo")
        return 2

    sys.path.insert(0, str(RAIZ / "engine"))
    sys.path.insert(0, str(RAIZ / "backend"))
    import numpy as np
    import vmd
    from app.core.texto import ean13

    pack = vmd.Pack()
    S = vmd.ESCALA
    fProv, fProd, fPdv, fMes, fVal = (
        pack.col[k] for k in ("fProv", "fProd", "fPdv", "fMes", "fVal"))
    fVal = fVal.astype(np.int64)
    eans_norm = [ean13(e) for e in pack.dic["prodEan"]]
    con_db = sqlite3.connect(str(DB))

    def ean_do_produto(produto_id: int) -> str | None:
        r = con_db.execute("SELECT ean FROM dim_product WHERE id=?", (produto_id,)).fetchone()
        return r[0] if r else None

    def idx_motor_por_ean(ean: str | None) -> int | None:
        return eans_norm.index(ean) if ean in eans_norm else None

    # ─────────────────────── ABC ───────────────────────
    secao("Curva ABC — conferência contra o oráculo (analise.py §5)")
    for nome, cid in (("EMEFARMA", cid_eme), ("MILLENIUM", cid_mil)):
        idx = pack.idx_of("provNome", nome)
        iB = pack.janela(2026, range(1, 8))
        m = np.isin(fProv, idx) & np.isin(fMes, iB)
        vB = np.bincount(fProd[m], weights=fVal[m], minlength=len(pack.dic["prodApres"])) / S
        o = np.argsort(-vB)
        tot = vB.sum()
        ac = 0.0
        classe_motor, nA = {}, 0
        nB_motor = nC_motor = 0
        for i in o:
            if vB[i] <= 0:
                break
            ac += vB[i] / tot * 100
            c = "A" if ac <= 80 else ("B" if ac <= 95 else "C")
            classe_motor[i] = c
            nA += c == "A"
            nB_motor += c == "B"
            nC_motor += c == "C"

        st, r = chamar("GET", f"/analytics/{cid}/abc?periodo_ini=202601&periodo_fim=202607")
        checar(f"{nome}: ABC disponível", st == 200 and r["disponivel"])
        checar(f"{nome}: contagem A/B/C bate com o motor",
               (r["resumo"]["A"]["n_produtos"], r["resumo"]["B"]["n_produtos"],
                r["resumo"]["C"]["n_produtos"]) == (nA, nB_motor, nC_motor),
               (r["resumo"]["A"]["n_produtos"], r["resumo"]["B"]["n_produtos"], r["resumo"]["C"]["n_produtos"]),
               (nA, nB_motor, nC_motor))

        divergiu = False
        for it in r["itens"][:20]:
            idxp = idx_motor_por_ean(ean_do_produto(it["produto_id"]))
            if idxp is not None and classe_motor.get(idxp) != it["classe_abc"]:
                divergiu = True
        checar(f"{nome}: classe individual dos 20 maiores bate com o motor", not divergiu)

    # limites invalidos
    st, r = chamar("GET", f"/analytics/{cid_eme}/abc?periodo_ini=202601&periodo_fim=202607&limite_a=95&limite_b=80")
    checar("ABC recusa limite_a > limite_b", r.get("disponivel") is False)

    # limites customizados mudam a contagem
    st, padrao = chamar("GET", f"/analytics/{cid_eme}/abc?periodo_ini=202601&periodo_fim=202607")
    st, estrito = chamar("GET", f"/analytics/{cid_eme}/abc?periodo_ini=202601&periodo_fim=202607&limite_a=50&limite_b=80")
    checar("limite_a mais apertado reduz produtos classe A",
           estrito["resumo"]["A"]["n_produtos"] < padrao["resumo"]["A"]["n_produtos"],
           estrito["resumo"]["A"]["n_produtos"], f"< {padrao['resumo']['A']['n_produtos']}")

    st, cresc = chamar("GET", f"/analytics/{cid_eme}/abc/crescimento?periodo_ini=202601&periodo_fim=202607")
    checar("ABC×crescimento disponível", st == 200 and cresc["disponivel"])
    checar("matriz tem as 3 classes", set(cresc["contagem"].keys()) == {"A", "B", "C"})

    # ─────────────────────── Cobertura ───────────────────────
    secao("Cobertura — conferência contra o oráculo (analise.py §7)")
    for nome, cid in (("EMEFARMA", cid_eme), ("MILLENIUM", cid_mil)):
        idx = pack.idx_of("provNome", nome)
        iB = pack.janela(2026, range(1, 8))
        m = np.isin(fProv, idx) & np.isin(fMes, iB)
        npdvB_motor = len(np.unique(fPdv[m]))
        cob_motor = defaultdict(set)
        for pr, pdvid in zip(fProd[m], fPdv[m]):
            cob_motor[pr].add(pdvid)

        st, r = chamar("GET", f"/analytics/{cid}/cobertura?periodo_ini=202601&periodo_fim=202607&limite=500")
        checar(f"{nome}: cobertura disponível", st == 200 and r["disponivel"])
        checar(f"{nome}: PDVs base bate com o motor (npdvB)",
               r["pdvs_base"] == npdvB_motor, r["pdvs_base"], npdvB_motor)

        divergiu = False
        for it in sorted(r["itens"], key=lambda x: -x["faturamento_atual"])[:10]:
            idxp = idx_motor_por_ean(ean_do_produto(it["produto_id"]))
            if idxp is not None:
                n_motor = len(cob_motor.get(idxp, set()))
                if n_motor != it["pdvs_compradores"]:
                    divergiu = True
        checar(f"{nome}: PDVs compradores dos 10 maiores batem com o motor", not divergiu)

    # cliente sem venda em UF inexistente
    st, r = chamar("GET", f"/analytics/{cid_eme}/cobertura?periodo_ini=202601&periodo_fim=202607&uf=XX")
    checar("cobertura por UF sem PDV devolve estado vazio, não erro",
           st == 200 and r["disponivel"] is False)

    st, matriz = chamar("GET", f"/analytics/{cid_eme}/cobertura/matriz?periodo_ini=202601&periodo_fim=202607")
    checar("matriz cobertura×faturamento disponível", st == 200 and matriz["disponivel"])
    soma_quadrantes = sum(matriz["resumo"].values())
    checar("soma dos quadrantes == total de produtos", soma_quadrantes == len(matriz["itens"]))

    st, pot = chamar("GET", f"/analytics/{cid_eme}/cobertura/potencial?periodo_ini=202601&periodo_fim=202607&incremento_pp=10")
    checar("potencial de cobertura disponível", st == 200 and pot["disponivel"])
    checar("potencial anual == total / meses * 12",
           abs(pot["potencial_estimado_anual"] - pot["potencial_estimado_total"] / 7 * 12) < 1)

    # piso de defesa: com piso altissimo, tudo cai em sem_dado_suficiente
    st, pot_piso = chamar("GET", f"/analytics/{cid_eme}/cobertura/potencial?periodo_ini=202601&periodo_fim=202607&minimo_pdvs_compradores=100000")
    checar("piso de PDVs muito alto esvazia os itens estimados e explica por quê",
           len(pot_piso["itens"]) == 0 and len(pot_piso["sem_dado_suficiente"]) > 0)

    # incremento maior gera potencial maior (mesmos produtos)
    st, pot5 = chamar("GET", f"/analytics/{cid_eme}/cobertura/potencial?periodo_ini=202601&periodo_fim=202607&incremento_pp=5")
    st, pot20 = chamar("GET", f"/analytics/{cid_eme}/cobertura/potencial?periodo_ini=202601&periodo_fim=202607&incremento_pp=20")
    checar("potencial cresce com o incremento_pp",
           pot5["potencial_estimado_total"] < pot20["potencial_estimado_total"])

    # ─────────────────────── Mix ───────────────────────
    secao("Mix de PDV — conferência contra o oráculo")
    for nome, cid in (("EMEFARMA", cid_eme), ("MILLENIUM", cid_mil)):
        idx = pack.idx_of("provNome", nome)
        iB = pack.janela(2026, range(1, 8))
        m = np.isin(fProv, idx) & np.isin(fMes, iB)
        mix_motor = defaultdict(set)
        vpB = defaultdict(float)
        for k, pr in zip(fPdv[m], fProd[m]):
            mix_motor[k].add(pr)
        for k, v in zip(fPdv[m], fVal[m]):
            vpB[k] += v / S

        st, r = chamar("GET", f"/analytics/{cid}/mix?periodo_ini=202601&periodo_fim=202607")
        checar(f"{nome}: mix disponível", st == 200 and r["disponivel"])
        for lo, hi, rot in ((1, 1, "1 SKU"), (2, 3, "2-3"), (4, 9, "4-9"), (10, 999, "10+")):
            ids = [k for k, x in mix_motor.items() if lo <= len(x) <= hi]
            vv = sum(vpB[i] for i in ids)
            item = next(x for x in r["resumo"] if x["sku_min"] == lo)
            checar(f"{nome}: faixa '{rot}' n_pdvs bate", item["n_pdvs"] == len(ids),
                   item["n_pdvs"], len(ids))
            checar(f"{nome}: faixa '{rot}' faturamento bate",
                   abs(item["faturamento"] - vv) < 0.01, round(item["faturamento"], 2), round(vv, 2))

    st, mono = chamar("GET", f"/analytics/{cid_eme}/mix/monoproduto?periodo_ini=202601&periodo_fim=202607")
    checar("monoproduto disponível e bate com a faixa '1 SKU' do resumo",
           st == 200 and mono["disponivel"])
    st, mixresumo = chamar("GET", f"/analytics/{cid_eme}/mix?periodo_ini=202601&periodo_fim=202607")
    faixa1 = next(x for x in mixresumo["resumo"] if x["sku_min"] == 1)
    checar("monoproduto.n_pdvs == faixa 1 SKU do resumo de mix",
           mono["n_pdvs"] == faixa1["n_pdvs"], mono["n_pdvs"], faixa1["n_pdvs"])

    st, alto = chamar("GET", f"/analytics/{cid_eme}/mix/alto?periodo_ini=202601&periodo_fim=202607&minimo_skus=10")
    faixa10 = next(x for x in mixresumo["resumo"] if x["sku_min"] == 10)
    checar("alto_mix.n_pdvs == faixa 10+ do resumo de mix",
           alto["n_pdvs"] == faixa10["n_pdvs"], alto["n_pdvs"], faixa10["n_pdvs"])

    st, exp = chamar("GET", f"/analytics/{cid_eme}/mix/oportunidades?periodo_ini=202601&periodo_fim=202607")
    checar("oportunidades de expansão de mix disponível", st == 200 and exp["disponivel"])
    checar("todo item de expansão tem faturamento >= referência da faixa seguinte",
           all(i["faturamento_atual"] >= i["rs_por_pdv_faixa_referencia"] for i in exp["itens"]))

    # ─────────────────────── Oportunidades ───────────────────────
    secao("Matriz de oportunidades — score e pesos")
    st, op = chamar("GET", f"/analytics/{cid_eme}/oportunidades?periodo_ini=202601&periodo_fim=202607")
    checar("oportunidades disponível", st == 200 and op["disponivel"])
    checar("itens ordenados por score decrescente",
           all(op["itens"][i]["score"] >= op["itens"][i + 1]["score"]
               for i in range(len(op["itens"]) - 1)))
    checar("toda oportunidade tem rótulo FATO",
           all(i["rotulo"] == "FATO" for i in op["itens"]))
    checar("toda oportunidade tem premissa não vazia",
           all(i["premissa"] for i in op["itens"]))

    # pesos customizados mudam o ranking (potencial 100%, resto 0)
    st, op_pot = chamar("GET", f"/analytics/{cid_eme}/oportunidades?periodo_ini=202601&periodo_fim=202607"
                               "&peso_potencial=100&peso_impacto=0&peso_facilidade=0")
    st, op_fac = chamar("GET", f"/analytics/{cid_eme}/oportunidades?periodo_ini=202601&periodo_fim=202607"
                               "&peso_potencial=0&peso_impacto=0&peso_facilidade=100")
    ranking_pot = [i["oportunidade"] for i in op_pot["itens"][:5]]
    ranking_fac = [i["oportunidade"] for i in op_fac["itens"][:5]]
    checar("pesos diferentes produzem ranking diferente", ranking_pot != ranking_fac)

    st, ae = chamar("GET", f"/analytics/{cid_eme}/alertas-expandidos?periodo_ini=202601&periodo_fim=202607")
    checar("alertas expandidos disponível e não vazio", st == 200 and ae["disponivel"] and ae["n_total"] > 0)
    st, ae_base = chamar("GET", f"/analytics/{cid_eme}/alertas?periodo_ini=202601&periodo_fim=202607")
    checar("alertas expandidos tem pelo menos os alertas da Etapa 2",
           ae["n_total"] >= ae_base["n_total"], ae["n_total"], f">= {ae_base['n_total']}")

    # ─────────────────────── Isolamento multicliente ───────────────────────
    secao("Isolamento multicliente")
    st, abc_eme = chamar("GET", f"/analytics/{cid_eme}/abc?periodo_ini=202601&periodo_fim=202607")
    st, abc_mil = chamar("GET", f"/analytics/{cid_mil}/abc?periodo_ini=202601&periodo_fim=202607")
    checar("curvas ABC diferentes entre clientes",
           abc_eme["resumo"] != abc_mil["resumo"])
    st, cob_eme = chamar("GET", f"/analytics/{cid_eme}/cobertura?periodo_ini=202601&periodo_fim=202607")
    st, cob_mil = chamar("GET", f"/analytics/{cid_mil}/cobertura?periodo_ini=202601&periodo_fim=202607")
    checar("base de PDVs de cobertura diferente entre clientes",
           cob_eme["pdvs_base"] != cob_mil["pdvs_base"])

    # ─────────────────────── Estado vazio ───────────────────────
    secao("Estado vazio: cliente sem distribuidor correspondente")
    st, novo = chamar("POST", "/clientes", {"nome": "CLIENTE ETAPA3 SEM DADOS"})
    cid_vazio = novo["id"]
    st, r = chamar("GET", f"/analytics/{cid_vazio}/abc?periodo_ini=202601&periodo_fim=202607")
    checar("ABC de cliente sem dados não inventa número", r["disponivel"] is False)
    st, r = chamar("GET", f"/analytics/{cid_vazio}/cobertura?periodo_ini=202601&periodo_fim=202607")
    checar("cobertura de cliente sem dados não inventa número", r["disponivel"] is False)
    st, r = chamar("GET", f"/analytics/{cid_vazio}/mix?periodo_ini=202601&periodo_fim=202607")
    checar("mix de cliente sem dados não inventa número", r["disponivel"] is False)
    chamar("DELETE", f"/clientes/{cid_vazio}")

    # ─────────────────────── Performance ───────────────────────
    secao("Performance")
    t0 = time.time()
    chamar("GET", f"/analytics/{cid_eme}/abc?periodo_ini=202601&periodo_fim=202607")
    chamar("GET", f"/analytics/{cid_eme}/cobertura?periodo_ini=202601&periodo_fim=202607")
    chamar("GET", f"/analytics/{cid_eme}/mix?periodo_ini=202601&periodo_fim=202607")
    dt = time.time() - t0
    checar(f"ABC+cobertura+mix respondem rápido ({dt:.2f}s)", dt < 5.0, round(dt, 2), "<5s")

    t0 = time.time()
    chamar("GET", f"/analytics/{cid_eme}/oportunidades?periodo_ini=202601&periodo_fim=202607")
    dt = time.time() - t0
    checar(f"matriz de oportunidades responde em tempo aceitável ({dt:.2f}s)", dt < 8.0, round(dt, 2), "<8s")

    print("\n" + "=" * 64)
    print(f"  {_ok} passaram | {_falha} falharam")
    if _erros:
        print("\n  Falhas:")
        for e in _erros:
            print(f"   - {e}")
    print("=" * 64)
    return 0 if _falha == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
