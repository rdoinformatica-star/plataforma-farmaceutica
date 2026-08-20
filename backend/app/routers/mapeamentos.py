"""Mapeamento de fontes.

Duas bases chamam o mesmo produto de nomes diferentes. O sistema sugere, mas
quem confirma e o usuario: casar errado aqui contamina toda analise cruzada.
"""
from difflib import SequenceMatcher

from fastapi import APIRouter, Query, Response

from .. import db, settings
from ..core import audit, errors, texto
from ..schemas import MapeamentoEntrada

router = APIRouter(prefix="/mapeamentos", tags=["mapeamentos"])

_TABELA = {"PRODUTO": ("dim_product", "nome_canonico"),
           "PDV": ("dim_pdv", "razao_social"),
           "DISTRIBUIDOR": ("dim_distribuidor", "nome")}


@router.get("")
def listar(response: Response, entidade: str | None = None, status: str | None = None,
           limite: int = Query(settings.LIMITE_PADRAO, le=settings.LIMITE_MAXIMO),
           offset: int = 0):
    where, params = [], []
    if entidade:
        where.append("m.entidade = ?")
        params.append(entidade)
    if status:
        where.append("m.status = ?")
        params.append(status)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""
    with db.conexao() as con:
        total = db.escalar(con, f"SELECT count(*) FROM source_mappings m{filtro}", params)
        linhas = db.varias(con,
            "SELECT m.*, f.codigo AS fonte FROM source_mappings m"
            " JOIN data_sources f ON f.id = m.data_source_id" + filtro +
            " ORDER BY m.id DESC LIMIT ? OFFSET ?", params + [limite, offset])
    response.headers["X-Total-Count"] = str(total)
    return linhas


@router.get("/sugestoes")
def sugestoes(entidade: str = Query("PRODUTO"), termo: str = Query(...),
              limite: int = Query(10, le=50)):
    """Candidatos por similaridade de texto. Nunca casa por preco nem por valor."""
    if entidade not in _TABELA:
        raise errors.invalido(f"Entidade invalida: {entidade}")
    tabela, campo = _TABELA[entidade]
    alvo = texto.normalizar(termo).lower()

    with db.conexao() as con:
        linhas = db.varias(con, f"SELECT id, {campo} AS nome FROM {tabela} LIMIT 20000")

    pontuados = []
    for l in linhas:
        n = texto.normalizar(l["nome"]).lower()
        r = SequenceMatcher(None, alvo, n).ratio()
        if r >= 0.5:
            pontuados.append({"entity_id": l["id"], "nome": l["nome"],
                              "confianca": round(r, 3),
                              "metodo": "EXATO" if r == 1.0 else
                                        "NORMALIZADO" if r > 0.92 else "FUZZY"})
    pontuados.sort(key=lambda x: x["confianca"], reverse=True)
    return pontuados[:limite]


@router.post("", status_code=201)
def criar(dados: MapeamentoEntrada):
    tabela, campo = _TABELA[dados.entidade]
    with db.transacao() as con:
        alvo = db.uma(con, f"SELECT id, {campo} AS nome FROM {tabela} WHERE id = ?",
                      (dados.entity_id,))
        if not alvo:
            raise errors.nao_encontrado(dados.entidade.capitalize(), dados.entity_id)
        con.execute(
            "INSERT OR REPLACE INTO source_mappings(entidade, data_source_id,"
            " codigo_origem, texto_origem, entity_id, metodo, confianca, status,"
            " confirmado_por, observacao)"
            " VALUES (?,?,?,?,?,'MANUAL',1.0,'ATIVO','usuario',?)",
            (dados.entidade, dados.data_source_id, dados.codigo_origem,
             dados.texto_origem, dados.entity_id, dados.observacao))
        audit.registrar(
            con, "MAPEAMENTO_CRIADO",
            f"'{dados.texto_origem}' ligado a '{alvo['nome']}'.",
            "source_mappings", dados.entity_id,
            {"entidade": dados.entidade, "origem": dados.texto_origem})
    return {"ok": True, "ligado_a": alvo["nome"]}


@router.delete("/{mid}")
def remover(mid: int):
    with db.transacao() as con:
        m = db.uma(con, "SELECT * FROM source_mappings WHERE id = ?", (mid,))
        if not m:
            raise errors.nao_encontrado("Mapeamento", mid)
        con.execute("DELETE FROM source_mappings WHERE id = ?", (mid,))
        audit.registrar(con, "MAPEAMENTO_REMOVIDO",
                        f"Mapeamento de '{m['texto_origem']}' removido.",
                        "source_mappings", mid)
    return {"ok": True}
