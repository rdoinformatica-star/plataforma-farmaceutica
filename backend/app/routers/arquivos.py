import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Query, UploadFile

from .. import db, settings
from ..core import errors, hashing
from ..ingest import registry
from ..schemas import DeteccaoEntrada

router = APIRouter(prefix="/arquivos", tags=["arquivos"])


def resolver_permitido(caminho: str | None) -> Path:
    """So deixa navegar dentro das raizes permitidas.

    Sem esta checagem, um caminho digitado na URL leria qualquer arquivo da
    maquina.
    """
    if not caminho:
        return settings.DADOS
    p = Path(caminho)
    if not p.is_absolute():
        p = settings.RAIZ / p
    try:
        p = p.resolve()
    except OSError:
        raise errors.invalido("Caminho invalido.")
    for raiz in settings.RAIZES_PERMITIDAS:
        try:
            p.relative_to(raiz.resolve())
            return p
        except ValueError:
            continue
    raise errors.ErroDeNegocio(
        403, "PASTA_NAO_PERMITIDA",
        "Esta pasta nao pode ser acessada pelo sistema.",
        "Sao permitidas apenas: " + ", ".join(r.name for r in settings.RAIZES_PERMITIDAS))


@router.get("/disco")
def listar_disco(pasta: str | None = Query(None)):
    p = resolver_permitido(pasta)
    if not p.exists():
        raise errors.nao_encontrado("Pasta", str(p))
    if p.is_file():
        p = p.parent

    itens = []
    for f in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if f.name.startswith("."):
            continue
        ext = f.suffix.lower()
        try:
            st = f.stat()
        except OSError:
            continue
        itens.append({
            "nome": f.name,
            "caminho": str(f),
            "tipo": "pasta" if f.is_dir() else "arquivo",
            "bytes": st.st_size if f.is_file() else None,
            "modificado_em": __import__("datetime").datetime.fromtimestamp(
                st.st_mtime).isoformat(timespec="seconds"),
            "ext": ext,
            "suportado": f.is_file() and ext in settings.EXTENSOES_SUPORTADAS,
        })

    pai = None
    for raiz in settings.RAIZES_PERMITIDAS:
        if p != raiz.resolve() and str(p).startswith(str(raiz.resolve())):
            pai = str(p.parent)
            break

    return {"pasta": str(p), "pai": pai,
            "raizes": [{"nome": r.name, "caminho": str(r)}
                       for r in settings.RAIZES_PERMITIDAS if r.exists()],
            "itens": itens}


@router.post("/upload")
async def upload(arquivo: UploadFile = File(...)):
    """Grava em blocos. Um await file.read() de 35 MB carregaria tudo na memoria."""
    if not arquivo.filename:
        raise errors.invalido("Nenhum arquivo enviado.")
    ext = Path(arquivo.filename).suffix.lower()
    if ext not in settings.EXTENSOES_SUPORTADAS:
        raise errors.invalido(
            f"O sistema nao le arquivos '{ext}'.",
            "Formatos aceitos: " + ", ".join(sorted(settings.EXTENSOES_SUPORTADAS)))

    temporario = settings.IMPORTS_TMP / f"{uuid.uuid4().hex}{ext}"
    tamanho = 0
    try:
        with open(temporario, "wb") as saida:
            while bloco := await arquivo.read(settings.BLOCO_HASH):
                tamanho += len(bloco)
                if tamanho > settings.MAX_UPLOAD_BYTES:
                    raise errors.invalido(
                        f"Arquivo maior que o limite de "
                        f"{settings.MAX_UPLOAD_BYTES // (1024*1024)} MB.",
                        "Se o arquivo ja esta na pasta do projeto, use a aba "
                        "'Da pasta do projeto' — e mais rapido e nao duplica o arquivo.")
                saida.write(bloco)
        sha = hashing.sha256_arquivo(temporario)
        destino = hashing.destino(sha, ext)
        if destino.exists():
            temporario.unlink(missing_ok=True)
        else:
            shutil.move(str(temporario), str(destino))
    finally:
        temporario.unlink(missing_ok=True)

    return {"sha256": sha, "nome": arquivo.filename, "bytes": tamanho,
            "caminho": str(destino)}


def caminho_de(origem: str, caminho: str | None, sha: str | None) -> Path:
    if origem == "DISCO":
        p = resolver_permitido(caminho)
        if not p.is_file():
            raise errors.nao_encontrado("Arquivo", caminho)
        return p
    if not sha:
        raise errors.invalido("Faltou identificar o arquivo enviado.")
    achados = list(settings.IMPORTS.glob(f"{sha[:2]}/{sha}.*"))
    if not achados:
        raise errors.nao_encontrado("Arquivo enviado", sha)
    return achados[0]


@router.post("/detectar")
def detectar(dados: DeteccaoEntrada):
    p = caminho_de(dados.origem, dados.caminho, dados.sha256)
    sha = dados.sha256 or hashing.sha256_arquivo(p)
    candidatos = registry.detectar(p)

    with db.conexao() as con:
        anterior = db.uma(con,
            "SELECT i.id, i.arquivo_nome, i.concluido_em, i.linhas_gravadas,"
            "       i.client_id, c.nome AS cliente, f.codigo AS fonte"
            "  FROM imports i"
            "  JOIN data_sources f ON f.id = i.data_source_id"
            "  LEFT JOIN clients c ON c.id = i.client_id"
            " WHERE i.sha256 = ? AND i.status='CONCLUIDO'"
            " ORDER BY i.id DESC LIMIT 1", (sha,))
        fontes = {f["codigo"]: f["id"] for f in
                  db.varias(con, "SELECT id, codigo FROM data_sources")}

    for c in candidatos:
        c["data_source_id"] = fontes.get(c["data_source"])

    if not candidatos:
        raise errors.invalido(
            "O sistema nao reconheceu o formato deste arquivo.",
            "Aceita planilhas (.xlsx, .csv) e os dashboards em .html.")

    previa = None
    if candidatos[0]["adaptador"] == "tabular":
        from ..ingest.adapters import tabular as tab
        try:
            previa = tab.previa(p, candidatos[0]["params_sugeridos"])
        except Exception as e:
            previa = {"erro": str(e)}

    return {"arquivo": {"nome": p.name, "caminho": str(p),
                        "bytes": p.stat().st_size, "sha256": sha},
            "candidatos": candidatos,
            "previa": previa,
            "ja_importado": anterior}
