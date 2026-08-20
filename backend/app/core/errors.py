"""Erros com mensagem em portugues, sem jargao tecnico.

O usuario nao e programador: um stack trace na tela e um beco sem saida.
"""
from fastapi import HTTPException


class ErroDeNegocio(HTTPException):
    def __init__(self, status: int, codigo: str, mensagem: str,
                 detalhe: str | None = None, extra: dict | None = None):
        corpo = {"erro": {"codigo": codigo, "mensagem": mensagem, "detalhe": detalhe}}
        if extra:
            corpo["erro"].update(extra)
        super().__init__(status_code=status, detail=corpo)


def nao_encontrado(oque: str, ident) -> ErroDeNegocio:
    return ErroDeNegocio(404, "NAO_ENCONTRADO",
                         f"{oque} nao encontrado.", f"Identificador: {ident}")


def conflito(codigo: str, mensagem: str, detalhe=None, extra=None) -> ErroDeNegocio:
    return ErroDeNegocio(409, codigo, mensagem, detalhe, extra)


def invalido(mensagem: str, detalhe=None) -> ErroDeNegocio:
    return ErroDeNegocio(400, "DADO_INVALIDO", mensagem, detalhe)


def traduzir(e: BaseException) -> str:
    """Converte a excecao numa frase que o usuario consegue agir em cima."""
    nome = type(e).__name__
    texto = str(e).strip()

    if isinstance(e, SystemExit):
        # engine/config.py levanta SystemExit quando falta arquivo em dados/.
        return texto or "O motor de leitura interrompeu o processamento."
    if isinstance(e, MemoryError):
        return ("Faltou memoria para processar este arquivo. Feche outros programas "
                "e tente de novo, ou importe um arquivo menor.")
    if isinstance(e, FileNotFoundError):
        return f"Arquivo nao encontrado: {getattr(e, 'filename', texto)}"
    if isinstance(e, PermissionError):
        return ("Sem permissao para ler o arquivo. Ele pode estar aberto no Excel — "
                "feche e tente de novo.")
    if isinstance(e, UnicodeDecodeError):
        return ("Nao foi possivel ler o texto do arquivo. A codificacao pode estar "
                "diferente do esperado.")
    if isinstance(e, (MemoryError, OSError)) and "space" in texto.lower():
        return "Espaco em disco insuficiente para concluir a importacao."
    return f"{nome}: {texto}" if texto else nome
