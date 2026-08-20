from fastapi import APIRouter, Query, Response

from .. import db, settings
from ..core import audit, errors, texto
from ..schemas import RevisaoDimensao

router = APIRouter(prefix="/dimensoes", tags=["dimensoes"])

_CFG = {
    "produtos": ("dim_product", "nome_canonico",
                 "id, chave_natural, nome_canonico, ean, apresentacao, marca,"
                 " molecula, eh_vitamedic, eh_novo, criado_em"),
    "pdvs": ("dim_pdv", "razao_social",
             "id, chave_natural, razao_social, cnpj, uf, cidade, grupo, tipo,"
             " eh_novo, criado_em"),
    "distribuidores": ("dim_distribuidor", "nome",
                       "id, chave_natural, nome, cnpj, uf, client_id, eh_novo,"
                       " criado_em"),
}


def _cfg(tipo: str):
    if tipo not in _CFG:
        raise errors.nao_encontrado("Dimensao", tipo)
    return _CFG[tipo]


@router.get("/{tipo}")
def listar(tipo: str, response: Response, busca: str = "", novo: bool | None = None,
           limite: int = Query(settings.LIMITE_PADRAO, le=settings.LIMITE_MAXIMO),
           offset: int = 0):
    tabela, campo_nome, campos = _cfg(tipo)
    where, params = [], []
    if busca:
        where.append(f"upper({campo_nome}) LIKE ?")
        params.append(f"%{texto.normalizar(busca)}%")
    if novo is not None:
        where.append("eh_novo = ?")
        params.append(int(novo))
    filtro = (" WHERE " + " AND ".join(where)) if where else ""
    with db.conexao() as con:
        total = db.escalar(con, f"SELECT count(*) FROM {tabela}{filtro}", params)
        linhas = db.varias(con,
            f"SELECT {campos} FROM {tabela}{filtro}"
            f" ORDER BY eh_novo DESC, {campo_nome} LIMIT ? OFFSET ?",
            params + [limite, offset])
    response.headers["X-Total-Count"] = str(total)
    return linhas


@router.post("/{tipo}/{did}/revisar")
def revisar(tipo: str, did: int, dados: RevisaoDimensao):
    """Tira (ou repoe) o selo de 'novo' depois que o usuario conferiu o cadastro."""
    tabela, campo_nome, _ = _cfg(tipo)
    with db.transacao() as con:
        item = db.uma(con, f"SELECT id, {campo_nome} AS nome FROM {tabela} WHERE id=?",
                      (did,))
        if not item:
            raise errors.nao_encontrado(tipo[:-1].capitalize(), did)
        con.execute(f"UPDATE {tabela} SET eh_novo=? WHERE id=?",
                    (int(dados.eh_novo), did))
        audit.registrar(con, "DIMENSAO_REVISADA",
                        f"'{item['nome']}' marcado como "
                        f"{'novo' if dados.eh_novo else 'revisado'}.",
                        tabela, did)
    return {"ok": True}
