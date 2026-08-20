"""Verificacao ponta a ponta da Etapa 1.

Nao e teste unitario: sobe nada, mas conversa com a API rodando e confere o
banco depois. A regra do projeto e que uma etapa so esta pronta quando a
aplicacao realmente funciona, entao o que este script mede e o comportamento
real, com os arquivos reais.

Uso:  python backend/testar_etapa1.py [--completo]
      --completo inclui o sell-out de 6,8 milhoes de linhas (leva minutos).
"""
import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
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
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def esperar(import_id: int, limite_seg: int = 900) -> dict:
    t0 = time.time()
    ultimo = ""
    while time.time() - t0 < limite_seg:
        _, d = chamar("GET", f"/importacoes/{import_id}")
        if d.get("etapa_atual") != ultimo:
            ultimo = d.get("etapa_atual") or ""
            print(f"        ... {ultimo}")
        if not d.get("em_andamento"):
            return d
        time.sleep(1.5)
    raise TimeoutError(f"Importacao {import_id} passou de {limite_seg}s.")


def sql(consulta: str, params=()):
    con = sqlite3.connect(DB)
    try:
        return con.execute(consulta, params).fetchone()[0]
    finally:
        con.close()


def secao(titulo: str):
    print(f"\n== {titulo} " + "=" * max(0, 58 - len(titulo)))


# ─────────────────────────────── testes ────────────────────────────────

def teste_saude():
    secao("Saude do sistema")
    st, d = chamar("GET", "/health")
    checar("API responde", st == 200, st, 200)
    checar("banco criado com todas as tabelas", d["n_tabelas"] >= 20, d["n_tabelas"], ">=20")
    checar("7 fontes de dados no seed", d["fontes"] == 7, d["fontes"], 7)
    checar("motor engine/ carregado", d["engine_ok"], d["engine_msg"])
    manual = next(c for c in d["ia"] if c["codigo"] == "MANUAL")
    checar("provedor de IA manual disponivel e sem custo",
           manual["disponivel"] and not manual["exige_chave"])
    checar("nenhum provedor pago ativo",
           all(not c["disponivel"] for c in d["ia"] if c["codigo"] != "MANUAL"))


def teste_clientes() -> int:
    secao("Cadastro de clientes")
    st, d = chamar("POST", "/clientes", {"nome": "EMEFARMA", "uf_principal": "RJ"})
    checar("cria cliente", st == 201, st, 201)
    cid = d["id"]

    st, e = chamar("POST", "/clientes", {"nome": "  emefarma "})
    checar("recusa nome duplicado", st == 409, st, 409)
    checar("erro duplicado vem em portugues, sem stack trace",
           "erro" in e and "Ja existe" in e["erro"]["mensagem"])

    st, e = chamar("POST", "/clientes", {"nome": "TESTE UF", "uf_principal": "XX"})
    checar("recusa sigla de estado invalida", st == 400, st, 400)

    st, e = chamar("POST", "/clientes", {"nome": "TESTE CNPJ", "cnpj": "11111111111111"})
    checar("recusa CNPJ invalido", st == 400, st, 400)

    st, _ = chamar("PUT", f"/clientes/{cid}", {"grupo": "Regional Sudeste"})
    checar("edita cliente", st == 200, st, 200)

    st, d2 = chamar("GET", f"/clientes/{cid}")
    checar("edicao persistiu", d2["grupo"] == "Regional Sudeste", d2["grupo"])

    st, _ = chamar("POST", "/clientes", {"nome": "MILLENIUM", "uf_principal": "ES"})
    checar("cria segundo cliente", st == 201, st, 201)
    return cid


def importar(caminho: str, adaptador: str, fonte_id: int, cid: int | None,
             params: dict, forcar=False):
    st, d = chamar("POST", "/importacoes", {
        "origem": "DISCO", "caminho": caminho, "adaptador": adaptador,
        "client_id": cid, "data_source_id": fonte_id, "params": params,
        "forcar_reimportacao": forcar})
    if st != 202:
        return st, d
    return st, esperar(d["import_id"])


def teste_estoque(cid: int):
    secao("Importacao 1 — estoque (planilha)")
    arq = "dados/estoque_emefarma_20-08-2026.xlsx"
    if not (RAIZ / arq).exists():
        print("  PULADO (arquivo ausente)")
        return

    st, det = chamar("POST", "/arquivos/detectar",
                     {"origem": "DISCO", "caminho": arq})
    checar("detecta o arquivo", st == 200, st, 200)
    melhor = det["candidatos"][0]
    checar("reconhece como estoque", melhor["adaptador"] == "estoque_xlsx",
           melhor["adaptador"])
    checar("confianca alta", melhor["confianca"] >= 0.9, melhor["confianca"])
    checar("oferece alternativa para o usuario trocar", len(det["candidatos"]) > 1)
    checar("le a data de referencia do nome do arquivo",
           melhor["params_sugeridos"].get("data_ref") == "2026-08-20",
           melhor["params_sugeridos"].get("data_ref"))

    st, imp = importar(arq, "estoque_xlsx", melhor["data_source_id"], cid,
                       melhor["params_sugeridos"])
    checar("importacao concluida", imp.get("status") == "CONCLUIDO",
           imp.get("status"), "CONCLUIDO")
    checar("leu as 371 linhas", imp["linhas_lidas"] == 371, imp["linhas_lidas"], 371)
    checar("gravou 368 linhas uteis", imp["linhas_gravadas"] == 368,
           imp["linhas_gravadas"], 368)
    checar("descartou as 3 linhas de subtotal", imp["linhas_descartadas"] == 3,
           imp["linhas_descartadas"], 3)
    checar("explica por que descartou", bool(imp.get("motivo_descarte")),
           imp.get("motivo_descarte"))
    iid = imp["id"]

    st, p = chamar("GET", f"/importacoes/{iid}/perfil")
    checar("perfil disponivel", st == 200, st, 200)
    checar("perfilou as 22 colunas", p["dataset"]["colunas"] == 22,
           p["dataset"]["colunas"], 22)
    checar("mostra quais linhas foram descartadas",
           len(p["dataset"]["amostras_descartadas"]) == 3)

    por_nome = {c["nome"]: c for c in p["colunas"]}
    ean = por_nome["EAN"]
    checar("EAN reconhecido como codigo de barras",
           ean["papel"]["valor"] == "CODIGO_EAN", ean["papel"]["valor"])
    checar("evidencia do EAN cita o digito verificador",
           "verificador" in ean["papel"]["evidencia"].lower(),
           ean["papel"]["evidencia"])
    checar("nao acusa outlier em codigo de barras",
           not any(x["tipo"] == "OUTLIER" for x in ean["problemas"]))
    checar("Produto reconhecido", por_nome["Produto"]["papel"]["valor"] == "PRODUTO",
           por_nome["Produto"]["papel"]["valor"])
    checar("Filial reconhecida como categoria",
           por_nome["Filial"]["papel"]["valor"] == "CATEGORIA",
           por_nome["Filial"]["papel"]["valor"])
    checar("colunas de R$ reconhecidas como valor",
           por_nome["Estoque Disponível R$"]["papel"]["valor"] == "VALOR",
           por_nome["Estoque Disponível R$"]["papel"]["valor"])

    checar("achou a chave (Filial + EAN)",
           any(set(k["colunas"]) == {"EAN", "Filial"} for k in p["chaves_candidatas"]),
           p["chaves_candidatas"])
    checar("avisa sobre o erro de digitacao na origem",
           any("Diponível" in a for a in p["dataset"]["avisos"]),
           p["dataset"]["avisos"])
    checar("declara a limitacao de ser foto de um dia",
           any("foto do estoque" in l for l in p["limitacoes"]))

    checar("368 linhas de estoque no banco",
           sql("SELECT count(*) FROM v_estoque") == 368,
           sql("SELECT count(*) FROM v_estoque"), 368)
    checar("produtos cadastrados", sql("SELECT count(*) FROM dim_product") > 100)
    checar("produtos entram marcados como novos",
           sql("SELECT count(*) FROM dim_product WHERE eh_novo=1") > 0)
    checar("EAN gravado como texto de 13 digitos, nao como numero",
           sql("SELECT count(*) FROM dim_product WHERE length(ean)=13") > 100)

    st, _ = chamar("POST", "/importacoes", {
        "origem": "DISCO", "caminho": arq, "adaptador": "estoque_xlsx",
        "client_id": cid, "data_source_id": 3, "params": {}})
    checar("recusa reimportar o mesmo arquivo", st == 409, st, 409)

    st, amostra = chamar("GET", f"/importacoes/{iid}/amostra?limite=5")
    checar("mostra amostra dos dados gravados", st == 200 and len(amostra) == 5)
    return iid


def teste_iqvia(cid: int):
    secao("Importacao 2 — mercado (IQVIA)")
    arq = "dados/Dashboard_Mercado_Relevante_VITAMEDIC.html"
    if not (RAIZ / arq).exists():
        print("  PULADO (arquivo ausente)")
        return

    st, det = chamar("POST", "/arquivos/detectar", {"origem": "DISCO", "caminho": arq})
    melhor = det["candidatos"][0]
    checar("reconhece como IQVIA", melhor["adaptador"] == "iqvia_mercado",
           melhor["adaptador"])
    checar("confianca alta", melhor["confianca"] >= 0.95, melhor["confianca"])
    checar("oferece escolher a aba",
           "m24" in melhor["params_sugeridos"].get("abas_disponiveis", []))

    st, imp = importar(arq, "iqvia_mercado", melhor["data_source_id"], cid,
                       {"aba": "m24"})
    checar("importacao concluida", imp.get("status") == "CONCLUIDO",
           imp.get("status"), "CONCLUIDO")
    checar("gravou as linhas de mercado", imp["linhas_gravadas"] > 100_000,
           imp["linhas_gravadas"])

    checar("fact_market populada", sql("SELECT count(*) FROM fact_market") > 100_000)
    checar("identificou as linhas da Vitamedic",
           sql("SELECT count(*) FROM fact_market WHERE eh_vitamedic=1") > 0)
    checar("resolveu os textos (mercado, UF, laboratorio)",
           sql("SELECT count(*) FROM fact_market WHERE mercado IS NOT NULL"
               " AND uf IS NOT NULL AND lab_full IS NOT NULL") > 100_000)
    checar("fonte marcada como elo PDV->consumidor",
           imp["natureza_elo"] == "PDV_CONSUMIDOR", imp["natureza_elo"])

    st, p = chamar("GET", f"/importacoes/{imp['id']}/perfil")
    checar("avisa que o preco nao e comparavel com sell-out",
           any("NAO e comparavel" in a or "nao e comparavel" in a.lower()
               for a in p["dataset"]["avisos"]), p["dataset"]["avisos"])
    checar("declara que share baixo nao e falha do distribuidor",
           any("espaco de mercado" in l for l in p["limitacoes"]))


def teste_sellout(cid: int):
    secao("Importacao 3 — sell-out (VMD1, 6,8 milhoes de linhas)")
    arq = "dados/Dashboard_Sellout_VITAMEDIC.html"
    if not (RAIZ / arq).exists():
        print("  PULADO (arquivo ausente)")
        return

    st, det = chamar("POST", "/arquivos/detectar", {"origem": "DISCO", "caminho": arq})
    melhor = det["candidatos"][0]
    checar("reconhece como sell-out VMD1", melhor["adaptador"] == "vmd_sellout",
           melhor["adaptador"])

    t0 = time.time()
    st, imp = importar(arq, "vmd_sellout", melhor["data_source_id"], cid, {})
    checar("importacao concluida", imp.get("status") == "CONCLUIDO",
           imp.get("status") or imp.get("erro_mensagem"), "CONCLUIDO")
    if imp.get("status") != "CONCLUIDO":
        return
    print(f"        tempo total: {time.time()-t0:.0f}s | "
          f"pico de memoria: {imp['pico_memoria_mb']} MB")

    n = sql("SELECT count(*) FROM fact_sales")
    checar("gravou os 6.802.108 registros", n == 6_802_108, n, 6_802_108)
    checar("547 distribuidores", sql("SELECT count(*) FROM dim_distribuidor") == 547,
           sql("SELECT count(*) FROM dim_distribuidor"), 547)
    checar("PDVs cadastrados", sql("SELECT count(*) FROM dim_pdv") > 100_000,
           sql("SELECT count(*) FROM dim_pdv"))
    checar("periodo de 202501 a 202607",
           (imp["periodo_min"], imp["periodo_max"]) == (202501, 202607),
           (imp["periodo_min"], imp["periodo_max"]))
    checar("indices criados",
           sql("SELECT count(*) FROM sqlite_master WHERE type='index'"
               " AND name LIKE 'ix_fs_%'") == 3)

    checar("resumo mensal materializado",
           sql("SELECT count(*) FROM v_vendas_mensal") > 100_000,
           sql("SELECT count(*) FROM v_vendas_mensal"))

    # O resumo tem que dar exatamente o mesmo total do grao bruto, senao ele
    # esta mentindo nas telas de visao geral.
    bruto = sql("SELECT round(sum(valor),2) FROM v_vendas")
    resumo = sql("SELECT round(sum(valor),2) FROM v_vendas_mensal")
    checar("resumo mensal bate com o grao bruto", bruto == resumo, resumo, bruto)

    did = sql("SELECT id FROM dim_distribuidor WHERE nome LIKE '%EMEFARMA%' LIMIT 1")
    for rotulo, consulta, params in (
        ("visao do distribuidor",
         "SELECT periodo, sum(valor), count(DISTINCT pdv_id) FROM v_vendas"
         " WHERE distribuidor_id=? GROUP BY periodo", (did,)),
        ("ranking nacional (usa o resumo)",
         "SELECT distribuidor_id, sum(valor) FROM v_vendas_mensal"
         " GROUP BY distribuidor_id ORDER BY 2 DESC LIMIT 10", ()),
        ("total do pais por mes (usa o resumo)",
         "SELECT periodo, sum(valor) FROM v_vendas_mensal GROUP BY periodo", ()),
    ):
        con = sqlite3.connect(DB)
        t0 = time.time()
        con.execute(consulta, params).fetchall()
        dt = time.time() - t0
        con.close()
        checar(f"{rotulo} responde rapido ({dt:.2f}s)", dt < 1.5, round(dt, 2), "<1,5s")


def teste_conferencia_com_motor():
    """O teste mais importante: o total do banco tem que bater com o motor antigo.

    Se divergir, ou a escala x100 esta errada, ou o mapeamento de dicionario
    trocou algum indice — os dois erros silenciosos mais caros deste projeto.
    """
    secao("Conferencia contra o motor original (engine/analise.py)")
    if sql("SELECT count(*) FROM fact_sales") == 0:
        print("  PULADO (sem sell-out importado — rode com --completo)")
        return

    sys.path.insert(0, str(RAIZ / "engine"))
    import numpy as np
    import vmd

    pack = vmd.Pack()
    col, dic = pack.col, pack.dic
    val = col["fVal"].astype(np.int64)
    und = col["fUnd"].astype(np.int64)

    con = sqlite3.connect(DB)
    try:
        for alvo in ("EMEFARMA", "MILLENIUM"):
            idx = pack.idx_of("provNome", alvo)
            if not idx:
                continue
            mascara = np.isin(col["fProv"], idx)
            motor_val = float(val[mascara].sum()) / vmd.ESCALA
            motor_und = float(und[mascara].sum()) / vmd.ESCALA

            linha = con.execute(
                "SELECT coalesce(sum(v.valor),0), coalesce(sum(v.unidades),0)"
                "  FROM v_vendas v JOIN dim_distribuidor d ON d.id=v.distribuidor_id"
                " WHERE upper(d.nome) LIKE ?", (f"%{alvo}%",)).fetchone()
            banco_val, banco_und = float(linha[0]), float(linha[1])

            print(f"        {alvo}: motor R$ {motor_val:,.2f} | "
                  f"banco R$ {banco_val:,.2f}")
            checar(f"{alvo}: valor bate com o motor ate o centavo",
                   abs(motor_val - banco_val) < 0.01,
                   round(banco_val, 2), round(motor_val, 2))
            checar(f"{alvo}: unidades batem com o motor",
                   abs(motor_und - banco_und) < 0.01,
                   round(banco_und, 2), round(motor_und, 2))
    finally:
        con.close()


def teste_limites():
    secao("Limites e protecoes")
    st, d = chamar("GET", "/importacoes?limite=1000")
    checar("recusa pedir mais de 500 linhas de uma vez", st == 422, st, 422)

    st, d = chamar("GET", "/arquivos/disco?pasta=C:\\Windows")
    checar("bloqueia navegar fora das pastas permitidas", st == 403, st, 403)

    st, d = chamar("GET", "/arquivos/disco")
    checar("lista a pasta dados/", st == 200 and any(
        i["nome"].endswith(".xlsx") for i in d["itens"]))

    st, d = chamar("GET", "/clientes/99999")
    checar("cliente inexistente devolve erro claro", st == 404, st, 404)

    st, d = chamar("GET", "/auditoria")
    checar("auditoria registrou as acoes", d["total"] > 0, d["total"])


def teste_preservacao():
    secao("Preservacao do motor original (nao pode ter mudado)")
    import subprocess
    r = subprocess.run(["git", "status", "--porcelain", "engine/"],
                       cwd=RAIZ, capture_output=True, text=True)
    checar("engine/ sem nenhuma alteracao", r.stdout.strip() == "",
           r.stdout.strip() or "limpo")
    for f in ("vmd.py", "iqvia.py", "analise.py", "config.py"):
        checar(f"engine/{f} continua existindo", (RAIZ / "engine" / f).exists())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--completo", action="store_true",
                    help="inclui o sell-out de 6,8 milhoes de linhas")
    args = ap.parse_args()

    print("=" * 64)
    print("  PHARMA INTELLIGENCE — verificacao da Etapa 1")
    print("=" * 64)

    try:
        chamar("GET", "/health")
    except Exception:
        print("\nA API nao esta respondendo em http://127.0.0.1:8000")
        print("Suba o servidor antes (iniciar.bat) e rode de novo.")
        return 2

    teste_saude()
    cid = teste_clientes()
    teste_estoque(cid)
    teste_iqvia(cid)
    if args.completo:
        teste_sellout(cid)
        teste_conferencia_com_motor()
    else:
        print("\n(sell-out nao testado — use --completo)")
    teste_limites()
    teste_preservacao()

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
