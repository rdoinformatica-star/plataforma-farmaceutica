"""Contrato dos adaptadores de importacao."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .profiler import Coluna

# Nos dashboards reais o bloco de dados vem depois de todo o HTML e do CSS:
# a 442 KB no sell-out e a 2,1 MB no IQVIA. Procurar so no inicio do arquivo
# nao acha nada.
LIMITE_BUSCA = 16 * 1024 * 1024
BLOCO_BUSCA = 1024 * 1024


def procurar(path: Path, marcador: bytes, limite: int = LIMITE_BUSCA) -> int:
    """Procura o marcador lendo em blocos, sem carregar o arquivo inteiro.

    A sobreposicao entre blocos evita perder um marcador partido na fronteira.
    """
    sobra = len(marcador) - 1
    lido = 0
    anterior = b""
    with open(path, "rb") as f:
        while lido < limite:
            bloco = f.read(BLOCO_BUSCA)
            if not bloco:
                return -1
            pos = (anterior + bloco).find(marcador)
            if pos >= 0:
                return lido - len(anterior) + pos
            lido += len(bloco)
            anterior = bloco[-sobra:] if sobra else b""
    return -1


@dataclass
class Lote:
    """O que um adaptador entrega ao pipeline.

    `colunas` alimenta o perfilador. `gravar` e a funcao que escreve os fatos —
    fica no adaptador porque cada fonte tem grao e volume muito diferentes
    (368 linhas de estoque contra 6,8 milhoes de sell-out).
    """
    fonte: str
    n_linhas: int
    colunas: list[Coluna]
    gravar: Any                       # (con, import_id, prog) -> int
    descartadas: int = 0
    motivo_descarte: str | None = None
    amostras_descartadas: list = field(default_factory=list)
    limitacoes: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    entidades: dict = field(default_factory=dict)
    periodo: dict | None = None
    colunas_novas: list[str] = field(default_factory=list)
    buscar_chaves: bool = True
    indices_pos_carga: list[str] = field(default_factory=list)
    resumo_mensal: bool = False


class Progresso(Protocol):
    def etapa(self, nome: str, pct: float) -> None: ...
    def linhas(self, lidas: int, total: int | None = None) -> None: ...
    def log(self, texto: str, nivel: str = "info") -> None: ...
    def cancelado(self) -> bool: ...


class Adaptador(Protocol):
    codigo: str
    rotulo: str
    data_source: str

    @staticmethod
    def pontuar(path: Path, cabeca: bytes, ext: str) -> tuple[float, str]: ...

    @staticmethod
    def params_sugeridos(path: Path, cabeca: bytes) -> dict: ...

    def abrir(self, path: Path, params: dict, prog: Progresso) -> Lote: ...
