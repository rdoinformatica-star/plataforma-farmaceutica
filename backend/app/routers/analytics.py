"""Rotas do motor de performance comercial (Etapa 2).

Toda rota exige client_id no caminho e sempre passa por
analytics.contexto.carregar(), que resolve os distribuidores vinculados a
esse cliente — nunca consulta fact_sales sem esse filtro. Isso e o que
garante o isolamento entre clientes (nenhuma rota le dados de outro cliente
por engano).
"""
import analytics.vendas as vendas
from analytics.contexto import carregar as carregar_disponibilidade
from analytics.periodo import validar as validar_periodo
from fastapi import APIRouter, Query

from .. import db
from ..core import errors

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _periodo(periodo_ini: int, periodo_fim: int) -> tuple[int, int]:
    try:
        validar_periodo(periodo_ini)
        validar_periodo(periodo_fim)
        if periodo_fim < periodo_ini:
            raise ValueError("periodo_fim antes de periodo_ini")
    except ValueError as e:
        raise errors.invalido("Período inválido.", str(e))
    return periodo_ini, periodo_fim


def _cliente_existe(con, client_id: int):
    if not db.uma(con, "SELECT id FROM clients WHERE id = ?", (client_id,)):
        raise errors.nao_encontrado("Cliente", client_id)


@router.get("/{client_id}/disponibilidade")
def disponibilidade(client_id: int):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        d = carregar_disponibilidade(con, client_id)
    return {
        "client_id": d.client_id, "cliente": d.cliente_nome,
        "distribuidor_ids": d.distribuidor_ids,
        "tem_distribuidor_vinculado": d.tem_distribuidor_vinculado,
        "tem_sellout": d.tem_sellout, "tem_iqvia": d.tem_iqvia,
        "tem_estoque": d.tem_estoque, "tem_uf": d.tem_uf, "tem_pdv": d.tem_pdv,
        "periodo_min": d.periodo_min, "periodo_max": d.periodo_max,
        "n_produtos": d.n_produtos, "n_pdvs": d.n_pdvs,
        "motivo_indisponivel": d.motivo_indisponivel,
    }


@router.get("/{client_id}/resumo")
def resumo(client_id: int, periodo_ini: int, periodo_fim: int):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.resumo_executivo(con, client_id, ini, fim)


@router.get("/{client_id}/evolucao-mensal")
def evolucao_mensal(client_id: int, periodo_ini: int, periodo_fim: int,
                    metrica: str = Query("faturamento",
                                         pattern="^(faturamento|unidades|pdvs|skus)$")):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.evolucao_mensal(con, client_id, metrica, ini, fim)


@router.get("/{client_id}/produtos")
def produtos(client_id: int, periodo_ini: int, periodo_fim: int,
            ordenar: str = Query("faturamento",
                                 pattern="^(faturamento|unidades|crescimento|queda)$"),
            limite: int = Query(20, le=500), offset: int = 0):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.ranking_produtos(con, client_id, ini, fim,
                                       ordenar=ordenar, limite=limite, offset=offset)


@router.get("/{client_id}/produtos/variacao")
def produtos_variacao(
        client_id: int, periodo_ini: int, periodo_fim: int,
        direcao: str = Query("crescimento", pattern="^(crescimento|queda)$"),
        limite_crescimento_pct: float = 10.0,
        limite_atencao_pct: float = -10.0,
        limite_queda_pct: float = -20.0,
        limite_critica_pct: float = -35.0):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.variacao_produtos(
            con, client_id, ini, fim, direcao=direcao,
            limite_crescimento_pct=limite_crescimento_pct,
            limite_atencao_pct=limite_atencao_pct,
            limite_queda_pct=limite_queda_pct,
            limite_critica_pct=limite_critica_pct)


@router.get("/{client_id}/uf")
def uf(client_id: int, periodo_ini: int, periodo_fim: int):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.analise_uf(con, client_id, ini, fim)


@router.get("/{client_id}/pdvs")
def pdvs(client_id: int, periodo_ini: int, periodo_fim: int,
         visao: str = Query("ranking", pattern="^(ranking|novos|sumidos)$"),
         limite: int = Query(20, le=500), offset: int = 0):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.ranking_pdvs(con, client_id, ini, fim,
                                   visao=visao, limite=limite, offset=offset)


@router.get("/{client_id}/concentracao")
def concentracao(client_id: int, periodo_ini: int, periodo_fim: int,
                 contexto: str = Query("produtos", pattern="^(produtos|pdvs)$")):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.concentracao(con, client_id, ini, fim, contexto=contexto)


@router.get("/{client_id}/alertas")
def alertas(client_id: int, periodo_ini: int, periodo_fim: int):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.alertas(con, client_id, ini, fim)
