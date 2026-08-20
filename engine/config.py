"""Caminhos do projeto. Tudo resolve a partir da raiz, sem depender do Downloads."""
import os

ENGINE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(ENGINE)
DADOS = os.path.join(RAIZ, "dados")
CACHE = os.path.join(RAIZ, "cache")
RELATORIOS = os.path.join(RAIZ, "relatorios")

os.makedirs(CACHE, exist_ok=True)

SELLOUT_HTML = os.path.join(DADOS, "Dashboard_Sellout_VITAMEDIC.html")
MERCADO_HTML = os.path.join(DADOS, "Dashboard_Mercado_Relevante_VITAMEDIC.html")

PACK_BIN = os.path.join(CACHE, "pack.bin")


def exigir(caminho, oque):
    if not os.path.exists(caminho):
        raise SystemExit(
            f"\nArquivo nao encontrado: {caminho}\n"
            f"Coloque o export do {oque} em 'dados/' com esse nome exato.\n"
        )
    return caminho
