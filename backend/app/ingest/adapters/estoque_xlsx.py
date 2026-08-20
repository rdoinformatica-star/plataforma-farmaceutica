"""Adaptador de estoque do distribuidor (planilha por SKU x filial).

O casamento das colunas e FUZZY de proposito. O export real tem
'Estoque Diponivel Un' — falta o "s". Casamento exato descartaria a coluna em
silencio, que e exatamente o que este sistema nao pode fazer.
"""
import json
import re
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from ...core.texto import ean13, ean13_valido, normalizar
from ..base import Lote
from . import tabular

CODIGO = "estoque_xlsx"
ROTULO = "Estoque do distribuidor (planilha)"
DATA_SOURCE = "ESTOQUE"

LIMIAR_COLUNA = 0.85

# campo do banco -> nomes canonicos aceitos
CANONICAS: dict[str, tuple[str, ...]] = {
    "filial":               ("filial", "unidade", "cd", "deposito"),
    "produto":              ("produto", "descricao", "item", "sku"),
    "ean":                  ("ean", "codigo de barras", "gtin"),
    "custo_rep_x100":       ("custo rep", "custo reposicao", "custo de reposicao"),
    "estoque_total_un":     ("estoque total un", "estoque total"),
    "estoque_disp_un":      ("estoque disponivel un", "estoque disponivel"),
    "estoque_disp_x100":    ("estoque disponivel r$", "estoque disponivel valor"),
    "cobertura_dias":       ("cobertura", "cobertura dias", "dias de estoque"),
    "pendencia_un":         ("pendencia un", "pendencia"),
    "transferencia_un":     ("transferencia", "transferencia un"),
    "media_venda_x100":     ("media venda r$", "media de venda r$"),
    "media_venda_sgc_x100": ("media venda s/ gc r$", "media venda s/gc r$"),
    "media_venda_un":       ("media venda un", "media de venda un"),
    "media_venda_sgc_un":   ("media venda s/gc un", "media venda s/ gc un"),
}
_CENTAVOS = {"custo_rep_x100", "estoque_disp_x100",
             "media_venda_x100", "media_venda_sgc_x100"}
_RE_DATA = re.compile(r"(\d{2})[-_.](\d{2})[-_.](\d{4})")


def _prox(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def casar_colunas(colunas) -> tuple[dict, list[str], list[str]]:
    """Devolve (campo -> coluna original, colunas nao reconhecidas, avisos)."""
    livres = {str(c): normalizar(c).lower() for c in colunas}
    mapa, avisos = {}, []
    for campo, nomes in CANONICAS.items():
        melhor, score, alvo = None, 0.0, ""
        for original, norm in livres.items():
            for n in nomes:
                r = 1.0 if norm == n else _prox(norm, n)
                if r > score:
                    melhor, score, alvo = original, r, n
        if melhor and score >= LIMIAR_COLUNA:
            mapa[campo] = melhor
            del livres[melhor]
            if score < 1.0:
                avisos.append(
                    f"A coluna '{melhor}' foi entendida como '{alvo}' "
                    f"({score:.0%} de semelhanca) — pode ser erro de digitacao "
                    f"na origem do arquivo.")
    return mapa, list(livres), avisos


def pontuar(path: Path, cabeca: bytes, ext: str) -> tuple[float, str]:
    if ext not in {".xlsx", ".xls"}:
        return 0.0, ""
    try:
        cab = pd.read_excel(path, sheet_name=0, nrows=0)
    except Exception:
        return 0.0, ""
    mapa, _, _ = casar_colunas(cab.columns)
    n = len(mapa)
    if n < 6:
        return 0.0, ""
    return min(0.97, 0.55 + 0.03 * n), \
        f"{n} de {len(CANONICAS)} colunas tipicas de estoque reconhecidas"


def params_sugeridos(path: Path, cabeca: bytes) -> dict:
    m = _RE_DATA.search(path.name)
    data_ref = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
    try:
        abas = pd.ExcelFile(path).sheet_names
    except Exception:
        abas = []
    return {"aba": abas[0] if abas else 0, "abas_disponiveis": abas,
            "data_ref": data_ref,
            "data_ref_origem": "nome do arquivo" if data_ref else None}


def _num(serie):
    return pd.to_numeric(serie, errors="coerce")


def _x100(serie):
    v = _num(serie)
    return [None if pd.isna(x) else int(round(float(x) * 100)) for x in v]


def abrir(path: Path, params: dict, prog) -> Lote:
    prog.etapa("Lendo a planilha de estoque", 0.05)
    df = pd.read_excel(path, sheet_name=params.get("aba", 0))
    mapa, desconhecidas, avisos = casar_colunas(df.columns)

    limpo, lixo, motivo = tabular.separar_lixo(df)
    prog.log(f"{len(df)} linhas lidas, {len(limpo)} validas, {len(lixo)} descartadas.")
    for a in avisos:
        prog.log(a, "aviso")

    data_ref = params.get("data_ref") or date.today().isoformat()

    # EAN: float64 no arquivo. Sem normalizar, a chave entre fontes quebra calada.
    col_ean = mapa.get("ean")
    eans = [ean13(v) for v in limpo[col_ean]] if col_ean else [None] * len(limpo)
    invalidos = sum(1 for e in eans if e and not ean13_valido(e))
    if invalidos:
        avisos.append(f"{invalidos} codigos EAN tem digito verificador incorreto.")

    col_prod = mapa.get("produto")
    nomes = (limpo[col_prod].astype(str).tolist() if col_prod
             else [f"produto {i}" for i in range(len(limpo))])
    filiais = (limpo[mapa["filial"]].astype(str).tolist() if "filial" in mapa
               else [None] * len(limpo))

    extras = [
        {str(c): (None if pd.isna(v) else (float(v) if isinstance(v, (int, float)) else str(v)))
         for c, v in zip(desconhecidas, linha)}
        for linha in zip(*[limpo[c] for c in desconhecidas])
    ] if desconhecidas else [{}] * len(limpo)

    numericos = {}
    for campo, coluna in mapa.items():
        if campo in ("filial", "produto", "ean"):
            continue
        numericos[campo] = (_x100(limpo[coluna]) if campo in _CENTAVOS
                            else [None if pd.isna(x) else float(x)
                                  for x in _num(limpo[coluna])])

    def gravar(con, import_id, p):
        from ..loader import upsert_produtos_texto
        p.etapa("Gravando o estoque", 0.75)
        con.execute("BEGIN")
        ids = upsert_produtos_texto(con, nomes, eans, import_id)
        # Ao contrario do sell-out (arquivo nacional), o export de estoque ja
        # e de um distribuidor especifico: o cliente escolhido no wizard para
        # esta importacao e o dono direto das linhas.
        client_id = con.execute(
            "SELECT client_id FROM imports WHERE id = ?", (import_id,)).fetchone()[0]
        campos = ["import_id", "client_id", "filial", "produto_id", "data_ref",
                  "extras_json"] + list(numericos)
        sql = (f"INSERT INTO fact_inventory({', '.join(campos)}) "
               f"VALUES ({', '.join('?' * len(campos))})")
        linhas = [
            [import_id, client_id, filiais[i], ids[i], data_ref,
             json.dumps(extras[i], ensure_ascii=False) if extras[i] else None]
            + [numericos[c][i] for c in numericos]
            for i in range(len(limpo))
        ]
        con.executemany(sql, linhas)
        con.execute("COMMIT")
        return len(linhas)

    colunas_perfil = tabular.colunas_para_perfil(limpo)
    return Lote(
        fonte="ESTOQUE",
        n_linhas=len(limpo),
        colunas=colunas_perfil,
        gravar=gravar,
        descartadas=len(lixo),
        motivo_descarte=motivo,
        amostras_descartadas=json.loads(lixo.head(5).to_json(orient="records"))
                             if len(lixo) else [],
        avisos=avisos,
        colunas_novas=desconhecidas,
        limitacoes=[
            f"Este arquivo e uma foto do estoque em {data_ref}. Nao ha serie "
            f"historica, entao nao da para calcular tendencia de estoque a partir "
            f"dele — so a posicao nessa data.",
            "Nem toda filial costuma ter posicao fisica de estoque. Filiais sem "
            "estoque podem indicar operacao sem deposito proprio, e nao erro.",
        ],
        entidades={"produtos": len({e or n for e, n in zip(eans, nomes)}),
                   "filiais": len({f for f in filiais if f})},
        periodo={"min": data_ref, "max": data_ref, "granularidade": "dia"},
    )
