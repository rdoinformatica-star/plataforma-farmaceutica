"""Normalizacao de texto.

Normalizar errado aqui produz chave natural errada, que produz dimensao
duplicada na reimportacao. Toda chave passa por NFC antes de qualquer coisa.
"""
import re
import unicodedata

_ESPACOS = re.compile(r"\s+")
_NAO_ALNUM = re.compile(r"[^A-Z0-9]+")

UFS = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)


def sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def normalizar(s) -> str:
    """Maiusculo, sem acento, espacos colapsados. Para busca e comparacao."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    return _ESPACOS.sub(" ", sem_acento(s).upper()).strip()


def chave(s) -> str:
    """Forma agressiva: so letras e numeros. Para chave natural de dimensao."""
    return _NAO_ALNUM.sub("", normalizar(s))


def slug_coluna(s) -> str:
    return _ESPACOS.sub("_", normalizar(s).lower()).strip("_")


def so_digitos(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def ean13(valor) -> str | None:
    """xlsx entrega EAN como float64 (7.89804979018e12). Sem esta conversao a
    chave entre fontes quebra em silencio."""
    if valor is None:
        return None
    if isinstance(valor, float):
        if valor != valor or valor in (float("inf"), float("-inf")):
            return None
        valor = int(valor)
    else:
        # pandas entrega o EAN como float, e str() deixa o ".0" no fim.
        # Sem isto o codigo vira 14 digitos e deixa de casar entre fontes.
        s = str(valor).strip()
        if re.fullmatch(r"\d+\.0+", s):
            valor = s.split(".")[0]
    d = so_digitos(valor)
    if not d or len(d) > 14:
        return None
    return d.zfill(13) if len(d) <= 13 else d


def ean13_valido(codigo: str) -> bool:
    if not codigo or len(codigo) != 13 or not codigo.isdigit():
        return False
    soma = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(codigo[:12]))
    return (10 - soma % 10) % 10 == int(codigo[12])


def cnpj_valido(valor) -> bool:
    c = so_digitos(valor)
    if len(c) != 14 or len(set(c)) == 1:
        return False
    for tam in (12, 13):
        pesos = list(range(tam - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(c[i]) * pesos[i] for i in range(tam))
        resto = soma % 11
        if int(c[tam]) != (0 if resto < 2 else 11 - resto):
            return False
    return True
