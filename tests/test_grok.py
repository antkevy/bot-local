"""Testes automatizados para o serviço Grok e pipeline de ofertas.

Cobre todos os 14 cenários da especificação:
1. Título normal não alterado desnecessariamente
2. Título extenso otimizado preservando características essenciais
3. Quantidade / Kit preservado
4. Marca / Modelo preservados
5. Detecção de cupom simples
6. Produto + cupom conjunto
7. Produto sem cupom (tem_cupom=False)
8. Frete grátis (tipo frete_gratis)
9. Mensagem irrelevante / informativa
10. Resposta inválida do Grok -> Fallback seguro
11. API indisponível / erro HTTP / timeout -> Fallback seguro
12. Cache por hash (segunda chamada não faz requisição externa)
13. Não inventar marca/modelo ausente
14. Imutabilidade de dados críticos (preço, preço original, link, id_produto, plataforma)
"""
from __future__ import annotations
import unittest

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import grok as _grok_mod
from ofertas.formatter import montar_caption
from ofertas.grok import GrokResult, GrokService, grok_service
from ofertas.models import Oferta

# O serviço do Grok persiste cada otimização em data/grok_cache.json. Sem este
# desvio, rodar esta suíte sobrescrevia o cache real do usuário com as respostas
# dos testes — chegou a reduzir um cache de 1112 para 264 bytes. Não é preciso
# recriar o serviço: `_carregar_cache`/`_salvar_cache` leem CACHE_FILE do módulo
# a cada chamada, então trocar o atributo aqui já basta.
_grok_mod.CACHE_FILE = Path(tempfile.gettempdir()) / "test_grok_cache.json"
if _grok_mod.CACHE_FILE.exists():
    _grok_mod.CACHE_FILE.unlink()




class TestGrokService(unittest.TestCase):
    def test_1_titulo_normal_mantido(self):
        service = GrokService()
        resultado = GrokResult(
            tipo="produto",
            titulo_otimizado="Fone Bluetooth JBL Tune 520BT",
            tem_cupom=False,
            cupom=None,
            beneficio_cupom=None,
            confianca=0.98,
        )
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(service, "analisar_texto", return_value=resultado):
            oferta = Oferta(
                plataforma="amazon",
                id_produto="B0C12345",
                titulo="Fone Bluetooth JBL Tune 520BT",
                url_afiliado="https://amzn.to/afiliado",
                preco=199.90,
            )
            otimizada = service.otimizar_oferta(oferta)
            assert otimizada.titulo == "Fone Bluetooth JBL Tune 520BT"
            assert otimizada.titulo_original == "Fone Bluetooth JBL Tune 520BT"
            print("✅ TESTE 1 (Título normal mantido): OK")


    def test_2_titulo_enorme_otimizado(self):
        service = GrokService()
        titulo_longo = (
            "Smart TV 50 Polegadas 4K UHD LED WiFi Bluetooth HDR Alexa Built-in "
            "Controle Remoto Inteligente Google Assistente Bivolt Oferta Imperdível"
        )
        resultado = GrokResult(
            tipo="produto",
            titulo_otimizado="Smart TV 50\" 4K UHD LED com Wi-Fi, Bluetooth e Alexa",
            tem_cupom=False,
            cupom=None,
            beneficio_cupom=None,
            confianca=0.97,
        )
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(service, "analisar_texto", return_value=resultado):
            oferta = Oferta(
                plataforma="mercadolivre",
                id_produto="MLB123456",
                titulo=titulo_longo,
                url_afiliado="https://meli.la/afiliado",
                preco=1999.00,
            )
            otimizada = service.otimizar_oferta(oferta)
            assert "50" in otimizada.titulo
            assert "4K" in otimizada.titulo
            assert otimizada.titulo_original == titulo_longo
            print("✅ TESTE 2 (Título longo otimizado com specs preservadas): OK")


    def test_3_quantidade_kit_preservada(self):
        service = GrokService()
        titulo_kit = "Kit 10 Meias Masculinas Cano Médio Algodão Confortável Promoção"
        resultado = GrokResult(
            tipo="produto",
            titulo_otimizado="Kit 10 Meias Masculinas Cano Médio em Algodão",
            tem_cupom=False,
            cupom=None,
            beneficio_cupom=None,
            confianca=0.96,
        )
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(service, "analisar_texto", return_value=resultado):
            oferta = Oferta(
                plataforma="shopee",
                id_produto="SHP123",
                titulo=titulo_kit,
                url_afiliado="https://shope.ee/afiliado",
                preco=29.90,
            )
            otimizada = service.otimizar_oferta(oferta)
            assert "Kit 10" in otimizada.titulo
            print("✅ TESTE 3 (Quantidade / Kit preservado): OK")


    def test_4_marca_modelo_preservados(self):
        service = GrokService()
        titulo_celular = "Samsung Galaxy A55 5G 128GB 8GB RAM Câmera Tripla 50MP Oferta"
        resultado = GrokResult(
            tipo="produto",
            titulo_otimizado="Samsung Galaxy A55 5G 128GB 8GB RAM",
            tem_cupom=False,
            cupom=None,
            beneficio_cupom=None,
            confianca=0.99,
        )
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(service, "analisar_texto", return_value=resultado):
            oferta = Oferta(
                plataforma="amazon",
                id_produto="B09876",
                titulo=titulo_celular,
                url_afiliado="https://amzn.to/a55",
                preco=1799.00,
            )
            otimizada = service.otimizar_oferta(oferta)
            assert "Samsung" in otimizada.titulo
            assert "Galaxy A55" in otimizada.titulo
            assert "128GB" in otimizada.titulo
            print("✅ TESTE 4 (Marca e Modelo preservados): OK")


    def test_5_cupom_simples(self):
        service = GrokService()
        texto_msg = "🎟️ CUPOM MERCADO LIVRE\nUse OFERTA20 e ganhe R$20 OFF em compras acima de R$100."
        mock_resp = {
            "tipo": "cupom",
            "titulo_otimizado": None,
            "tem_cupom": True,
            "cupom": "OFERTA20",
            "beneficio_cupom": "R$20 OFF acima de R$100",
            "confianca": 0.98,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_resp)}}]
            }
            mock_post.return_value = mock_http

            res = service.analisar_texto(texto_msg, usar_cache=False)
            assert res.tipo == "cupom"
            assert res.tem_cupom is True
            assert res.cupom == "OFERTA20"
            assert res.beneficio_cupom == "R$20 OFF acima de R$100"
            print("✅ TESTE 5 (Cupom simples extraído): OK")


    def test_6_produto_com_cupom(self):
        service = GrokService()
        texto_msg = "🔥 Fone Bluetooth TWS\nDe R$89,90 por R$49,90\nCupom: OFERTA20"
        mock_resp = {
            "tipo": "produto",
            "titulo_otimizado": "Fone Bluetooth TWS",
            "tem_cupom": True,
            "cupom": "OFERTA20",
            "beneficio_cupom": None,
            "confianca": 0.96,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_resp)}}]
            }
            mock_post.return_value = mock_http

            oferta = Oferta(
                plataforma="shopee",
                id_produto="SHP99",
                titulo="Fone Bluetooth TWS Sem Fio Barato",
                url_afiliado="https://shope.ee/tws",
                preco=49.90,
                preco_original=89.90,
            )
            otimizada = service.otimizar_oferta(oferta, texto_contexto=texto_msg)
            assert otimizada.tipo == "produto"
            assert otimizada.cupom == "OFERTA20"
            assert otimizada.titulo == "Fone Bluetooth TWS"

            caption = montar_caption(otimizada)
            assert "🏷️ Cupom: <code>OFERTA20</code>" in caption
            print("✅ TESTE 6 (Produto + Cupom extraído e formatado): OK")


    def test_7_produto_sem_cupom(self):
        service = GrokService()
        texto_msg = "🔥 Fone Bluetooth TWS por R$29,90\nAproveite a oferta!"
        mock_resp = {
            "tipo": "produto",
            "titulo_otimizado": "Fone Bluetooth TWS",
            "tem_cupom": False,
            "cupom": None,
            "beneficio_cupom": None,
            "confianca": 0.95,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_resp)}}]
            }
            mock_post.return_value = mock_http

            res = service.analisar_texto(texto_msg, usar_cache=False)
            assert res.tipo == "produto"
            assert res.tem_cupom is False
            assert res.cupom is None
            print("✅ TESTE 7 (Produto sem cupom): OK")


    def test_8_frete_gratis(self):
        service = GrokService()
        texto_msg = "🚚 FRETE GRÁTIS no Mercado Livre hoje em produtos selecionados!"
        mock_resp = {
            "tipo": "frete_gratis",
            "titulo_otimizado": None,
            "tem_cupom": False,
            "cupom": None,
            "beneficio_cupom": "Frete Grátis",
            "confianca": 0.94,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_resp)}}]
            }
            mock_post.return_value = mock_http

            res = service.analisar_texto(texto_msg, usar_cache=False)
            assert res.tipo == "frete_gratis"
            print("✅ TESTE 8 (Classificação de frete grátis): OK")


    def test_9_postagem_irrelevante(self):
        service = GrokService()
        texto_msg = "Bom dia pessoal, alguém sabe que horas abre a loja física hoje?"
        mock_resp = {
            "tipo": "irrelevante",
            "titulo_otimizado": None,
            "tem_cupom": False,
            "cupom": None,
            "beneficio_cupom": None,
            "confianca": 0.99,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_resp)}}]
            }
            mock_post.return_value = mock_http

            res = service.analisar_texto(texto_msg, usar_cache=False)
            assert res.tipo == "irrelevante"
            print("✅ TESTE 9 (Classificação de postagem irrelevante): OK")


    def test_10_resposta_invalida_fallback(self):
        service = GrokService()
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": "JSON TOTALMENTE INVALIDO {{"}}]
            }
            mock_post.return_value = mock_http

            res = service.analisar_texto("Título de Teste para Fallback", usar_cache=False)
            assert res.usou_fallback is True
            assert res.titulo_otimizado == "Título de Teste para Fallback"
            print("✅ TESTE 10 (JSON inválido -> Fallback seguro): OK")


    def test_11_api_indisponivel_fallback(self):
        service = GrokService()
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post", side_effect=Exception("Connection Refused")):
            res = service.analisar_texto("Título Produto Fallback", usar_cache=False)
            assert res.usou_fallback is True
            assert res.titulo_otimizado == "Título Produto Fallback"
            print("✅ TESTE 11 (API indisponível -> Bot continua funcionando com fallback): OK")


    def test_12_cache_segunda_chamada(self):
        service = GrokService()
        service._cache.clear()

        mock_resp = {
            "tipo": "produto",
            "titulo_otimizado": "Smartwatch Relógio Inteligente",
            "tem_cupom": False,
            "cupom": None,
            "beneficio_cupom": None,
            "confianca": 0.95,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(GrokService, "api_key", new_callable=PropertyMock(return_value="xai-mock-key")), \
             patch("requests.post") as mock_post:
            mock_http = MagicMock()
            mock_http.status_code = 200
            mock_http.json.return_value = {
                "choices": [{"message": {"content": json.dumps(mock_resp)}}]
            }
            mock_post.return_value = mock_http

            # 1ª chamada: deve bater na API
            res1 = service.analisar_texto("Smartwatch Relógio Inteligente Pro", usar_cache=True)
            assert mock_post.call_count == 1
            assert res1.usou_cache is False

            # 2ª chamada: deve ler do cache sem fazer nova requisição HTTP
            res2 = service.analisar_texto("Smartwatch Relógio Inteligente Pro", usar_cache=True)
            assert mock_post.call_count == 1  # Continua 1!
            assert res2.usou_cache is True
            assert res2.titulo_otimizado == "Smartwatch Relógio Inteligente"
            print("✅ TESTE 12 (Cache hit na 2ª chamada sem requisição): OK")


    def test_13_nao_inventar_dados(self):
        service = GrokService()
        mock_resp = {
            "tipo": "produto",
            "titulo_otimizado": "Garrafa Térmica 1L em Inox",
            "tem_cupom": False,
            "cupom": None,
            "beneficio_cupom": None,
            "confianca": 0.95,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(service, "analisar_texto", return_value=GrokResult(**mock_resp)):
            oferta = Oferta(
                plataforma="aliexpress",
                id_produto="ALI1234",
                titulo="Garrafa Térmica 1L Inox Portátil Academia Camping Promoção",
                url_afiliado="https://s.click.aliexpress.com/e/afiliado",
                preco=45.00,
            )
            otimizada = service.otimizar_oferta(oferta)
            assert "Stanley" not in otimizada.titulo
            assert "Kouda" not in otimizada.titulo
            assert otimizada.titulo == "Garrafa Térmica 1L em Inox"
            print("✅ TESTE 13 (Não inventa marcas/dados ausentes): OK")


    def test_14_dados_criticos_protegidos(self):
        service = GrokService()
        mock_resp = {
            "tipo": "produto",
            "titulo_otimizado": "Air Fryer Fritadeira Sem Óleo 4L",
            "tem_cupom": True,
            "cupom": "FRY10",
            "beneficio_cupom": "10% OFF",
            "confianca": 0.98,
        }
        with patch.object(GrokService, "ativo", new_callable=PropertyMock(return_value=True)), \
             patch.object(service, "analisar_texto", return_value=GrokResult(**mock_resp)):
            oferta_original = Oferta(
                plataforma="mercadolivre",
                id_produto="MLB998877",
                titulo="Fritadeira Elétrica Sem Óleo Air Fryer 4 Litros 1500W Bivolt",
                url_afiliado="https://mercadolivre.com/afiliado_real",
                url_produto="https://mercadolivre.com/produto_original",
                preco=249.90,
                preco_original=399.90,
                desconto_pct=37,
                imagem="https://img.mercadolivre.com/foto.jpg",
                extra="Frete grátis",
            )
            otimizada = service.otimizar_oferta(oferta_original)

            # Campos críticos INTACTOS
            assert otimizada.plataforma == "mercadolivre"
            assert otimizada.id_produto == "MLB998877"
            assert otimizada.uid == "mercadolivre:MLB998877"
            assert otimizada.url_afiliado == "https://mercadolivre.com/afiliado_real"
            assert otimizada.url_produto == "https://mercadolivre.com/produto_original"
            assert otimizada.preco == 249.90
            assert otimizada.preco_original == 399.90
            assert otimizada.desconto == 37
            assert otimizada.imagem == "https://img.mercadolivre.com/foto.jpg"
            assert otimizada.extra == "Frete grátis"

            # Título original preservado para auditoria
            assert otimizada.titulo_original == "Fritadeira Elétrica Sem Óleo Air Fryer 4 Litros 1500W Bivolt"
            assert otimizada.titulo == "Air Fryer Fritadeira Sem Óleo 4L"
            assert otimizada.cupom == "FRY10"

            # Template monta perfeitamente
            caption = montar_caption(otimizada)
            assert "Air Fryer Fritadeira Sem Óleo 4L" in caption
            assert "R$ 249,90" in caption
            assert "R$ 399,90" in caption
            assert "37% OFF" in caption
            assert "🏷️ Cupom: <code>FRY10</code>" in caption
            assert "💛 Mercado Livre" in caption
            print("✅ TESTE 14 (Dados críticos de preço/link/ID 100% protegidos): OK")


