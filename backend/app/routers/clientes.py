from fastapi import APIRouter, Query

from .. import db
from ..core import audit, errors, texto
from ..schemas import ClienteAtualizacao, ClienteEntrada

router = APIRouter(prefix="/clientes", tags=["clientes"])

_SELECT = """
SELECT c.*,
       (SELECT count(*) FROM imports i WHERE i.client_id = c.id) AS n_importacoes,
       (SELECT max(i.concluido_em) FROM imports i
         WHERE i.client_id = c.id AND i.status='CONCLUIDO') AS ultima_importacao
  FROM clients c
"""


@router.get("")
def listar(busca: str = "", ativo: bool | None = None):
    where, params = [], []
    if busca:
        where.append("c.nome_norm LIKE ?")
        params.append(f"%{texto.normalizar(busca)}%")
    if ativo is not None:
        where.append("c.ativo = ?")
        params.append(int(ativo))
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY c.nome"
    with db.conexao() as con:
        return db.varias(con, sql, params)


@router.get("/{cid}")
def obter(cid: int):
    with db.conexao() as con:
        c = db.uma(con, _SELECT + " WHERE c.id = ?", (cid,))
        if not c:
            raise errors.nao_encontrado("Cliente", cid)
        c["fontes"] = db.varias(con,
            "SELECT f.codigo, f.nome, f.natureza_elo, count(i.id) AS n_importacoes,"
            "       max(i.concluido_em) AS ultima"
            "  FROM imports i JOIN data_sources f ON f.id = i.data_source_id"
            " WHERE i.client_id = ? AND i.status='CONCLUIDO'"
            " GROUP BY f.id ORDER BY f.codigo", (cid,))
        c["importacoes"] = db.varias(con,
            "SELECT i.id, i.arquivo_nome, i.status, i.linhas_gravadas, i.vigente,"
            "       i.iniciado_em, i.concluido_em, f.codigo AS fonte"
            "  FROM imports i JOIN data_sources f ON f.id = i.data_source_id"
            " WHERE i.client_id = ? ORDER BY i.id DESC LIMIT 50", (cid,))
        return c


@router.post("", status_code=201)
def criar(dados: ClienteEntrada):
    norm = texto.normalizar(dados.nome)
    if not norm:
        raise errors.invalido("O nome do cliente nao pode ficar em branco.")
    cnpj = texto.so_digitos(dados.cnpj) or None
    if cnpj and not texto.cnpj_valido(cnpj):
        raise errors.invalido(
            "Este CNPJ nao e valido.",
            "Confira os numeros. O campo tambem pode ficar vazio.")
    uf = (dados.uf_principal or "").strip().upper() or None
    if uf and uf not in texto.UFS:
        raise errors.invalido(f"'{uf}' nao e uma sigla de estado valida.")

    with db.transacao() as con:
        if db.uma(con, "SELECT id FROM clients WHERE nome_norm = ?", (norm,)):
            raise errors.conflito(
                "CLIENTE_DUPLICADO", f"Ja existe um cliente chamado '{dados.nome}'.",
                "Use outro nome ou edite o cliente que ja existe.")
        cur = con.execute(
            "INSERT INTO clients(nome, nome_norm, cnpj, uf_principal, grupo, observacoes)"
            " VALUES (?,?,?,?,?,?)",
            (dados.nome.strip(), norm, cnpj, uf, dados.grupo, dados.observacoes))
        cid = cur.lastrowid
        audit.registrar(con, "CLIENTE_CRIADO", f"Cliente '{dados.nome}' cadastrado.",
                        "clients", cid)
        # Se o sell-out ja foi importado antes deste cliente existir, liga
        # agora aos distribuidores da base cujo nome corresponde.
        from analytics.vinculo import resolver_vinculos
        resolver_vinculos(con, client_id=cid)
        return db.uma(con, _SELECT + " WHERE c.id = ?", (cid,))


@router.put("/{cid}")
def atualizar(cid: int, dados: ClienteAtualizacao):
    campos = dados.model_dump(exclude_unset=True)
    if not campos:
        raise errors.invalido("Nenhum campo para atualizar.")

    with db.transacao() as con:
        atual = db.uma(con, "SELECT * FROM clients WHERE id = ?", (cid,))
        if not atual:
            raise errors.nao_encontrado("Cliente", cid)

        sets, params = [], []
        if "nome" in campos:
            norm = texto.normalizar(campos["nome"])
            outro = db.uma(con,
                "SELECT id FROM clients WHERE nome_norm = ? AND id <> ?", (norm, cid))
            if outro:
                raise errors.conflito("CLIENTE_DUPLICADO",
                                      f"Ja existe outro cliente chamado '{campos['nome']}'.")
            sets += ["nome = ?", "nome_norm = ?"]
            params += [campos["nome"].strip(), norm]
        if "cnpj" in campos:
            cnpj = texto.so_digitos(campos["cnpj"]) or None
            if cnpj and not texto.cnpj_valido(cnpj):
                raise errors.invalido("Este CNPJ nao e valido.")
            sets.append("cnpj = ?")
            params.append(cnpj)
        if "uf_principal" in campos:
            uf = (campos["uf_principal"] or "").strip().upper() or None
            if uf and uf not in texto.UFS:
                raise errors.invalido(f"'{uf}' nao e uma sigla de estado valida.")
            sets.append("uf_principal = ?")
            params.append(uf)
        for campo in ("grupo", "observacoes"):
            if campo in campos:
                sets.append(f"{campo} = ?")
                params.append(campos[campo])
        if "ativo" in campos:
            sets.append("ativo = ?")
            params.append(int(campos["ativo"]))

        sets.append("atualizado_em = datetime('now','localtime')")
        con.execute(f"UPDATE clients SET {', '.join(sets)} WHERE id = ?", params + [cid])
        audit.registrar(con, "CLIENTE_ATUALIZADO",
                        f"Cliente '{atual['nome']}' atualizado.", "clients", cid,
                        {"campos": list(campos)})
        if "nome" in campos:
            # O nome mudou: pode passar a corresponder a distribuidores que
            # antes nao casavam. Nunca desfaz um vinculo ja feito.
            from analytics.vinculo import resolver_vinculos
            resolver_vinculos(con, client_id=cid)
        return db.uma(con, _SELECT + " WHERE c.id = ?", (cid,))


@router.delete("/{cid}")
def excluir(cid: int, desativar: bool = Query(False)):
    with db.transacao() as con:
        c = db.uma(con, "SELECT * FROM clients WHERE id = ?", (cid,))
        if not c:
            raise errors.nao_encontrado("Cliente", cid)
        n = db.escalar(con, "SELECT count(*) FROM imports WHERE client_id = ?", (cid,))

        if desativar:
            con.execute("UPDATE clients SET ativo=0,"
                        " atualizado_em=datetime('now','localtime') WHERE id=?", (cid,))
            audit.registrar(con, "CLIENTE_DESATIVADO",
                            f"Cliente '{c['nome']}' desativado.", "clients", cid)
            return {"ok": True, "acao": "desativado"}

        if n:
            raise errors.conflito(
                "CLIENTE_COM_IMPORTACOES",
                f"'{c['nome']}' tem {n} importacao(oes) e nao pode ser excluido.",
                "Apagar o cliente apagaria o historico. Prefira desativar.",
                {"n_importacoes": n, "sugestao": "desativar"})

        con.execute("DELETE FROM clients WHERE id = ?", (cid,))
        audit.registrar(con, "CLIENTE_EXCLUIDO", f"Cliente '{c['nome']}' excluido.",
                        "clients", cid)
        return {"ok": True, "acao": "excluido"}
