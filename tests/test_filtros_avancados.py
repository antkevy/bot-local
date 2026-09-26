"""Testes completos para o Sistema Avançado de Filtros, Publicação e AliExpress.

Cobre requisitos 83 a 142:
- Conversão de estrelas percentuais do AliExpress (96% -> 4.8)
- Extração de vendas e remoção de comissão da postagem
- Filtro por quantidade mínima de estrelas
- Filtro por quantidade mínima de vendas
- Tratamento de dados ausentes (estrelas/vendas sem transformar em 0)
- Regras de desconto real vs produtos sem desconto (nunca inventar "De/Por")
- Cupom separado de desconto
- Controle de publicação (intervalo, pausa em blocos, limite de posts)
- Normalização de @username de fontes do Telegram
- Filtro central com motivo detalhado de rejeição
- Simulação ponta a ponta (End-to-End Dry-Run)
"""

import unittest
from unittest.mock import patch, MagicMock

from ofertas.models import Oferta
from ofertas.marketplaces import (
    get_marketplace_display,
    normalizar_marketplace,
    formatar_marketplace_postagem,
)
from ofertas.filters import passes_product_filters
from ofertas.publishing_control import PublishingController
from ofertas.formatter import formatar_mensagem
from ofertas.sources.aliexpress import (
    _converter_rating_percentual,
    _item_para_oferta,
)
from ofertas.sources.telegram_scraper import normalizar_username_telegram


class TestFiltrosEPublicacao(unittest.TestCase):

    # =====================================================================
    # 1. TESTES DO ALIEXPRESS: RATING, VENDAS, COMISSÃO E NOME
    # =====================================================================

    def test_aliexpress_rating_conversion(self):
        """Item 100, 101, 102: Converte porcentagem de avaliação em nota de 1 a 5 estrelas."""
        # 96% -> 4.8
        self.assertEqual(_converter_rating_percentual("96.0%"), 4.8)
        self.assertEqual(_converter_rating_percentual("96%"), 4.8)
        self.assertEqual(_converter_rating_percentual(96), 4.8)
        
        # 100% -> 5.0
        self.assertEqual(_converter_rating_percentual("100%"), 5.0)
        
        # 90% -> 4.5
        self.assertEqual(_converter_rating_percentual("90%"), 4.5)
        
        # 84% -> 4.2
        self.assertEqual(_converter_rating_percentual("84%"), 4.2)
        
        # Se já for nota 1-5, preserva
        self.assertEqual(_converter_rating_percentual(4.8), 4.8)
        self.assertEqual(_converter_rating_percentual("4.8"), 4.8)
        
        # Dado ausente ou inválido -> None
        self.assertIsNone(_converter_rating_percentual(None))
        self.assertIsNone(_converter_rating_percentual(""))
        self.assertIsNone(_converter_rating_percentual("N/A"))

    def test_aliexpress_item_parsing_sem_comissao_na_postagem(self):
        """Item 103, 107, 108, 109, 130: Extrai rating 4.8, vendas 1500, e comissão NUNCA vai para postagem."""
        raw_item = {
            "product_id": 1005001234567,
            "product_title": "Fone Bluetooth Sem Fio TWS",
            "target_sale_price": "39.90",
            "target_original_price": "79.90",
            "discount": "50%",
            "evaluate_rate": "96.0%",
            "lastest_volume": 1500,
            "commission_rate": "12.0%",
            "promotion_link": "https://s.click.aliexpress.com/e/_teste",
            "product_main_image_url": "https://ae01.alicdn.com/kf/teste.jpg",
        }
        
        oferta = _item_para_oferta(raw_item)
        self.assertIsNotNone(oferta)
        self.assertEqual(oferta.plataforma, "aliexpress")
        self.assertEqual(oferta.preco, 39.90)
        self.assertEqual(oferta.preco_original, 79.90)
        self.assertEqual(oferta.desconto_pct, 50)
        self.assertEqual(oferta.avaliacao, 4.8)
        self.assertEqual(oferta.vendas, 1500)
        self.assertEqual(oferta.comissao_pct, 12.0)
        
        # Formata a mensagem pública para o Telegram
        msg = formatar_mensagem(oferta)
        
        # Validações estritas
        self.assertIn("AliExpress", msg)
        self.assertIn("⭐ 4.8", msg)
        self.assertTrue("1.500 vendidos" in msg or "1500 vendidos" in msg)
        self.assertIn("R$ 39,90", msg)
        
        # A comissão NUNCA deve aparecer no texto público
        self.assertNotIn("12%", msg)
        self.assertNotIn("Comissão", msg)
        self.assertNotIn("comissao", msg.lower())
        self.assertNotIn("commission", msg.lower())

    def test_marketplace_central_display(self):
        """Item 104, 105, 106: Padrão central de exibição de marketplaces."""
        disp_ali = get_marketplace_display("aliexpress")
        self.assertEqual(disp_ali["nome"], "AliExpress")
        self.assertEqual(disp_ali["emoji"], "🔴")
        
        disp_ml = get_marketplace_display("mercadolivre")
        self.assertEqual(disp_ml["nome"], "Mercado Livre")
        self.assertEqual(disp_ml["emoji"], "💛")
        
        disp_amz = get_marketplace_display("amazon")
        self.assertEqual(disp_amz["nome"], "Amazon")
        self.assertEqual(disp_amz["emoji"], "📦")
        
        disp_shp = get_marketplace_display("shopee")
        self.assertEqual(disp_shp["nome"], "Shopee")
        self.assertEqual(disp_shp["emoji"], "🧡")

    # =====================================================================
    # 2. TESTES DE FILTRO DE ESTRELAS E VENDAS (QUALIDADE)
    # =====================================================================

    def test_filtro_estrelas(self):
        """Item 101, 133: Avaliação mínima 4.5 aprova 4.8 e rejeita 4.3."""
        with patch("ofertas.filters.config") as mock_cfg:
            mock_cfg.palavras_bloqueadas = []
            mock_cfg.avaliacao_minima = 4.5
            mock_cfg.vendas_minimas = 0
            mock_cfg.desconto_minimo = 0
            mock_cfg.desconto_minimo_pct = 0
            mock_cfg.preco_minimo = 0
            mock_cfg.preco_maximo = 0
            mock_cfg.permitir_sem_avaliacao = True
            mock_cfg.permitir_sem_vendas = True
            mock_cfg.permitir_sem_desconto = True
            
            # Produto com rating 4.3 -> Rejeitado
            o_baixa = Oferta(
                id_produto="ali_1",
                plataforma="aliexpress",
                titulo="Fone Ruim",
                preco=50.0,
                avaliacao=4.3,
                url_produto="https://aliexpress.com/item/1",
            )
            aprovado, motivo = passes_product_filters(o_baixa)
            self.assertFalse(aprovado)
            self.assertIn("avaliacao_baixa", motivo)
            
            # Produto com rating 4.8 -> Aprovado
            o_alta = Oferta(
                id_produto="ali_2",
                plataforma="aliexpress",
                titulo="Fone Excelente",
                preco=50.0,
                avaliacao=4.8,
                url_produto="https://aliexpress.com/item/2",
            )
            aprovado, motivo = passes_product_filters(o_alta)
            self.assertTrue(aprovado)
            self.assertEqual(motivo, "aprovado")

    def test_filtro_vendas(self):
        """Item 85, 134: Mínimo 500 vendas rejeita 300 e aprova 1500."""
        with patch("ofertas.filters.config") as mock_cfg:
            mock_cfg.palavras_bloqueadas = []
            mock_cfg.avaliacao_minima = 0
            mock_cfg.vendas_minimas = 500
            mock_cfg.desconto_minimo = 0
            mock_cfg.desconto_minimo_pct = 0
            mock_cfg.preco_minimo = 0
            mock_cfg.preco_maximo = 0
            mock_cfg.permitir_sem_avaliacao = True
            mock_cfg.permitir_sem_vendas = True
            mock_cfg.permitir_sem_desconto = True

            o_pouco = Oferta(
                id_produto="ali_3",
                plataforma="aliexpress",
                titulo="Poucas Vendas",
                preco=50.0,
                vendas=300,
                url_produto="https://aliexpress.com/item/3",
            )
            aprovado, motivo = passes_product_filters(o_pouco)
            self.assertFalse(aprovado)
            self.assertIn("vendas_insuficientes", motivo)
            
            o_muito = Oferta(
                id_produto="ali_4",
                plataforma="aliexpress",
                titulo="Muitas Vendas",
                preco=50.0,
                vendas=1500,
                url_produto="https://aliexpress.com/item/4",
            )
            aprovado, motivo = passes_product_filters(o_muito)
            self.assertTrue(aprovado)
            self.assertEqual(motivo, "aprovado")

    def test_dados_ausentes_politica(self):
        """Item 86: Trata dados ausentes sem converter null em 0."""
        o_sem_dados = Oferta(
            id_produto="ml_1",
            plataforma="mercadolivre",
            titulo="Produto Sem Estrelas Nem Vendas",
            preco=49.90,
            avaliacao=None,
            vendas=None,
            url_produto="https://mercadolivre.com.br/item/1",
        )

        # Cenário A: Permitir dados ausentes
        with patch("ofertas.filters.config") as mock_cfg:
            mock_cfg.palavras_bloqueadas = []
            mock_cfg.avaliacao_minima = 4.5
            mock_cfg.vendas_minimas = 100
            mock_cfg.desconto_minimo = 0
            mock_cfg.desconto_minimo_pct = 0
            mock_cfg.preco_minimo = 0
            mock_cfg.preco_maximo = 0
            mock_cfg.permitir_sem_avaliacao = True
            mock_cfg.permitir_sem_vendas = True
            mock_cfg.permitir_sem_desconto = True
            
            aprovado, _ = passes_product_filters(o_sem_dados)
            self.assertTrue(aprovado)
        
        # Cenário B: Bloquear quando avaliação for ausente
        with patch("ofertas.filters.config") as mock_cfg:
            mock_cfg.palavras_bloqueadas = []
            mock_cfg.avaliacao_minima = 4.5
            mock_cfg.vendas_minimas = 100
            mock_cfg.desconto_minimo = 0
            mock_cfg.desconto_minimo_pct = 0
            mock_cfg.preco_minimo = 0
            mock_cfg.preco_maximo = 0
            mock_cfg.permitir_sem_avaliacao = False
            mock_cfg.permitir_sem_vendas = True
            mock_cfg.permitir_sem_desconto = True

            aprovado, motivo = passes_product_filters(o_sem_dados)
            self.assertFalse(aprovado)
            self.assertIn("avaliacao_ausente", motivo)
        
        # Cenário C: Bloquear quando vendas for ausente
        with patch("ofertas.filters.config") as mock_cfg:
            mock_cfg.palavras_bloqueadas = []
            mock_cfg.avaliacao_minima = 0
            mock_cfg.vendas_minimas = 100
            mock_cfg.desconto_minimo = 0
            mock_cfg.desconto_minimo_pct = 0
            mock_cfg.preco_minimo = 0
            mock_cfg.preco_maximo = 0
            mock_cfg.permitir_sem_avaliacao = True
            mock_cfg.permitir_sem_vendas = False
            mock_cfg.permitir_sem_desconto = True

            aprovado, motivo = passes_product_filters(o_sem_dados)
            self.assertFalse(aprovado)
            self.assertIn("vendas_ausente", motivo)

    # =====================================================================
    # 3. TESTES DE DESCONTO E FORMATAÇÃO VISUAL (REGRAS 87, 88, 89, 90, 131, 132)
    # =====================================================================

    def test_produto_sem_desconto_sem_cupom(self):
        """Item 87, 131: Produto R$ 39,90 sem desconto -> Publica só preço atual sem inventar De/Por."""
        o = Oferta(
            id_produto="ml_2",
            plataforma="mercadolivre",
            titulo="Cabo USB-C Reforçado",
            preco=39.90,
            preco_original=None,
            desconto_pct=None,
            cupom=None,
            url_produto="https://mercadolivre.com.br/item/2",
        )
        
        msg = formatar_mensagem(o)
        self.assertIn("R$ 39,90", msg)
        self.assertNotIn("De:", msg)
        self.assertNotIn("OFF", msg)
        self.assertNotIn("0%", msg)
        self.assertNotIn("Cupom", msg)

    def test_produto_sem_desconto_com_cupom(self):
        """Item 88, 132: Produto R$ 39,90 sem desconto mas com cupom X20 -> Não inventa desconto."""
        o = Oferta(
            id_produto="shp_1",
            plataforma="shopee",
            titulo="Fone Bluetooth QCY",
            preco=39.90,
            preco_original=None,
            desconto_pct=None,
            cupom="X20",
            url_produto="https://shopee.com.br/item/1",
        )
        
        msg = formatar_mensagem(o)
        self.assertIn("R$ 39,90", msg)
        self.assertIn("X20", msg)
        self.assertIn("🏷️ Cupom", msg)
        self.assertNotIn("De:", msg)
        self.assertNotIn("OFF", msg)

    def test_produto_com_desconto_real(self):
        """Item 89, 90: Produto De R$ 100 Por R$ 70 -> Mostra 30% OFF."""
        o = Oferta(
            id_produto="amz_1",
            plataforma="amazon",
            titulo="Echo Pop Smart Speaker",
            preco=70.00,
            preco_original=100.00,
            desconto_pct=30,
            url_produto="https://amazon.com.br/dp/B012345",
        )
        
        msg = formatar_mensagem(o)
        self.assertIn("R$ 70,00", msg)
        self.assertIn("R$ 100,00", msg)
        self.assertIn("30% OFF", msg)

    # =====================================================================
    # 4. TESTES DE CONTROLE DE CADÊNCIA / PUBLICAÇÃO (ITENS 91-97, 135, 136)
    # =====================================================================

    def test_publication_controller_intervalo(self):
        """Item 92, 93: Respeita intervalo mínimo entre posts."""
        with patch("ofertas.publishing_control.config") as mock_cfg:
            mock_cfg.intervalo_entre_posts_segundos = 10
            mock_cfg.posts_antes_pausa = 5
            mock_cfg.tempo_pausa_segundos = 60
            mock_cfg.max_posts_periodo = 20
            mock_cfg.periodo_horas = 24

            ctrl = PublishingController()
            ctrl.reset()
            
            # 1º post liberado
            pode, motivo, espera = ctrl.pode_publicar(agora_ts=1000.0)
            self.assertTrue(pode)
            
            ctrl.registrar_publicacao(agora_ts=1000.0)
            
            # 2 segundos após -> bloqueado por intervalo (espera restante = 8s)
            pode, motivo, espera = ctrl.pode_publicar(agora_ts=1002.0)
            self.assertFalse(pode)
            self.assertIn("intervalo_minimo", motivo)
            self.assertEqual(espera, 8.0)

    def test_publication_controller_pausa_bloco(self):
        """Item 94, 135: Após 5 posts, entra em pausa configurada de 30 minutos."""
        with patch("ofertas.publishing_control.config") as mock_cfg:
            mock_cfg.intervalo_entre_posts_segundos = 0
            mock_cfg.posts_antes_pausa = 5
            mock_cfg.tempo_pausa_segundos = 1800
            mock_cfg.max_posts_periodo = 20
            mock_cfg.periodo_horas = 24

            ctrl = PublishingController()
            ctrl.reset()
            
            # Simula 5 posts
            for i in range(5):
                ctrl.registrar_publicacao(agora_ts=1000.0 + i)
            
            # 6º post deve cair em pausa de bloco
            pode, motivo, espera = ctrl.pode_publicar(agora_ts=1010.0)
            self.assertFalse(pode)
            self.assertIn("pausa", motivo)
            self.assertTrue(1700 <= espera <= 1800)

    def test_publication_controller_limite_periodo(self):
        """Item 95, 96, 136: Atingiu limite de 20 posts no período de 24h -> bloqueia."""
        with patch("ofertas.publishing_control.config") as mock_cfg:
            mock_cfg.intervalo_entre_posts_segundos = 0
            mock_cfg.posts_antes_pausa = 0
            mock_cfg.tempo_pausa_segundos = 0
            mock_cfg.max_posts_periodo = 20
            mock_cfg.periodo_horas = 24

            ctrl = PublishingController()
            ctrl.reset()
            
            # Simula 20 posts registrados
            for i in range(20):
                ctrl.registrar_publicacao(agora_ts=1000.0 + i)
            
            pode, motivo, espera = ctrl.pode_publicar(agora_ts=1100.0)
            self.assertFalse(pode)
            self.assertIn("limite_periodo", motivo)

    # =====================================================================
    # 5. TESTE DE NORMALIZAÇÃO DE USERNAME TELEGRAM (ITENS 113-115)
    # =====================================================================

    def test_telegram_username_normalization(self):
        """Item 114: Normaliza formatos variados para @username."""
        self.assertEqual(normalizar_username_telegram("@canal_ofertas"), "@canal_ofertas")
        self.assertEqual(normalizar_username_telegram("canal_ofertas"), "@canal_ofertas")
        self.assertEqual(normalizar_username_telegram("https://t.me/canal_ofertas"), "@canal_ofertas")
        self.assertEqual(normalizar_username_telegram("t.me/canal_ofertas/"), "@canal_ofertas")
        self.assertEqual(normalizar_username_telegram("-1001234567890"), "-1001234567890")

    # =====================================================================
    # 6. TESTE END-TO-END DRY RUN (ITEM 138)
    # =====================================================================

    def test_end_to_end_scraping_flow(self):
        """Item 138: Fluxo completo Mensagem -> AliExpress -> Rating 96% -> 4.8 -> Vendas 1500 -> Filtro -> Template."""
        with patch("ofertas.filters.config") as mock_filter_cfg, \
             patch("ofertas.publishing_control.config") as mock_pub_cfg:
            
            mock_filter_cfg.palavras_bloqueadas = []
            mock_filter_cfg.avaliacao_minima = 4.5
            mock_filter_cfg.vendas_minimas = 500
            mock_filter_cfg.desconto_minimo = 0
            mock_filter_cfg.desconto_minimo_pct = 0
            mock_filter_cfg.preco_minimo = 0
            mock_filter_cfg.preco_maximo = 0
            mock_filter_cfg.permitir_sem_avaliacao = True
            mock_filter_cfg.permitir_sem_vendas = True
            mock_filter_cfg.permitir_sem_desconto = True

            mock_pub_cfg.intervalo_entre_posts_segundos = 0
            mock_pub_cfg.posts_antes_pausa = 5
            mock_pub_cfg.tempo_pausa_segundos = 1800
            mock_pub_cfg.max_posts_periodo = 20
            mock_pub_cfg.periodo_horas = 24
            
            # 1. Simula dado bruto do AliExpress
            raw_item = {
                "product_id": 999888777,
                "product_title": "Smartwatch Pro AMOLED 1.43 pol",
                "target_sale_price": "149.90",
                "target_original_price": "299.90",
                "discount": "50%",
                "evaluate_rate": "96.0%",
                "lastest_volume": 1500,
                "commission_rate": "15.0%",
                "promotion_link": "https://s.click.aliexpress.com/e/_smartwatch",
                "product_main_image_url": "https://ae01.alicdn.com/kf/watch.jpg",
            }
            
            # 2. Parse AliExpress
            oferta = _item_para_oferta(raw_item)
            self.assertEqual(oferta.avaliacao, 4.8)
            self.assertEqual(oferta.vendas, 1500)
            
            # 3. Filtro de Qualidade
            aprovado, motivo = passes_product_filters(oferta)
            self.assertTrue(aprovado)
            
            # 4. Formatação de template
            mensagem = formatar_mensagem(oferta)
            self.assertIn("Smartwatch Pro AMOLED", mensagem)
            self.assertIn("⭐ 4.8", mensagem)
            self.assertTrue("1.500 vendidos" in mensagem or "1500 vendidos" in mensagem)
            self.assertIn("R$ 149,90", mensagem)
            self.assertIn("50% OFF", mensagem)
            self.assertIn("🔴 AliExpress", mensagem)
            self.assertNotIn("15.0%", mensagem)  # comissão oculta
            
            # 5. Controle de publicação
            ctrl = PublishingController()
            ctrl.reset()
            pode, mot, _ = ctrl.pode_publicar(agora_ts=1000.0)
            self.assertTrue(pode)
            ctrl.registrar_publicacao(agora_ts=1000.0)
            
            status = ctrl.obter_status(agora_ts=1000.0)
            self.assertEqual(status["posts_no_bloco_atual"], 1)
            self.assertEqual(status["posts_no_periodo_atual"], 1)


if __name__ == "__main__":
    unittest.main()
