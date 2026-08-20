"""Ponte para o motor original em engine/.

Reusa engine/vmd.py e engine/iqvia.py sem alterar uma linha deles. Sao modulos
bem escritos e que ja custaram caro para acertar (offset em bytes, valores x100);
reescrever seria repetir os mesmos erros.

Dois cuidados que o codigo original impoe:

1. engine/vmd.py e engine/iqvia.py fazem `import config` — modulo de nivel raiz.
   So importam com engine/ no sys.path, e o nome `config` fica global. Por isso
   nenhum modulo deste backend se chama config (usamos settings.py).

2. engine/config.exigir() levanta SystemExit, que herda de BaseException.
   Um `except Exception` no job NAO pega. Quem chama daqui tem que usar
   BaseException — ver jobs.executar_job.
"""
import base64
import gzip
import io
import re
import threading
from pathlib import Path

from .. import settings

_LOCK = threading.Lock()
_MODULOS = None

_RE_PACK = re.compile(
    rb'<script[^>]+id="pack"[^>]*>(.*?)</script>', re.S | re.I)
_RE_MODEL = re.compile(
    rb'<script[^>]+id="__model_json__"[^>]*>(.*?)</script>', re.S | re.I)


def carregar():
    """Coloca engine/ no sys.path uma unica vez e devolve (config, vmd, iqvia)."""
    global _MODULOS
    with _LOCK:
        if _MODULOS is None:
            import sys
            caminho = str(settings.ENGINE_DIR)
            if caminho not in sys.path:
                sys.path.insert(0, caminho)
            import config, iqvia, vmd  # noqa: E402
            _MODULOS = (config, vmd, iqvia)
        return _MODULOS


def disponivel() -> tuple[bool, str]:
    try:
        config, vmd, iqvia = carregar()
    except BaseException as e:
        return False, f"Motor nao carregou: {e}"
    faltando = [n for n, p in (("vmd.Pack", hasattr(vmd, "Pack")),
                               ("vmd.ESCALA", hasattr(vmd, "ESCALA")),
                               ("iqvia.load", hasattr(iqvia, "load"))) if not p]
    if faltando:
        return False, "Faltam no motor: " + ", ".join(faltando)
    return True, f"engine/ carregado (ESCALA={vmd.ESCALA})"


# ─────────────────────────── sell-out (VMD1) ───────────────────────────

def _eh_arquivo_padrao(html: Path, alvo: Path) -> bool:
    try:
        return html.resolve() == alvo.resolve()
    except OSError:
        return False


def extrair_pack(html_path: Path, sha: str, log=None) -> Path:
    """HTML -> binario VMD1 em cache/.

    Quando o arquivo escolhido for o padrao de dados/, chama a funcao original
    do motor para compartilhar cache/pack.bin com os scripts de terminal — evita
    gastar outros 122 MB de disco com o mesmo conteudo.
    """
    config, vmd, _ = carregar()
    padrao = Path(config.SELLOUT_HTML)

    if _eh_arquivo_padrao(html_path, padrao):
        destino = Path(config.PACK_BIN)
        if destino.exists():
            if log:
                log("Base ja descompactada, reaproveitando o cache do motor.")
            return destino
        if log:
            log("Descompactando a base de sell-out (pode levar cerca de 1 minuto)...")
        vmd._extrair_pack()
        return destino

    destino = settings.CACHE / f"pack_{sha[:12]}.bin"
    if destino.exists():
        if log:
            log("Base ja descompactada, reaproveitando o cache.")
        return destino
    if log:
        log("Descompactando a base de sell-out (pode levar cerca de 1 minuto)...")
    bruto = html_path.read_bytes()
    m = _RE_PACK.search(bruto)
    if not m:
        raise ValueError(
            "Este arquivo nao tem o bloco de dados do sell-out "
            "(<script id=\"pack\">). Confira se e o dashboard correto."
        )
    dados = gzip.decompress(base64.b64decode(m.group(1).strip()))
    destino.write_bytes(dados)
    return destino


def abrir_pack(bin_path: Path):
    _, vmd, _ = carregar()
    return vmd.Pack(str(bin_path))


# ──────────────────────────── mercado (IQVIA) ──────────────────────────

def carregar_iqvia(html_path: Path, aba: str, sha: str, log=None) -> dict:
    import json

    config, _, iqvia = carregar()
    padrao = Path(config.MERCADO_HTML)

    if _eh_arquivo_padrao(html_path, padrao):
        if log:
            log(f"Lendo a aba {aba} pelo motor (compartilha o cache do terminal).")
        return iqvia.load(aba)

    cache = settings.CACHE / f"iqvia_{sha[:12]}_{aba}.json"
    if cache.exists():
        if log:
            log("Base de mercado ja processada, reaproveitando o cache.")
        return json.loads(cache.read_text(encoding="utf-8"))

    if log:
        log("Lendo a base de mercado...")
    m = _RE_MODEL.search(html_path.read_bytes())
    if not m:
        raise ValueError(
            "Este arquivo nao tem o bloco de dados do mercado "
            "(<script id=\"__model_json__\">). Confira se e o dashboard correto."
        )
    modelo = json.loads(m.group(1).decode("utf-8"))
    d = modelo.get(aba)
    if d is None:
        disponiveis = [k for k in modelo if isinstance(modelo.get(k), dict)]
        raise ValueError(
            f"A aba '{aba}' nao existe neste arquivo. Abas encontradas: "
            f"{', '.join(disponiveis) or 'nenhuma'}."
        )
    d["_meta"] = modelo.get("meta", {})
    cache.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def constantes_iqvia():
    """Indices posicionais das colunas do IQVIA, lidos do proprio motor.

    Nunca duplicar esses numeros: se o formato mudar, muda num lugar so.
    """
    _, _, iqvia = carregar()
    return {n: getattr(iqvia, n) for n in
            ("MER", "APRE", "UF", "CANAL", "TIPO", "LAB",
             "U_CUR", "R_CUR", "U_PRV", "R_PRV",
             "U_YTD", "R_YTD", "U_YTDP", "R_YTDP")}


def labs_vitamedic(d: dict) -> set:
    _, _, iqvia = carregar()
    return iqvia.vitamedic_labs(d)


def escala() -> float:
    _, vmd, _ = carregar()
    return vmd.ESCALA
