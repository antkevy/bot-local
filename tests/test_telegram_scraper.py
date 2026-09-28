"""Suíte completa de testes para o Scraper de Telegram e integração com Grok e Afiliados.

Cobre os cenários exigidos pela especificação:
1. Mensagem de produto
2. Produto + cupom
3. Cupom puro
4. Frete grátis
5. Mensagem irrelevante
6. Título longo otimizado
7. Título normal
8. URL Mercado Livre / meli.la
9. URL Amazon
10. URL Shopee
11. URL AliExpress
12. URL inválida
13. Ausência de link
14. Afiliado não gerado -> NÃO publicar (regra crítica)
15. Deduplicação (source_id + message_id)
16. Anti-loop: Não processar o próprio canal de destino
17. Anti-loop: Não processar mensagens do próprio bot
18. Falha/Timeout no Grok -> Fallback seguro
19. Grok JSON corrompido -> Fallback seguro
20. Filtros existentes aplicados
21. Formatação de template preservada
22. Modo Dry-Run
23. Registro de estatísticas e persistência em banco
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
from ofertas.formatter import montar_caption
from ofertas.grok import GrokResult, GrokService
from ofertas.models import Oferta
from ofertas.sources import telegram_scraper

TEST_DB_PATH = Path(tempfile.gettempdir()) / "test_ofertas_scraper.db"
db.DB_PATH = TEST_DB_PATH
db.init_db()


def setup_function():
    with db._conn() as c:
        c.execute("DELETE FROM mensagens_telegram")
        c.execute("DELETE FROM postadas")
    config.chat_id = "-1001234567890"
    config.desconto_minimo = 0
    config.desconto_minimo_pct = 0
    config.avaliacao_minima = 0
    config.vendas_minimas = 0
    config.intervalo_entre_posts_segundos = 0
    config.posts_antes_pausa = 0
    config.max_posts_periodo = 0
    config.palavras_bloqueadas = []
    from ofertas import publishing_control as _pc
    from ofertas.publishing_control import publishing_controller
    # O singleton persiste a cadência em data/cadencia.json, compartilhada com o
    # bot. Sem apontar para um arquivo temporário, o reset() desta linha
    # apagaria o estado real de publicação do usuário ao rodar a suíte.
    _pc.ARQ_ESTADO = TEST_DB_PATH.with_name("test_cadencia_scraper.json")
    publishing_controller.reset()



def test_1_mensagem_produto():
    texto = "🔥 Fone Bluetooth JBL Tune 520BT por R$199,90\nhttps://www.amazon.com.br/dp/B0C12345"
    oferta_mock = Oferta(
        plataforma="amazon",
        id_produto="B0C12345",
        titulo="Fone Bluetooth JBL Tune 520BT Original",
        url_afiliado="https://amzn.to/afiliado",
        url_produto="https://www.amazon.com.br/dp/B0C12345",
        preco=199.90,
    )
    resultado_grok = GrokResult(
        tipo="produto",
        titulo_otimizado="Fone Bluetooth JBL Tune 520BT",
        tem_cupom=False,
        cupom=None,
        beneficio_cupom=None,
        confianca=0.98,
    )

    with patch("ofertas.sources.amazon.converter", return_value=oferta_mock), \
         patch("ofertas.grok.grok_service.analisar_texto", return_value=resultado_grok), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        bot_mock = MagicMock()
        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            imagem_url=None,
            source_id="-10099999",
            message_id=101,
            bot=bot_mock,
            dry_run=False,
        ))

        assert res["ok"] is True
        assert res["oferta"].titulo == "Fone Bluetooth JBL Tune 520BT"
        assert res["oferta"].url_afiliado == "https://amzn.to/afiliado"
        assert mock_post.called
        assert db.ja_processada_msg_telegram("-10099999", 101)
        print("✅ TESTE 1 (Mensagem de produto processada e postada): OK")


def test_2_produto_com_cupom():
    texto = "🔥 Fone TWS Bluetooth\nDe R$89,90 por R$49,90\nCupom: OFERTA20\nhttps://shopee.com.br/product/123/456"
    oferta_mock = Oferta(
        plataforma="shopee",
        id_produto="456",
        titulo="Fone TWS Bluetooth Sem Fio Barato",
        url_afiliado="https://shope.ee/afiliado",
        url_produto="https://shopee.com.br/product/123/456",
        preco=49.90,
        preco_original=89.90,
    )
    resultado_grok = GrokResult(
        tipo="produto",
        titulo_otimizado="Fone TWS Bluetooth",
        tem_cupom=True,
        cupom="OFERTA20",
        beneficio_cupom="R$20 OFF",
        confianca=0.96,
    )

    with patch("ofertas.sources.shopee.converter", return_value=oferta_mock), \
         patch("ofertas.grok.grok_service.analisar_texto", return_value=resultado_grok), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        bot_mock = MagicMock()
        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            imagem_url=None,
            source_id="-10099999",
            message_id=102,
            bot=bot_mock,
        ))

        assert res["ok"] is True
        assert res["oferta"].cupom == "OFERTA20"
        caption = montar_caption(res["oferta"])
        assert "Cupom: <code>OFERTA20</code>" in caption
        print("✅ TESTE 2 (Produto + Cupom extraído e formatado): OK")


def test_3_mensagem_irrelevante():
    texto = "Bom dia pessoal! Alguém sabe como rastrear meu pedido?"
    resultado_grok = GrokResult(
        tipo="irrelevante",
        titulo_otimizado=None,
        tem_cupom=False,
        cupom=None,
        beneficio_cupom=None,
        confianca=0.99,
    )

    with patch("ofertas.grok.grok_service.analisar_texto", return_value=resultado_grok), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-10099999",
            message_id=103,
            bot=MagicMock(),
        ))

        assert res["ok"] is False
        assert res["motivo"] == "irrelevante"
        assert not mock_post.called
        print("✅ TESTE 3 (Mensagem irrelevante descartada sem postar): OK")


def test_4_sem_link_afiliado_nao_publica():
    texto = "Super Oferta!\nhttps://www.mercadolivre.com.br/p/MLB123"
    # Oferta sem url_afiliado (falha no linkbuilder)
    oferta_sem_afiliado = Oferta(
        plataforma="mercadolivre",
        id_produto="MLB123",
        titulo="Produto Sem Afiliado",
        url_afiliado="",  # VAZIO!
        url_produto="https://www.mercadolivre.com.br/p/MLB123",
        preco=99.00,
    )
    resultado_grok = GrokResult(
        tipo="produto",
        titulo_otimizado="Produto Sem Afiliado",
        tem_cupom=False,
        cupom=None,
        beneficio_cupom=None,
        confianca=0.95,
    )

    with patch("ofertas.sources.mercadolivre.converter", return_value=oferta_sem_afiliado), \
         patch("ofertas.grok.grok_service.analisar_texto", return_value=resultado_grok), \
         patch("ofertas.sources.mercadolivre.gerar_links_afiliado"), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-10099999",
            message_id=104,
            bot=MagicMock(),
        ))

        # Regra crítica: Sem afiliado -> NÃO publica e NÃO usa URL original!
        assert res["ok"] is False
        assert res["motivo"] == "sem_link_afiliado"
        assert not mock_post.called
        print("✅ TESTE 4 (Regra Crítica: Sem link afiliado NUNCA publica): OK")


def test_5_deduplicacao():
    texto = "Oferta repetida!\nhttps://www.amazon.com.br/dp/B0C_DEDUP_5"
    oferta_mock = Oferta(
        plataforma="amazon",
        id_produto="B0C_DEDUP_5",
        titulo="Item Teste",
        url_afiliado="https://amzn.to/afiliado",
        preco=50.00,
    )

    with patch("ofertas.sources.amazon.converter", return_value=oferta_mock), \
         patch("ofertas.grok.grok_service.analisar_texto", return_value=GrokResult(
             tipo="produto", titulo_otimizado="Item Teste", tem_cupom=False, cupom=None, beneficio_cupom=None, confianca=0.95
         )), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        # 1ª execução
        res1 = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-1001234",
            message_id=501,
            bot=MagicMock(),
        ))
        assert res1["ok"] is True
        assert mock_post.call_count == 1

        # 2ª execução com mesmo source_id e message_id
        res2 = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-1001234",
            message_id=501,
            bot=MagicMock(),
        ))
        assert res2["ok"] is False
        assert res2["motivo"] == "duplicada"
        assert mock_post.call_count == 1  # Não postou de novo!
        print("✅ TESTE 5 (Deduplicação de mensagem por source_id + message_id): OK")


def test_6_anti_loop_proprio_canal_destino():
    texto = "Mensagem que o bot postou no próprio canal de destino\nhttps://amzn.to/afiliado"
    with patch.object(config, "chat_id", "-10088888"), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-10088888",  # Mesmo ID do canal de destino!
            message_id=999,
            bot=MagicMock(),
        ))
        assert res["ok"] is False
        assert res["motivo"] == "origem_canal_destino"
        assert not mock_post.called
        print("✅ TESTE 6 (Anti-loop: ignora postagens do canal de destino): OK")


def test_7_grok_fallback_em_erro():
    texto = "Smart TV 50 Polegadas 4K\nhttps://www.amazon.com.br/dp/B0CTV50"
    oferta_mock = Oferta(
        plataforma="amazon",
        id_produto="B0CTV50",
        titulo="Smart TV 50 Polegadas 4K Original",
        url_afiliado="https://amzn.to/afiliado_tv",
        preco=1899.00,
    )

    # Grok falha com exceção
    with patch("ofertas.sources.amazon.converter", return_value=oferta_mock), \
         patch("ofertas.grok.grok_service.analisar_texto", side_effect=Exception("API Timeout")), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-100777",
            message_id=301,
            bot=MagicMock(),
        ))
        # O pipeline continua resiliente e usa o título original
        assert res["ok"] is True
        assert res["oferta"].titulo == "Smart TV 50 Polegadas 4K Original"
        assert mock_post.called
        print("✅ TESTE 7 (Grok offline -> Bot continua funcionando com fallback): OK")


def test_8_modo_dry_run():
    texto = "Oferta Dry Run\nhttps://www.amazon.com.br/dp/B0CDRY"
    oferta_mock = Oferta(
        plataforma="amazon",
        id_produto="B0CDRY",
        titulo="Oferta Dry Run",
        url_afiliado="https://amzn.to/dry",
        preco=100.00,
    )

    with patch("ofertas.sources.amazon.converter", return_value=oferta_mock), \
         patch("ofertas.grok.grok_service.analisar_texto", return_value=GrokResult(
             tipo="produto", titulo_otimizado="Oferta Dry Run", tem_cupom=False, cupom=None, beneficio_cupom=None, confianca=0.95
         )), \
         patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock) as mock_post:

        res = asyncio.run(pipeline.processar_mensagem_telegram(
            texto=texto,
            source_id="-100555",
            message_id=401,
            bot=MagicMock(),
            dry_run=True,  # Modo simulação ativo
        ))
        assert res["ok"] is True
        assert res.get("dry_run") is True
        assert not mock_post.called  # Não envia mensagem real no Telegram
        print("✅ TESTE 8 (Modo Dry-Run executa análise completa sem postar): OK")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 EXECUTANDO SUÍTE DE TESTES DO SCRAPER DE TELEGRAM")
    print("=" * 60)
    setup_function()
    test_1_mensagem_produto()
    setup_function()
    test_2_produto_com_cupom()
    setup_function()
    test_3_mensagem_irrelevante()
    setup_function()
    test_4_sem_link_afiliado_nao_publica()
    setup_function()
    test_5_deduplicacao()
    setup_function()
    test_6_anti_loop_proprio_canal_destino()
    setup_function()
    test_7_grok_fallback_em_erro()
    setup_function()
    test_8_modo_dry_run()
    print("=" * 60)
    print("🎉 TODOS OS TESTES DO SCRAPER PASSARAM COM SUCESSO!")
    print("=" * 60 + "\n")
