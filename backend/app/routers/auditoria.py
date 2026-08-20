import json

from fastapi import APIRouter, Query, Response

from .. import db, settings

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("")
def listar(response: Response, acao: str | None = None, entidade: str | None = None,
           limite: int = Query(100, le=settings.LIMITE_MAXIMO), offset: int = 0):
    where, params = [], []
    if acao:
        where.append("acao = ?")
        params.append(acao)
    if entidade:
        where.append("entidade = ?")
        params.append(entidade)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""
    with db.conexao() as con:
        total = db.escalar(con, f"SELECT count(*) FROM audit_logs{filtro}", params)
        linhas = db.varias(con,
            f"SELECT * FROM audit_logs{filtro} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limite, offset])
        acoes = [r["acao"] for r in con.execute(
            "SELECT DISTINCT acao FROM audit_logs ORDER BY acao")]
    for l in linhas:
        l["detalhe"] = json.loads(l.pop("detalhe_json") or "null")
    response.headers["X-Total-Count"] = str(total)
    return {"itens": linhas, "total": total, "acoes": acoes}
