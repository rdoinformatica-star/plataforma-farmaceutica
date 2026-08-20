"""Registro de auditoria. Toda acao que muda estado passa por aqui."""
import json
import sqlite3


def registrar(con: sqlite3.Connection, acao: str, resumo: str,
              entidade: str | None = None, entidade_id: int | None = None,
              detalhe: dict | None = None, ator: str = "usuario") -> None:
    con.execute(
        "INSERT INTO audit_logs(ator, acao, entidade, entidade_id, resumo, detalhe_json)"
        " VALUES (?,?,?,?,?,?)",
        (ator, acao, entidade, entidade_id, resumo,
         json.dumps(detalhe, ensure_ascii=False) if detalhe else None),
    )
