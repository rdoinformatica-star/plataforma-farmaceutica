"""Worker de importacao.

O progresso e gravado no BANCO, nao guardado em memoria. Isso e o que faz o
acompanhamento sobreviver a um F5, a fechar a aba e a reiniciar o servidor — e
e por isso que o frontend consulta por polling em vez de SSE: o transporte
extra nao acrescentaria nada que ja nao esteja persistido.
"""
import gc
import json
import logging
import sqlite3
import time
import traceback
from io import StringIO

from .. import db
from ..core import audit
from ..core.errors import traduzir
from . import profiler, registry

log = logging.getLogger("pharma.ingest")

MAX_LOG = 200
ETAPAS_ATIVAS = ("FILA", "ABRINDO", "PERFILANDO", "DIMENSOES", "CARREGANDO", "INDEXANDO")


class Progresso:
    """Escreve o andamento do job no banco."""

    def __init__(self, import_id: int):
        self.import_id = import_id
        self.eventos: list[dict] = []
        self.t0 = time.perf_counter()
        self._ultima_escrita = 0.0
        self._lidas = 0
        self._total = None
        self._cancelado = False

    # --- escrita ---
    def _executar(self, sql: str, params) -> None:
        """Progresso e informacao de acompanhamento, nao dado.

        Se o banco estiver ocupado pela propria carga, perder uma atualizacao
        de barra e irrelevante; derrubar a importacao por causa disso nao e.
        """
        try:
            with db.conexao() as con:
                con.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "locked" not in str(e) and "busy" not in str(e):
                raise
            log.debug("progresso ignorado (banco ocupado): %s", e)

    def _salvar(self, **campos):
        campos["log_json"] = json.dumps(self.eventos[-MAX_LOG:], ensure_ascii=False)
        sets = ", ".join(f"{k} = ?" for k in campos)
        self._executar(f"UPDATE imports SET {sets} WHERE id = ?",
                       list(campos.values()) + [self.import_id])

    def etapa(self, nome: str, pct: float, status: str | None = None):
        campos = {"etapa_atual": nome, "progresso": round(min(max(pct, 0), 1), 4)}
        if status:
            campos["status"] = status
        self._salvar(**campos)

    def linhas(self, lidas: int, total: int | None = None):
        self._lidas, self._total = lidas, total or self._total
        agora = time.perf_counter()
        if agora - self._ultima_escrita < 0.5:
            return
        self._ultima_escrita = agora
        self._executar("UPDATE imports SET linhas_gravadas = ? WHERE id = ?",
                       (lidas, self.import_id))

    def log(self, texto: str, nivel: str = "info"):
        self.eventos.append({"ts": time.strftime("%H:%M:%S"),
                             "nivel": nivel, "texto": str(texto).strip()})
        log.info("[import %s] %s", self.import_id, texto)
        self._salvar()

    # --- leitura ---
    def cancelado(self) -> bool:
        if self._cancelado:
            return True
        with db.conexao() as con:
            v = db.escalar(con, "SELECT cancelar_pedido FROM imports WHERE id = ?",
                           (self.import_id,))
        self._cancelado = bool(v)
        return self._cancelado

    def decorrido(self) -> float:
        return time.perf_counter() - self.t0

    class _Saida(StringIO):
        """Captura os print() do motor antigo para dentro do log da importacao."""

        def __init__(self, prog):
            super().__init__()
            self.prog = prog

        def write(self, texto):
            t = texto.strip()
            if t:
                self.prog.log(t, "motor")
            return len(texto)

    def como_saida(self):
        return Progresso._Saida(self)


def destravar_orfaos() -> int:
    """Importacoes que ficaram em andamento quando o servidor caiu.

    Sem isto, uma queda de energia deixaria a barra de progresso girando para
    sempre, sem nenhuma explicacao ao usuario.
    """
    marcas = ",".join("?" * len(ETAPAS_ATIVAS))
    with db.conexao() as con:
        n = db.escalar(con, f"SELECT count(*) FROM imports WHERE status IN ({marcas})",
                       ETAPAS_ATIVAS)
        if n:
            con.execute(
                f"UPDATE imports SET status='ERRO',"
                f" erro_mensagem='O servidor foi reiniciado durante esta importacao.',"
                f" erro_detalhe='Importe o arquivo de novo para concluir.',"
                f" concluido_em=datetime('now','localtime')"
                f" WHERE status IN ({marcas})", ETAPAS_ATIVAS)
            log.warning("%d importacao(oes) interrompida(s) foram marcadas como erro", n)
    return n or 0


def executar(import_id: int) -> None:
    """Ponto de entrada do worker.

    except BaseException e proposital: engine/config.exigir() levanta SystemExit,
    que herda de BaseException. Com `except Exception` o job morreria em silencio
    e a importacao ficaria travada em andamento para sempre.
    """
    prog = Progresso(import_id)
    try:
        _rodar(import_id, prog)
    except InterruptedError as e:
        with db.conexao() as con:
            con.execute(
                "UPDATE imports SET status='CANCELADO', etapa_atual=?, "
                "concluido_em=datetime('now','localtime'), duracao_seg=? WHERE id=?",
                (str(e), round(prog.decorrido(), 2), import_id))
        prog.log("Importacao cancelada.", "aviso")
    except BaseException as e:
        mensagem = traduzir(e)
        log.exception("Importacao %s falhou", import_id)
        prog.log(mensagem, "erro")
        with db.conexao() as con:
            con.execute(
                "UPDATE imports SET status='ERRO', erro_mensagem=?, erro_detalhe=?,"
                " concluido_em=datetime('now','localtime'), duracao_seg=? WHERE id=?",
                (mensagem, traceback.format_exc()[-4000:],
                 round(prog.decorrido(), 2), import_id))
    finally:
        gc.collect()


def _rodar(import_id: int, prog: Progresso) -> None:
    from pathlib import Path

    with db.conexao() as con:
        imp = db.uma(con, "SELECT * FROM imports WHERE id = ?", (import_id,))
    if not imp:
        raise ValueError(f"Importacao {import_id} nao existe.")

    modulo = registry.obter(imp["adaptador"])
    if modulo is None:
        raise ValueError(f"Adaptador desconhecido: {imp['adaptador']}")

    params = json.loads(imp["params_json"] or "{}")
    params["_sha"] = imp["sha256"]
    caminho = Path(imp["arquivo_path"])

    prog.etapa("Abrindo o arquivo", 0.02, status="ABRINDO")
    prog.log(f"Iniciando: {imp['arquivo_nome']} ({modulo.ROTULO}).")

    import tracemalloc
    tracemalloc.start()
    try:
        lote = modulo.abrir(caminho, params, prog)

        if prog.cancelado():
            raise InterruptedError("Cancelada antes de gravar.")

        prog.etapa("Analisando o conteudo (perfil do dado)", 0.25, status="PERFILANDO")
        perfil = profiler.perfilar(
            lote.colunas, n_linhas=lote.n_linhas, fonte=lote.fonte,
            descartadas=lote.descartadas, motivo_descarte=lote.motivo_descarte,
            amostras_descartadas=lote.amostras_descartadas,
            limitacoes=lote.limitacoes, avisos=lote.avisos,
            entidades=lote.entidades, periodo=lote.periodo,
            bytes_arquivo=imp["arquivo_bytes"], buscar_chaves=lote.buscar_chaves)
        prog.log(f"Perfil pronto: {len(lote.colunas)} colunas analisadas.")

        _gravar_perfil(import_id, perfil, lote)

        prog.etapa("Gravando os dados", 0.35, status="CARREGANDO")
        # Cada adaptador controla as proprias transacoes: o volume e o ritmo de
        # commit sao muito diferentes entre 368 linhas e 6,8 milhoes.
        con = db.conectar_carga()
        try:
            escritas = lote.gravar(con, import_id, prog)

            if lote.indices_pos_carga:
                prog.etapa("Criando indices", 0.86, status="INDEXANDO")
                from .loader import criar_indices
                criar_indices(con, lote.indices_pos_carga, prog)

            if lote.resumo_mensal:
                from .loader import materializar_resumo_mensal
                materializar_resumo_mensal(con, import_id, prog)

            db.encerrar_carga(con)
        finally:
            con.close()

        pico = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        periodo = lote.periodo or {}
        pmin, pmax = periodo.get("min"), periodo.get("max")

        with db.conexao() as con:
            con.execute(
                "UPDATE imports SET status='CONCLUIDO', progresso=1,"
                " etapa_atual='Concluida', linhas_lidas=?, linhas_gravadas=?,"
                " linhas_descartadas=?, motivo_descarte=?, periodo_min=?,"
                " periodo_max=?, duracao_seg=?, pico_memoria_mb=?,"
                " concluido_em=datetime('now','localtime') WHERE id=?",
                (lote.n_linhas + lote.descartadas, escritas, lote.descartadas,
                 lote.motivo_descarte,
                 pmin if isinstance(pmin, int) else None,
                 pmax if isinstance(pmax, int) else None,
                 round(prog.decorrido(), 2), round(pico, 1), import_id))
            audit.registrar(
                con, "IMPORT_CONCLUIDO",
                f"'{imp['arquivo_nome']}' importado: {escritas} registros gravados.",
                "imports", import_id,
                {"adaptador": imp["adaptador"], "linhas": escritas,
                 "descartadas": lote.descartadas})
        prog.log(f"Concluido em {prog.decorrido():.1f}s — "
                 f"{escritas} registros gravados.")
    finally:
        tracemalloc.stop()


def _gravar_perfil(import_id: int, perfil: dict, lote) -> None:
    novas = set(lote.colunas_novas)
    with db.transacao() as con:
        con.execute("DELETE FROM profiles WHERE import_id = ?", (import_id,))
        con.execute(
            "INSERT INTO profiles(import_id, duracao_ms, json) VALUES (?,?,?)",
            (import_id, perfil["dataset"]["duracao_ms"],
             json.dumps(perfil, ensure_ascii=False)))

        con.execute("DELETE FROM import_columns WHERE import_id = ?", (import_id,))
        linhas = []
        for c in perfil["colunas"]:
            eh_nova = c["nome"] in novas
            linhas.append((
                import_id, c["ordem"], c["nome"], c["nome_norm"],
                c["tipo_inferido"], c["papel"]["valor"], c["papel"]["confianca"],
                c["papel"]["evidencia"], int(eh_nova),
                "PENDENTE" if eh_nova else "ARMAZENAR",
                json.dumps({k: c[k] for k in
                            ("n_nulos", "pct_nulos", "n_distintos", "cardinalidade",
                             "numerico", "texto", "top", "exemplos", "problemas")},
                           ensure_ascii=False),
            ))
        con.executemany(
            "INSERT INTO import_columns(import_id, ordem, nome_original, nome_norm,"
            " tipo_detectado, papel_semantico, papel_confianca, papel_evidencia,"
            " eh_nova, decisao, stats_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)", linhas)
