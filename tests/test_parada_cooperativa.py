"""A coleta precisa ceder o caminho quando o serviço está encerrando.

O sintoma que estes testes existem para impedir: o bot recebia SIGTERM no meio
do ciclo e continuava coletando. Não por bug no handler — o `SystemExit` do
PTB desenroscava a thread principal na hora. O problema é que a coleta roda em
`asyncio.to_thread`, e o interpretador, ao sair, espera as threads não-daemon
terminarem. Sem ponto de parada, essa thread levava os ~10 minutos do ciclo
todo: o `TimeoutStopSec` de 30s estourava e o systemd matava o processo com
SIGKILL no meio da coleta.

Um restart, então, custava um ciclo inteiro de coleta jogado fora. E, pior: o
SIGKILL acontece no meio do trabalho, sem chance de o estado ser gravado.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Redireciona data/cadencia.json, grok_cache e banco do usuário.
import isolamento  # noqa: F401,E402

from ofertas import parada, pipeline  # noqa: E402
from ofertas.models import Oferta  # noqa: E402

filtrar = pipeline.filtrar


def _oferta(uid: str) -> Oferta:
    return Oferta(
        plataforma="shopee",
        id_produto=uid,
        titulo=f"Produto {uid} para teste de parada",
        url_afiliado="",
        url_produto=f"https://shopee.com.br/item/{uid}",
        preco=10.0,
        preco_original=20.0,
    )


def _oferta_postavel(uid: str, titulo: str) -> Oferta:
    """Oferta que PASSA o filtro e chega na hora de postar.

    Importa: o ciclo tem três camadas que descartariam a oferta antes da
    postagem — `url_afiliado` vazio, preço repetido e equivalência de conteúdo
    com o que já saiu no mesmo lote. Com ofertas homogêneas, um teste que
    verifica "não postou" passaria mesmo SEM a proteção que está sendo testada,
    porque o descarte viria de outra camada.

    Os títulos são deliberadamente sem palavra em comum: com um texto de
    preenchimento ("... para teste de parada"), `_equivalente_a_postado` acusava
    as duas de serem o mesmo produto e a segunda nunca chegava à postagem.
    """
    return Oferta(
        plataforma="shopee",
        id_produto=uid,
        titulo=titulo,
        url_afiliado=f"https://shopee.com.br/item/{uid}?af=x",
        url_produto=f"https://shopee.com.br/item/{uid}",
        preco=10.0 + int(uid) * 7,
        preco_original=20.0 + int(uid) * 7,
    )


class TestEventoDeParada(unittest.TestCase):
    """O `Event` em si — inclusive que o ciclo novo não herda a parada antiga."""

    def tearDown(self):
        parada.limpar()

    def test_comeca_sem_parada(self):
        self.assertFalse(parada.pedido())

    def test_pedir_marca_e_limpar_desmarca(self):
        parada.pedir()
        self.assertTrue(parada.pedido())
        parada.limpar()
        self.assertFalse(parada.pedido())

    def test_limpar_e_idempotente(self):
        parada.limpar()
        parada.limpar()
        self.assertFalse(parada.pedido())


class TestColetarCede(unittest.TestCase):
    """`coletar` para entre as fontes, e devolve o que já juntou."""

    def setUp(self):
        parada.limpar()
        self.fontes = MagicMock()
        self.fontes.buscar_ofertas.side_effect = lambda *a, **k: [_oferta("x")]

    def tearDown(self):
        parada.limpar()

    def _mundo(self, ativas):
        """Deixa as 4 fontes ativas no config, com `buscar_ofertas` controllado."""
        return [
            patch.object(pipeline.config, "fonte_shopee", {"ativa": "shopee" in ativas}),
            patch.object(pipeline.config, "fonte_amazon", {"ativa": "amazon" in ativas}),
            patch.object(pipeline.config, "fonte_ml", {"ativa": "ml" in ativas}),
            patch.object(pipeline.config, "fonte_aliexpress", {"ativa": "ali" in ativas}),
            patch.object(pipeline.config, "shopee_app_id", "id"),
            patch.object(pipeline.config, "shopee_app_secret", "sec"),
            patch.object(pipeline.config, "amazon_tag", "tag"),
            patch.object(pipeline.config, "aliexpress_app_key", "k"),
            patch.object(pipeline.config, "aliexpress_app_secret", "s"),
            patch.object(pipeline, "shopee", self.fontes),
            patch.object(pipeline, "amazon", self.fontes),
            patch.object(pipeline, "mercadolivre", self.fontes),
            patch.object(pipeline, "aliexpress", self.fontes),
        ]

    def test_parada_antes_de_comecar_nao_chega_nem_a_primeira_fonte(self):
        parada.pedir()
        with _patchados(self._mundo({"shopee", "amazon", "ml", "ali"})):
            resultado = pipeline.coletar()
        self.assertEqual(resultado, [])
        self.fontes.buscar_ofertas.assert_not_called()

    def test_parada_entre_as_fontes_para_ali(self):
        """A primeira fonte roda; ao terminar, a parada impede a segunda."""
        chamadas: list[str] = []

        def buscar(*_a, **_k):
            chamada = len(chamadas)
            chamadas.append("x")
            if chamada == 0:
                # A parada chega DEPOIS da primeira fonte, como quando o
                # SIGTERM cai entre a Shopee e o Mercado Livre.
                parada.pedir()
            return [_oferta(f"o{chamada}")]

        self.fontes.buscar_ofertas.side_effect = buscar
        with _patchados(self._mundo({"shopee", "amazon", "ml", "ali"})):
            resultado = pipeline.coletar()

        self.assertEqual(len(resultado), 1)
        self.assertEqual(len(chamadas), 1)

    def test_sem_parada_todas_as_fontes_rodam(self):
        """Contraprova: a checagem não está cortando o caminho normal."""
        with _patchados(self._mundo({"shopee", "amazon", "ml", "ali"})):
            resultado = pipeline.coletar()
        self.assertEqual(self.fontes.buscar_ofertas.call_count, 4)
        self.assertEqual(len(resultado), 4)


class TestCicloNaoPostaDepoisDaParada(unittest.TestCase):
    """A parada durante a coleta impede a publicação, e a janela é limpa."""

    def setUp(self):
        self.postas: list[str] = []

    def tearDown(self):
        parada.limpar()

    def _ciclo(self, ao_coletar):
        # `coletar` é sincrona: `executar_ciclo` a joga numa thread com
        # `asyncio.to_thread`. Uma `async def` aqui devolveria uma corrotina
        # não aguardada, e o teste estaria medindo a coisa errada.
        def coletar_que_aborta():
            ofertas = [_oferta_postavel("101", "Furadeira Impacto 710W"),
                       _oferta_postavel("202", "Cozedor Ovos Bluetooth")]
            ao_coletar()
            return ofertas

        return [
            patch.object(pipeline, "coletar", side_effect=coletar_que_aborta),
            patch.object(pipeline, "dentro_do_horario", return_value=True),
            patch.object(pipeline.db, "preco_ultima_postagem", return_value=None),
            patch.object(pipeline.db, "reservar", return_value=True),
            patch.object(pipeline.db, "registrar"),
            # `max_posts_por_ciclo` vem do config.yaml da máquina; sem fixar,
            # este teste passa a medir o ajuste do dono, não a parada.
            patch.object(pipeline.config, "max_posts_por_ciclo", 2),
            patch.object(pipeline.config, "espacamento_segundos", 0),
            patch.object(pipeline.config, "intervalo_entre_posts_segundos", 0),
            patch.object(pipeline.publishing_controller, "pode_publicar",
                         return_value=(True, "", 0)),
            patch.object(pipeline, "grok_service", MagicMock(ativo=False)),
            patch.object(pipeline, "postar_oferta",
                         side_effect=self._postou),
        ]

    def _postou(self, _bot, oferta, _chat):
        self.postas.append(oferta.uid)

    def test_parada_durante_a_coleta_nao_posta_nada(self):
        with _patchados(self._ciclo(parada.pedir)):
            bot = MagicMock()
            bot.send_message = MagicMock()
            import asyncio
            total = asyncio.run(pipeline.executar_ciclo(bot))
        self.assertEqual(total, 0)
        self.assertEqual(self.postas, [])

    def test_ciclo_novo_limpa_a_parada_do_ciclo_anterior(self):
        """A parada do encerramento não pode contaminar o ciclo das próximas horas.

        A parada pendurada é o pior jeito de falhar aqui: o processo já foi
        reiniciado, ninguém pede parada de novo, e mesmo assim todo ciclo
        sairia no `return 0` logo após coletar. O canal ficaria mudo sem
        nenhuma pista no log. Por isso o alvo é o `filtrar`: chegar nele prova
        que o ciclo passou pela checagem e seguiu.
        """
        import asyncio

        parada.pedir()
        with _patchados(self._ciclo(lambda: None)):
            with patch.object(pipeline, "filtrar", side_effect=filtrar) as viu_filtrar:
                bot = MagicMock()
                bot.send_message = MagicMock()
                asyncio.run(pipeline.executar_ciclo(bot))

        self.assertFalse(parada.pedido(), "a janela antiga de parada sobreviveu ao ciclo")
        viu_filtrar.assert_called_once()
        # Contraprova: as MESMAS ofertas, sem parada pendurada, chegam a
        # postar. Se nem isso postasse, o teste acima não provaria nada.
        self.assertEqual(len(self.postas), 2)


import contextlib


@contextlib.contextmanager
def _patchados(contextos):
    with contextlib.ExitStack() as stack:
        for c in contextos:
            stack.enter_context(c)
        yield


class TestFontesCedem(unittest.TestCase):
    """Cada fonte tem que ter o seu próprio ponto de parada.

    Checar só em `coletar` não resolve: a fonte mais lenta (Mercado Livre)
    leva minutos sozinha dentro do laço, e é exatamente ali que o processo
    ficava pendurado.
    """

    def tearDown(self):
        parada.limpar()

    def test_shopee_para_entre_termos(self):
        from ofertas.sources import shopee

        # Os termos vêm de `fonte_shopee["buscas"]`. Sem patchar isso, o teste
        # vira só CONFIG da máquina: no repo de trabalho há buscas e o laço
        # roda; numa cópia com config.yaml mínimo não há, a função cai no
        # caminho da lista de destaque e vai bater na rede de verdade.
        with patch.object(shopee, "sessao", MagicMock()), \
             patch.object(shopee, "_chamar", MagicMock()), \
             patch.object(shopee, "_buscar_keyword") as buscar, \
             patch.object(shopee.config, "fonte_shopee",
                          {"ativa": True, "limite": 30, "buscas": ["a", "b", "c"]}):
            parada.pedir()
            resultado = shopee.buscar_ofertas(30)

        buscar.assert_not_called()
        self.assertEqual(resultado, [])

    def test_amazon_para_entre_tarefas(self):
        from ofertas.sources import amazon

        tarefas = [{"rotulo": f"t{i}", "params": {"i": str(i)}} for i in range(3)]
        with patch.object(amazon, "sessao", MagicMock()), \
             patch.object(amazon, "_sessao", MagicMock()), \
             patch.object(amazon, "_buscar_por_scraping", return_value=[]), \
             patch.object(amazon, "_tarefas_do_ciclo", return_value=tarefas):
            parada.pedir()
            # `_buscar_por_scraping` é a própria fonte; o teste real é o laço
            # interno, verificado com uma sessao que registra as chamadas.
            with patch.object(amazon.config, "fonte_amazon", {"ativa": True, "paginas": 2}):
                resultado = amazon._buscar_por_scraping(tarefas)
        self.assertEqual(resultado, [])

    def test_mercadolivre_para_entre_paginas(self):
        from ofertas.sources import mercadolivre

        resposta = MagicMock()
        resposta.text = "<html></html>"
        resposta.raise_for_status = MagicMock()
        sessao = MagicMock()
        sessao.get.return_value = resposta

        with patch.object(mercadolivre, "sessao", return_value=sessao), \
             patch.object(mercadolivre, "_categorias",
                          return_value={"c1": "um", "c2": "dois"}), \
             patch.object(mercadolivre, "_parse_pagina", return_value=[]), \
             patch.object(mercadolivre.time, "sleep"), \
             patch.object(mercadolivre.config, "fonte_ml", {"ativa": True, "paginas": 2}):
            parada.pedir()
            mercadolivre.buscar_ofertas()

        # Com a parada pedida, nenhuma requisição é feita — nem a primeira.
        sessao.get.assert_not_called()


class TestHandlerDeSinal(unittest.TestCase):
    """O handler pede a parada ANTES de desenroscar, nessa ordem."""

    def tearDown(self):
        parada.limpar()

    def test_handler_pede_parada_e_levanta_systemexit(self):
        import signal

        anterior = signal.getsignal(signal.SIGTERM)
        try:
            # O callback que o `instalar_handlers` registra e passa para a
            # parada. Exercitamos o handler DIRETO (sem sinal real, para não
            # matar o processo de teste).
            parada.instalar_handlers(parada.pedir)
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler), "SIGTERM ficou sem handler")
            with self.assertRaises(SystemExit) as ctx:
                handler(signal.SIGTERM, None)
            self.assertEqual(ctx.exception.code, 128 + int(signal.SIGTERM))
            self.assertTrue(parada.pedido(),
                            "a parada tem de estar pedida ANTES do SystemExit: "
                            "é o que faz a thread da coleta ceder")
        finally:
            signal.signal(signal.SIGTERM, anterior)

    def test_falha_ao_pedir_parada_nao_impede_a_saida(self):
        """Um erro dentro do pedido custaria o encerramento: não pode."""
        import signal

        def explode():
            raise RuntimeError("de proposito")

        anterior = signal.getsignal(signal.SIGTERM)
        try:
            parada.instalar_handlers(explode)
            with self.assertRaises(SystemExit):
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        finally:
            signal.signal(signal.SIGTERM, anterior)


if __name__ == "__main__":
    unittest.main(verbosity=2)