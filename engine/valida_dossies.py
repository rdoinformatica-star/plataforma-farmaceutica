"""Valida a estrutura dos dossies antes de publicar.

    python valida_dossies.py                      # valida todos em relatorios/
    python valida_dossies.py ../relatorios/x.html # valida um arquivo

Confere o que quebra a renderizacao sem dar erro visivel:
  - tags nao fechadas ou fechadas fora de ordem
  - tabelas com numero de colunas inconsistente entre linhas (considera colspan)
  - <title> ausente
  - numeracao das secoes fora de sequencia

Complementa verifica_dossies.py, que confere os NUMEROS contra a base.
Este aqui confere a ESTRUTURA.
"""
import glob
import io
import os
import re
import sys
from html.parser import HTMLParser

import config

VOID = {"br", "hr", "img", "input", "link", "meta", "source", "col", "area", "base"}


class Validador(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha = []
        self.erros = []
        self.tabelas = []
        self._tab = None
        self._cols = 0
        self._ini = 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        self.pilha.append((tag, self.getpos()[0]))
        if tag == "table":
            self._tab = []
            self._ini = self.getpos()[0]
        elif tag == "tr" and self._tab is not None:
            self._cols = 0
        elif tag in ("td", "th") and self._tab is not None:
            span = 1
            for k, v in attrs:
                if k == "colspan":
                    try:
                        span = int(v)
                    except ValueError:
                        pass
            self._cols += span

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag == "tr" and self._tab is not None:
            self._tab.append(self._cols)
        elif tag == "table" and self._tab is not None:
            self.tabelas.append((self._ini, self._tab))
            self._tab = None
        if not self.pilha:
            self.erros.append(f"L{self.getpos()[0]}: </{tag}> sem abertura correspondente")
            return
        if self.pilha[-1][0] != tag:
            self.erros.append(
                f"L{self.getpos()[0]}: </{tag}> mas o aberto era "
                f"<{self.pilha[-1][0]}> (L{self.pilha[-1][1]})")
            for i in range(len(self.pilha) - 1, -1, -1):
                if self.pilha[i][0] == tag:
                    del self.pilha[i:]
                    return
            return
        self.pilha.pop()


def valida(caminho):
    nome = os.path.basename(caminho)
    src = io.open(caminho, encoding="utf-8").read()
    v = Validador()
    v.feed(src)
    problemas = 0

    print(f"\n=== {nome}  ({len(src):,} bytes) ===")

    abertas = [t for t in v.pilha if t[0] not in ("html", "body", "head")]
    if v.erros:
        problemas += len(v.erros)
        print(f"  TAGS: {len(v.erros)} problema(s)")
        for e in v.erros[:10]:
            print(f"    {e}")
    elif abertas:
        problemas += len(abertas)
        print("  TAGS: nao fechada(s): " + ", ".join(f"<{t}> L{l}" for t, l in abertas[:10]))
    else:
        print("  TAGS: balanceadas")

    ruins = [(ln, cols) for ln, cols in v.tabelas if len(set(cols)) > 1]
    print(f"  TABELAS: {len(v.tabelas)}")
    if ruins:
        problemas += len(ruins)
        for ln, cols in ruins:
            print(f"    L{ln}: colunas irregulares entre linhas -> {sorted(set(cols))}")
    else:
        print("    numero de colunas consistente em todas")

    if "<title>" not in src:
        problemas += 1
        print("  TITULO: AUSENTE")

    n_sec = len(re.findall(r"<section id=", src))
    nums = re.findall(r'<span class="snum">(\d+)</span>', src)
    esperado = [f"{i:02d}" for i in range(1, n_sec + 1)]
    if nums == esperado:
        print(f"  SECOES: {n_sec}, numeracao sequencial")
    else:
        problemas += 1
        print(f"  SECOES: {n_sec}, numeracao FORA DE ORDEM -> {nums}")

    return problemas


alvos = sys.argv[1:] or sorted(glob.glob(os.path.join(config.RELATORIOS, "*.html")))
if not alvos:
    raise SystemExit("Nenhum dossie encontrado em relatorios/.")

total = sum(valida(a) for a in alvos)
print("\n" + "=" * 62)
print("TUDO OK - pronto para publicar" if total == 0 else f"{total} PROBLEMA(S) - corrija antes de publicar")
print("=" * 62)
sys.exit(1 if total else 0)
