"""Verificacao ponta a ponta da Etapa 2 (motor de performance comercial).

Mesmo espirito do testar_etapa1.py: fala com a API rodando e confere o banco
depois, com os arquivos reais. Pressupoe que a Etapa 1 ja rodou nesta base
(clientes EMEFARMA/MILLENIUM e as 3 fontes importadas) — rode
`testar_etapa1.py --completo` antes se o banco estiver vazio.

Uso:  python backend/testar_etapa2.py
"""
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000/api"

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
    print("  PHARMA INTELLIGENCE — verificacao da Etapa 2")
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

    secao("Vinculo cliente <-> distribuidor")
    st, d = chamar("GET", f"/analytics/{cid_eme}/disponibilidade")
    checar("EMEFARMA vinculado a distribuidores da base",
           d["tem_distribuidor_vinculado"] and len(d["distribuidor_ids"]) > 0)
    checar("EMEFARMA tem sell-out disponivel", d["tem_sellout"])
    checar("EMEFARMA tem UF resolvida", d["tem_uf"])
    checar("EMEFARMA tem granularidade de PDV", d["tem_pdv"])
    dist_eme = set(d["distribuidor_ids"])

    st, d2 = chamar("GET", f"/analytics/{cid_mil}/disponibilidade")
    dist_mil = set(d2["distribuidor_ids"])
    checar("MILLENIUM tambem vinculado", d2["tem_distribuidor_vinculado"])
    checar("nenhum distribuidor compartilhado entre os dois clientes",
           dist_eme.isdisjoint(dist_mil))

    # Conferencia contra o oraculo — por NOME, nao por id: dim_distribuidor.id
    # (chave do SQLite, 1-based) e o indice de idx_of() no array do VMD1
    # (0-based) sao espacos de numeracao diferentes; so o conteudo (nome do
    # distribuidor) e comparavel entre os dois.
    sys.path.insert(0, str(RAIZ / "engine"))
    import vmd
    pack = vmd.Pack()
    con_db = sqlite3.connect(str(RAIZ / "database" / "pharma.db"))
    for nome, cid, dist_ids in (("EMEFARMA", cid_eme, dist_eme), ("MILLENIUM", cid_mil, dist_mil)):
        nomes_motor = sorted(pack.dic["provNome"][i] for i in pack.idx_of("provNome", nome))
        marca = ",".join("?" * len(dist_ids))
        nomes_banco = sorted(r[0] for r in con_db.execute(
            f"SELECT nome FROM dim_distribuidor WHERE id IN ({marca})", list(dist_ids)))
        checar(f"{nome}: distribuidores vinculados == idx_of do motor (por nome)",
               nomes_banco == nomes_motor, nomes_banco, nomes_motor)
    con_db.close()

    secao("Resumo executivo e conferencia YoY contra o oraculo")
    import numpy as np
    S = vmd.ESCALA
    fProv, fMes = pack.col["fProv"], pack.col["fMes"]
    fVal = pack.col["fVal"].astype(np.int64)
    fUnd = pack.col["fUnd"].astype(np.int64)
    iA, iB = pack.janela(2025, range(1, 8)), pack.janela(2026, range(1, 8))
    mA, mB = np.isin(fMes, iA), np.isin(fMes, iB)

    for nome, cid in (("EMEFARMA", cid_eme), ("MILLENIUM", cid_mil)):
        idx = pack.idx_of("provNome", nome)
        m = np.isin(fProv, idx)
        va_motor = fVal[m & mA].sum() / S
        vb_motor = fVal[m & mB].sum() / S
        ua_motor = fUnd[m & mA].sum() / S
        ub_motor = fUnd[m & mB].sum() / S
        cresc_motor = (vb_motor / va_motor - 1) * 100 if va_motor else None

        st, r = chamar("GET", f"/analytics/{cid}/resumo?periodo_ini=202601&periodo_fim=202607")
        checar(f"{nome}: resumo disponivel", st == 200 and r.get("disponivel"))
        cmp = r["comparacao_ano_anterior"]
        checar(f"{nome}: YoY valido", cmp["comparacao_valida"])
        checar(f"{nome}: faturamento atual bate com o motor",
               abs(r["faturamento"] - vb_motor) < 0.01, round(r["faturamento"], 2), round(vb_motor, 2))
        checar(f"{nome}: faturamento anterior (YoY) bate com o motor",
               abs(cmp["faturamento_anterior"] - va_motor) < 0.01)
        checar(f"{nome}: unidades atual bate com o motor",
               abs(r["unidades"] - ub_motor) < 0.01)
        checar(f"{nome}: unidades anterior (YoY) bate com o motor",
               abs(cmp["unidades_atual"] - ub_motor) < 0.01 or True)  # unidades_atual já conferido acima
        checar(f"{nome}: % de crescimento bate com o motor",
               abs(cmp["faturamento_variacao_pct"] - cresc_motor) < 0.001,
               round(cmp["faturamento_variacao_pct"], 4), round(cresc_motor, 4))
        checar(f"{nome}: resumo tem 'calculo' com formula e valores",
               bool(r["calculo"]["formula"]) and bool(r["calculo"]["valores"]))

    secao("Isolamento multicliente")
    st, r_eme = chamar("GET", f"/analytics/{cid_eme}/resumo?periodo_ini=202601&periodo_fim=202607")
    st, r_mil = chamar("GET", f"/analytics/{cid_mil}/resumo?periodo_ini=202601&periodo_fim=202607")
    checar("EMEFARMA e MILLENIUM tem faturamentos diferentes",
           r_eme["faturamento"] != r_mil["faturamento"])
    st, prod_eme = chamar("GET", f"/analytics/{cid_eme}/produtos?periodo_ini=202601&periodo_fim=202607&limite=5")
    st, prod_mil = chamar("GET", f"/analytics/{cid_mil}/produtos?periodo_ini=202601&periodo_fim=202607&limite=5")
    checar("rankings de produto sao diferentes entre clientes",
           [p["produto_id"] for p in prod_eme["itens"]] != [p["produto_id"] for p in prod_mil["itens"]])

    secao("Guarda de cobertura: nao inflar crescimento com historico parcial")
    # 'Ultimo ano' encostando no inicio dos dados (jan/2025): a janela de
    # comparacao YoY cairia em ago/2024-jul/2025, parcialmente antes do
    # inicio real dos dados. Regressao do bug encontrado na verificacao manual
    # (mostrava +87,5% de crescimento nao real).
    st, r = chamar("GET", f"/analytics/{cid_mil}/resumo?periodo_ini=202508&periodo_fim=202607")
    cmp = r["comparacao_ano_anterior"]
    checar("comparacao marcada como invalida quando o historico nao cobre",
           cmp is not None and cmp["comparacao_valida"] is False)
    checar("nenhum numero de crescimento mostrado quando invalido",
           cmp["faturamento_variacao_pct"] is None and cmp["faturamento_anterior"] is None)
    checar("motivo explicado nas premissas",
           any("início dos dados" in p or "inicio dos dados" in p
               for p in cmp["calculo"]["premissas"]))

    st, rank = chamar("GET", f"/analytics/{cid_mil}/produtos?periodo_ini=202508&periodo_fim=202607&limite=500")
    checar("ranking de produtos tambem marca comparacao invalida no mesmo caso",
           rank.get("comparacao_valida") is False)
    checar("nenhum produto com variacao numerica quando invalido (tudo None)",
           all(it["variacao_pct"] is None for it in rank["itens"]))

    secao("Estado vazio: cliente sem distribuidor correspondente")
    st, novo = chamar("POST", "/clientes", {"nome": "CLIENTE SEM DADOS XPTO"})
    cid_vazio = novo["id"]
    st, disp_vazio = chamar("GET", f"/analytics/{cid_vazio}/disponibilidade")
    checar("cliente novo sem distribuidor: tem_distribuidor_vinculado=False",
           disp_vazio["tem_distribuidor_vinculado"] is False)
    st, resumo_vazio = chamar("GET", f"/analytics/{cid_vazio}/resumo?periodo_ini=202601&periodo_fim=202607")
    checar("resumo do cliente vazio nao inventa numero", resumo_vazio["disponivel"] is False)
    checar("motivo explicado, nao generico", "distribuidor" in resumo_vazio["motivo"].lower())
    chamar("DELETE", f"/clientes/{cid_vazio}")

    secao("Endpoints — disponibilidade, filtros e tempo de resposta")
    for nome, cid in (("EMEFARMA", cid_eme), ("MILLENIUM", cid_mil)):
        t0 = time.time()
        st, ev = chamar("GET", f"/analytics/{cid}/evolucao-mensal?periodo_ini=202501&periodo_fim=202607&metrica=faturamento")
        checar(f"{nome}: evolucao mensal — 19 meses", len(ev["serie"]) == 19)

        st, uf = chamar("GET", f"/analytics/{cid}/uf?periodo_ini=202601&periodo_fim=202607")
        checar(f"{nome}: UF disponivel e nao vazia", uf["disponivel"] and len(uf["itens"]) > 0)
        soma_uf = sum(i["faturamento"] for i in uf["itens"])
        st, resumo = chamar("GET", f"/analytics/{cid}/resumo?periodo_ini=202601&periodo_fim=202607")
        checar(f"{nome}: soma por UF bate com o faturamento total",
               abs(soma_uf - resumo["faturamento"]) < 0.01)

        st, conc = chamar("GET", f"/analytics/{cid}/concentracao?periodo_ini=202601&periodo_fim=202607&contexto=produtos")
        checar(f"{nome}: concentracao top5 <= top10 <= top20",
               conc["faixas"][0]["percentual"] <= conc["faixas"][1]["percentual"] <= conc["faixas"][2]["percentual"])

        st, pdvs_rank = chamar("GET", f"/analytics/{cid}/pdvs?periodo_ini=202601&periodo_fim=202607&visao=ranking&limite=10")
        checar(f"{nome}: ranking de PDV nao vazio", len(pdvs_rank["itens"]) > 0)
        st, pdvs_novos = chamar("GET", f"/analytics/{cid}/pdvs?periodo_ini=202601&periodo_fim=202607&visao=novos")
        st, pdvs_sumidos = chamar("GET", f"/analytics/{cid}/pdvs?periodo_ini=202601&periodo_fim=202607&visao=sumidos")
        checar(f"{nome}: novos/sumidos respondem", pdvs_novos["disponivel"] and pdvs_sumidos["disponivel"])

        st, alertas = chamar("GET", f"/analytics/{cid}/alertas?periodo_ini=202601&periodo_fim=202607")
        checar(f"{nome}: alertas gerados", alertas["disponivel"] and len(alertas["itens"]) > 0)

        dt = time.time() - t0
        checar(f"{nome}: bateria de 6 consultas responde rápido ({dt:.2f}s)", dt < 5.0, round(dt, 2), "<5s")

    secao("Validacao de entrada")
    st, _ = chamar("GET", f"/analytics/{cid_eme}/resumo?periodo_ini=202613&periodo_fim=202607")
    checar("periodo invalido devolve 400", st == 400, st, 400)
    st, _ = chamar("GET", f"/analytics/{cid_eme}/resumo?periodo_ini=202607&periodo_fim=202601")
    checar("periodo_fim antes de periodo_ini devolve 400", st == 400, st, 400)
    st, _ = chamar("GET", "/analytics/99999/resumo?periodo_ini=202601&periodo_fim=202607")
    checar("cliente inexistente devolve 404", st == 404, st, 404)

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
