"""O scraper recebia update do Telegram e não capturava nada.

O sintoma era silêncio: o userbot conectava, logava "Monitorando 1 fontes
ativas", e as mensagens seguiam chegando ao banco dezeras. `ultima_msg_id`
ficava no zero e `mensagens_telegram` vazia. E o pior: o próprio log escondia
a causa, porque o handler voltava *antes* da primeira linha de log.

A causa: o handler casava a mensagem com a fonte pelo username, montando
"@nerdofertas" a partir de `chat.username`. Para canal, esse campo chega
`None` — o Telethon devolve o que está no cache de entidades da sessão, e ali
só há id e título. Com o username vazio, nenhuma das três candidatas batia com
a chave cadastrada, e a função devolvia None: três mensagens do dia inteiras
descartadas sem um único registro.

Aqui o problema é testado pelo ângulo que o reproduce: com o username
ausente, que é como o Telegram entrega. Os testes que cobrem só o caminho com
username passavam antes e depois da correção, sem ver nada.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import db
from ofertas.sources import telegram_userbot as ub

ID_NERD = 1465877129
OUTRO_CHAT = 3987480199


def _normaliza(chat_id: str) -> str:
    """Reduz as três formas de escrever o mesmo id do Telegram a um número."""
    return str(chat_id).strip().removeprefix("-100")


class Entidade:
    def __init__(self, id, username=None, title="", first_name=""):
        self.id = id
        self.username = username
        self.title = title
        self.first_name = first_name
        self.last_name = ""


class Mensagem:
    def __init__(self, id, texto="", chat_id=ID_NERD, photo=None):
        self.id = id
        self.raw_text = texto
        self.chat_id = chat_id
        self.photo = photo


class ClienteFalso:
    """Cliente Telethon mínimo: resolve entidade por chave e devolve histórico.

    Reproduz de propósito a limitação que derrubou o scraper: a entidade
    devolvida NÃO tem username, igual à que o Telethon monta a partir do cache
    de entidades da sessão. Resolver "@nerdofertas" dá certo e mesmo assim
    continua sem username — por isso o código não pode depender dele.
    """

    def __init__(self, ids_por_chave=None, historico=None, resolucoes=None):
        self.ids_por_chave = dict(ids_por_chave or {})
        self.resolucoes = {"@nerdofertas": ID_NERD}
        if resolucoes is not None:
            self.resolucoes = dict(resolucoes)
        self.historico = list(historico or [])
        self.entidades_chamadas = []
        self.handlers = {}
        self.conectado = False
        self.bytes_da_foto = b"\xf0\x9f\x93\xb7 bytes-da-foto"
        self.erro_download = False
        self.downloads = []

    # -- Telegram -------------------------------------------------------
    async def download_media(self, message, file=bytes):
        """Mínimo que o userbot precisa para levar a foto ao pipeline."""
        self.downloads.append(message)
        if self.erro_download:
            raise RuntimeError("a rede caiu no meio do download")
        return self.bytes_da_foto

    # -- ciclo de vida -------------------------------------------------
    def is_connected(self):
        return self.conectado

    async def connect(self):
        self.conectado = True

    async def is_user_authorized(self):
        return True

    async def get_me(self):
        return Entidade(1382089335, username="fastzera", title="fastzera", first_name="fastzera")

    def on(self, evento):
        def registrar(func):
            self.handlers[evento] = func
            return func
        return registrar

    # -- dados --------------------------------------------------------
    async def get_entity(self, alvo):
        self.entidades_chamadas.append(str(alvo))
        chave = str(alvo).strip()
        if chave.lower() in self.resolucoes:
            return Entidade(self.resolucoes[chave.lower()], title="NERD OFERTAS")
        if chave in self.ids_por_chave:
            return Entidade(self.ids_por_chave[chave])
        if _normaliza(chave).isdigit() and int(_normaliza(chave)) == ID_NERD:
            return Entidade(ID_NERD, title="NERD OFERTAS")
        raise ValueError(f"entidade desconhecida: {alvo}")

    def iter_messages(self, entidade, min_id=0, limit=0):
        # Ignora `limit` de propósito: o teto é responsabilidade do código, e
        # um teste que só passa porque o mock é obediente não prova nada.
        async def gerador():
            for m in self.historico:
                if m.id > min_id:
                    yield m
        return gerador()


class EventoFalso:
    def __init__(self, chat_id, texto, message_id, username=None, title="NERD OFERTAS",
                 photo=None):
        self.chat_id = chat_id
        self.id = message_id
        self.raw_text = texto
        self.username = username
        self.title = title
        self.message = type("M", (), {"message": texto, "id": message_id, "photo": photo})()

    async def get_chat(self):
        return Entidade(self.chat_id, username=self.username, title=self.title)


class BaseUserbot(unittest.TestCase):
    def setUp(self):
        self.banco_anterior = db.DB_PATH
        self.pasta = tempfile.mkdtemp(prefix="teste_userbot_")
        db.DB_PATH = Path(self.pasta) / "ofertas.db"
        db.init_db()
        ub._indice_por_id.clear()
        ub._ids_por_chave.clear()
        ub._chaves_ja_resolvidas.clear()
        # A idempotência do iniciar_userbot mora num global de módulo: sem o
        # reset, o primeiro teste registra o handler e os seguintes batem na
        # guarda e devolvem True sem registrar nada (handlers vazios).
        ub._monitor_iniciado = False

    def tearDown(self):
        db.DB_PATH = self.banco_anterior
        ub._indice_por_id.clear()
        ub._ids_por_chave.clear()
        ub._chaves_ja_resolvidas.clear()


# ─────────────────────────────────────────────────────────────────────
# 1. O bug: casar a fonte pelo id, e não pelo username que não vem
# ─────────────────────────────────────────────────────────────────────

class TestChaveDoChat(BaseUserbot):
    def test_encontra_fonte_cadastrada_por_username_sem_o_username_chegar(self):
        """A forma exata da falha: fonte é "@nerdofertas", chat chega sem username."""
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        cliente = ClienteFalso()
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))

        achada = asyncio.run(ub._chave_do_chat(cliente, ID_NERD, str(ID_NERD), ""))
        self.assertEqual(achada, "@nerdofertas")

    def test_sem_a_correcao_o_username_vazio_nao_encontra_nada(self):
        """Documenta a falha original: só o username casava, e ele não vem."""
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        self.assertIsNone(ub._chave_cadastrada(str(ID_NERD), ""))

    def test_fonte_cadastrada_por_id_completo(self):
        db.salvar_fonte_telegram(f"-100{ID_NERD}", "NERD OFERTAS")
        cliente = ClienteFalso()
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))
        achada = asyncio.run(ub._chave_do_chat(cliente, ID_NERD, str(ID_NERD), ""))
        self.assertEqual(achada, f"-100{ID_NERD}")

    def test_fonte_cadastrada_por_id_curto(self):
        db.salvar_fonte_telegram(str(ID_NERD), "NERD OFERTAS")
        cliente = ClienteFalso()
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))
        achada = asyncio.run(ub._chave_do_chat(cliente, ID_NERD, str(ID_NERD), ""))
        self.assertEqual(achada, str(ID_NERD))

    def test_chat_que_nao_e_fonte_devolve_none(self):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        cliente = ClienteFalso()
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))
        achada = asyncio.run(ub._chave_do_chat(cliente, OUTRO_CHAT, str(OUTRO_CHAT), ""))
        self.assertIsNone(achada)

    def test_fonte_adicionada_com_o_bot_ja_no_ar_e_resolvida(self):
        """Fonte cadastrada depois do startup ainda tem de ser capturada.

        O teste anterior desta ideia usava uma fonte por id, e o `_chave_cadastrada`
        antigo acertava na queda — o teste passava mesmo com a resolução sob
        demanda desligada. Aqui a fonte é "@nerdofertas": só o índice acha.
        """
        cliente = ClienteFalso()
        asyncio.run(ub._montar_indice_fontes(cliente, []))

        # O dono cadastra a fonte pelo username com o bot no ar.
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")

        achada = asyncio.run(ub._chave_do_chat(cliente, ID_NERD, str(ID_NERD), ""))
        self.assertEqual(achada, "@nerdofertas")

    def test_fonte_que_o_telegram_nao_resolve_nao_trava_o_monitor(self):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        db.salvar_fonte_telegram("@nao_existe_esse_canal", "Fantasma")
        cliente = ClienteFalso()
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))
        achada = asyncio.run(ub._chave_do_chat(cliente, ID_NERD, str(ID_NERD), ""))
        self.assertEqual(achada, "@nerdofertas")


# ─────────────────────────────────────────────────────────────────────
# 2. O handler completo: a mensagem chega ao pipeline
# ─────────────────────────────────────────────────────────────────────

class TestHandlerCaptura(BaseUserbot):
    def _subir(self, cliente):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        with patch.object(ub, "tem_credenciais", return_value=True), \
             patch.object(ub, "tem_sessao_salva", return_value=True), \
             patch.object(ub, "_cliente_global", cliente), \
             patch.object(ub, "_recuperar_perdidas", new=AsyncMock(return_value=0)):
            return asyncio.run(ub.iniciar_userbot(bot_poster=None, dry_run=True))

    def test_mensagem_do_canal_chega_ao_pipeline(self):
        cliente = ClienteFalso()
        self.assertTrue(self._subir(cliente))
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            evento = EventoFalso(ID_NERD, "Fone Bluetooth\nhttps://shopee.com.br/product/123456/1", 5001)
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))

        pipeline.assert_awaited_once()
        self.assertEqual(pipeline.await_args.kwargs["message_id"], 5001)
        self.assertEqual(pipeline.await_args.kwargs["source_id"], "@nerdofertas")

    def test_mensagem_com_foto_baixa_os_bytes_e_lega_ao_pipeline(self):
        """A foto que o grupo já tem deve atravessar a captura (hoje era descartada)."""
        cliente = ClienteFalso()
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            evento = EventoFalso(ID_NERD, "Fone com foto\nhttps://shopee.com.br/product/123456/1",
                                 5003, photo=object())
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))
        pipeline.assert_awaited_once()
        self.assertEqual(pipeline.await_args.kwargs["imagem_url"], cliente.bytes_da_foto)
        self.assertEqual(len(cliente.downloads), 1)

    def test_mensagem_sem_foto_nao_tenta_baixar_nada(self):
        cliente = ClienteFalso()
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            evento = EventoFalso(ID_NERD, "Só texto\nhttps://shopee.com.br/product/123456/1", 5004)
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))
        pipeline.assert_awaited_once()
        self.assertIsNone(pipeline.await_args.kwargs["imagem_url"])
        self.assertEqual(len(cliente.downloads), 0)

    def test_falha_ao_baixar_a_foto_nao_derruba_a_captura(self):
        """Rede caiu no download? A mensagem segue sem foto, não some do pipeline."""
        cliente = ClienteFalso()
        cliente.erro_download = True
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            evento = EventoFalso(ID_NERD, "Foto quebrada\nhttps://shopee.com.br/product/123456/1",
                                 5005, photo=object())
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))
        pipeline.assert_awaited_once()
        self.assertIsNone(pipeline.await_args.kwargs["imagem_url"])
        self.assertEqual(pipeline.await_args.kwargs["message_id"], 5005)

    def test_recuperacao_tambem_carrega_a_foto_da_mensagem_perdida(self):
        cliente = ClienteFalso()
        self._subir(cliente)
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 100)
        cliente.historico = [Mensagem(150, "Oferta\nhttps://shopee.com.br/product/9/8", photo=object())]
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            asyncio.run(ub._recuperar_perdidas(cliente, None, dry_run=True))
        pipeline.assert_awaited_once()
        self.assertEqual(pipeline.await_args.kwargs["imagem_url"], cliente.bytes_da_foto)
        self.assertEqual(pipeline.await_args.kwargs["message_id"], 150)

    def test_mensagem_capturada_marca_ultima_mensagem_da_fonte(self):
        cliente = ClienteFalso()
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})):
            evento = EventoFalso(ID_NERD, "Oferta com https://shopee.com.br/product/123456/1", 5002)
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))

        fonte = db.listar_fontes_telegram()[0]
        self.assertEqual(fonte["ultima_msg_id"], 5002)

    def test_mensagem_de_outro_chat_nao_chega_ao_pipeline(self):
        cliente = ClienteFalso()
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            evento = EventoFalso(OUTRO_CHAT, "Grupo qualquer", 6001)
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))
        pipeline.assert_not_awaited()

    def test_mensagem_do_canal_de_destino_e_ignorada(self):
        """Anti-loop: o bot não deve recolher o que ele mesmo publicou."""
        from ofertas.config import config
        destino = int(str(config.chat_id).removeprefix("-100"))
        cliente = ClienteFalso()
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            evento = EventoFalso(destino, "Post do bot", 7001)
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))
        pipeline.assert_not_awaited()

    def test_erro_do_pipeline_nao_derruba_o_monitor(self):
        cliente = ClienteFalso()
        self._subir(cliente)
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(side_effect=RuntimeError("link builder morreu"))):
            evento = EventoFalso(ID_NERD, "Oferta com https://shopee.com.br/product/123456/1", 5003)
            asyncio.run(cliente.handlers[list(cliente.handlers)[0]](evento))
        # Continua registrado para a próxima mensagem.
        self.assertTrue(cliente.handlers)


# ─────────────────────────────────────────────────────────────────────
# 3. Recuperação do que chegou enquanto o bot estava fora
# ─────────────────────────────────────────────────────────────────────

class TestRecuperacao(BaseUserbot):
    def test_recupera_somente_o_que_ficou_para_tras(self):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 1000)
        cliente = ClienteFalso(historico=[
            Mensagem(1003, "terceira\nhttps://shopee.com.br/product/333333/1"),
            Mensagem(1002, "segunda\nhttps://shopee.com.br/product/222222/1"),
            Mensagem(1001, "primeira\nhttps://shopee.com.br/product/111111/1"),
            Mensagem(1000, "ja processada antes"),
        ])
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))

        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            total = asyncio.run(ub._recuperar_perdidas(cliente, bot_poster=None, dry_run=True))

        self.assertEqual(total, 3)
        self.assertEqual([c.kwargs["message_id"] for c in pipeline.await_args_list],
                         [1001, 1002, 1003])

    def test_respeita_o_teto_de_mensagens(self):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 1000)
        cliente = ClienteFalso(historico=[Mensagem(1000 + i, f"msg {i}") for i in range(1, 400)])
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))

        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})):
            total = asyncio.run(ub._recuperar_perdidas(cliente, bot_poster=None, dry_run=True))
        self.assertEqual(total, ub.MAX_MSG_RECUPERACAO)

    def test_fonte_que_nunca_capturou_nao_despeja_historico(self):
        """Sem marcação não há onde recuar — e o canal tem 140 mil mensagens."""
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        cliente = ClienteFalso(historico=[Mensagem(i, f"antiga {i}") for i in range(1, 50)])
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))

        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            total = asyncio.run(ub._recuperar_perdidas(cliente, bot_poster=None, dry_run=True))
        self.assertEqual(total, 0)
        pipeline.assert_not_awaited()

    def test_fonte_desligada_nao_e_recuperada(self):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 1000)
        db.atualizar_status_fonte_telegram("@nerdofertas", False)
        cliente = ClienteFalso(historico=[Mensagem(1001, "perdida")])
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))

        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            total = asyncio.run(ub._recuperar_perdidas(cliente, bot_poster=None, dry_run=True))
        self.assertEqual(total, 0)
        pipeline.assert_not_awaited()

    def test_uma_fonte_que_erra_nao_impede_as_outras(self):
        db.salvar_fonte_telegram("@nerdofertas", "NERD OFERTAS")
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 1000)
        db.salvar_fonte_telegram("-1009999999", "Fonte quebrada")
        db.marcar_ultima_mensagem_fonte("-1009999999", 1000)

        cliente = ClienteFalso(historico=[Mensagem(1001, "recuperada")])
        # A fonte quebrada não resolve; a boa continua funcionando.
        asyncio.run(ub._montar_indice_fontes(cliente, db.listar_fontes_telegram(ativas_apenas=True)))
        with patch.object(ub.pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True})) as pipeline:
            total = asyncio.run(ub._recuperar_perdidas(cliente, bot_poster=None, dry_run=True))
        self.assertEqual(total, 1)
        self.assertEqual(pipeline.await_args.kwargs["source_id"], "@nerdofertas")


if __name__ == "__main__":
    unittest.main(verbosity=2)
