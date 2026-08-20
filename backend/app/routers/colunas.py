import json

from fastapi import APIRouter

from .. import db
from ..core import audit, errors
from ..schemas import DecisaoColuna

router = APIRouter(prefix="/colunas", tags=["colunas"])


@router.get("/pendentes")
def pendentes():
    """Campos novos que o sistema encontrou e ainda nao sabe o que fazer com."""
    with db.conexao() as con:
        linhas = db.varias(con,
            "SELECT c.*, i.arquivo_nome, i.id AS import_id, f.codigo AS fonte"
            "  FROM import_columns c"
            "  JOIN imports i ON i.id = c.import_id"
            "  JOIN data_sources f ON f.id = i.data_source_id"
            " WHERE c.decisao='PENDENTE' ORDER BY c.import_id DESC, c.ordem")
    for c in linhas:
        c["stats"] = json.loads(c.pop("stats_json") or "{}")
    return linhas


@router.put("/{cid}/decisao")
def decidir(cid: int, dados: DecisaoColuna):
    with db.transacao() as con:
        col = db.uma(con, "SELECT * FROM import_columns WHERE id = ?", (cid,))
        if not col:
            raise errors.nao_encontrado("Coluna", cid)
        if dados.decisao in ("MAPEAR", "RELACIONAR") and not dados.mapeado_para:
            raise errors.invalido(
                "Escolha para qual campo esta coluna deve apontar.")
        con.execute(
            "UPDATE import_columns SET decisao=?, mapeado_para=?,"
            " decidido_por='usuario', decidido_em=datetime('now','localtime')"
            " WHERE id=?", (dados.decisao, dados.mapeado_para, cid))
        audit.registrar(
            con, "COLUNA_DECIDIDA",
            f"Coluna '{col['nome_original']}' definida como {dados.decisao}.",
            "import_columns", cid,
            {"import_id": col["import_id"], "decisao": dados.decisao,
             "mapeado_para": dados.mapeado_para})
        atualizado = db.uma(con, "SELECT * FROM import_columns WHERE id = ?", (cid,))
    atualizado["stats"] = json.loads(atualizado.pop("stats_json") or "{}")
    return atualizado
