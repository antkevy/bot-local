"""AliExpress: busca de ofertas e geração de links de afiliados via AliExpress Open Platform.

Documentação oficial: AliExpress Affiliate Open API
Gateway padrão: https://api-sg.aliexpress.com/sync (ou https://api-sg.aliexpress.com/rest)
Operações suportadas:
- aliexpress.affiliate.product.query (pesquisa de ofertas com comissão)
- aliexpress.affiliate.productdetail.get (detalhes de produto específico)
- aliexpress.affiliate.link.generate (geração de links de afiliados)
"""
import datetime as dt
import hashlib
import hmac
import json
import logging
import os
import re
import time
from urllib.parse import parse_qs, urlparse

import requests

from ..config import config
from ..models import Oferta
from ..utils import sessao

log = logging.getLogger("ofertas.aliexpress")

ENDPOINT_PADRAO = "https://api-sg.aliexpress.com/sync"


def e_link(url: str) -> bool:
    """Verifica se a URL pertence ao AliExpress."""
    url_lower = url.lower()
    return any(d in url_lower for d in (
        "aliexpress.com",
        "pt.aliexpress.com",
        "a.aliexpress.com",
        "s.click.aliexpress.com",
        "ali.ski",
    ))


def _obter_credenciais() -> tuple[str, str, str, str, str]:
    """Retorna (app_key, app_secret, tracking_id, endpoint, sign_method)."""
    app_key = getattr(config, "aliexpress_app_key", "") or os.getenv("ALIEXPRESS_APP_KEY", "").strip()
    app_secret = getattr(config, "aliexpress_app_secret", "") or os.getenv("ALIEXPRESS_APP_SECRET", "").strip()
    tracking_id = getattr(config, "aliexpress_tracking_id", "") or os.getenv("ALIEXPRESS_TRACKING_ID", "").strip()
    endpoint = (getattr(config, "aliexpress_api_endpoint", "") or os.getenv("ALIEXPRESS_API_ENDPOINT", "").strip()) or ENDPOINT_PADRAO
    sign_method = (getattr(config, "aliexpress_sign_method", "") or os.getenv("ALIEXPRESS_SIGN_METHOD", "").strip().lower()) or "sha256"
    return app_key, app_secret, tracking_id, endpoint, sign_method


def _gerar_assinatura(params: dict, secret: str, metodo: str = "sha256") -> str:
    """Gera a assinatura TOP/AliExpress Open Platform.
    
    1. Ordena todos os parâmetros alfabeticamente por chave.
    2. Concatena chave e valor em uma única string: k1v1k2v2...
    3. Para HMAC-SHA256: HMAC(secret, string, SHA256) em hexadecimal maiúsculo.
       Para MD5: MD5(secret + string + secret) em hexadecimal maiúsculo.
    """
    chaves_ordenadas = sorted(k for k in params.keys() if k != "sign" and params[k] is not None)
    texto = "".join(f"{k}{params[k]}" for k in chaves_ordenadas)

    if metodo == "md5":
        bruto = f"{secret}{texto}{secret}"
        return hashlib.md5(bruto.encode("utf-8")).hexdigest().upper()
    else:  # sha256 / hmac-sha256 padrão
        return hmac.new(
            secret.encode("utf-8"),
            texto.encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()


def _chamar_api(metodo_api: str, params_api: dict | None = None) -> dict:
    """Executa uma chamada à API oficial do AliExpress Open Platform."""
    app_key, app_secret, _, endpoint, sign_method = _obter_credenciais()
    if not (app_key and app_secret):
        raise RuntimeError("Configure ALIEXPRESS_APP_KEY e ALIEXPRESS_APP_SECRET no .env para usar o AliExpress.")

    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    params: dict = {
        "app_key": app_key,
        "timestamp": agora,
        "format": "json",
        "v": "2.0",
        "sign_method": sign_method,
        "method": metodo_api,
    }

    if params_api:
        for k, v in params_api.items():
            if v is not None:
                params[k] = str(v)

    params["sign"] = _gerar_assinatura(params, app_secret, sign_method)

    try:
        r = requests.post(endpoint, data=params, timeout=25)
        r.raise_for_status()
        dados = r.json()
    except requests.exceptions.RequestException as e:
        log.error("Erro na requisição ao AliExpress: %s", e)
        raise RuntimeError(f"Falha de conexão com a API do AliExpress: {e}")
    except json.JSONDecodeError:
        raise RuntimeError("Resposta inválida recebida da API do AliExpress.")

    # Verificação de erros no formato TOP / AliExpress
    if "error_response" in dados:
        err = dados["error_response"]
        msg = err.get("sub_msg") or err.get("msg") or f"Erro código {err.get('code')}"
        sub_code = err.get("sub_code") or ""
        log.error("AliExpress API Error [%s]: %s", sub_code, msg)
        raise RuntimeError(f"AliExpress API: {msg}")

    return dados


def _converter_rating_percentual(raw_val) -> float | None:
    """Converte avaliação percentual do AliExpress (ex: '96.0%', 96) para escala 1-5 estrelas (4.8)."""
    if raw_val is None:
        return None
    try:
        val_str = str(raw_val).replace("%", "").strip()
        if not val_str or val_str.upper() in ("NONE", "NULL", "N/A"):
            return None
        val_float = float(val_str)
        if val_float > 5.0:
            # Escala de 0-100% -> 0-5.0 (ex: 96% / 20 = 4.8)
            return round(val_float / 20.0, 1)
        elif val_float >= 0:
            return round(val_float, 1)
        return None
    except (ValueError, TypeError):
        return None


def _item_para_oferta(item: dict) -> Oferta:
    """Normaliza um produto retornado pela API do AliExpress para o modelo interno Oferta."""
    pid = str(item.get("product_id") or item.get("item_id") or "")
    titulo = str(item.get("product_title") or item.get("title") or "Oferta AliExpress").strip()
    
    # Preços (target_sale_price é na moeda de destino configurada, ex: BRL)
    preco_venda_raw = item.get("target_sale_price") or item.get("sale_price") or item.get("target_app_sale_price") or 0
    preco_orig_raw = item.get("target_original_price") or item.get("original_price") or 0

    try:
        preco = float(str(preco_venda_raw).replace(",", ".")) if preco_venda_raw else None
    except (ValueError, TypeError):
        preco = None

    try:
        preco_original = float(str(preco_orig_raw).replace(",", ".")) if preco_orig_raw else None
    except (ValueError, TypeError):
        preco_original = None

    # Desconto
    desconto_raw = str(item.get("discount") or "").replace("%", "").strip()
    try:
        desconto_pct = int(float(desconto_raw)) if desconto_raw else None
    except (ValueError, TypeError):
        desconto_pct = None

    if preco and preco_original and preco_original > preco and not desconto_pct:
        desconto_pct = round(100 * (1 - preco / preco_original))

    imagem = item.get("product_main_image_url")
    if not imagem:
        # A API manda `product_small_image_urls: {"string": [url, ...]}`. O `[0]`
        # antigo rodava sobre o valor cru: se `string` vier como texto (e não
        # lista), pegava o primeiro CARACTERE e o envio da foto quebrava.
        menores = item.get("product_small_image_urls")
        lista_pequenas = menores.get("string") if isinstance(menores, dict) else None
        if isinstance(lista_pequenas, list) and lista_pequenas:
            imagem = lista_pequenas[0]

    # Links. O `promotion_link` das APIs (product.query / productdetail.get) veio
    # CONSTANTE e genérico (ex.: best.aliexpress.com) para produtos diferentes —
    # não aponta para o produto e não pode virar o link público. O link de
    # afiliado certo só sai de aliexpress.affiliate.link.generate; por isso aqui
    # fica vazio e quem monta a oferta gera o link (_garantir_link_afiliado).
    url_afiliado = ""
    url_produto = item.get("product_detail_url") or f"https://pt.aliexpress.com/item/{pid}.html" if pid else ""

    # Avaliação (AliExpress retorna percentual ex: 96% -> 4.8 estrelas)
    avaliacao = _converter_rating_percentual(item.get("evaluate_rate"))


    # Quantidade de vendas / pedidos
    vendas: int | None = None
    raw_vendas = item.get("lastest_volume") or item.get("volume") or item.get("sale_count")
    if raw_vendas:
        try:
            vendas = int(raw_vendas)
        except (ValueError, TypeError):
            pass

    # Comissão de afiliado (dado técnico interno — NUNCA enviado ao template)
    comissao_pct: float | None = None
    if item.get("commission_rate"):
        try:
            comissao_pct = float(str(item["commission_rate"]).replace("%", "").strip())
        except (ValueError, TypeError):
            pass

    return Oferta(
        plataforma="aliexpress",
        id_produto=pid,
        titulo=titulo,
        url_afiliado=url_afiliado,
        url_produto=url_produto,
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto_pct,
        imagem=imagem,
        avaliacao=avaliacao,
        vendas=vendas,
        comissao_pct=comissao_pct,
        extra=None,
    )


def _garantir_link_afiliado(oferta: Oferta) -> Oferta:
    """Garante que a oferta carregue SEMPRE o nosso link de afiliado do produto.

    As APIs de produto devolvem `promotion_link` genérico/constante (medido:
    best.aliexpress.com para itens distintos). O link que resolve para o item
    exato com o nosso aff_fcid só sai de aliexpress.affiliate.link.generate.
    Levanta se a API falhar — sem link de afiliado, sem post.
    """
    if not oferta.url_produto:
        raise RuntimeError("Sem URL de produto para gerar o link de afiliado")
    oferta.url_afiliado = gerar_link_afiliado(oferta.url_produto)
    return oferta


def testar_conexao() -> dict:
    """Valida as credenciais chamando a API de pesquisa de produtos de afiliados."""
    app_key, app_secret, tracking_id, _, _ = _obter_credenciais()
    if not app_key or not app_secret:
        return {"ok": False, "erro": "ALIEXPRESS_APP_KEY ou ALIEXPRESS_APP_SECRET não configurados no .env."}

    log.info("[ALIEXPRESS] Testando conexão com a API oficial...")
    params = {
        "page_no": 1,
        "page_size": 2,
        "target_currency": "BRL",
        "target_language": "PT",
        "ship_to_country": "BR",
        "sort": "SALE_PRICE_ASC",
    }
    if tracking_id:
        params["tracking_id"] = tracking_id

    try:
        dados = _chamar_api("aliexpress.affiliate.product.query", params)
        resp = (
            dados.get("aliexpress_affiliate_product_query_response")
            or dados.get("resp_result")
            or {}
        )
        result = resp.get("resp_result", {}).get("result") or resp.get("result") or {}
        produtos = result.get("products", {}).get("product", []) if isinstance(result.get("products"), dict) else (result.get("products") or [])

        log.info("[ALIEXPRESS] Conexão bem-sucedida! Retornados %d produto(s) de teste.", len(produtos))
        return {
            "ok": True,
            "msg": f"Conexão com AliExpress validada com sucesso! ({len(produtos)} produtos retornados na consulta de teste)",
            "produtos_retornados": len(produtos),
        }
    except Exception as e:
        log.error("[ALIEXPRESS] Falha no teste de conexão: %s", e)
        return {"ok": False, "erro": str(e)}


def buscar_ofertas(limite: int = 30) -> list[Oferta]:
    """Busca ofertas no AliExpress usando aliexpress.affiliate.product.query."""
    _, _, tracking_id, _, _ = _obter_credenciais()
    termos = getattr(config, "fonte_aliexpress", {}).get("buscas") or []
    if not termos:
        termos = ["tecnologia", "eletronicos", "fone bluetooth", "smartwatch", "gadgets"]

    por_termo = max(5, limite // len(termos))
    todas_ofertas: dict[str, Oferta] = {}

    log.info("[ALIEXPRESS] Busca de ofertas iniciada para %d termos...", len(termos))

    for termo in termos:
        params = {
            "keywords": termo,
            "page_no": 1,
            "page_size": min(por_termo, 50),
            "target_currency": "BRL",
            "target_language": "PT",
            "ship_to_country": "BR",
            "sort": "LAST_VOLUME_DESC",
        }
        if tracking_id:
            params["tracking_id"] = tracking_id

        try:
            dados = _chamar_api("aliexpress.affiliate.product.query", params)
            resp = (
                dados.get("aliexpress_affiliate_product_query_response")
                or dados.get("resp_result")
                or {}
            )
            result = resp.get("resp_result", {}).get("result") or resp.get("result") or {}
            produtos_raw = result.get("products", {}).get("product", []) if isinstance(result.get("products"), dict) else (result.get("products") or [])

            for p in produtos_raw:
                oferta = _item_para_oferta(p)
                if not (oferta.id_produto and oferta.url_produto):
                    continue
                try:
                    _garantir_link_afiliado(oferta)
                except Exception as e:
                    log.warning("[ALIEXPRESS] Sem link de afiliado p/ %s: %s",
                                oferta.id_produto, e)
                    continue
                todas_ofertas[oferta.id_produto] = oferta
        except Exception as e:
            log.warning("[ALIEXPRESS] Erro ao buscar termo '%s': %s", termo, e)

    lista = list(todas_ofertas.values())
    log.info("[ALIEXPRESS] Busca finalizada: %d produtos encontrados.", len(lista))
    return lista


_RE_ITEM_ID = re.compile(r"/item/(\d+)\.html|item_id=(\d+)|productId=(\d+)")


def extrair_item_id(url: str) -> str | None:
    """Extrai o product ID numérico de uma URL do AliExpress."""
    m = _RE_ITEM_ID.search(url)
    if m:
        return m.group(1) or m.group(2) or m.group(3)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for chave in ("id", "itemId", "productId", "item_id"):
        if chave in qs and qs[chave]:
            return qs[chave][0]
    return None


def e_id_produto(id_produto: str | None) -> bool:
    """Diz se o id é de um produto, e não de uma página da loja.

    O `converter` só devolve ids extraídos de /item/<id> (numéricos) — páginas
    de vitrine/wholesale/cupom são descartadas na conversão. Com a função
    explícita, o pipeline classifica qualquer slug residual como não-produto em
    vez de assumir True (o padrão para fontes sem a função).
    """
    return bool(id_produto) and str(id_produto).isdigit()


def gerar_link_afiliado(url: str) -> str:
    """Gera um link de afiliado oficial para qualquer URL de produto do AliExpress."""
    app_key, app_secret, tracking_id, _, _ = _obter_credenciais()
    if not (app_key and app_secret):
        raise RuntimeError("Credenciais do AliExpress não configuradas.")

    params = {
        "promotion_link_type": 0,
        "source_values": url,
    }
    if tracking_id:
        params["tracking_id"] = tracking_id

    dados = _chamar_api("aliexpress.affiliate.link.generate", params)
    resp = (
        dados.get("aliexpress_affiliate_link_generate_response")
        or dados.get("resp_result")
        or {}
    )
    result = resp.get("resp_result", {}).get("result") or resp.get("result") or {}
    links = result.get("promotion_links", {}).get("promotion_link", []) if isinstance(result.get("promotion_links"), dict) else (result.get("promotion_links") or [])

    if links and isinstance(links, list):
        link_obj = links[0]
        prom_link = link_obj.get("promotion_link")
        if prom_link:
            log.info("[ALIEXPRESS] Link de afiliado gerado com sucesso para: %s", url[:50])
            return prom_link

    raise RuntimeError("A API do AliExpress não retornou o link promocional.")


def converter(url: str) -> Oferta:
    """URL de produto do AliExpress -> Oferta completa com link de afiliado.

    Só converte URL de produto (item_id presente). Página de loja, categoria,
    cupom ou link desconhecido é descartada com RuntimeError — nunca vira oferta
    com título genérico e link de afiliado gerado sobre a página errada.
    """
    # Expandir links curtos caso necessário
    if any(s in url for s in ("a.aliexpress.com", "s.click.aliexpress.com", "ali.ski")):
        try:
            url_expandida = sessao().get(url, allow_redirects=True, timeout=15).url
            if url_expandida:
                url = url_expandida
        except Exception as e:
            log.warning("[ALIEXPRESS] Não foi possível expandir o link curto: %s", e)

    item_id = extrair_item_id(url)
    _, _, tracking_id, _, _ = _obter_credenciais()

    # Se temos o ID do produto, buscar detalhes enriquecidos
    if item_id:
        try:
            params = {
                "product_ids": item_id,
                "target_currency": "BRL",
                "target_language": "PT",
                "ship_to_country": "BR",
            }
            if tracking_id:
                params["tracking_id"] = tracking_id
            
            dados = _chamar_api("aliexpress.affiliate.productdetail.get", params)
            resp = (
                dados.get("aliexpress_affiliate_productdetail_get_response")
                or dados.get("resp_result")
                or {}
            )
            result = resp.get("resp_result", {}).get("result") or resp.get("result") or {}
            produtos_raw = result.get("products", {}).get("product", []) if isinstance(result.get("products"), dict) else (result.get("products") or [])
            if produtos_raw:
                oferta = _item_para_oferta(produtos_raw[0])
                # promotion_link das APIs vem genérico/constante (ex.:
                # best.aliexpress.com); o link do item exato com o nosso
                # aff_fcid só sai do link.generate — sempre gerar.
                _garantir_link_afiliado(oferta)
                return oferta
        except Exception as e:
            log.warning("[ALIEXPRESS] Falha ao obter detalhes do item %s: %s", item_id, e)

    # URL sem id de item (vitrine, categoria, cupom, página desconhecida). Gerar
    # um link aqui transformaria uma página de loja em "oferta" — inventar
    # produto onde não há. Descarta (o pipeline tenta o próximo link).
    if not item_id:
        raise RuntimeError("URL não é de produto AliExpress (sem itemId)")

    # Fallback: o productdetail.get falhou (item fora do catálogo de afiliados,
    # erro transitório), mas a URL É de produto. O link continua saindo do
    # link.generate — nunca cru, nunca o de outro item.
    link_afiliado = gerar_link_afiliado(url)
    return Oferta(
        plataforma="aliexpress",
        id_produto=item_id,
        titulo="Oferta AliExpress",
        url_afiliado=link_afiliado,
        url_produto=url,
    )
