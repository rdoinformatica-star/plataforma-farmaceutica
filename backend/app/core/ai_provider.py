"""Abstracao de provedor de IA — deliberadamente sem nenhuma implementacao paga.

O sistema funciona 100% offline. Todo calculo quantitativo e local (numpy/SQL).
Quando uma pergunta exigir raciocinio generativo, a Etapa 6 vai gerar um prompt
estruturado para o usuario colar no Claude Code, e colar a resposta de volta.
Isso e o provedor MANUAL: custo zero, sem chave de API, sem rede.

Os outros provedores existem so como contrato para o futuro. Nenhum e ligado.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Capacidade:
    codigo: str
    rotulo: str
    disponivel: bool
    exige_rede: bool
    exige_chave: bool
    observacao: str


class AIProvider(Protocol):
    codigo: str
    rotulo: str

    def disponivel(self) -> bool: ...
    def capacidade(self) -> Capacidade: ...
    def gerar(self, prompt: str, **kw) -> str: ...


class ProvedorManual:
    """O unico provedor ativo: o proprio usuario leva o prompt ao Claude Code."""

    codigo = "MANUAL"
    rotulo = "Claude Code (manual, copiar e colar)"

    def disponivel(self) -> bool:
        return True

    def capacidade(self) -> Capacidade:
        return Capacidade(
            self.codigo, self.rotulo, True, False, False,
            "O sistema gera o prompt pronto; voce cola no Claude Code e traz a "
            "resposta de volta. Sem custo de API e sem depender de internet.",
        )

    def gerar(self, prompt: str, **kw) -> str:
        raise NotImplementedError(
            "O provedor manual nao gera texto. Ele monta o prompt para voce copiar."
        )


class _Indisponivel:
    exige_rede = True
    exige_chave = True

    def disponivel(self) -> bool:
        return False

    def capacidade(self) -> Capacidade:
        return Capacidade(self.codigo, self.rotulo, False, True, True,
                          "Nao configurado. O sistema funciona sem ele.")

    def gerar(self, prompt: str, **kw) -> str:
        raise NotImplementedError(f"{self.rotulo} nao esta configurado.")


class ProvedorClaude(_Indisponivel):
    codigo, rotulo = "CLAUDE_API", "API da Anthropic"


class ProvedorOpenAI(_Indisponivel):
    codigo, rotulo = "OPENAI_API", "API da OpenAI"


class ProvedorLocal(_Indisponivel):
    codigo, rotulo = "LOCAL", "Modelo local (Ollama)"
    exige_rede = False
    exige_chave = False


PROVEDORES: list = [ProvedorManual(), ProvedorClaude(), ProvedorOpenAI(), ProvedorLocal()]
ATIVO = PROVEDORES[0]


def listar() -> list[dict]:
    return [c.__dict__ for c in (p.capacidade() for p in PROVEDORES)]
