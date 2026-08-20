import sqlite3
import sys

from fastapi import APIRouter

from .. import db, settings
from ..core import ai_provider

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health():
    with db.conexao() as con:
        tabelas = [
            r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        fontes = db.escalar(con, "SELECT count(*) FROM data_sources")

    try:
        from ..ingest import engine_bridge
        engine_ok, engine_msg = engine_bridge.disponivel()
    except Exception as e:  # a ponte nunca pode derrubar o health
        engine_ok, engine_msg = False, str(e)

    tamanho = settings.DB_PATH.stat().st_size / (1024 * 1024) if settings.DB_PATH.exists() else 0
    return {
        "ok": True,
        "produto": "Pharma Intelligence",
        "versao": settings.VERSAO,
        "etapa": settings.ETAPA,
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "db_path": str(settings.DB_PATH),
        "db_tamanho_mb": round(tamanho, 2),
        "tabelas": tabelas,
        "n_tabelas": len(tabelas),
        "fontes": fontes,
        "engine_ok": engine_ok,
        "engine_msg": engine_msg,
        "ia": ai_provider.listar(),
    }


@router.get("/estatisticas")
def estatisticas():
    with db.conexao() as con:
        e = db.escalar
        ultima = db.uma(con,
            "SELECT i.id, i.arquivo_nome, i.status, i.concluido_em, i.linhas_gravadas,"
            "       f.codigo AS fonte, c.nome AS cliente"
            "  FROM imports i"
            "  JOIN data_sources f ON f.id = i.data_source_id"
            "  LEFT JOIN clients c ON c.id = i.client_id"
            " ORDER BY i.id DESC LIMIT 1")
        por_fonte = db.varias(con,
            "SELECT f.codigo, f.nome, count(i.id) AS n_importacoes,"
            "       coalesce(sum(i.linhas_gravadas),0) AS linhas"
            "  FROM data_sources f"
            "  LEFT JOIN imports i ON i.data_source_id = f.id"
            "       AND i.status='CONCLUIDO' AND i.vigente=1"
            " GROUP BY f.id ORDER BY f.id")
        return {
            "clientes": e(con, "SELECT count(*) FROM clients WHERE ativo=1"),
            "importacoes": e(con, "SELECT count(*) FROM imports WHERE status='CONCLUIDO'"),
            "produtos": e(con, "SELECT count(*) FROM dim_product"),
            "produtos_novos": e(con, "SELECT count(*) FROM dim_product WHERE eh_novo=1"),
            "pdvs": e(con, "SELECT count(*) FROM dim_pdv"),
            "distribuidores": e(con, "SELECT count(*) FROM dim_distribuidor"),
            "linhas_vendas": e(con, "SELECT count(*) FROM fact_sales"),
            "linhas_estoque": e(con, "SELECT count(*) FROM fact_inventory"),
            "linhas_mercado": e(con, "SELECT count(*) FROM fact_market"),
            "colunas_pendentes": e(con,
                "SELECT count(*) FROM import_columns WHERE decisao='PENDENTE'"),
            "mapeamentos_pendentes": e(con,
                "SELECT count(*) FROM source_mappings WHERE status='PENDENTE'"),
            "por_fonte": por_fonte,
            "ultima_importacao": ultima,
        }
