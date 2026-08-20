"""Rotas do motor de performance comercial (Etapa 2: vendas: | Etapa 3: abc/
cobertura/mix/oportunidades).

Toda rota exige client_id no caminho e sempre passa por
analytics.contexto.carregar(), que resolve os distribuidores vinculados a
esse cliente — nunca consulta fact_sales sem esse filtro. Isso e o que
garante o isolamento entre clientes (nenhuma rota le dados de outro cliente
por engano).
"""
import analytics.abc as abc_mod
import analytics.cobertura as cobertura_mod
import analytics.mix as mix_mod
import analytics.oportunidades as oportunidades_mod
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


# ─────────────────────────────── Etapa 3 ────────────────────────────────

@router.get("/{client_id}/abc")
def abc(client_id: int, periodo_ini: int, periodo_fim: int,
       limite_a: float = 80.0, limite_b: float = 95.0, uf: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return abc_mod.curva_abc(con, client_id, ini, fim,
                                 limite_a=limite_a, limite_b=limite_b, uf=uf)


@router.get("/{client_id}/abc/crescimento")
def abc_crescimento(client_id: int, periodo_ini: int, periodo_fim: int,
                    limite_a: float = 80.0, limite_b: float = 95.0,
                    limite_crescimento_pct: float = 10.0,
                    limite_queda_pct: float = -10.0, uf: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return abc_mod.abc_crescimento(
            con, client_id, ini, fim, limite_a=limite_a, limite_b=limite_b,
            limite_crescimento_pct=limite_crescimento_pct,
            limite_queda_pct=limite_queda_pct, uf=uf)


@router.get("/{client_id}/cobertura")
def cobertura(client_id: int, periodo_ini: int, periodo_fim: int,
             uf: str | None = None, limite: int = Query(100, le=500), offset: int = 0):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return cobertura_mod.cobertura_produtos(con, client_id, ini, fim,
                                                uf=uf, limite=limite, offset=offset)


@router.get("/{client_id}/cobertura/matriz")
def cobertura_matriz(client_id: int, periodo_ini: int, periodo_fim: int,
                     uf: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return cobertura_mod.matriz_cobertura_faturamento(con, client_id, ini, fim, uf=uf)


@router.get("/{client_id}/cobertura/potencial")
def cobertura_potencial(client_id: int, periodo_ini: int, periodo_fim: int,
                        incremento_pp: float = Query(10.0, gt=0, le=100),
                        top_n: int = Query(20, le=200),
                        minimo_pdvs_compradores: int = 5, uf: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return cobertura_mod.potencial_cobertura(
            con, client_id, ini, fim, incremento_pp=incremento_pp, top_n=top_n,
            minimo_pdvs_compradores=minimo_pdvs_compradores, uf=uf)


@router.get("/{client_id}/mix")
def mix(client_id: int, periodo_ini: int, periodo_fim: int, uf: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mix_mod.mix_por_pdv(con, client_id, ini, fim, uf=uf)


@router.get("/{client_id}/mix/monoproduto")
def mix_monoproduto(client_id: int, periodo_ini: int, periodo_fim: int,
                    uf: str | None = None, limite: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mix_mod.monoproduto(con, client_id, ini, fim, uf=uf, limite=limite)


@router.get("/{client_id}/mix/alto")
def mix_alto(client_id: int, periodo_ini: int, periodo_fim: int,
            minimo_skus: int = Query(10, ge=2), uf: str | None = None,
            limite: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mix_mod.alto_mix(con, client_id, ini, fim, minimo_skus=minimo_skus,
                                uf=uf, limite=limite)


@router.get("/{client_id}/mix/oportunidades")
def mix_oportunidades(client_id: int, periodo_ini: int, periodo_fim: int,
                      uf: str | None = None, limite: int = Query(30, le=200)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mix_mod.oportunidades_expansao(con, client_id, ini, fim, uf=uf, limite=limite)


@router.get("/{client_id}/oportunidades")
def oportunidades(client_id: int, periodo_ini: int, periodo_fim: int,
                  peso_potencial: float = 40.0, peso_impacto: float = 35.0,
                  peso_facilidade: float = 25.0,
                  incremento_pp: float = Query(10.0, gt=0, le=100),
                  top_n: int = Query(30, le=200)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return oportunidades_mod.matriz_oportunidades(
            con, client_id, ini, fim, peso_potencial=peso_potencial,
            peso_impacto=peso_impacto, peso_facilidade=peso_facilidade,
            incremento_pp=incremento_pp, top_n=top_n)


@router.get("/{client_id}/alertas-expandidos")
def alertas_expandidos(client_id: int, periodo_ini: int, periodo_fim: int):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return oportunidades_mod.alertas_expandidos(con, client_id, ini, fim)
