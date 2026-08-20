import json

from fastapi import APIRouter, Query, Request, Response

from .. import db, settings
from ..core import audit, errors, hashing
from ..ingest import jobs, registry
from ..schemas import ImportacaoEntrada
from .arquivos import caminho_de

router = APIRouter(prefix="/importacoes", tags=["importacoes"])

_LISTA = """
SELECT i.id, i.arquivo_nome, i.arquivo_bytes, i.adaptador, i.status, i.progresso,
       i.etapa_atual, i.linhas_lidas, i.linhas_gravadas, i.linhas_descartadas,
       i.motivo_descarte,
       i.vigente, i.substituido_por, i.duracao_seg, i.pico_memoria_mb,
       i.periodo_min, i.periodo_max, i.erro_mensagem,
       i.iniciado_em, i.concluido_em, i.origem, i.adaptador_forcado,
       f.codigo AS fonte, f.nome AS fonte_nome, f.natureza_elo,
       c.nome AS cliente, i.client_id
  FROM imports i
  JOIN data_sources f ON f.id = i.data_source_id
  LEFT JOIN clients c ON c.id = i.client_id
"""


@router.get("")
def listar(response: Response, client_id: int | None = None, status: str | None = None,
           limite: int = Query(settings.LIMITE_PADRAO, le=settings.LIMITE_MAXIMO),
           offset: int = 0):
    where, params = [], []
    if client_id:
        where.append("i.client_id = ?")
        params.append(client_id)
    if status:
        where.append("i.status = ?")
        params.append(status)
    filtro = (" WHERE " + " AND ".join(where)) if where else ""
    with db.conexao() as con:
        total = db.escalar(con, f"SELECT count(*) FROM imports i{filtro}", params)
        linhas = db.varias(con, _LISTA + filtro + " ORDER BY i.id DESC LIMIT ? OFFSET ?",
                           params + [limite, offset])
    response.headers["X-Total-Count"] = str(total)
    return linhas


@router.post("", status_code=202)
def criar(dados: ImportacaoEntrada, request: Request):
    modulo = registry.obter(dados.adaptador)
    if modulo is None:
        raise errors.invalido(f"Adaptador desconhecido: {dados.adaptador}")

    origem_path = caminho_de(dados.origem, dados.caminho, dados.sha256)
    sha = dados.sha256 or hashing.sha256_arquivo(origem_path)

    with db.conexao() as con:
        fonte = db.uma(con, "SELECT * FROM data_sources WHERE id = ?",
                       (dados.data_source_id,))
        if not fonte:
            raise errors.nao_encontrado("Fonte de dados", dados.data_source_id)
        if dados.client_id and not db.uma(
                con, "SELECT id FROM clients WHERE id = ?", (dados.client_id,)):
            raise errors.nao_encontrado("Cliente", dados.client_id)

        anterior = db.uma(con,
            "SELECT id, arquivo_nome, concluido_em, linhas_gravadas FROM imports"
            " WHERE sha256=? AND status='CONCLUIDO' AND vigente=1"
            "   AND data_source_id=? AND coalesce(client_id,0)=coalesce(?,0)"
            " ORDER BY id DESC LIMIT 1",
            (sha, dados.data_source_id, dados.client_id))

    if anterior and not dados.forcar_reimportacao:
        raise errors.conflito(
            "ARQUIVO_JA_IMPORTADO",
            "Este arquivo ja foi importado para este cliente e esta fonte.",
            f"Importado em {anterior['concluido_em']} com "
            f"{anterior['linhas_gravadas']} registros.",
            {"import_id": anterior["id"]})

    # Guarda uma copia no acervo. O mesmo conteudo ocupa disco uma vez so.
    arquivado = hashing.arquivar(origem_path, sha)

    with db.transacao() as con:
        cur = con.execute(
            "INSERT INTO imports(client_id, data_source_id, adaptador, adaptador_conf,"
            " adaptador_forcado, origem, arquivo_nome, arquivo_path, arquivo_bytes,"
            " sha256, params_json, status, etapa_atual)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,'FILA','Aguardando na fila')",
            (dados.client_id, dados.data_source_id, dados.adaptador, None,
             int(dados.adaptador_forcado), dados.origem, origem_path.name,
             str(arquivado), origem_path.stat().st_size, sha,
             json.dumps(dados.params, ensure_ascii=False)))
        import_id = cur.lastrowid

        if anterior and dados.forcar_reimportacao:
            # Reimportar nunca apaga: a anterior sai dos calculos mas fica no historico.
            con.execute("UPDATE imports SET vigente=0, substituido_por=? WHERE id=?",
                        (import_id, anterior["id"]))
            audit.registrar(con, "IMPORT_SUBSTITUIDA",
                            f"A importacao #{anterior['id']} saiu dos calculos, "
                            f"substituida pela #{import_id}.",
                            "imports", anterior["id"])

        audit.registrar(con, "IMPORT_INICIADO",
                        f"Importacao de '{origem_path.name}' iniciada "
                        f"({modulo.ROTULO}).", "imports", import_id,
                        {"adaptador": dados.adaptador, "sha256": sha})

    request.app.state.executor.submit(jobs.executar, import_id)

    with db.conexao() as con:
        fila = db.escalar(con,
            "SELECT count(*) FROM imports WHERE status='FILA' AND id < ?", (import_id,))
    return {"import_id": import_id, "status": "FILA", "posicao_na_fila": fila}


@router.get("/{iid}")
def obter(iid: int):
    with db.conexao() as con:
        imp = db.uma(con, _LISTA + " WHERE i.id = ?", (iid,))
        if not imp:
            raise errors.nao_encontrado("Importacao", iid)
        bruto = db.uma(con, "SELECT log_json, params_json, erro_detalhe,"
                            " cancelar_pedido FROM imports WHERE id = ?", (iid,))
        tem_perfil = bool(db.escalar(
            con, "SELECT count(*) FROM profiles WHERE import_id = ?", (iid,)))
        pendentes = db.escalar(
            con, "SELECT count(*) FROM import_columns"
                 " WHERE import_id = ? AND decisao='PENDENTE'", (iid,))
        if imp["status"] == "FILA":
            imp["posicao_na_fila"] = db.escalar(con,
                "SELECT count(*) FROM imports WHERE status='FILA' AND id < ?", (iid,))

    imp["log"] = json.loads(bruto["log_json"] or "[]")
    imp["params"] = json.loads(bruto["params_json"] or "{}")
    imp["erro_detalhe"] = bruto["erro_detalhe"]
    imp["cancelamento_pedido"] = bool(bruto["cancelar_pedido"])
    imp["tem_perfil"] = tem_perfil
    imp["colunas_pendentes"] = pendentes
    imp["em_andamento"] = imp["status"] in jobs.ETAPAS_ATIVAS

    # ETA pela taxa media observada — util porque a carga do sell-out leva minutos.
    imp["eta_seg"] = None
    if imp["em_andamento"] and imp["progresso"] and imp["duracao_seg"] is None:
        pass
    if imp["em_andamento"] and 0.02 < imp["progresso"] < 1:
        import datetime as _dt
        try:
            inicio = _dt.datetime.fromisoformat(imp["iniciado_em"])
            decorrido = (_dt.datetime.now() - inicio).total_seconds()
            imp["eta_seg"] = max(0, round(decorrido / imp["progresso"] - decorrido))
        except (ValueError, ZeroDivisionError):
            pass
    return imp


@router.get("/{iid}/perfil")
def perfil(iid: int):
    with db.conexao() as con:
        p = db.uma(con, "SELECT * FROM profiles WHERE import_id = ?", (iid,))
        if not p:
            imp = db.uma(con, "SELECT status FROM imports WHERE id = ?", (iid,))
            if not imp:
                raise errors.nao_encontrado("Importacao", iid)
            raise errors.nao_encontrado(
                "Perfil desta importacao (status: %s)" % imp["status"], iid)
        imp = db.uma(con, _LISTA + " WHERE i.id = ?", (iid,))
    dados = json.loads(p["json"])
    dados["importacao"] = imp
    return dados


@router.get("/{iid}/colunas")
def colunas(iid: int):
    with db.conexao() as con:
        linhas = db.varias(con,
            "SELECT * FROM import_columns WHERE import_id = ? ORDER BY ordem", (iid,))
    for c in linhas:
        c["stats"] = json.loads(c.pop("stats_json") or "{}")
    return linhas


@router.get("/{iid}/amostra")
def amostra(iid: int, limite: int = Query(50, le=settings.LIMITE_MAXIMO)):
    """Primeiras linhas ja gravadas, para conferencia visual."""
    with db.conexao() as con:
        imp = db.uma(con, "SELECT * FROM imports WHERE id = ?", (iid,))
        if not imp:
            raise errors.nao_encontrado("Importacao", iid)
        fonte = db.escalar(con, "SELECT codigo FROM data_sources WHERE id = ?",
                           (imp["data_source_id"],))
        if fonte == "SELLOUT":
            return db.varias(con,
                "SELECT d.nome AS distribuidor, p.nome_canonico AS produto,"
                "       v.razao_social AS pdv, v.uf, s.periodo,"
                "       s.unidades_x100/100.0 AS unidades, s.valor_x100/100.0 AS valor"
                "  FROM fact_sales s"
                "  JOIN dim_distribuidor d ON d.id = s.distribuidor_id"
                "  JOIN dim_product p ON p.id = s.produto_id"
                "  LEFT JOIN dim_pdv v ON v.id = s.pdv_id"
                " WHERE s.import_id = ? LIMIT ?", (iid, limite))
        if fonte == "ESTOQUE":
            return db.varias(con,
                "SELECT e.filial, p.nome_canonico AS produto, p.ean, e.data_ref,"
                "       e.estoque_disp_un, e.estoque_disp_x100/100.0 AS estoque_valor,"
                "       e.cobertura_dias, e.media_venda_x100/100.0 AS media_venda"
                "  FROM fact_inventory e JOIN dim_product p ON p.id = e.produto_id"
                " WHERE e.import_id = ? LIMIT ?", (iid, limite))
        if fonte == "IQVIA":
            return db.varias(con,
                "SELECT mercado, apresentacao, molecula, uf, canal, lab_full,"
                "       eh_vitamedic, un_atual, valor_atual_x100/100.0 AS valor_atual"
                "  FROM fact_market WHERE import_id = ? LIMIT ?", (iid, limite))
    return []


@router.post("/{iid}/cancelar")
def cancelar(iid: int):
    with db.transacao() as con:
        imp = db.uma(con, "SELECT status, arquivo_nome FROM imports WHERE id = ?", (iid,))
        if not imp:
            raise errors.nao_encontrado("Importacao", iid)
        if imp["status"] not in jobs.ETAPAS_ATIVAS:
            raise errors.conflito("IMPORT_NAO_ESTA_RODANDO",
                                  "Esta importacao ja terminou.",
                                  f"Situacao atual: {imp['status']}.")
        con.execute("UPDATE imports SET cancelar_pedido=1 WHERE id=?", (iid,))
        audit.registrar(con, "IMPORT_CANCELAMENTO_PEDIDO",
                        f"Cancelamento pedido para '{imp['arquivo_nome']}'.",
                        "imports", iid)
    return {"ok": True,
            "mensagem": "Cancelamento solicitado. A importacao para no proximo bloco."}


@router.post("/{iid}/desfazer")
def desfazer(iid: int):
    """Remove os dados desta importacao. O registro dela permanece no historico."""
    with db.conexao() as con:
        imp = db.uma(con, "SELECT * FROM imports WHERE id = ?", (iid,))
        if not imp:
            raise errors.nao_encontrado("Importacao", iid)
        if imp["status"] in jobs.ETAPAS_ATIVAS:
            raise errors.conflito("IMPORT_EM_ANDAMENTO",
                                  "Esta importacao ainda esta rodando.",
                                  "Cancele antes de desfazer.")
        apagados = 0
        for tabela in ("fact_sales", "fact_inventory", "fact_market",
                       "agg_vendas_mensal"):
            cur = con.execute(f"DELETE FROM {tabela} WHERE import_id = ?", (iid,))
            apagados += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        con.execute(
            "UPDATE imports SET vigente=0, status='CANCELADO',"
            " etapa_atual='Dados removidos pelo usuario' WHERE id=?", (iid,))
        if imp["substituido_por"] is None:
            con.execute("UPDATE imports SET vigente=1, substituido_por=NULL"
                        " WHERE substituido_por = ?", (iid,))
        audit.registrar(con, "IMPORT_DESFEITA",
                        f"Dados da importacao '{imp['arquivo_nome']}' removidos "
                        f"({apagados} registros).", "imports", iid,
                        {"registros_removidos": apagados})
    return {"ok": True, "registros_removidos": apagados}
