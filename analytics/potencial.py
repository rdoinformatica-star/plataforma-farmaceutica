"""Potencial de crescimento por produto e por PDV.

Duas perguntas diferentes, com bases de comparacao diferentes — e por isso
duas funcoes, nunca um numero so:

  produtos -> compara com o MERCADO (IQVIA). "Este SKU esta sub-penetrado
              em relacao ao proprio mercado dele?"
  pdvs     -> compara com PDVs SEMELHANTES da propria carteira. O IQVIA nao
              tem grao de PDV: nao existe "mercado deste PDV" no dado. Fingir
              que existe seria inventar numero.

Os dois usam a mesma logica de FAIR SHARE (indice): mede-se o desempenho
atual contra uma referencia observada na propria base, e o potencial e a
diferenca ate essa referencia. Nunca contra o mercado inteiro — "vender 100%
do mercado" nao e potencial, e fantasia, e foi exatamente o erro que o dossie
da EMEFARMA sinaliza ao dizer que potenciais sobrepostos nao se somam.

Toda saida traz o indice junto do valor: 100 = no ritmo da referencia,
abaixo de 100 = sub-penetrado (e ai ha potencial), acima = ja acima da media.
"""
import sqlite3
import statistics

from .contexto import carregar
from .formulas import Calculo
from .mercado import ponte_produtos
from .mix import FAIXAS_PADRAO, _mix_bruto


def _sem(motivo: str) -> dict:
    return {"disponivel": False, "motivo": motivo}


def _mediana(vals: list[float]) -> float:
    return statistics.median(vals) if vals else 0.0


def potencial_produtos(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                       *, uf: str | None = None, top_n: int = 50,
                       min_unidades_mercado: float = 100.0) -> dict:
    """Potencial de cada SKU contra o mercado IQVIA da molecula/apresentacao.

    referencia = share medio PONDERADO da carteira (soma das unidades do
    cliente / soma das unidades de mercado dos SKUs ligados). Ponderado, e nao
    media dos shares, porque a media simples daria o mesmo peso a um SKU de
    100 unidades e a um de 100 mil.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return _sem(disp.motivo_indisponivel)
    if uf is not None and not disp.tem_uf:
        return _sem("Este cliente nao tem UF de PDV resolvida nos dados importados.")

    ponte = ponte_produtos(con, disp.distribuidor_ids, ini, fim, uf=uf, top_n=100000)
    if not ponte.get("disponivel"):
        return ponte

    # SKU com mercado minusculo produz share instavel (1 unidade a mais vira
    # dezenas de pontos). Fica de fora do calculo da referencia E do ranking,
    # mas e contado para o usuario saber quantos ficaram fora.
    validos = [i for i in ponte["itens"]
               if i["mercado_un"] >= min_unidades_mercado and i["unidades_cliente"] > 0]
    descartados = len(ponte["itens"]) - len(validos)

    # SO ligacao por apresentacao vira potencial em R$. A ligacao por molecula
    # compara UM SKU com o mercado da molecula INTEIRA (todas as dosagens,
    # formas e laboratorios) — na base real isso da 35 milhoes de unidades de
    # mercado contra 1,2 mil do cliente, e o "potencial" resultante seria maior
    # que a carteira toda. Esses casos saem em contexto_molecula, sem valor
    # somado, porque o numero seria falso e nao apenas impreciso.
    elegiveis = [i for i in validos if i["nivel_ligacao"] == "apresentacao"]
    amplos = [i for i in validos if i["nivel_ligacao"] != "apresentacao"]
    if not elegiveis:
        return _sem(
            f"Nenhum SKU ligado ao mercado por apresentacao exata com pelo menos "
            f"{min_unidades_mercado:.0f} unidades de mercado no periodo. "
            f"{len(amplos)} SKU(s) so casaram por molecula, o que e amplo demais "
            f"para virar meta de potencial.")

    soma_cliente = sum(i["unidades_cliente"] for i in elegiveis)
    soma_mercado = sum(i["mercado_un"] for i in elegiveis)
    share_ref = (soma_cliente / soma_mercado) if soma_mercado else 0.0

    contexto_molecula = sorted(
        [{"produto_id": i["produto_id"], "produto": i["produto"],
          "mercado": i["mercado"], "referencia_mercado": i["referencia_mercado"],
          "faturamento_atual": i["faturamento_cliente"],
          "unidades_atual": i["unidades_cliente"],
          "mercado_molecula_un": i["mercado_un"],
          "penetracao_na_molecula_pct": i["unidades_cliente"] / i["mercado_un"] * 100}
         for i in amplos],
        key=lambda x: x["faturamento_atual"], reverse=True)[:top_n]

    itens = []
    for i in elegiveis:
        share_atual = i["unidades_cliente"] / i["mercado_un"]
        alvo_un = i["mercado_un"] * share_ref
        pot_un = max(0.0, alvo_un - i["unidades_cliente"])
        preco = (i["faturamento_cliente"] / i["unidades_cliente"]
                 if i["unidades_cliente"] else 0.0)
        itens.append({
            "produto_id": i["produto_id"],
            "produto": i["produto"],
            "mercado": i["mercado"],
            "nivel_ligacao": i["nivel_ligacao"],
            "faturamento_atual": i["faturamento_cliente"],
            "unidades_atual": i["unidades_cliente"],
            "mercado_un": i["mercado_un"],
            "penetracao_pct": share_atual * 100,
            "penetracao_referencia_pct": share_ref * 100,
            "indice": (share_atual / share_ref * 100) if share_ref else None,
            "unidades_alvo": alvo_un,
            "potencial_un": pot_un,
            "preco_medio": preco,
            "potencial_valor": pot_un * preco,
            "share_industria_pct": i["share_industria_pct"],
        })
    itens.sort(key=lambda x: x["potencial_valor"], reverse=True)
    total_pot = sum(x["potencial_valor"] for x in itens)

    return {
        "disponivel": True,
        "uf": uf,
        "penetracao_referencia_pct": share_ref * 100,
        "n_skus": len(itens),
        "n_skus_fora": descartados,
        "n_so_molecula": len(amplos),
        "contexto_molecula": contexto_molecula,
        "n_sem_correspondencia": ponte["n_sem_correspondencia"],
        "cobertura_da_ponte_pct": ponte["cobertura_da_ponte_pct"],
        "potencial_total": total_pot,
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula=("penetracao = unidades do cliente / unidades do mercado (IQVIA), "
                     "so onde a apresentacao casa exatamente; "
                     "referencia = penetracao media ponderada da carteira; "
                     "potencial (un) = mercado x referencia - unidades atuais; "
                     "potencial (R$) = potencial (un) x preco medio do proprio SKU"),
            valores={
                "penetracao de referencia": f"{share_ref * 100:.2f}%",
                "SKUs medidos": len(itens),
                "SKUs fora (mercado pequeno demais)": descartados,
                "SKUs so com match de molecula (sem potencial)": len(amplos),
                "SKUs sem correspondencia no IQVIA": ponte["n_sem_correspondencia"],
                "cobertura da ponte": (f"{ponte['cobertura_da_ponte_pct']:.1f}%"
                                       if ponte["cobertura_da_ponte_pct"] is not None
                                       else "n/d"),
                "potencial total": round(total_pot, 2),
            },
            premissas=[
                "A referencia e a MEDIA DA PROPRIA CARTEIRA, nao o mercado "
                "inteiro: o potencial responde 'se este SKU vendesse no ritmo "
                "dos seus outros SKUs', nao 'se voce dominasse o mercado'.",
                "So entram SKUs cuja APRESENTACAO casa exatamente com o IQVIA. "
                "Quando o casamento e so por molecula, o mercado comparado inclui "
                "outras dosagens, formas e laboratorios — comparar um SKU com "
                "isso produziria um potencial maior que a carteira inteira. "
                "Esses casos aparecem em 'contexto_molecula', sem valor somado.",
                "OS POTENCIAIS NAO SE SOMAM sem cuidado: dois SKUs da mesma "
                "molecula competem entre si, e o total assume que todos chegam "
                "a referencia ao mesmo tempo — o que nao acontece na pratica.",
                "Preco medio e o do proprio cliente naquele SKU no periodo; se "
                "ele vender mais unidades a preco menor, o valor cai.",
                f"SKUs com menos de {min_unidades_mercado:.0f} unidades de "
                f"mercado ficam fora: com base pequena o share oscila demais "
                f"para virar meta.",
                "A ponte com o IQVIA e parcial (nomes divergem entre as fontes). "
                "A cobertura da ponte diz o quanto da carteira esta representado.",
            ] + ([f"Recorte: so o mercado do estado {uf}."] if uf else []),
        ).como_dict(),
    }


def potencial_pdvs(con: sqlite3.Connection, client_id: int, ini: int, fim: int,
                   *, uf: str | None = None, top_n: int = 50,
                   faixas: list[tuple[int, int, str]] | None = None) -> dict:
    """Potencial de cada PDV contra PDVs semelhantes da propria carteira.

    O IQVIA nao tem PDV — entao a referencia aqui e INTERNA: PDVs sao agrupados
    por tamanho de mix (1 / 2-3 / 4-9 / 10+ SKUs) e cada um e comparado com a
    faixa IMEDIATAMENTE ACIMA da sua. O alvo e o mix mediano dessa faixa, ao
    R$/SKU mediano dela.

    Um PDV que ja esta na faixa mais alta nao recebe potencial: nao ha
    referencia observada acima dele, e extrapolar seria inventar teto.
    """
    disp = carregar(con, client_id)
    if not disp.tem_sellout:
        return _sem(disp.motivo_indisponivel)
    if uf is not None and not disp.tem_uf:
        return _sem("Este cliente nao tem UF de PDV resolvida nos dados importados.")

    fx = faixas or FAIXAS_PADRAO
    pdvs = _mix_bruto(con, disp.distribuidor_ids, ini, fim, uf=uf)
    if not pdvs:
        return _sem("Nenhum PDV comprador neste periodo.")

    def faixa_de(n: int) -> int:
        for idx, (lo, hi, _) in enumerate(fx):
            if lo <= n <= hi:
                return idx
        return len(fx) - 1

    # Perfil observado de cada faixa: mix mediano e R$/SKU mediano.
    perfil: list[dict] = []
    for idx, (lo, hi, rotulo) in enumerate(fx):
        grupo = [p for p in pdvs if lo <= p["n_skus"] <= hi]
        perfil.append({
            "faixa": rotulo, "indice": idx, "n_pdvs": len(grupo),
            "mix_mediano": _mediana([float(p["n_skus"]) for p in grupo]),
            "rs_por_sku_mediano": _mediana(
                [p["faturamento"] / p["n_skus"] for p in grupo if p["n_skus"]]),
            "rs_por_pdv_mediano": _mediana([float(p["faturamento"]) for p in grupo]),
        })

    ids = [p["pdv_id"] for p in pdvs]
    nomes, ufs = {}, {}
    for lote_ini in range(0, len(ids), 900):  # limite de variaveis do SQLite
        lote = ids[lote_ini:lote_ini + 900]
        for pid, razao, u in con.execute(
            f"SELECT id, razao_social, uf FROM dim_pdv WHERE id IN "
            f"({','.join('?' * len(lote))})", lote):
            nomes[pid] = razao
            ufs[pid] = u

    itens = []
    sem_referencia = 0
    for p in pdvs:
        atual_idx = faixa_de(p["n_skus"])
        alvo_idx = atual_idx + 1
        if alvo_idx >= len(fx) or perfil[alvo_idx]["n_pdvs"] == 0:
            sem_referencia += 1
            continue
        alvo = perfil[alvo_idx]
        mix_alvo = alvo["mix_mediano"]
        if mix_alvo <= p["n_skus"]:
            continue
        skus_a_ganhar = mix_alvo - p["n_skus"]
        pot = skus_a_ganhar * alvo["rs_por_sku_mediano"]
        if pot <= 0:
            continue
        itens.append({
            "pdv_id": p["pdv_id"],
            "pdv": nomes.get(p["pdv_id"], f"PDV #{p['pdv_id']}"),
            "uf": ufs.get(p["pdv_id"]),
            "faturamento_atual": p["faturamento"],
            "n_skus": p["n_skus"],
            "faixa_atual": fx[atual_idx][2],
            "faixa_alvo": alvo["faixa"],
            "mix_alvo": mix_alvo,
            "skus_a_ganhar": skus_a_ganhar,
            "rs_por_sku_referencia": alvo["rs_por_sku_mediano"],
            "potencial_valor": pot,
            "indice": (p["faturamento"] / alvo["rs_por_pdv_mediano"] * 100
                       if alvo["rs_por_pdv_mediano"] else None),
        })
    itens.sort(key=lambda x: x["potencial_valor"], reverse=True)
    total_pot = sum(x["potencial_valor"] for x in itens)

    return {
        "disponivel": True,
        "uf": uf,
        "n_pdvs_avaliados": len(pdvs),
        "n_pdvs_com_potencial": len(itens),
        "n_pdvs_sem_referencia": sem_referencia,
        "potencial_total": total_pot,
        "perfil_faixas": perfil,
        "itens": itens[:top_n],
        "calculo": Calculo(
            formula=("alvo = mix mediano da faixa imediatamente acima; "
                     "potencial (R$) = (mix alvo - mix atual) x R$/SKU mediano "
                     "dessa faixa"),
            valores={
                "PDVs avaliados": len(pdvs),
                "PDVs com potencial": len(itens),
                "PDVs ja no topo (sem referencia acima)": sem_referencia,
                "potencial total": round(total_pot, 2),
            },
            premissas=[
                "O IQVIA NAO TEM GRAO DE PDV. Esta referencia e interna: PDVs "
                "semelhantes da propria carteira, nao o mercado da praca. Nao e "
                "'quanto este PDV compra de medicamento no total'.",
                "A comparacao e com a faixa IMEDIATAMENTE ACIMA, um degrau de "
                "cada vez — nao com o melhor PDV da base, que seria uma meta "
                "sem lastro para a maioria.",
                "Mediana, nao media: um PDV gigante na faixa nao puxa o alvo de "
                "todo mundo para cima.",
                "PDV que ja esta na faixa mais alta fica sem potencial: nao ha "
                "referencia observada acima dele. Aparece na contagem, nao na lista.",
                "OS POTENCIAIS NAO SE SOMAM como meta: assumem que cada PDV sobe "
                "um degrau, e o R$/SKU tipico continua valendo depois da subida.",
                "Premissa central: PDVs na mesma faixa de mix sao comparaveis. "
                "Porte da loja, regiao e sortimento do proprio PDV nao estao na "
                "base e podem explicar parte da diferenca.",
            ] + ([f"Recorte: so PDVs do estado {uf}."] if uf else []),
        ).como_dict(),
    }
