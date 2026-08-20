"""Leitor do sell-out VITAMEDIC (formato binario proprio VMD1).

O dashboard exportado traz a base embutida em <script id="pack">, como
base64 -> gzip -> binario VMD1. Este modulo descompacta uma vez para
cache/pack.bin e depois le direto de la.

Layout do VMD1:
    "VMD1" (4 bytes) + uint32 LE com o tamanho do header + header JSON + colunas

Duas pegadinhas que custam caro:
  1. o campo "o" de cada coluna e offset em BYTES, nao em elementos;
  2. fUnd e fVal estao armazenados x100 (o JS do dashboard faz und/100, val/100).
"""
import base64
import gzip
import json
import os
import re
import struct

import numpy as np

import config

DT = {"i8": np.uint8, "i16": np.uint16, "i32": np.uint32}

ESCALA = 100.0  # unidades e valores vem multiplicados por 100


def _extrair_pack():
    """Descompacta o payload do HTML para cache/pack.bin (so na primeira vez)."""
    if os.path.exists(config.PACK_BIN):
        return config.PACK_BIN
    config.exigir(config.SELLOUT_HTML, "Dashboard de Sell-out")
    print("Descompactando a base de sell-out (so acontece na primeira execucao)...")
    with open(config.SELLOUT_HTML, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    m = re.search(r'<script id="pack" type="text/plain">(.*?)</script>', src, re.S)
    if not m:
        raise SystemExit("Bloco <script id='pack'> nao encontrado no HTML de sell-out.")
    raw = gzip.decompress(base64.b64decode(m.group(1).strip()))
    with open(config.PACK_BIN, "wb") as fh:
        fh.write(raw)
    print(f"  -> {len(raw):,} bytes em {config.PACK_BIN}")
    return config.PACK_BIN


class Pack:
    def __init__(self, path=None):
        path = path or _extrair_pack()
        with open(path, "rb") as fh:
            raw = fh.read()
        if raw[:4] != b"VMD1":
            raise SystemExit("Assinatura VMD1 ausente - arquivo corrompido.")
        hlen = struct.unpack("<I", raw[4:8])[0]
        self.hdr = json.loads(raw[8:8 + hlen].decode("utf-8"))
        base = 8 + hlen
        self.col = {}
        for c in self.hdr["cols"]:
            dt = np.dtype(DT[c["t"]])
            ini = base + c["o"]                      # offset em BYTES
            n = c["len"] * dt.itemsize
            self.col[c["n"]] = np.frombuffer(raw[ini:ini + n], dtype=dt).copy()
        self.dic = self.hdr["dic"]
        self.periodos = self.hdr["periodos"]

    def d(self, nome):
        return self.dic[nome]

    def idx_of(self, dic_nome, alvo, exato=False):
        """Indices do dicionario que casam com 'alvo' (case-insensitive)."""
        vals = self.dic[dic_nome]
        a = alvo.upper()
        if exato:
            return [i for i, v in enumerate(vals) if v.upper() == a]
        return [i for i, v in enumerate(vals) if a in v.upper()]

    def janela(self, ano, meses=range(1, 8)):
        """Indices de periodo para uma janela de meses de um ano (default jan-jul)."""
        out = []
        for m in meses:
            p = f"{ano}{m:02d}"
            if p in self.periodos:
                out.append(self.periodos.index(p))
        return out


def fmt_brl(v):
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def fmt_int(v):
    return f"{v:,.0f}".replace(",", ".")


def fmt_pct(v, casas=1):
    if v is None:
        return "n/d"
    return f"{v:+.{casas}f}%".replace(".", ",")


def periodo_label(p):
    return f"{p[4:]}/{p[:4]}"
