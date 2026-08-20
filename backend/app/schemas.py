"""Contratos de entrada da API."""
from typing import Literal

from pydantic import BaseModel, Field


class ClienteEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    cnpj: str | None = None
    uf_principal: str | None = Field(default=None, max_length=2)
    grupo: str | None = None
    observacoes: str | None = None


class ClienteAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=160)
    cnpj: str | None = None
    uf_principal: str | None = Field(default=None, max_length=2)
    grupo: str | None = None
    observacoes: str | None = None
    ativo: bool | None = None


class DeteccaoEntrada(BaseModel):
    origem: Literal["DISCO", "UPLOAD"]
    caminho: str | None = None
    sha256: str | None = None


class ImportacaoEntrada(BaseModel):
    origem: Literal["DISCO", "UPLOAD"]
    caminho: str | None = None
    sha256: str | None = None
    adaptador: str
    client_id: int | None = None
    data_source_id: int
    params: dict = Field(default_factory=dict)
    forcar_reimportacao: bool = False
    adaptador_forcado: bool = False


class DecisaoColuna(BaseModel):
    decisao: Literal["PENDENTE", "ARMAZENAR", "IGNORAR", "MAPEAR", "RELACIONAR"]
    mapeado_para: str | None = None


class MapeamentoEntrada(BaseModel):
    entidade: Literal["PRODUTO", "PDV", "DISTRIBUIDOR"]
    data_source_id: int
    texto_origem: str
    entity_id: int
    codigo_origem: str | None = None
    observacao: str | None = None


class RevisaoDimensao(BaseModel):
    eh_novo: bool = False
