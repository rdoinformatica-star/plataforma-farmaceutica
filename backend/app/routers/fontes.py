from fastapi import APIRouter

from .. import db

router = APIRouter(prefix="/fontes", tags=["fontes"])

_AVISO_ELO = {
    "DISTRIBUIDOR_PDV": "Preco do distribuidor para o PDV.",
    "PDV_CONSUMIDOR": "Preco de varejo (PDV para o consumidor). "
                      "Nao e comparavel com preco de sell-out.",
    "ESTOQUE": "Foto de estoque numa data. Nao e serie historica.",
    "CADASTRAL": "Cadastro, sem valores de venda.",
    "INDUSTRIA_DISTRIBUIDOR": "Venda da industria para o distribuidor.",
    "INDEFINIDO": "O elo da cadeia precisa ser informado em cada linha.",
}


@router.get("")
def listar():
    with db.conexao() as con:
        fontes = db.varias(con,
            "SELECT f.*,"
            "       (SELECT count(*) FROM imports i WHERE i.data_source_id=f.id"
            "         AND i.status='CONCLUIDO') AS n_importacoes"
            "  FROM data_sources f WHERE f.ativo=1 ORDER BY f.id")
    for f in fontes:
        f["aviso_elo"] = _AVISO_ELO.get(f["natureza_elo"], "")
    return fontes
