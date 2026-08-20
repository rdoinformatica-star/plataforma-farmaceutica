"""sha256 em streaming e destino dos arquivos importados."""
import hashlib
import shutil
from pathlib import Path

from .. import settings


def sha256_arquivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while bloco := f.read(settings.BLOCO_HASH):
            h.update(bloco)
    return h.hexdigest()


def destino(sha: str, ext: str) -> Path:
    """imports/<2 primeiros do sha>/<sha><ext> — mesmo conteudo ocupa disco uma vez."""
    pasta = settings.IMPORTS / sha[:2]
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{sha}{ext.lower()}"


def arquivar(origem: Path, sha: str) -> Path:
    alvo = destino(sha, origem.suffix)
    if not alvo.exists():
        shutil.copy2(origem, alvo)
    return alvo
