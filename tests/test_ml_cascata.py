"""Suíte de Testes Automatizados para a Autenticação em Cascata do Mercado Livre.

Cobre com precisão todos os 12 cenários exigidos pela especificação:
TESTE 1: Link Builder funcionando -> usa Link Builder.
TESTE 2: Link Builder falha + cookie válido -> usa cookie.
TESTE 3: Link Builder falha + cookie expirado -> não publica.
TESTE 4: Link Builder falha + sem cookie -> não publica + notificação ao admin.
TESTE 5: Cookie inválido -> não publica.
TESTE 6: Novo cookie válido -> substitui o anterior somente após validação bem-sucedida.
TESTE 7: Novo cookie inválido -> mantém o anterior.
TESTE 8: 100 produtos falhando -> uma única notificação ao administrador (cooldown ativo).
TESTE 9: Autenticação renovada -> processa ofertas pendentes automaticamente.
TESTE 10: Oferta já publicada -> não duplica durante o retry de pendências.
TESTE 11: Erro temporário do Mercado Livre (ex: 503 / timeout) -> não marca como cookie expirado.
TESTE 12: Fluxo completo de Scraping de grupo + ML com fallback para Cookie -> afiliado gerado e postado.
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import tempfile
from pathlib import Path

from ofertas import db, pipeline
from ofertas.config import config
from ofertas.models import Oferta
from ofertas.sources import ml_auth
from ofertas.sources.ml_auth import ml_auth_service

TEST_DB_PATH = Path(tempfile.gettempdir()) / "test_ofertas_ml.db"
db.DB_PATH = TEST_DB_PATH
db.init_db()


def setup_function():
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


def test_1_linkbuilder_funcionando():
    """TESTE 1: Link Builder funcionando -> usa Link Builder."""
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB101",
        url_produto="https://www.mercadolivre.com.br/p/MLB101",
        titulo="Produto Link Builder",
        preco=100.0,
    )

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=True), \
         patch("ofertas.sources.mercadolivre._gerar_links_linkbuilder_batch", side_effect=lambda ofs, tag: setattr(ofs[0], "url_afiliado", "https://meli.la/lb_link")):

        ml_auth_service.gerar_links_afiliado([oferta])

        assert oferta.url_afiliado == "https://meli.la/lb_link"
        assert db.total_ofertas_pendentes_ml() == 0
        print("✅ TESTE 1 (Link Builder funcionando -> usa Link Builder): OK")


def test_2_linkbuilder_falha_cookie_valido():
    """TESTE 2: Link Builder falha + cookie válido -> usa cookie."""
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB202",
        url_produto="https://www.mercadolivre.com.br/p/MLB202",
        titulo="Produto Fallback Cookie",
        preco=150.0,
    )

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=True), \
         patch("ofertas.sources.mercadolivre._gerar_links_linkbuilder_batch", side_effect=RuntimeError("Sessão expirou")), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_valido_123"), \
         patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/cookie_link"]):

        ml_auth_service.gerar_links_afiliado([oferta])

        assert oferta.url_afiliado == "https://meli.la/cookie_link"
        assert db.total_ofertas_pendentes_ml() == 0
        print("✅ TESTE 2 (Link Builder falha + cookie válido -> usa cookie): OK")


def test_3_linkbuilder_falha_cookie_expirado():
    """TESTE 3: Link Builder falha + cookie expirado -> não publica."""
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB303",
        url_produto="https://www.mercadolivre.com.br/p/MLB303",
        titulo="Produto Sem Auth",
        preco=200.0,
    )

    bot_mock = MagicMock()

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_expirado"), \
         patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=PermissionError("Cookie expirado")):

        ml_auth_service.gerar_links_afiliado([oferta], bot=bot_mock)

        # Regra absoluta: sem afiliado -> url_afiliado permanece vazio e salva como pendente
        assert oferta.url_afiliado == ""
        assert db.total_ofertas_pendentes_ml() == 1
        print("✅ TESTE 3 (Link Builder falha + cookie expirado -> não publica): OK")


def test_4_linkbuilder_falha_sem_cookie():
    """TESTE 4: Link Builder falha + sem cookie -> não publica + notificação ao admin."""
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB404",
        url_produto="https://www.mercadolivre.com.br/p/MLB404",
        titulo="Produto Sem Cookie",
        preco=300.0,
    )

    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value=""):

        ml_auth_service.gerar_links_afiliado([oferta], bot=bot_mock)

        assert oferta.url_afiliado == ""
        assert db.total_ofertas_pendentes_ml() == 1
        assert bot_mock.send_message.called
        print("✅ TESTE 4 (Link Builder falha + sem cookie -> não publica + notificação): OK")


def test_5_cookie_invalido():
    """TESTE 5: Cookie inválido -> não publica."""
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB505",
        url_produto="https://www.mercadolivre.com.br/p/MLB505",
        titulo="Produto Cookie Invalido",
        preco=80.0,
    )

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="bad_cookie"), \
         patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=ValueError("Formato invalido")):

        ml_auth_service.gerar_links_afiliado([oferta])

        assert oferta.url_afiliado == ""
        print("✅ TESTE 5 (Cookie inválido -> não publica): OK")


def test_6_novo_cookie_valido_substitui():
    """TESTE 6: Novo cookie válido -> substitui o anterior somente após validação."""
    with patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/new_link"]), \
         patch("ofertas.sources.ml_auth.salvar_cookie_local") as mock_save:

        res = ml_auth_service.validar_e_salvar_novo_cookie("novo_cookie_100_valido")
        assert res["ok"] is True
        assert mock_save.called
        assert mock_save.call_args[0][0] == "novo_cookie_100_valido"
        print("✅ TESTE 6 (Novo cookie válido -> testado e substituído): OK")


def test_7_novo_cookie_invalido_mantem_anterior():
    """TESTE 7: Novo cookie inválido -> mantém o anterior."""
    with patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=PermissionError("Expired")), \
         patch("ofertas.sources.ml_auth.salvar_cookie_local") as mock_save:

        res = ml_auth_service.validar_e_salvar_novo_cookie("novo_cookie_ruim")
        assert res["ok"] is False
        assert not mock_save.called
        print("✅ TESTE 7 (Novo cookie inválido -> rejeitado e anterior mantido): OK")


def test_8_100_produtos_falhando_unica_notificacao():
    """TESTE 8: 100 produtos falhando -> uma única notificação ao administrador (cooldown ativo)."""
    ofertas = [
        Oferta(plataforma="mercadolivre", id_produto=f"MLB_BATCH_{i}", url_produto=f"https://www.mercadolivre.com.br/p/MLB_BATCH_{i}", titulo=f"Item {i}", preco=50.0)
        for i in range(100)
    ]

    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value=""):

        # Executa geração para 100 itens
        ml_auth_service.gerar_links_afiliado(ofertas, bot=bot_mock)

        # Deve chamar send_message exatamente UMA vez
        assert bot_mock.send_message.call_count == 1
        assert db.total_ofertas_pendentes_ml() == 100
        print("✅ TESTE 8 (100 produtos falhando -> 1 única notificação anti-spam): OK")


def test_9_autenticacao_renovada_processa_pendentes():
    """TESTE 9: Autenticação renovada -> processa ofertas pendentes automaticamente."""
    oferta_pendente = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB_PEND_9",
        url_produto="https://www.mercadolivre.com.br/p/MLB_PEND_9",
        titulo="Item Pendente para Retry",
        preco=99.0,
    )
    db.salvar_oferta_pendente_ml(oferta_pendente)
    assert db.total_ofertas_pendentes_ml() == 1

    bot_mock = MagicMock()

    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_renovado"), \
         patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/retry_link"]), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        total = ml_auth_service.processar_ofertas_pendentes(bot=bot_mock)

        assert total == 1
        assert db.total_ofertas_pendentes_ml() == 0
        assert mock_post.called
        print("✅ TESTE 9 (Autenticação renovada -> ofertas pendentes reprocessadas): OK")


def test_10_oferta_ja_publicada_nao_duplica_retry():
    """TESTE 10: Oferta já publicada -> não duplica no retry."""
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB_DUPL_10",
        url_produto="https://www.mercadolivre.com.br/p/MLB_DUPL_10",
        titulo="Item Já Postado",
        preco=120.0,
    )
    # Já está no banco como postada
    db.registrar(oferta)
    # E ficou como pendente
    db.salvar_oferta_pendente_ml(oferta)

    bot_mock = MagicMock()
    with patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:
        total = ml_auth_service.processar_ofertas_pendentes(bot=bot_mock)
        assert total == 0
        assert not mock_post.called
        assert db.total_ofertas_pendentes_ml() == 0
        print("✅ TESTE 10 (Oferta já publicada descartada no retry sem duplicar): OK")


def test_11_erro_temporario_nao_marca_expirado():
    """TESTE 11: Erro temporário do Mercado Livre -> não classifica como cookie expirado."""
    with patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_ok"), \
         patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", side_effect=ConnectionError("Timeout 503")):

        res = ml_auth_service.testar_autenticacao()
        assert res["authenticated"] is False
        assert res["error"] == "cookie_error"  # Distingue de cookie_expired
        print("✅ TESTE 11 (Erro temporário de conexão diferenciado de cookie expirado): OK")


def test_12_scraping_grupo_fluxo_ml_completo():
    """TESTE 12: Scraping de grupo + ML -> scraper -> Grok -> ML -> Link Builder falha -> Cookie -> afiliado -> template -> publicação."""
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
         patch("ofertas.sources.ml_auth.tem_sessao_linkbuilder", return_value=False), \
         patch("ofertas.sources.ml_auth.obter_cookie_configurado", return_value="cookie_ativo"), \
         patch("ofertas.sources.ml_auth._gerar_via_cookie_raw", return_value=["https://meli.la/afiliado_grupo"]), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-100333",
            message_id=888,
            bot=bot_mock,
        ))

        assert res["ok"] is True
        assert res["oferta"].url_afiliado == "https://meli.la/afiliado_grupo"
        assert res["oferta"].titulo == "Smartphone Top de Linha"
        assert mock_post.called
        print("✅ TESTE 12 (Fluxo completo Scraper -> Grok -> ML Cascata -> Afiliado -> Publicação): OK")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 EXECUTANDO SUÍTE COMPLETA DA AUTENTICAÇÃO MERCADO LIVRE")
    print("=" * 60)
    setup_function(); test_1_linkbuilder_funcionando()
    setup_function(); test_2_linkbuilder_falha_cookie_valido()
    setup_function(); test_3_linkbuilder_falha_cookie_expirado()
    setup_function(); test_4_linkbuilder_falha_sem_cookie()
    setup_function(); test_5_cookie_invalido()
    setup_function(); test_6_novo_cookie_valido_substitui()
    setup_function(); test_7_novo_cookie_invalido_mantem_anterior()
    setup_function(); test_8_100_produtos_falhando_unica_notificacao()
    setup_function(); test_9_autenticacao_renovada_processa_pendentes()
    setup_function(); test_10_oferta_ja_publicada_nao_duplica_retry()
    setup_function(); test_11_erro_temporario_nao_marca_expirado()
    setup_function(); test_12_scraping_grupo_fluxo_ml_completo()
    print("=" * 60)
    print("🎉 TODOS OS 12 TESTES DA CASCATA PASSARAM COM SUCESSO!")
    print("=" * 60)
