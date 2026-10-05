"""F1 e F2 dentro da `executar_ciclo`.

F1 — `max_posts_por_ciclo > 1` nunca era respeitado: com o intervalo mínimo
maior que o espaçamento, o ciclo dava `break` na segunda oferta e postava 1
por ciclo, não importando o teto configurado. Agora a espera curta
(`aguardando_intervalo_minimo`, limitada ao próprio intervalo) é aguardada
dentro do ciclo; bloqueios longos (pausa de bloco, limite de período,
cadência ilegível) seguem quebrando o ciclo.

F2 — o link de afiliado do AliExpress só é gerado para as escolhidas (a API
`link.generate` tem cota da Open Platform), nunca para o lote coletado.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Redireciona data/cadencia.json, grok_cache e banco do usuário. Sem isto,
# `registrar_publicacao()` do singleton gravaria no cadência real do bot.
import isolamento  # noqa: F401,E402

from ofertas import pipeline  # noqa: E402
from ofertas.models import Oferta  # noqa: E402


def _oferta_ali(pid: str, preco: float, original: float, titulo: str) -> Oferta:
    return Oferta(
        plataforma="aliexpress",
        id_produto=pid,
        titulo=titulo,
        url_afiliado="",
        url_produto=f"https://pt.aliexpress.com/item/{pid}.html",
        preco=preco,
        preco_original=original,
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.banco_anterior = pipeline.db.DB_PATH
        pipeline.db.DB_PATH = Path(tempfile.mkdtemp(prefix="teste_ciclo_")) / "ofertas.db"
        pipeline.db.init_db()

    def tearDown(self):
        pipeline.db.DB_PATH = self.banco_anterior

    def _mundo(self, ofertas, pode, intervalo=300, max_ciclo=2, ciclo_minutos=45,
               dentro_do_horario=True):
        """Patcha o mundo do ciclo e devolve (posta, gera, dorme).

        `ExitStack` garante que, se um patch falhar no meio, os anteriores já
        aplicados sejam desfeitos — um leak aqui derrubava os testes seguintes
        do mesmo processo.

        `dentro_do_horario` entra no patch (e não vem do config.yaml da máquina):
        sem isto o F1 vira relógio — rodando de madrugada com `horario_ativo`
        preenchido no config local, a espera terminaria fora da janela e o ciclo
        quebraria sem ter nada a ver com o que está sendo testado.
        """
        from contextlib import ExitStack

        from ofertas.sources import aliexpress

        stack = ExitStack()
        stack.enter_context(patch.object(pipeline, "coletar", return_value=ofertas))
        stack.enter_context(patch.object(pipeline.db, "preco_ultima_postagem", return_value=None))
        stack.enter_context(patch.object(pipeline.db, "reservar", return_value=True))
        stack.enter_context(patch.object(pipeline.db, "liberar_reserva"))
        stack.enter_context(patch.object(pipeline.db, "registrar"))
        stack.enter_context(patch.object(pipeline.publishing_controller, "pode_publicar",
                                         side_effect=pode))
        stack.enter_context(patch.object(pipeline, "grok_service", MagicMock(ativo=False)))
        stack.enter_context(patch.object(pipeline.config, "max_posts_por_ciclo", max_ciclo))
        stack.enter_context(patch.object(pipeline.config, "espacamento_segundos", 1))
        stack.enter_context(patch.object(pipeline.config, "intervalo_entre_posts_segundos",
                                         intervalo))
        stack.enter_context(patch.object(pipeline.config, "intervalo_minutos", ciclo_minutos))
        _janela = dentro_do_horario
        if callable(_janela) or isinstance(_janela, (list, tuple)):
            # Respostas em sequência: o topo do ciclo e a checagem depois da
            # espera precisam dar respostas diferentes para o teste do F3.
            stack.enter_context(patch.object(pipeline, "dentro_do_horario",
                                             side_effect=_janela))
        else:
            stack.enter_context(patch.object(pipeline, "dentro_do_horario",
                                             return_value=_janela))
        stack.enter_context(patch.object(pipeline, "postar_oferta", new_callable=AsyncMock))
        stack.enter_context(patch.object(aliexpress, "gerar_link_afiliado",
                                         side_effect=lambda url: "https://s.click.aliexpress.com/e/_sub"))
        stack.enter_context(patch("asyncio.sleep", new_callable=AsyncMock))
        self.addCleanup(stack.close)
        return pipeline.postar_oferta, aliexpress.gerar_link_afiliado, __import__("asyncio").sleep

    def _ciclo(self, ofertas, pode, **kw):
        postar, gera, dorme = self._mundo(ofertas, pode, **kw)
        n = asyncio.run(pipeline.executar_ciclo(MagicMock()))
        return n, gera, postar, dorme


class TestF2AliLinkSoEscolhidas(Base):
    def test_gera_link_apenas_das_escolhidas(self):
        ofertas = [
            _oferta_ali("1005000000001", 10.0, 20.0, "Produto Um"),
            _oferta_ali("1005000000002", 20.0, 30.0, "Produto Dois"),
            _oferta_ali("1005000000003", 30.0, 31.0, "Produto Tres"),
        ]
        n, gera, postar, _ = self._ciclo(ofertas, pode=[(True, "ok", 0.0)] * 5)

        self.assertEqual(n, 2)
        self.assertEqual(len(postar.await_args_list), 2)
        self.assertEqual(len(gera.call_args_list), 2,
                         "não pode gerar link para o que não foi escolhido")
        urls = {c.args[0] for c in gera.call_args_list}
        self.assertEqual(urls, {
            "https://pt.aliexpress.com/item/1005000000001.html",
            "https://pt.aliexpress.com/item/1005000000002.html",
        })


class TestF1EsperaIntervalo(Base):
    def test_espera_o_intervalo_e_publica_o_ciclo_inteiro(self):
        ofertas = [
            _oferta_ali("1005000000001", 10.0, 20.0, "Primeiro"),
            _oferta_ali("1005000000002", 20.0, 30.0, "Segundo"),
        ]
        n, _, postar, dorme = self._ciclo(
            ofertas,
            pode=[(False, "aguardando_intervalo_minimo (210s restantes)", 210.0),
                  (True, "ok", 0.0),
                  (True, "ok", 0.0)])

        self.assertEqual(n, 2, "sem a espera o ciclo postaria 1 (ou 0)")
        self.assertEqual(len(postar.await_args_list), 2)
        self.assertTrue(
            any(c.args == (210.0,) for c in dorme.await_args_list),
            f"esperava dormir 210s dentro do ciclo; dormiu: "
            f"{[c.args for c in dorme.await_args_list]}")

    def test_bloqueio_longo_continua_quebrando_o_ciclo(self):
        ofertas = [
            _oferta_ali("1005000000001", 10.0, 20.0, "Primeiro"),
            _oferta_ali("1005000000002", 20.0, 30.0, "Segundo"),
        ]
        n, _, postar, dorme = self._ciclo(
            ofertas,
            pode=[(False, "limite_periodo_atingido (20/20 em 24h)", 7200.0)])

        self.assertEqual(n, 0)
        self.assertEqual(postar.await_args_list, [])
        self.assertEqual(dorme.await_args_list, [],
                         "bloqueio longo não se espera dentro do ciclo")

    def test_espera_maior_que_o_ciclo_quebra_em_vez_de_segurar(self):
        """Esperar mais que o intervalo entre ciclos atrasa o agendamento.

        O JobQueue não empilha execuções do mesmo job: um ciclo que segura o
        evento por mais tempo que `intervalo_minutos` faz o próximo ciclo ser
        perdido. Quebrar é melhor — o próximo ciclo chega antes de o slot abrir.
        """
        ofertas = [
            _oferta_ali("1005000000001", 10.0, 20.0, "Primeiro"),
            _oferta_ali("1005000000002", 20.0, 30.0, "Segundo"),
        ]
        n, _, postar, dorme = self._ciclo(
            ofertas,
            pode=[(False, "aguardando_intervalo_minimo (3600s restantes)", 3600.0),
                  (True, "ok", 0.0)],
            ciclo_minutos=25)

        self.assertEqual(n, 0)
        self.assertEqual(postar.await_args_list, [])
        self.assertEqual(dorme.await_args_list, [],
                         "espera maior que o ciclo não pode segurar o ciclo")

    def test_espera_que_atravessa_o_fim_da_janela_nao_posta(self):
        """A espera do intervalo não pode empurrar o post para fora da janela.

        Com "07:00-23:00" e a última publicação às 22:41, o intervalo de 20 min
        só termina às 23:01. A checagem do topo do ciclo já passou às 22:50,
        então sem a segunda checagem o bot postaria às 23:01 — fora do horário
        que o painel promete.
        """
        ofertas = [
            _oferta_ali("1005000000001", 10.0, 20.0, "Primeiro"),
            _oferta_ali("1005000000002", 20.0, 30.0, "Segundo"),
        ]
        n, _, postar, dorme = self._ciclo(
            ofertas,
            pode=[(False, "aguardando_intervalo_minimo (1200s restantes)", 1200.0),
                  (True, "ok", 0.0),
                  (True, "ok", 0.0)],
            intervalo=1200,
            ciclo_minutos=25,
            dentro_do_horario=[True, False, False])

        self.assertEqual(n, 0)
        self.assertEqual(postar.await_args_list, [],
                         "postou fora da janela ativa depois de esperar o intervalo")
        self.assertTrue(
            any(c.args == (1200.0,) for c in dorme.await_args_list),
            f"a espera do intervalo foi feita; só não pode virar post; "
            f"dormiu: {[c.args for c in dorme.await_args_list]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)