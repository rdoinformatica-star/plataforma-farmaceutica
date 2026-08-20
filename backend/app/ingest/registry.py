"""Reconhecimento do tipo de arquivo.

Le so o inicio do arquivo — nunca o conteudo inteiro. Devolve TODOS os
candidatos ordenados por confianca; quem decide e o usuario. Uma deteccao
errada aceita em silencio poluiria o banco, e o sistema nao pode presumir.
"""
from pathlib import Path

from .adapters import estoque_xlsx, iqvia_mercado, tabular, vmd_sellout

ADAPTADORES = {
    m.CODIGO: m for m in (vmd_sellout, iqvia_mercado, estoque_xlsx, tabular)
}

CABECA_BYTES = 256 * 1024


def obter(codigo: str):
    return ADAPTADORES.get(codigo)


def _cabeca(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read(CABECA_BYTES)


def detectar(path: Path) -> list[dict]:
    cabeca = _cabeca(path)
    ext = path.suffix.lower()
    candidatos = []
    for codigo, mod in ADAPTADORES.items():
        try:
            score, motivo = mod.pontuar(path, cabeca, ext)
        except Exception as e:
            score, motivo = 0.0, f"nao foi possivel avaliar: {e}"
        if score > 0:
            try:
                params = mod.params_sugeridos(path, cabeca)
            except Exception:
                params = {}
            candidatos.append({
                "adaptador": codigo,
                "rotulo": mod.ROTULO,
                "data_source": mod.DATA_SOURCE,
                "confianca": round(score, 3),
                "motivo": motivo,
                "params_sugeridos": params,
            })
    candidatos.sort(key=lambda c: c["confianca"], reverse=True)
    return candidatos
