"""Aritmetica de periodo no formato AAAAMM (inteiro), o mesmo formato de
fact_sales.periodo e agg_vendas_mensal.periodo.

Toda a Etapa 2 trabalha só com [periodo_ini, periodo_fim] inclusive — o
frontend resolve presets (mes/trimestre/semestre/ano) para esse par antes de
chamar a API. O backend nunca precisa saber o que é "trimestre".
"""
from dataclasses import dataclass


def validar(p: int) -> int:
    if not (200001 <= p <= 209912) or not (1 <= p % 100 <= 12):
        raise ValueError(f"'{p}' nao e um periodo AAAAMM valido.")
    return p


def contar_meses(ini: int, fim: int) -> int:
    """Quantidade de meses no intervalo [ini, fim], inclusive."""
    validar(ini)
    validar(fim)
    if fim < ini:
        raise ValueError(f"periodo_fim ({fim}) e anterior a periodo_ini ({ini}).")
    ai, mi = divmod(ini, 100)
    af, mf = divmod(fim, 100)
    return (af - ai) * 12 + (mf - mi) + 1


def periodo_mais_meses(p: int, meses: int) -> int:
    """202601 + (-1) -> 202512. Aceita meses negativo (voltar no tempo)."""
    validar(p)
    ano, mes = divmod(p, 100)
    total = ano * 12 + (mes - 1) + meses
    ano2, mes2 = divmod(total, 12)
    return ano2 * 100 + (mes2 + 1)


def periodo_label(p: int) -> str:
    """202607 -> '07/2026'."""
    ano, mes = divmod(validar(p), 100)
    return f"{mes:02d}/{ano}"


@dataclass(frozen=True)
class Janela:
    ini: int
    fim: int

    @property
    def n_meses(self) -> int:
        return contar_meses(self.ini, self.fim)

    @property
    def rotulo(self) -> str:
        if self.ini == self.fim:
            return periodo_label(self.ini)
        return f"{periodo_label(self.ini)} a {periodo_label(self.fim)}"


def janela_anterior(ini: int, fim: int) -> Janela:
    """Mesma quantidade de meses, imediatamente antes — para comparacao MoM
    ou de periodo customizado. Ex.: 202601-202607 (7 meses) -> 202506-202512.
    """
    n = contar_meses(ini, fim)
    return Janela(periodo_mais_meses(ini, -n), periodo_mais_meses(fim, -n))


def janela_ano_anterior(ini: int, fim: int) -> Janela:
    """Mesmos meses, um ano antes — para YoY. Reproduz o que engine/analise.py
    faz manualmente com ANO_A/ANO_B: 202601-202607 -> 202501-202507.
    """
    validar(ini)
    validar(fim)
    return Janela(periodo_mais_meses(ini, -12), periodo_mais_meses(fim, -12))
