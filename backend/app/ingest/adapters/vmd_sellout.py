"""Adaptador do sell-out (dashboard com payload binario VMD1).

Reusa engine/vmd.py inteiro. Aquele modulo ja resolve os dois detalhes que
custam caro se passarem despercebidos:
  * o offset de cada coluna e em BYTES, nao em elementos;
  * fUnd e fVal vem multiplicados por 100.

Aqui os valores continuam x100 ate o banco: e assim que a soma fica exata.
A divisao acontece so na view v_vendas.

Toda a traducao e vetorizada. Um laco Python sobre 6,8 milhoes de linhas levaria
minutos; indexacao array-por-array resolve em segundos porque o laco roda em C.
"""
from pathlib import Path

import numpy as np

from .. import engine_bridge, loader
from ..base import Lote, procurar
from ..profiler import Coluna

CODIGO = "vmd_sellout"
ROTULO = "Sell-out (dashboard VMD1)"
DATA_SOURCE = "SELLOUT"

_MARCA = b'id="pack"'


def pontuar(path: Path, cabeca: bytes, ext: str) -> tuple[float, str]:
    if ext not in {".html", ".htm"}:
        return 0.0, ""
    if _MARCA in cabeca or procurar(path, _MARCA) >= 0:
        return 0.99, 'bloco <script id="pack"> encontrado — payload VMD1 de sell-out'
    return 0.0, ""


def params_sugeridos(path: Path, cabeca: bytes) -> dict:
    return {}


def abrir(path: Path, params: dict, prog) -> Lote:
    sha = params.get("_sha", "")
    prog.etapa("Preparando a base de sell-out", 0.05)
    bin_path = engine_bridge.extrair_pack(path, sha, log=prog.log)

    prog.etapa("Lendo a base de sell-out", 0.15)
    pack = engine_bridge.abrir_pack(bin_path)
    col, dic = pack.col, pack.dic
    n = int(len(col["fVal"]))
    periodos = [int(p) for p in pack.periodos]
    prog.log(f"Base aberta: {n:,} linhas, {len(periodos)} periodos, "
             f"{len(dic.get('provNome', []))} distribuidores."
             .replace(",", "."))

    def gravar(con, import_id, p):
        p.etapa("Cadastrando distribuidores, produtos e PDVs", 0.30)
        con.execute("BEGIN")
        dist_map = loader.upsert_distribuidores(
            con, dic["provNome"], dic.get("provCnpj"), import_id)
        prod_map = loader.upsert_produtos_vmd(
            con, dic["prodApres"], dic.get("prodEan"), dic.get("prodFcc"),
            dic.get("produto"), dic.get("marca"),
            col.get("prodPro"), col.get("prodMar"), import_id)
        pdv_map, colisoes = loader.upsert_pdvs(
            con, dic["pdvRazao"], dic.get("pdvCnpj"), col, dic, import_id)
        con.execute("COMMIT")
        if colisoes:
            p.log(f"{colisoes} PDVs compartilham o mesmo identificador e foram "
                  f"tratados como o mesmo ponto de venda.", "aviso")

        p.etapa("Traduzindo as linhas de venda", 0.38)
        per = np.asarray(periodos, dtype=np.int64)[col["fMes"]]
        matriz = np.column_stack((
            np.full(n, import_id, dtype=np.int64),
            dist_map[col["fProv"]],
            prod_map[col["fProd"]],
            pdv_map[col["fPdv"]],
            per,
            col["fUnd"].astype(np.int64),   # continua x100 de proposito
            col["fVal"].astype(np.int64),
        ))
        del per
        escritas = loader.gravar_em_blocos(
            con, loader.INSERT_VENDAS, matriz, p, "Gravando vendas")
        del matriz
        return escritas

    # O perfil sai quase de graca: o VMD1 ja entrega tudo como indice inteiro,
    # entao bincount resolve a contagem exata dos 6,8 milhoes em milissegundos.
    colunas = [
        Coluna("Distribuidor", col["fProv"], list(dic["provNome"])),
        Coluna("Produto (apresentacao)", col["fProd"], list(dic["prodApres"])),
        Coluna("PDV", col["fPdv"], list(dic["pdvRazao"])),
        Coluna("Periodo", np.asarray(periodos, dtype=np.int64)[col["fMes"]]),
        Coluna("Unidades", col["fUnd"].astype(np.float64) / 100.0),
        Coluna("Valor R$", col["fVal"].astype(np.float64) / 100.0),
    ]
    if "pdvUf" in col:
        colunas.append(Coluna("UF do PDV", col["pdvUf"][col["fPdv"]],
                              list(dic.get("uf", []))))
    if "pdvGrp" in col:
        colunas.append(Coluna("Rede do PDV", col["pdvGrp"][col["fPdv"]],
                              list(dic.get("grupo", []))))

    return Lote(
        fonte="SELLOUT",
        n_linhas=n,
        colunas=colunas,
        gravar=gravar,
        # 6,8 milhoes de linhas x 8 colunas em np.unique(axis=0) custaria minutos
        # e nao responderia nada que o grao do arquivo ja nao diga.
        buscar_chaves=False,
        entidades={
            "distribuidores": len(dic["provNome"]),
            "produtos": len(dic["prodApres"]),
            "pdvs": len(dic["pdvRazao"]),
            "periodos": len(periodos),
            "ufs": len(dic.get("uf", [])),
        },
        periodo={"min": min(periodos), "max": max(periodos), "granularidade": "mes"},
        limitacoes=[
            "O sell-out mede a venda do distribuidor para o ponto de venda. Nao "
            "diz o que o consumidor comprou, nem o que o distribuidor tem em "
            "estoque.",
            "O CNPJ do faturador nao e a praca de venda: um CNPJ pode atender "
            "outro estado. Para avaliar praca, use a UF do PDV.",
            "Um mesmo PDV compra de varios distribuidores. Ao medir a perda de um "
            "distribuidor, so vale o que aquele PDV comprava dele.",
        ],
        indices_pos_carga=list(loader.INDICES_VENDAS),
        resumo_mensal=True,
    )
