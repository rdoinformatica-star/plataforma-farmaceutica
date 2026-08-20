"""PHARMA INTELLIGENCE — API local."""
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db, settings
from .core.errors import ErroDeNegocio, traduzir

log = logging.getLogger("pharma")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

# Uma thread so: SQLite aceita um escritor, o app e de usuario unico, e uma fila
# de um torna o tempo de espera previsivel. numpy e sqlite liberam o GIL nos
# trechos pesados, entao a API continua respondendo durante uma carga longa.
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    info = db.migrar()
    log.info("Banco pronto: %d tabelas, %d fontes", len(info["tabelas"]), info["fontes"])
    from .ingest import jobs
    jobs.destravar_orfaos()
    app.state.executor = EXECUTOR
    yield
    EXECUTOR.shutdown(wait=False, cancel_futures=True)


app = FastAPI(
    title="Pharma Intelligence",
    version=settings.VERSAO,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


@app.exception_handler(ErroDeNegocio)
async def _erro_negocio(request: Request, exc: ErroDeNegocio):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(Exception)
async def _erro_inesperado(request: Request, exc: Exception):
    log.exception("Erro em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"erro": {"codigo": "ERRO_INTERNO",
                          "mensagem": "Algo deu errado no servidor.",
                          "detalhe": traduzir(exc)}},
    )


from .routers import (  # noqa: E402
    arquivos, auditoria, clientes, colunas, dimensoes, fontes,
    health, importacoes, mapeamentos,
)

for _r in (health, clientes, fontes, arquivos, importacoes, colunas,
           mapeamentos, dimensoes, auditoria):
    app.include_router(_r.router, prefix="/api")
