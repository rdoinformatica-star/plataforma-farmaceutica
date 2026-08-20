"""Deteccao do papel semantico de uma coluna.

Regra que atravessa tudo: os testes sao ESTRUTURAIS. Nada de nome de arquivo,
nome de cliente ou numero conhecido embutido — o mesmo codigo tem que funcionar
para um relatorio que ainda nao existe.

Score = 0.45 * nome + 0.55 * valores. Vence com >= 0.60; abaixo disso o papel e
DESCONHECIDO. Preferimos admitir que nao sabemos a chutar.

Todo papel devolve uma frase de evidencia, mostrada na interface — o usuario
precisa poder discordar da maquina com base em algo.
"""
import re
from difflib import SequenceMatcher

from ..core.texto import UFS, ean13, ean13_valido, normalizar, so_digitos

LIMIAR = 0.60
PESO_NOME = 0.45
PESO_VALOR = 0.55

SINONIMOS: dict[str, tuple[str, ...]] = {
    "PRODUTO": ("produto", "item", "sku", "descricao", "apresentacao", "mercadoria",
                "material", "medicamento", "artigo", "descricao produto", "nome produto"),
    "PDV": ("pdv", "cliente", "farmacia", "drogaria", "razao social", "loja",
            "ponto de venda", "estabelecimento", "razao"),
    "DISTRIBUIDOR": ("distribuidor", "fornecedor", "atacadista", "provedor",
                     "distribuidora", "prov nome"),
    "UF": ("uf", "estado", "sigla", "sigla uf", "unidade federativa"),
    "CIDADE": ("cidade", "municipio", "localidade"),
    "PERIODO": ("periodo", "mes", "competencia", "anomes", "ano mes", "referencia"),
    "DATA": ("data", "dt", "emissao", "data ref", "data referencia", "vencimento"),
    "VALOR": ("valor", "r$", "faturamento", "receita", "vlr", "total", "venda r$",
              "preco", "custo", "montante"),
    "UNIDADE": ("un", "und", "unid", "qtd", "quantidade", "caixas", "volume",
                "unidades", "qtde", "venda un"),
    "CODIGO_EAN": ("ean", "gtin", "codigo barras", "cod barras", "barras"),
    "CNPJ": ("cnpj", "cpf cnpj", "documento"),
    "CATEGORIA": ("categoria", "tipo", "canal", "classe", "grupo", "linha",
                  "segmento", "familia", "filial"),
    "MARCA": ("marca", "brand", "laboratorio", "lab", "fabricante", "industria"),
    "CODIGO": ("codigo", "cod", "id", "chave", "referencia"),
}

_DOSAGEM = re.compile(r"\d+\s?(MG|MCG|G|ML|UI|CPD|CAP|CPR|COM|GTS|%)\b")
_RAZAO = re.compile(r"\b(FARMA|DROGA|LTDA|EIRELI|S/?A|ME\b|EPP|COMERCIO|DISTRIB)")
_DECIMAL2 = re.compile(r"^-?\d+[.,]\d{2}$")


def _prox(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def score_nome(nome: str) -> dict[str, float]:
    """Similaridade do nome da coluna contra o dicionario de sinonimos.

    E o que resolve erro de digitacao na origem: 'Estoque Diponivel Un' tem 0,96
    de similaridade com o nome correto. Casamento exato nao pegaria.
    """
    n = normalizar(nome).lower()
    if not n:
        return {}
    out = {}
    for papel, termos in SINONIMOS.items():
        melhor = 0.0
        for t in termos:
            if n == t:
                melhor = 1.0
                break
            r = _prox(n, t)
            if t in n or n in t:
                r = max(r, 0.82)
            melhor = max(melhor, r)
        if melhor > 0.55:
            out[papel] = round(melhor, 3)
    return out


def _amostra_texto(valores: list) -> list[str]:
    return [str(v).strip() for v in valores if v is not None and str(v).strip() != ""]


def score_valores(valores: list, eh_numerico: bool,
                  n_distintos: int, n_linhas: int) -> dict[str, tuple[float, str]]:
    """Testes de forma sobre os valores. Cada um devolve (score, evidencia)."""
    amostra = _amostra_texto(valores)
    if not amostra:
        return {}
    n = len(amostra)
    out: dict[str, tuple[float, str]] = {}

    # --- EAN: 13 digitos com digito verificador valido ---
    codigos = [ean13(v) for v in amostra]
    treze = [c for c in codigos if c and len(c) == 13]
    if treze and len(treze) / n >= 0.9:
        validos = sum(1 for c in treze if ean13_valido(c))
        pct_dv = validos / len(treze)
        out["CODIGO_EAN"] = (
            0.55 + 0.45 * pct_dv,
            f"13 digitos em {len(treze)/n:.0%} dos valores e digito verificador "
            f"valido em {pct_dv:.1%}",
        )

    # --- CNPJ ---
    from ..core.texto import cnpj_valido
    catorze = [so_digitos(v) for v in amostra if len(so_digitos(v)) == 14]
    if catorze and len(catorze) / n >= 0.8:
        pct = sum(1 for c in catorze if cnpj_valido(c)) / len(catorze)
        out["CNPJ"] = (0.5 + 0.5 * pct, f"digito verificador de CNPJ valido em {pct:.0%}")

    # --- UF: conjunto fechado de 27 siglas ---
    if n_distintos <= 30:
        vals = {normalizar(v) for v in amostra}
        if vals and vals <= UFS:
            out["UF"] = (0.98, f"todos os {len(vals)} valores sao siglas de estado")

    # --- PERIODO: AAAAMM plausivel ---
    inteiros = [so_digitos(v) for v in amostra]
    aaaamm = [c for c in inteiros
              if len(c) == 6 and 2000 <= int(c[:4]) <= 2099 and 1 <= int(c[4:]) <= 12]
    if aaaamm and len(aaaamm) / n >= 0.95:
        ordenados = sorted(set(aaaamm))
        out["PERIODO"] = (0.95,
                          f"{ordenados[0]}-{ordenados[-1]}, {len(ordenados)} periodos")

    # --- DATA ---
    datas = sum(1 for v in amostra
                if re.match(r"^\d{2,4}[-/]\d{1,2}[-/]\d{1,4}", str(v)))
    if datas / n >= 0.9:
        out["DATA"] = (0.85, f"{datas/n:.0%} dos valores tem formato de data")

    if eh_numerico:
        numeros = []
        for v in amostra:
            try:
                numeros.append(float(str(v).replace(",", ".")))
            except (TypeError, ValueError):
                pass
        if numeros:
            com2 = sum(1 for x in numeros if abs(round(x, 2) - x) < 1e-9)
            inteiro = sum(1 for x in numeros if float(x).is_integer())
            nao_neg = sum(1 for x in numeros if x >= 0)
            fracionario = len(numeros) - inteiro
            if com2 / len(numeros) >= 0.9 and fracionario:
                out["VALOR"] = (0.6 + 0.35 * (com2 / len(numeros)),
                                f"{com2/len(numeros):.0%} dos valores tem exatamente "
                                f"2 casas decimais")
            elif fracionario / len(numeros) >= 0.5:
                # Dinheiro em export de sistema costuma vir com precisao cheia
                # (1.279045), entao "2 casas" sozinho nao serve de teste.
                out["VALOR"] = (0.45,
                                f"{fracionario/len(numeros):.0%} dos valores tem "
                                f"parte decimal")
            if inteiro / len(numeros) >= 0.95 and nao_neg / len(numeros) >= 0.95:
                out.setdefault("UNIDADE",
                               (0.66, f"{inteiro/len(numeros):.0%} sao inteiros "
                                      f"nao negativos"))
    else:
        maiusc = [normalizar(v) for v in amostra]
        dos = sum(1 for v in maiusc if _DOSAGEM.search(v))
        if dos / n > 0.5:
            out["PRODUTO"] = (0.6 + 0.35 * (dos / n),
                              f"{dos/n:.0%} dos valores contem dosagem farmaceutica "
                              f"(mg, ml, ui...)")
        raz = sum(1 for v in maiusc if _RAZAO.search(v))
        if raz / n > 0.3:
            out["PDV"] = (0.55 + 0.4 * (raz / n),
                          f"{raz/n:.0%} dos valores parecem razao social "
                          f"(farmacia, drogaria, ltda...)")
        if n_linhas and n_distintos <= 50 and n_linhas / max(n_distintos, 1) >= 20:
            out.setdefault("CATEGORIA",
                           (0.62, f"{n_distintos} valores distintos em "
                                  f"{n_linhas} linhas"))

    # --- CHAVE: unico e sem falha ---
    if n_linhas and n_distintos == n_linhas and len(amostra) == n_linhas:
        out["CHAVE"] = (0.7, f"valor unico e preenchido nas {n_linhas} linhas")

    return out


def detectar(nome: str, valores: list, *, eh_numerico: bool,
             n_distintos: int, n_linhas: int) -> dict:
    """Combina nome e valores. Devolve papel, confianca, evidencia e alternativas."""
    sn = score_nome(nome)
    sv = score_valores(valores, eh_numerico, n_distintos, n_linhas)

    papeis = set(sn) | set(sv)
    ranking = []
    for p in papeis:
        n_s = sn.get(p, 0.0)
        v_s, evid = sv.get(p, (0.0, ""))
        total = PESO_NOME * n_s + PESO_VALOR * v_s
        if n_s >= 0.99:
            # Nome da coluna e IGUAL a um sinonimo (ex.: coluna chamada exatamente
            # "Distribuidor" ou "Periodo"), nao uma aproximacao fuzzy. Para papeis
            # sem teste de forma proprio (DISTRIBUIDOR, MARCA, CIDADE) o nome exato
            # e a unica evidencia possivel, e sozinho ja e forte o suficiente.
            total = max(total, 0.62)
        partes = []
        if n_s:
            partes.append(f"o nome da coluna combina com '{p.lower()}' ({n_s:.0%})")
        if evid:
            partes.append(evid)
        ranking.append((round(total, 3), p, "; ".join(partes) or "sem evidencia forte"))

    ranking.sort(reverse=True)
    if not ranking or ranking[0][0] < LIMIAR:
        alt = [{"valor": p, "confianca": s} for s, p, _ in ranking[:3]]
        return {
            "valor": "DESCONHECIDO",
            "confianca": round(ranking[0][0], 3) if ranking else 0.0,
            "evidencia": "Nenhum papel atingiu confianca suficiente. "
                         "Este campo precisa da sua decisao.",
            "alternativas": alt,
        }

    melhor = ranking[0]
    return {
        "valor": melhor[1],
        "confianca": melhor[0],
        "evidencia": melhor[2],
        "alternativas": [{"valor": p, "confianca": s} for s, p, _ in ranking[1:4]],
    }
