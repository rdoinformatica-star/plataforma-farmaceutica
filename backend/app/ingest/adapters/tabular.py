"""Adaptador generico de CSV / Excel.

E o fallback: qualquer planilha entra por aqui. Nada e presumido em silencio —
encoding, separador e decimal sao detectados, mostrados ao usuario e so entao
confirmados.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ...core.texto import normalizar
from ..base import Lote
from ..profiler import Coluna

CODIGO = "tabular"
ROTULO = "Planilha generica (CSV ou Excel)"
DATA_SOURCE = "OUTROS"

_EXT_EXCEL = {".xlsx", ".xls"}
_EXT_TEXTO = {".csv", ".txt", ".tsv"}
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_SEPARADORES = (";", ",", "\t", "|")

# Rotulos de subtotal/rodape que exports brasileiros costumam deixar na planilha.
_LIXO = {"total", "totais", "subtotal", "soma", "nenhum filtro aplicado",
         "-", "", "nan", "none", "resultado"}


def pontuar(path: Path, cabeca: bytes, ext: str) -> tuple[float, str]:
    if ext in _EXT_EXCEL:
        return 0.30, "arquivo Excel — leitura generica de planilha"
    if ext in _EXT_TEXTO:
        return 0.30, "arquivo de texto separado por delimitador"
    return 0.0, ""


def _detectar_encoding(cabeca: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            cabeca.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _detectar_separador(texto: str) -> str:
    linhas = [l for l in texto.splitlines()[:20] if l.strip()]
    if not linhas:
        return ";"
    melhor, melhor_n = ";", -1
    for sep in _SEPARADORES:
        # conta fora de aspas
        contagens = [len(re.split(rf'{re.escape(sep)}(?=(?:[^"]*"[^"]*")*[^"]*$)', l)) - 1
                     for l in linhas]
        if not contagens:
            continue
        n = min(contagens)
        if n > melhor_n and n > 0 and len(set(contagens)) <= 3:
            melhor, melhor_n = sep, n
    return melhor


def _detectar_decimal(texto: str) -> str:
    virgula = len(re.findall(r"\d+,\d{1,4}\b", texto))
    ponto = len(re.findall(r"\d+\.\d{1,4}\b", texto))
    return "," if virgula > ponto else "."


def params_sugeridos(path: Path, cabeca: bytes) -> dict:
    ext = path.suffix.lower()
    if ext in _EXT_EXCEL:
        try:
            abas = pd.ExcelFile(path).sheet_names
        except Exception:
            abas = []
        return {"aba": abas[0] if abas else 0, "abas_disponiveis": abas}
    enc = _detectar_encoding(cabeca)
    texto = cabeca.decode(enc, errors="replace")
    sep = _detectar_separador(texto)
    return {"encoding": enc, "separador": sep, "decimal": _detectar_decimal(texto),
            "milhar": "." if _detectar_decimal(texto) == "," else ","}


def previa(path: Path, params: dict, n: int = 10) -> dict:
    df = _ler(path, params, nrows=n)
    return {"colunas": [str(c) for c in df.columns],
            "linhas": json.loads(df.head(n).to_json(orient="records", date_format="iso"))}


def _ler(path: Path, params: dict, nrows: int | None = None) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext in _EXT_EXCEL:
        return pd.read_excel(path, sheet_name=params.get("aba", 0), nrows=nrows)
    return pd.read_csv(
        path,
        sep=params.get("separador", ";"),
        encoding=params.get("encoding", "utf-8"),
        decimal=params.get("decimal", "."),
        thousands=params.get("milhar") or None,
        nrows=nrows,
        dtype_backend="numpy_nullable",
        on_bad_lines="warn",
    )


def separar_lixo(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    """Descarta linhas de subtotal por regra generica, nunca por nome de arquivo.

    Ancoramos na primeira coluna textual: se o rotulo dela e vazio ou e uma
    palavra de totalizacao, a linha e rodape de relatorio, nao dado.
    """
    # pandas 3 devolve dtype 'str' para texto; comparar com object nao pega mais.
    textuais = [c for c in df.columns if not (
        pd.api.types.is_numeric_dtype(df[c])
        or pd.api.types.is_bool_dtype(df[c])
        or pd.api.types.is_datetime64_any_dtype(df[c]))]
    if not textuais:
        return df, df.iloc[0:0], None
    chave = textuais[0]
    marca = df[chave].isna() | df[chave].astype(str).str.strip().str.lower().isin(_LIXO)
    if not marca.any():
        return df, df.iloc[0:0], None
    return (df[~marca].reset_index(drop=True), df[marca],
            f"linhas de subtotal ou rodape identificadas pela coluna '{chave}'")


def colunas_para_perfil(df: pd.DataFrame) -> list[Coluna]:
    cols = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            cols.append(Coluna(nome=str(c), valores=s.astype("float64").to_numpy()))
        else:
            cols.append(Coluna(nome=str(c), valores=s.astype(object).to_numpy()))
    return cols


def abrir(path: Path, params: dict, prog) -> Lote:
    prog.etapa("Lendo a planilha", 0.05)
    df = _ler(path, params)
    limpo, lixo, motivo = separar_lixo(df)
    prog.log(f"{len(df)} linhas lidas, {len(limpo)} validas.")

    amostras = json.loads(lixo.head(5).to_json(orient="records")) if len(lixo) else []

    def gravar(con, import_id, p):
        # A fonte generica nao tem tabela de fato propria na Etapa 1: o valor
        # esta no perfil e nas dimensoes. Guardamos o conteudo como referencia.
        return 0

    return Lote(
        fonte="OUTROS",
        n_linhas=len(limpo),
        colunas=colunas_para_perfil(limpo),
        gravar=gravar,
        descartadas=len(lixo),
        motivo_descarte=motivo,
        amostras_descartadas=amostras,
        limitacoes=[
            "Esta fonte foi lida como planilha generica: o sistema perfilou as "
            "colunas, mas ainda nao sabe o significado de negocio de cada uma. "
            "Confirme os papeis das colunas para que ela entre nas analises."
        ],
        entidades={"colunas": len(limpo.columns)},
    )
