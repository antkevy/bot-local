"""Testes da autenticação do Mercado Livre (cookie-only).

Cobre os cenários exigidos adaptados ao modelo atual:
1. Cookie válido -> gera link.
2. Sem cookie -> não publica + salva pendência + notifica admin.
3. Cookie expirado/inválido -> não publica + salva pendência.
4. Novo cookie válido -> validado, salvo e reprocessa pendências.
5. Novo cookie inválido -> mantém o anterior.
6. 100 falhas -> uma única notificação (cooldown anti-spam).
7. Autenticação renovada -> processa pendências sem duplicar.
8. Oferta já publicada -> não duplica no retry.
9. Erro temporário -> diferenciado de cookie expirado.
10. Fluxo completo scraper -> Grok -> cookie -> afiliado -> publicação.
11-13. Normalização de cookie (JSON/header/validação).
"""
from __future__ import annotations
import unittest

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import db, pipeline
from ofertas.config import config
from ofertas.models import Oferta
from ofertas.sources import ml_auth
from ofertas.sources.ml_auth import ml_auth_service

TEST_DB_PATH = Path(tempfile.gettempdir()) / "test_ofertas_ml.db"

import ofertas.grok as _grok_mod  # noqa: E402
_grok_mod.CACHE_FILE = Path(tempfile.gettempdir()) / "test_grok_cache_ml.json"


class TestCascataMl(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = TEST_DB_PATH
        db.init_db()
        with db._conn() as c:
            c.execute("DELETE FROM postadas")
            c.execute("DELETE FROM mensagens_telegram")
            c.execute("DELETE FROM ofertas_pendentes_ml")
        config.chat_id = "-1001234567890"
        config.owner_id = 999888
        config.desconto_minimo = 0
        config.ml_etiqueta = "fastpromo"
        ml_auth._notificacao_enviada = False
        ml_auth._ultimo_aviso_ts = 0.0
        import ofertas.publishing_control as _pc
        _pc.ARQ_ESTADO = TEST_DB_PATH.with_name("test_cadencia_ml.json")
        _pc.publishing_controller.reset()

    def test_1_cookie_valido_gera_link(self):
        oferta = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB101",
            url_produto="https://www.mercadolivre.com.br/p/MLB101",
            titulo="Produto Cookie",
            preco=100.0,
        )
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_valido_123"), \
             patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/cookie_link"]):
            ml_auth_service.gerar_links_afiliado([oferta])
        self.assertEqual(oferta.url_afiliado, "https://meli.la/cookie_link")
        self.assertEqual(db.total_ofertas_pendentes_ml(), 0)
        print("✅ TESTE 1 (Cookie válido -> gera link): OK")

    def test_2_sem_cookie_nao_publica(self):
        oferta = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB404",
            url_produto="https://www.mercadolivre.com.br/p/MLB404",
            titulo="Produto Sem Cookie",
            preco=300.0,
        )
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value=""):
            ml_auth_service.gerar_links_afiliado([oferta], bot=bot_mock)
        self.assertEqual(oferta.url_afiliado, "")
        self.assertEqual(db.total_ofertas_pendentes_ml(), 1)
        self.assertTrue(bot_mock.send_message.called)
        print("✅ TESTE 2 (Sem cookie -> não publica + notificação): OK")

    def test_3_cookie_expirado_nao_publica(self):
        oferta = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB303",
            url_produto="https://www.mercadolivre.com.br/p/MLB303",
            titulo="Produto Sem Auth",
            preco=200.0,
        )
        bot_mock = MagicMock()
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_expirado"), \
             patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=PermissionError("Cookie expirado")):
            ml_auth_service.gerar_links_afiliado([oferta], bot=bot_mock)
        self.assertEqual(oferta.url_afiliado, "")
        self.assertEqual(db.total_ofertas_pendentes_ml(), 1)
        print("✅ TESTE 3 (Cookie expirado -> não publica): OK")

    def test_4_cookie_invalido_nao_publica(self):
        oferta = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB505",
            url_produto="https://www.mercadolivre.com.br/p/MLB505",
            titulo="Produto Cookie Invalido",
            preco=80.0,
        )
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="bad_cookie"), \
             patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=ValueError("Formato invalido")):
            ml_auth_service.gerar_links_afiliado([oferta])
        self.assertEqual(oferta.url_afiliado, "")
        print("✅ TESTE 4 (Cookie inválido -> não publica): OK")

    def test_5_novo_cookie_valido_substitui(self):
        with patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/new_link"]), \
             patch("ofertas.sources.ml_auth.salvar_cookie_local") as mock_save:
            res = ml_auth_service.validar_e_salvar_novo_cookie("novo_cookie_100_valido")
        self.assertTrue(res["ok"])
        self.assertTrue(mock_save.called)
        self.assertEqual(mock_save.call_args[0][0], "novo_cookie_100_valido")
        print("✅ TESTE 5 (Novo cookie válido -> testado e substituído): OK")

    def test_6_novo_cookie_invalido_mantem_anterior(self):
        with patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=PermissionError("Expired")), \
             patch("ofertas.sources.ml_auth.salvar_cookie_local") as mock_save:
            res = ml_auth_service.validar_e_salvar_novo_cookie("novo_cookie_ruim")
        self.assertFalse(res["ok"])
        self.assertFalse(mock_save.called)
        print("✅ TESTE 6 (Novo cookie inválido -> rejeitado e anterior mantido): OK")

    def test_7_100_produtos_falhando_unica_notificacao(self):
        ofertas = [
            Oferta(plataforma="mercadolivre", id_produto=f"MLB_BATCH_{i}",
                   url_produto=f"https://www.mercadolivre.com.br/p/MLB_BATCH_{i}",
                   titulo=f"Item {i}", preco=50.0)
            for i in range(100)
        ]
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value=""):
            ml_auth_service.gerar_links_afiliado(ofertas, bot=bot_mock)
        self.assertEqual(bot_mock.send_message.call_count, 1)
        self.assertEqual(db.total_ofertas_pendentes_ml(), 100)
        print("✅ TESTE 7 (100 produtos falhando -> 1 única notificação anti-spam): OK")

    def test_8_autenticacao_renovada_processa_pendentes(self):
        oferta_pendente = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB_PEND_9",
            url_produto="https://www.mercadolivre.com.br/p/MLB_PEND_9",
            titulo="Item Pendente para Retry",
            preco=99.0,
        )
        db.salvar_oferta_pendente_ml(oferta_pendente)
        self.assertEqual(db.total_ofertas_pendentes_ml(), 1)
        bot_mock = MagicMock()
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_renovado"), \
             patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/retry_link"]), \
             patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:
            total = ml_auth_service.processar_ofertas_pendentes(bot=bot_mock)
        self.assertEqual(total, 1)
        self.assertEqual(db.total_ofertas_pendentes_ml(), 0)
        self.assertTrue(mock_post.called)
        print("✅ TESTE 8 (Autenticação renovada -> ofertas pendentes reprocessadas): OK")

    def test_9_oferta_ja_publicada_nao_duplica_retry(self):
        oferta = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB_DUPL_10",
            url_produto="https://www.mercadolivre.com.br/p/MLB_DUPL_10",
            titulo="Item Já Postado",
            preco=120.0,
        )
        db.registrar(oferta)
        db.salvar_oferta_pendente_ml(oferta)
        bot_mock = MagicMock()
        with patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:
            total = ml_auth_service.processar_ofertas_pendentes(bot=bot_mock)
        self.assertEqual(total, 0)
        self.assertFalse(mock_post.called)
        self.assertEqual(db.total_ofertas_pendentes_ml(), 0)
        print("✅ TESTE 9 (Oferta já publicada descartada no retry sem duplicar): OK")

    def test_10_erro_temporario_nao_marca_expirado(self):
        with patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_ok"), \
             patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=ConnectionError("Timeout 503")):
            res = ml_auth_service.testar_autenticacao()
        self.assertFalse(res["authenticated"])
        self.assertEqual(res["error"], "cookie_error")
        print("✅ TESTE 10 (Erro temporário de conexão diferenciado de cookie expirado): OK")

    def test_11_fluxo_completo_scraping_cookie(self):
        """Scraper -> Grok -> cookie -> afiliado -> publicação."""
        texto = "🔥 Super Oferta Mercado Livre!\nSmartphone Top de Linha\nhttps://www.mercadolivre.com.br/p/MLB1212"
        oferta_scraper = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB1212",
            url_produto="https://www.mercadolivre.com.br/p/MLB1212",
            titulo="Smartphone Top de Linha Original",
            preco=1299.0,
            preco_original=1899.0,
        )
        from ofertas.grok import GrokResult
        grok_mock = GrokResult(
            tipo="produto",
            titulo_otimizado="Smartphone Top de Linha",
            tem_cupom=False,
            cupom=None,
            beneficio_cupom=None,
            confianca=0.98,
        )
        bot_mock = MagicMock()
        with patch("ofertas.sources.mercadolivre.converter", return_value=oferta_scraper), \
             patch("ofertas.grok.grok_service.analisar_texto", return_value=grok_mock), \
             patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_ativo"), \
             patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/afiliado_grupo"]), \
             patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:
            res = asyncio.run(pipeline.processar_mensagem_telegram(
                texto=texto,
                source_id="-100333",
                message_id=888,
                bot=bot_mock,
            ))
        self.assertTrue(res["ok"])
        self.assertEqual(res["oferta"].url_afiliado, "https://meli.la/afiliado_grupo")
        self.assertEqual(res["oferta"].titulo, "Smartphone Top de Linha")
        self.assertTrue(mock_post.called)
        print("✅ TESTE 11 (Fluxo completo Scraper -> Grok -> Cookie -> Afiliado -> Publicação): OK")

    def test_12_normaliza_cookie_json_export(self):
        bruto = json.dumps([
            {"name": "ssid", "value": "abc", "domain": ".mercadolivre.com.br"},
            {"name": "orguserid", "value": "123", "domain": ".mercadolivre.com.br"},
            {"name": "inválido"},
        ])
        self.assertEqual(ml_auth.normalizar_cookie(bruto), "ssid=abc; orguserid=123")
        print("✅ TESTE 12 (JSON de extensão -> header normalizado): OK")

    def test_13_cookie_header_intacto(self):
        self.assertEqual(ml_auth.normalizar_cookie("a=1; b=2"), "a=1; b=2")
        self.assertEqual(ml_auth.normalizar_cookie(""), "")
        print("✅ TESTE 13 (Header já correto passa intacto): OK")

    def test_14_validar_salva_cookie_json_normalizado(self):
        bruto = json.dumps([{"name": "ssid", "value": "xyz"}])
        with patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/x"]) as gerar, \
             patch("ofertas.sources.ml_auth.salvar_cookie_local") as mock_save:
            res = ml_auth_service.validar_e_salvar_novo_cookie(bruto)
        self.assertTrue(res["ok"])
        self.assertEqual(gerar.call_args[0][2], "ssid=xyz")
        self.assertEqual(mock_save.call_args[0][0], "ssid=xyz")
        print("✅ TESTE 14 (Cookie JSON validado/salvo já normalizado): OK")


if __name__ == "__main__":
    unittest.main(verbosity=2)
