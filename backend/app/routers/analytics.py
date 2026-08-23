"""Rotas do motor de performance comercial (Etapa 2: vendas | Etapa 3: abc/
cobertura/mix/oportunidades | Etapa 4: estoque/mercado/preco).

Toda rota exige client_id no caminho e sempre passa por
analytics.contexto.carregar(), que resolve os distribuidores vinculados a
esse cliente — nunca consulta fact_sales sem esse filtro. Isso e o que
garante o isolamento entre clientes (nenhuma rota le dados de outro cliente
por engano).
"""
import analytics.abc as abc_mod
import analytics.cobertura as cobertura_mod
import analytics.combos as combos_mod
import analytics.compra as compra_mod
import analytics.estoque as estoque_mod
import analytics.mercado as mercado_mod
import analytics.mix as mix_mod
import analytics.oportunidades as oportunidades_mod
import analytics.potencial as potencial_mod
import analytics.preco as preco_mod
import analytics.vendas as vendas
from analytics.contexto import carregar as carregar_disponibilidade
from analytics.periodo import validar as validar_periodo
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

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
            uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
            limite: int = Query(20, le=500), offset: int = 0):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.ranking_produtos(con, client_id, ini, fim, ordenar=ordenar,
                                       uf=uf.upper() if uf else None,
                                       limite=limite, offset=offset)


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
         uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
         limite: int = Query(20, le=500), offset: int = 0):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return vendas.ranking_pdvs(con, client_id, ini, fim, visao=visao,
                                   uf=uf.upper() if uf else None,
                                   limite=limite, offset=offset)


@router.get("/{client_id}/potencial/produtos")
def potencial_produtos(client_id: int, periodo_ini: int, periodo_fim: int,
                       uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
                       top_n: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return potencial_mod.potencial_produtos(
            con, client_id, ini, fim, uf=uf.upper() if uf else None, top_n=top_n)


@router.get("/{client_id}/potencial/pdvs")
def potencial_pdvs(client_id: int, periodo_ini: int, periodo_fim: int,
                   uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
                   top_n: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return potencial_mod.potencial_pdvs(
            con, client_id, ini, fim, uf=uf.upper() if uf else None, top_n=top_n)


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


@router.get("/{client_id}/abc/mercado")
def abc_mercado(client_id: int, periodo_ini: int, periodo_fim: int,
                limite_a: float = 80.0, limite_b: float = 95.0,
                uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
                top_n: int = Query(100, le=1000)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return abc_mod.abc_vs_mercado(con, client_id, ini, fim,
                                      limite_a=limite_a, limite_b=limite_b,
                                      uf=uf.upper() if uf else None, top_n=top_n)


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


@router.get("/{client_id}/mix/faixa")
def mix_faixa(client_id: int, periodo_ini: int, periodo_fim: int,
              sku_min: int = Query(1, ge=1), sku_max: int | None = Query(None, ge=1),
              uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
              limite: int = Query(200, le=2000)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        try:
            return mix_mod.detalhe_faixa(con, client_id, ini, fim,
                                         sku_min=sku_min, sku_max=sku_max,
                                         uf=uf.upper() if uf else None, limite=limite)
        except ValueError as e:
            raise errors.invalido(str(e))


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
                  uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
                  escopo: str | None = Query(None, pattern="^(PRODUTO|PDV)$"),
                  top_n: int = Query(30, le=200)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return oportunidades_mod.matriz_oportunidades(
            con, client_id, ini, fim, peso_potencial=peso_potencial,
            peso_impacto=peso_impacto, peso_facilidade=peso_facilidade,
            incremento_pp=incremento_pp, uf=uf.upper() if uf else None,
            escopo=escopo, top_n=top_n)


class _PedidoEntrada(BaseModel):
    """DDE por grupo e por produto vem no corpo: sao mapas de tamanho variavel,
    e o comprador ajusta varias linhas antes de recalcular."""
    periodo_ini: int
    periodo_fim: int
    agrupamento: str = "abc"
    dde_padrao: float = compra_mod.DDE_ALVO_PADRAO
    dde_por_grupo: dict[str, float] = {}
    dde_por_produto: dict[int, float] = {}
    base_velocidade: str = "fonte"
    filial: str | None = None
    valor_alvo: float | None = None
    teto_por_sku: float = compra_mod.TETO_POR_SKU_PADRAO
    incluir_sem_giro: bool = False


def _montar_pedido(con, client_id: int, e: _PedidoEntrada) -> dict:
    ini, fim = _periodo(e.periodo_ini, e.periodo_fim)
    if e.base_velocidade not in ("fonte", "periodo"):
        raise errors.invalido("base_velocidade deve ser 'fonte' ou 'periodo'.")
    try:
        return compra_mod.sugerir_pedido(
            con, client_id, ini, fim, agrupamento=e.agrupamento,
            dde_por_grupo=e.dde_por_grupo, dde_padrao=e.dde_padrao,
            dde_por_produto=e.dde_por_produto, base_velocidade=e.base_velocidade,
            filial=e.filial, valor_alvo=e.valor_alvo, teto_por_sku=e.teto_por_sku,
            incluir_sem_giro=e.incluir_sem_giro)
    except ValueError as exc:
        raise errors.invalido(str(exc))


@router.post("/{client_id}/compra")
def compra_sugestao(client_id: int, entrada: _PedidoEntrada):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return _montar_pedido(con, client_id, entrada)


@router.post("/{client_id}/compra/xlsx")
def compra_xlsx(client_id: int, entrada: _PedidoEntrada):
    with db.conexao() as con:
        cliente = _cliente_existe(con, client_id)
        dados = _montar_pedido(con, client_id, entrada)
        if not dados.get("disponivel"):
            raise errors.invalido(dados.get("motivo", "Sem dados para exportar."))
        nome = (cliente or {}).get("nome") if isinstance(cliente, dict) else None
        if not nome:
            row = db.uma(con, "SELECT nome FROM clients WHERE id = ?", (client_id,))
            nome = (row or {}).get("nome", f"cliente {client_id}")
        conteudo = compra_mod.exportar_xlsx(dados, nome)

    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in nome)
    arquivo = f"proposta_compra_{seguro}_{dados['data_ref']}.xlsx"
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{arquivo}"'},
    )


@router.get("/{client_id}/combos")
def combos(client_id: int, periodo_ini: int, periodo_fim: int,
           foco: str = Query("geral", pattern="^(geral|criticos|zumbi|misto|giro_rapido)$"),
           uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
           max_acompanhantes: int = Query(2, ge=1, le=5),
           top_n: int = Query(20, le=200)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        try:
            return combos_mod.sugerir_combos(
                con, client_id, ini, fim, foco=foco, uf=uf.upper() if uf else None,
                max_acompanhantes=max_acompanhantes, top_n=top_n)
        except ValueError as e:
            raise errors.invalido(str(e))


@router.get("/{client_id}/combos/afinidade")
def combos_afinidade(client_id: int, periodo_ini: int, periodo_fim: int,
                     uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
                     top_n: int = Query(100, le=1000)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return combos_mod.afinidade(con, client_id, ini, fim,
                                    uf=uf.upper() if uf else None, top_n=top_n)


@router.get("/{client_id}/ajuste-preco")
def ajuste_preco(client_id: int, periodo_ini: int, periodo_fim: int,
                 uf: str | None = Query(None, pattern="^[A-Za-z]{2}$"),
                 limite_alerta_pct: float = Query(8.0, ge=0, le=100),
                 top_n: int = Query(30, le=200)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return combos_mod.ajuste_preco(
            con, client_id, ini, fim, uf=uf.upper() if uf else None,
            limite_alerta_pct=limite_alerta_pct, top_n=top_n)


@router.get("/{client_id}/alertas-expandidos")
def alertas_expandidos(client_id: int, periodo_ini: int, periodo_fim: int):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return oportunidades_mod.alertas_expandidos(con, client_id, ini, fim)


# --- Etapa 4: estoque, mercado/IQVIA e preco -------------------------------
# Estoque e preco passam pelo cliente (dado dele). Mercado/IQVIA e base unica
# e compartilhada — as rotas de mercado ficam sob o cliente mesmo assim,
# porque o que muda por cliente e a PONTE com os produtos que ele distribui.


@router.get("/{client_id}/estoque/perfil")
def estoque_perfil(client_id: int):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return estoque_mod.perfil(con, client_id)


@router.get("/{client_id}/estoque")
def estoque_posicao(client_id: int, periodo_ini: int, periodo_fim: int,
                    base_velocidade: str = Query("fonte", pattern="^(fonte|periodo)$"),
                    filial: str | None = None, classe: str | None = None,
                    limite: int = Query(200, le=2000)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        try:
            return estoque_mod.posicao(con, client_id, ini, fim,
                                       base_velocidade=base_velocidade,
                                       filial=filial, classe=classe, limite=limite)
        except ValueError as e:
            raise errors.invalido(str(e))


@router.get("/{client_id}/estoque/resumo")
def estoque_resumo(client_id: int, periodo_ini: int, periodo_fim: int,
                   base_velocidade: str = Query("fonte", pattern="^(fonte|periodo)$"),
                   filial: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return estoque_mod.resumo(con, client_id, ini, fim,
                                  base_velocidade=base_velocidade, filial=filial)


@router.get("/{client_id}/estoque/zumbi")
def estoque_zumbi(client_id: int, periodo_ini: int, periodo_fim: int,
                  limite_dias: float = Query(365, gt=0),
                  base_velocidade: str = Query("fonte", pattern="^(fonte|periodo)$"),
                  filial: str | None = None, top_n: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return estoque_mod.zumbi(con, client_id, ini, fim, limite_dias=limite_dias,
                                 base_velocidade=base_velocidade, filial=filial,
                                 top_n=top_n)


@router.get("/{client_id}/estoque/capital-parado")
def estoque_capital(client_id: int, periodo_ini: int, periodo_fim: int,
                    base_velocidade: str = Query("fonte", pattern="^(fonte|periodo)$"),
                    filial: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return estoque_mod.capital_parado(con, client_id, ini, fim,
                                          base_velocidade=base_velocidade,
                                          filial=filial)


@router.get("/{client_id}/estoque/simulador")
def estoque_simulador(client_id: int, periodo_ini: int, periodo_fim: int,
                      objetivo_dias: float = Query(60, gt=0, le=3650),
                      base_velocidade: str = Query("fonte", pattern="^(fonte|periodo)$"),
                      filial: str | None = None, top_n: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return estoque_mod.simulador(con, client_id, ini, fim,
                                     objetivo_dias=objetivo_dias,
                                     base_velocidade=base_velocidade,
                                     filial=filial, top_n=top_n)


@router.get("/{client_id}/estoque/matriz")
def estoque_matriz(client_id: int, periodo_ini: int, periodo_fim: int,
                   base_velocidade: str = Query("fonte", pattern="^(fonte|periodo)$"),
                   filial: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return estoque_mod.matriz_estoque_vendas(con, client_id, ini, fim,
                                                 base_velocidade=base_velocidade,
                                                 filial=filial)


@router.get("/{client_id}/mercado/perfil")
def mercado_perfil(client_id: int):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mercado_mod.perfil(con)


@router.get("/{client_id}/mercado")
def mercado_resumo(client_id: int, uf: str | None = None, mercado: str | None = None,
                   molecula: str | None = None, canal: str | None = None):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mercado_mod.resumo(con, uf=uf, mercado=mercado,
                                  molecula=molecula, canal=canal)


@router.get("/{client_id}/mercado/share")
def mercado_share(client_id: int, uf: str | None = None, mercado: str | None = None,
                  molecula: str | None = None, canal: str | None = None,
                  base: str = Query("unidades", pattern="^(unidades|valor)$")):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mercado_mod.share_industria(con, uf=uf, mercado=mercado,
                                           molecula=molecula, canal=canal, base=base)


@router.get("/{client_id}/mercado/share-cliente")
def mercado_share_cliente(client_id: int):
    """Devolve indisponivel com o motivo — ver docstring de analytics.mercado."""
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mercado_mod.share_do_cliente(con, client_id)


@router.get("/{client_id}/mercado/ranking")
def mercado_ranking(client_id: int, uf: str | None = None, canal: str | None = None,
                    top_n: int = Query(30, le=200),
                    minimo_unidades: float = Query(0, ge=0)):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mercado_mod.ranking_mercados(con, uf=uf, canal=canal, top_n=top_n,
                                            minimo_unidades=minimo_unidades)


@router.get("/{client_id}/mercado/regional")
def mercado_regional(client_id: int, mercado: str | None = None,
                     molecula: str | None = None, canal: str | None = None,
                     top_n: int = Query(30, le=200)):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return mercado_mod.regional(con, mercado=mercado, molecula=molecula,
                                    canal=canal, top_n=top_n)


@router.get("/{client_id}/mercado/vs-cliente")
def mercado_vs_cliente(client_id: int, uf: str | None = None,
                       mercado: str | None = None, molecula: str | None = None):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        d = carregar_disponibilidade(con, client_id)
        return mercado_mod.cliente_vs_mercado(con, client_id, d.distribuidor_ids,
                                              uf=uf, mercado=mercado, molecula=molecula)


@router.get("/{client_id}/mercado/ponte")
def mercado_ponte(client_id: int, periodo_ini: int, periodo_fim: int,
                  uf: str | None = None, top_n: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        d = carregar_disponibilidade(con, client_id)
        return mercado_mod.ponte_produtos(con, d.distribuidor_ids, ini, fim,
                                          uf=uf, top_n=top_n)


@router.get("/{client_id}/preco/comparabilidade")
def preco_comparabilidade(client_id: int):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return preco_mod.comparabilidade(con)


@router.get("/{client_id}/preco")
def preco_vs_concorrentes(client_id: int, periodo_ini: int, periodo_fim: int,
                          uf: str | None = None,
                          minimo_unidades: float = Query(200, ge=0),
                          limite_alerta_pct: float = Query(8.0, gt=0),
                          top_n: int = Query(50, le=500)):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        d = carregar_disponibilidade(con, client_id)
        return preco_mod.preco_vs_concorrentes(
            con, d.distribuidor_ids, ini, fim, uf=uf,
            minimo_unidades=minimo_unidades,
            limite_alerta_pct=limite_alerta_pct, top_n=top_n)


@router.get("/{client_id}/preco/evolucao")
def preco_evolucao(client_id: int, periodo_ini: int, periodo_fim: int,
                   produto_id: int | None = None, uf: str | None = None):
    ini, fim = _periodo(periodo_ini, periodo_fim)
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        d = carregar_disponibilidade(con, client_id)
        return preco_mod.evolucao_preco(con, d.distribuidor_ids, ini, fim,
                                        produto_id=produto_id, uf=uf)


@router.get("/{client_id}/preco/varejo")
def preco_varejo(client_id: int, uf: str | None = None, mercado: str | None = None,
                 molecula: str | None = None, top_n: int = Query(30, le=200),
                 minimo_unidades: float = Query(200, ge=0)):
    with db.conexao() as con:
        _cliente_existe(con, client_id)
        return preco_mod.preco_varejo_iqvia(con, uf=uf, mercado=mercado,
                                            molecula=molecula, top_n=top_n,
                                            minimo_unidades=minimo_unidades)
