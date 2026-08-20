"""PERFIL DO DADO.

A entrada e uma LISTA DE COLUNAS, nao um DataFrame — assim o mesmo perfilador
serve para pandas e para os arrays numpy do VMD1, que sao milhoes de linhas ja
codificadas como indice inteiro.

Contagens (nulos, distintos, min, max, soma) sao EXATAS sobre a coluna inteira.
Distribuicoes caras usam amostra, e o JSON declara qual base foi usada em cada
caso. Declarar o metodo faz parte de nao inventar numero.

Nada e corrigido em silencio: inconsistencias sao reportadas para o usuario
decidir.
"""
import itertools
import math
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..core.texto import ean13, ean13_valido, normalizar
from . import semantica

AMOSTRA_MAX = 100_000
_ESPACO_SOBRANDO = re.compile(r"^\s|\s$|\s{2,}")


@dataclass
class Coluna:
    """Uma coluna a perfilar.

    valores: array/serie com os dados, ou os INDICES quando `rotulos` vem junto
             (o VMD1 entrega tudo codificado, o que torna o perfil quase gratuito).
    """
    nome: str
    valores: Any
    rotulos: list[str] | None = None
    meta: dict = field(default_factory=dict)


def _classificar_tipo(arr, eh_num: bool, n_preenchidos: int) -> str:
    if n_preenchidos == 0:
        return "VAZIO"
    if not eh_num:
        return "TEXTO"
    finitos = arr[np.isfinite(arr)]
    if len(finitos) and np.all(finitos == np.floor(finitos)):
        return "INTEIRO"
    return "DECIMAL"


def _valores_texto(col: Coluna) -> tuple[np.ndarray, np.ndarray]:
    """Devolve (codigos, rotulos) — sempre em forma codificada.

    Para o VMD1 os codigos ja vem prontos. Para pandas, fatoramos uma vez.
    Trabalhar com inteiros faz bincount resolver contagem exata em milhoes de
    linhas em milissegundos.
    """
    if col.rotulos is not None:
        return np.asarray(col.valores), np.asarray(col.rotulos, dtype=object)
    import pandas as pd
    s = pd.Series(col.valores)
    codigos, rotulos = pd.factorize(s, use_na_sentinel=True)
    return np.asarray(codigos), np.asarray(rotulos, dtype=object)


def _amostrar(v, n: int, limite: int = AMOSTRA_MAX):
    if n <= limite:
        return v, "completa"
    passo = max(1, n // limite)
    return v[::passo][:limite], f"amostra({limite})"


def _histograma(numeros: np.ndarray, bins: int = 20) -> list[dict]:
    finitos = numeros[np.isfinite(numeros)]
    if len(finitos) < 2:
        return []
    lo, hi = float(finitos.min()), float(finitos.max())
    if lo == hi:
        return [{"de": lo, "ate": hi, "n": int(len(finitos))}]
    contagem, bordas = np.histogram(finitos, bins=bins)
    return [{"de": float(bordas[i]), "ate": float(bordas[i + 1]), "n": int(contagem[i])}
            for i in range(len(contagem))]


def _padrao(texto: str) -> str:
    return "".join("9" if c.isdigit() else "A" if c.isalpha() else c for c in texto)


def _perfilar_numerica(arr: np.ndarray) -> tuple[dict, list[dict]]:
    problemas = []
    finitos = arr[np.isfinite(arr)]
    if not len(finitos):
        return {}, problemas

    q1, med, q3 = (float(x) for x in np.percentile(finitos, [25, 50, 75]))
    iqr = q3 - q1
    fora = int(np.sum((finitos < q1 - 1.5 * iqr) | (finitos > q3 + 1.5 * iqr))) if iqr else 0
    negativos = int(np.sum(finitos < 0))

    if fora:
        problemas.append({"tipo": "OUTLIER", "n": fora,
                          "detalhe": f"{fora} valores fora de 1,5x o intervalo "
                                     f"interquartil"})
    info = {
        "min": float(finitos.min()), "max": float(finitos.max()),
        "soma": float(finitos.sum()), "media": float(finitos.mean()),
        "mediana": med, "p25": q1, "p75": q3,
        "desvio": float(finitos.std()),
        "n_zeros": int(np.sum(finitos == 0)),
        "n_negativos": negativos,
        "tem_decimal": bool(np.any(finitos != np.floor(finitos))),
        "n_outliers": fora,
        "histograma": _histograma(finitos),
    }
    return info, problemas


def _perfilar_texto(rotulos: np.ndarray, n_total: int) -> tuple[dict, list[dict]]:
    problemas = []
    textos = [str(r) for r in rotulos if r is not None and str(r) != "nan"]
    if not textos:
        return {}, problemas

    tam = [len(t) for t in textos]
    espacos = sum(1 for t in textos if _ESPACO_SOBRANDO.search(t))
    if espacos:
        problemas.append({"tipo": "ESPACOS_SOBRANDO", "n": espacos,
                          "detalhe": f"{espacos} valores comecam, terminam ou tem "
                                     f"espacos duplicados"})

    caixas: dict[str, set] = {}
    for t in textos:
        caixas.setdefault(normalizar(t), set()).add(t)
    variantes = sum(1 for v in caixas.values() if len(v) > 1)
    if variantes:
        problemas.append({"tipo": "VARIANTES_DE_CAIXA", "n": variantes,
                          "detalhe": f"{variantes} valores aparecem escritos de mais "
                                     f"de um jeito (maiuscula/acento)"})

    padroes: dict[str, int] = {}
    for t in textos[:5000]:
        padroes[_padrao(t)] = padroes.get(_padrao(t), 0) + 1
    dom, dom_n = max(padroes.items(), key=lambda kv: kv[1]) if padroes else ("", 0)
    base_pad = min(len(textos), 5000)

    so_digitos = sum(1 for t in textos if t.isdigit())
    if so_digitos and so_digitos / len(textos) > 0.95:
        problemas.append({"tipo": "NUMERO_COMO_TEXTO", "n": so_digitos,
                          "detalhe": "a coluna guarda numeros como texto"})

    return {
        "tam_min": min(tam), "tam_max": max(tam),
        "tam_medio": round(sum(tam) / len(tam), 1),
        "pct_so_digitos": round(100 * so_digitos / len(textos), 1),
        "padrao_dominante": dom,
        "padrao_pct": round(100 * dom_n / base_pad, 1) if base_pad else 0,
    }, problemas


def perfilar_coluna(col: Coluna, n_linhas: int, ordem: int) -> dict:
    codigos, rotulos = _valores_texto(col)
    n = len(codigos)

    eh_num = col.rotulos is None and np.issubdtype(
        np.asarray(col.valores).dtype, np.number)

    if eh_num:
        arr = np.asarray(col.valores, dtype=np.float64)
        nulos = int(np.sum(~np.isfinite(arr)))
        distintos = int(len(np.unique(arr[np.isfinite(arr)])))
        info_num, prob_num = _perfilar_numerica(arr)
        info_txt, prob_txt = {}, []
        finitos = arr[np.isfinite(arr)]
        amostra_num = finitos[:2000]
        # Inteiro sem ".0": str(202501.0) tem um digito a mais que corrompe o
        # teste de periodo/codigo em semantica.py (so_digitos pega o "0" do ".0").
        amostra_valores = (
            [int(x) for x in amostra_num]
            if len(amostra_num) and bool(np.all(amostra_num == np.floor(amostra_num)))
            else [float(x) for x in amostra_num]
        )
        top = []
    else:
        nulos = int(np.sum(codigos < 0))
        distintos = int(len(rotulos))
        contagem = np.bincount(codigos[codigos >= 0], minlength=len(rotulos)) \
            if len(rotulos) else np.array([])
        ordem_top = np.argsort(contagem)[::-1][:10] if len(contagem) else []
        top = [{"v": str(rotulos[i]), "n": int(contagem[i]),
                "pct": round(100 * contagem[i] / max(n, 1), 2)} for i in ordem_top]
        info_num, prob_num = {}, []
        info_txt, prob_txt = _perfilar_texto(rotulos, n)
        amostra_valores = [str(rotulos[i]) for i in ordem_top[:20]]
        if len(rotulos) > 20:
            amostra_valores += [str(r) for r in rotulos[:30]]

    problemas = prob_num + prob_txt

    if not eh_num:
        codigos_ean = [ean13(v) for v in amostra_valores[:500]]
        treze = [c for c in codigos_ean if c and len(c) == 13]
        if treze and len(treze) >= 0.9 * len(amostra_valores[:500]):
            ruins = sum(1 for c in treze if not ean13_valido(c))
            if ruins:
                problemas.append({"tipo": "CODIGO_INVALIDO", "n": ruins,
                                  "detalhe": f"{ruins} codigos com digito "
                                             f"verificador incorreto"})

    papel = semantica.detectar(
        col.nome, amostra_valores[:1000], eh_numerico=eh_num,
        n_distintos=distintos, n_linhas=n)

    # Dispersao estatistica nao diz nada sobre um identificador: um EAN "fora da
    # media" e so um produto de outra faixa de codigo, nao um dado suspeito, e a
    # SOMA ou MEDIA de codigos de barras e um numero sem nenhum significado.
    if papel["valor"] in ("CODIGO_EAN", "CNPJ", "PERIODO", "CODIGO", "CHAVE"):
        problemas = [p for p in problemas if p["tipo"] != "OUTLIER"]
        if papel["valor"] == "PERIODO":
            # min/max ainda fazem sentido aqui (primeiro/ultimo periodo); o
            # resto (soma, media, desvio...) nao.
            info_num = {k: v for k, v in info_num.items() if k in ("min", "max")}
        else:
            info_num = {}

    return {
        "ordem": ordem,
        "nome": col.nome,
        "nome_norm": normalizar(col.nome),
        "tipo_bruto": str(np.asarray(col.valores).dtype) if col.rotulos is None else "categoria",
        "tipo_inferido": _classificar_tipo(
            np.asarray(col.valores, dtype=np.float64) if eh_num else np.array([]),
            eh_num, n - nulos),
        "n_nulos": nulos,
        "pct_nulos": round(100 * nulos / max(n, 1), 2),
        "n_distintos": distintos,
        "cardinalidade": round(distintos / max(n, 1), 4),
        "papel": papel,
        "numerico": info_num,
        "texto": info_txt,
        "top": top,
        "exemplos": [str(v) for v in amostra_valores[:8]],
        "problemas": problemas,
        **col.meta,
    }


def _chaves_candidatas(colunas: list[Coluna], perfis: list[dict],
                       n_linhas: int) -> list[dict]:
    """Simples primeiro; compostas so se nao houver simples."""
    simples = [{"colunas": [p["nome"]], "unica": True, "n_duplicatas": 0,
                "base": "completa"}
               for p in perfis
               if p["n_distintos"] == n_linhas and p["n_nulos"] == 0 and n_linhas > 0]
    if simples:
        return simples[:5]

    candidatas = sorted(
        [(p["n_distintos"], i) for i, p in enumerate(perfis) if p["n_nulos"] == 0],
        reverse=True)[:8]
    if len(candidatas) < 2:
        return []

    matrizes = {}
    for _, i in candidatas:
        cod, _r = _valores_texto(colunas[i])
        matrizes[i] = np.asarray(cod)

    achadas = []
    for tam in (2, 3):
        for combo in itertools.combinations([i for _, i in candidatas], tam):
            empilhado = np.column_stack([matrizes[i] for i in combo])
            unicos = len(np.unique(empilhado, axis=0))
            if unicos == n_linhas:
                achadas.append({
                    "colunas": [perfis[i]["nome"] for i in combo],
                    "unica": True, "n_duplicatas": 0, "base": "completa"})
                if len(achadas) >= 3:
                    return achadas
        if achadas:
            break
    return achadas


def _duplicatas(colunas: list[Coluna], n_linhas: int) -> dict:
    if not colunas or n_linhas == 0:
        return {"linhas_integrais": 0, "exemplos": []}
    amostra, base = _amostrar(np.arange(n_linhas), n_linhas, 50_000)
    matriz = np.column_stack([_valores_texto(c)[0][amostra] for c in colunas])
    unicos = len(np.unique(matriz, axis=0))
    dup = len(amostra) - unicos
    return {"linhas_integrais": int(dup), "base": base, "exemplos": []}


def perfilar(colunas: list[Coluna], *, n_linhas: int, fonte: str,
             descartadas: int = 0, motivo_descarte: str | None = None,
             amostras_descartadas: list | None = None,
             limitacoes: list[str] | None = None,
             avisos: list[str] | None = None,
             entidades: dict | None = None,
             periodo: dict | None = None,
             bytes_arquivo: int = 0,
             buscar_chaves: bool = True) -> dict:
    import time
    t0 = time.perf_counter()

    perfis = [perfilar_coluna(c, n_linhas, i) for i, c in enumerate(colunas)]
    avisos = list(avisos or [])

    # Erro de digitacao na origem: duas colunas quase iguais no mesmo arquivo.
    # Series numeradas (MES, MES1, MES2) sao intencionais e nao viram aviso.
    nomes = [p["nome"] for p in perfis]
    raiz = lambda s: re.sub(r"\d+$", "", normalizar(s).lower()).strip()  # noqa: E731
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            if raiz(a) == raiz(b):
                continue
            r = semantica._prox(normalizar(a).lower(), normalizar(b).lower())
            if 0.88 <= r < 1.0:
                avisos.append(
                    f"As colunas '{a}' e '{b}' tem nomes muito parecidos "
                    f"({r:.0%}) — pode ser erro de digitacao na origem.")

    chaves = _chaves_candidatas(colunas, perfis, n_linhas) if buscar_chaves else []

    return {
        "versao": "1",
        "dataset": {
            "fonte": fonte,
            "linhas_lidas": n_linhas + descartadas,
            "linhas_validas": n_linhas,
            "linhas_descartadas": descartadas,
            "motivo_descarte": motivo_descarte,
            "amostras_descartadas": amostras_descartadas or [],
            "colunas": len(colunas),
            "bytes": bytes_arquivo,
            "duracao_ms": int((time.perf_counter() - t0) * 1000),
            "base_estatistica": "completa" if n_linhas <= AMOSTRA_MAX
                                else f"exata para contagens, amostra({AMOSTRA_MAX}) "
                                     f"para distribuicoes",
            "periodo": periodo or {"min": None, "max": None, "granularidade": None},
            "entidades": entidades or {},
            "avisos": avisos,
        },
        "colunas": perfis,
        "chaves_candidatas": chaves,
        "duplicatas": _duplicatas(colunas, n_linhas) if buscar_chaves
                      else {"linhas_integrais": 0, "exemplos": []},
        "limitacoes": limitacoes or [],
    }
