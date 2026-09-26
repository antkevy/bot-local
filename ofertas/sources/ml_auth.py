"""Serviço central de Autenticação em Cascata do Mercado Livre.

Ordem de prioridade estrita:
1. Link Builder (Playwright / Perfil Chrome local em data/ml_profile)
2. Cookie (Fallback direto via API createLink autenticada por cookie)
3. Falha definitiva -> Salva em ofertas_pendentes_ml e notifica o admin (com cooldown)

NUNCA publica ofertas do Mercado Livre sem link de afiliado válido.
NUNCA utiliza a URL original como affiliate_link.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

from .. import db
from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import USER_AGENT, sessao

log = logging.getLogger("ofertas.ml_auth")

COOKIE_FILE = DATA_DIR / "ml_cookies.json"
API_CREATELINK = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"
URL_TESTE_DEFAULT = "https://www.mercadolivre.com.br/p/MLB12345678"

# Controle de estado de notificação (anti-spam)
_notificacao_enviada: bool = False
_ultimo_aviso_ts: float = 0.0
COOLDOWN_NOTIFICACAO_SEGUNDOS: int = 3600  # 1 hora de intervalo entre avisos automáticos


def _mascarar_cookie(cookie: str) -> str:
    """Mascara o cookie para evitar vazamento em logs ou rastreamentos."""
    if not cookie:
        return "[VAZIO]"
    return "[REDACTED]"


def obter_cookie_configurado() -> str:
    """Retorna o cookie ativo salvo em arquivo local ou no .env."""
    if COOKIE_FILE.exists():
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                c = dados.get("cookie", "").strip()
                if c:
                    return c
        except Exception as e:
            log.warning("[ML-AUTH] Erro ao ler cookie do arquivo local: %s", e)

    return (config.ml_cookie or "").strip()


def salvar_cookie_local(cookie_str: str) -> None:
    """Salva o cookie validado de forma segura no diretório data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump({"cookie": cookie_str.strip(), "atualizado_em": time.time()}, f, indent=2)
    config.ml_cookie = cookie_str.strip()


def tem_cookie() -> bool:
    """Verifica se há um cookie configurado."""
    return bool(obter_cookie_configurado())


def tem_sessao_linkbuilder() -> bool:
    """Verifica se há perfil persistente do Linkbuilder em data/ml_profile."""
    from . import mercadolivre
    return mercadolivre.tem_sessao()


def _gerar_via_cookie_raw(urls: list[str], etiqueta: str, cookie_str: str, timeout: int = 15) -> list[str]:
    """Chama a API createLink diretamente com o Cookie HTTP fornecido."""
    if not cookie_str:
        raise ValueError("Cookie não fornecido")
    if not etiqueta:
        raise ValueError("ML_ETIQUETA não configurada")

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.mercadolivre.com.br",
        "Referer": "https://www.mercadolivre.com.br/afiliados/linkbuilder",
        "Cookie": cookie_str,
    }
    payload = {"urls": urls, "tag": etiqueta}

    try:
        r = requests.post(API_CREATELINK, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise ConnectionError(f"Erro de conexão com a API do Mercado Livre: {e}") from e

    if r.status_code == 401 or r.status_code == 403 or "login" in r.url:
        raise PermissionError(f"Cookie do Mercado Livre expirado ou não autorizado (HTTP {r.status_code})")

    if r.status_code != 200:
        raise RuntimeError(f"API createLink respondeu HTTP {r.status_code}: {r.text[:200]}")

    try:
        dados = r.json()
    except Exception as e:
        raise ValueError(f"Resposta inválida da API do Mercado Livre (não é JSON): {r.text[:200]}") from e

    itens = dados.get("urls") or []
    links = [i.get("short_url") or "" for i in itens]
    if len(links) != len(urls) or not all(links):
        raise RuntimeError(f"createLink devolveu links incompletos: {dados}")

    return links


class MercadoLivreAuthService:
    """Gerenciador central de autenticação e geração de links de afiliado em cascata."""

    def __init__(self):
        pass

    def gerar_links_afiliado(self, ofertas: list[Oferta], bot: Any = None) -> None:
        """Gera links de afiliado para uma lista de ofertas utilizando a cascata Link Builder -> Cookie.
        
        Se ambos os métodos falharem, salva as ofertas pendentes no banco e notifica o admin.
        """
        pendentes = [o for o in ofertas if not o.url_afiliado and o.url_produto]
        if not pendentes:
            return

        etiqueta = config.ml_etiqueta or "fastpromo"
        falha_linkbuilder = False
        falha_cookie = False

        # ── 1. Tentar primeiro via Link Builder ────────────────────────
        if tem_sessao_linkbuilder():
            log.info("[ML-AUTH] Tentando geração de links via Link Builder...")
            try:
                from . import mercadolivre
                # Chama o gerador via Playwright
                mercadolivre._gerar_links_linkbuilder_batch(pendentes, etiqueta)
                # Verifica se gerou para todos
                ainda_sem = [o for o in pendentes if not o.url_afiliado]
                if not ainda_sem:
                    log.info("[ML-AUTH] ✅ %d link(s) gerado(s) com sucesso via Link Builder.", len(pendentes))
                    return
                else:
                    pendentes = ainda_sem
                    falha_linkbuilder = True
            except Exception as e:
                log.warning("[ML-AUTH] Link Builder falhou (%s). Iniciando fallback para Cookie...", type(e).__name__)
                falha_linkbuilder = True
        else:
            log.info("[ML-AUTH] Sessão do Link Builder não encontrada. Iniciando fallback para Cookie...")
            falha_linkbuilder = True

        # ── 2. Fallback automático para Cookie ─────────────────────────
        cookie = obter_cookie_configurado()
        if cookie:
            log.info("[ML-AUTH] Tentando geração de links via Cookie (fallback)...")
            try:
                urls = [o.url_produto for o in pendentes]
                links = _gerar_via_cookie_raw(urls, etiqueta, cookie)
                for o, link in zip(pendentes, links):
                    o.url_afiliado = link
                log.info("[ML-AUTH] ✅ %d link(s) gerado(s) com sucesso via Cookie.", len(pendentes))
                return
            except PermissionError as pe:
                log.warning("[ML-AUTH] Cookie do Mercado Livre expirado/inválido: %s", pe)
                falha_cookie = True
            except Exception as e:
                log.warning("[ML-AUTH] Erro ao gerar link via Cookie: %s", e)
                falha_cookie = True
        else:
            log.warning("[ML-AUTH] Nenhum cookie configurado para fallback.")
            falha_cookie = True

        # ── 3. Falha definitiva: Não publicar + Salvar pendência + Avisar admin
        if falha_linkbuilder and falha_cookie:
            log.error("[ML-AUTH] ❌ Falha em todos os métodos de autenticação do Mercado Livre. Bloqueando publicação.")
            for o in pendentes:
                o.url_afiliado = ""  # GARANTIA: Nunca usar URL original
                db.salvar_oferta_pendente_ml(o, status="aguardando_autenticacao")

            # Enviar aviso privado ao admin
            self.notificar_admin_se_necessario(bot)

    def testar_autenticacao(self, url_teste: str = URL_TESTE_DEFAULT) -> dict[str, Any]:
        """Testa o status de autenticação seguindo a cascata Link Builder -> Cookie."""
        etiqueta = config.ml_etiqueta or "fastpromo"

        # 1. Testar Link Builder
        if tem_sessao_linkbuilder():
            try:
                from . import mercadolivre
                oferta_teste = Oferta(plataforma="mercadolivre", id_produto="TEST1", url_produto=url_teste, titulo="Teste")
                mercadolivre._gerar_links_linkbuilder_batch([oferta_teste], etiqueta)
                if oferta_teste.url_afiliado:
                    return {
                        "authenticated": True,
                        "method": "linkbuilder",
                        "affiliate_generation": True,
                        "error": None,
                        "link_teste": oferta_teste.url_afiliado,
                    }
            except Exception as e:
                log.info("[ML-AUTH] Teste do Link Builder falhou: %s", e)

        # 2. Testar Cookie
        cookie = obter_cookie_configurado()
        if cookie:
            try:
                links = _gerar_via_cookie_raw([url_teste], etiqueta, cookie, timeout=10)
                if links and links[0]:
                    return {
                        "authenticated": True,
                        "method": "cookie",
                        "affiliate_generation": True,
                        "error": None,
                        "link_teste": links[0],
                    }
            except PermissionError as pe:
                return {
                    "authenticated": False,
                    "method": "cookie",
                    "affiliate_generation": False,
                    "error": "cookie_expired",
                    "detalhe": str(pe),
                }
            except Exception as e:
                return {
                    "authenticated": False,
                    "method": "cookie",
                    "affiliate_generation": False,
                    "error": "cookie_error",
                    "detalhe": str(e),
                }

        # 3. Nenhum método funcionando
        return {
            "authenticated": False,
            "method": None,
            "affiliate_generation": False,
            "error": "authentication_expired",
            "detalhe": "Link Builder e Cookie não autenticados",
        }

    def validar_e_salvar_novo_cookie(self, novo_cookie: str, bot: Any = None) -> dict[str, Any]:
        """Testa o novo cookie antes de salvar. Se for válido, atualiza e processa pendências."""
        cookie_limpo = novo_cookie.strip()
        if not cookie_limpo:
            return {"ok": False, "erro": "Cookie fornecido está vazio."}

        etiqueta = config.ml_etiqueta or "fastpromo"
        try:
            links = _gerar_via_cookie_raw([URL_TESTE_DEFAULT], etiqueta, cookie_limpo, timeout=12)
            if not links or not links[0]:
                return {"ok": False, "erro": "O novo cookie não gerou links válidos. O cookie anterior foi mantido."}
        except PermissionError:
            return {"ok": False, "erro": "O novo cookie está expirado ou não autorizado pelo Mercado Livre. O cookie anterior foi mantido."}
        except Exception as e:
            return {"ok": False, "erro": f"Falha ao validar o novo cookie: {e}. O cookie anterior foi mantido."}

        # Sucesso no teste -> Salvar e resetar alerta
        salvar_cookie_local(cookie_limpo)
        global _notificacao_enviada
        _notificacao_enviada = False

        log.info("[ML-AUTH] ✅ Novo cookie do Mercado Livre validado e salvo com sucesso!")

        # Processar ofertas que estavam pendentes
        total_reprocessadas = 0
        if bot:
            try:
                total_reprocessadas = self.processar_ofertas_pendentes(bot)
            except Exception as e:
                log.error("[ML-AUTH] Erro ao reprocessar pendências após salvar cookie: %s", e)

        return {
            "ok": True,
            "msg": "Novo cookie do Mercado Livre validado e salvo com sucesso!",
            "ofertas_reprocessadas": total_reprocessadas,
            "link_teste": links[0],
        }

    def notificar_admin_se_necessario(self, bot: Any = None) -> bool:
        """Envia uma notificação privada ao administrador do bot com cooldown anti-spam."""
        global _notificacao_enviada, _ultimo_aviso_ts
        agora = time.time()

        if not config.owner_id:
            log.debug("[ML-AUTH] TELEGRAM_OWNER_ID não configurado — impossível enviar notificação privada.")
            return False

        if not bot:
            log.debug("[ML-AUTH] Instância do bot não disponível para enviar notificação privada.")
            return False

        # Verifica cooldown para evitar flood
        if _notificacao_enviada and (agora - _ultimo_aviso_ts) < COOLDOWN_NOTIFICACAO_SEGUNDOS:
            log.info("[ML-AUTH] Notificação de autenticação suprimida (cooldown ativo).")
            return False

        msg = (
            "⚠️ <b>Mercado Livre precisa de autenticação</b>\n\n"
            "Não foi possível gerar o link de afiliado de um ou mais produtos porque a "
            "autenticação atual do Mercado Livre expirou ou está inválida.\n\n"
            "Escolha uma opção para renovar:\n"
            "🔐 <b>Login via Link Builder:</b> Rode <code>uv run python -m ofertas ml-login</code> no terminal ou pelo painel.\n"
            "🍪 <b>Atualizar Cookie:</b> Envie o comando <code>/setcookie &lt;cookie&gt;</code> aqui no privado.\n\n"
            "<i>Os produtos afetados foram salvos e aguardam a renovação para serem publicados automaticamente.</i>"
        )

        try:
            import asyncio
            if asyncio.iscoroutinefunction(bot.send_message):
                # Se estivermos dentro de uma função async
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(bot.send_message(chat_id=config.owner_id, text=msg, parse_mode="HTML"))
                except RuntimeError:
                    asyncio.run(bot.send_message(chat_id=config.owner_id, text=msg, parse_mode="HTML"))
            else:
                bot.send_message(chat_id=config.owner_id, text=msg, parse_mode="HTML")

            _notificacao_enviada = True
            _ultimo_aviso_ts = agora
            log.info("[ML-AUTH] 📢 Notificação privada de autenticação enviada ao admin (ID: %s).", config.owner_id)
            return True
        except Exception as e:
            log.error("[ML-AUTH] Erro ao enviar notificação de autenticação ao admin: %s", e)
            return False

    def processar_ofertas_pendentes(self, bot: Any) -> int:
        """Reprocessa ofertas do Mercado Livre que estavam aguardando autenticação."""
        pendentes_db = db.listar_ofertas_pendentes_ml(status="aguardando_autenticacao")
        if not pendentes_db:
            return 0

        log.info("[ML-AUTH] 🔄 Reprocessando %d oferta(s) pendente(s) do Mercado Livre...", len(pendentes_db))
        total_publicadas = 0

        from ..formatter import montar_caption
        from ..pipeline import filtrar, postar_oferta

        for row in pendentes_db:
            uid = row["uid"]
            # Deduplicação: se já foi postada nesse intervalo, apenas limpa a pendência
            if db.ja_postada(uid, config.nao_repetir_dias):
                db.remover_oferta_pendente_ml(uid)
                continue

            oferta = Oferta(
                plataforma="mercadolivre",
                id_produto=uid.split(":")[-1] if ":" in uid else uid,
                titulo=row["titulo"],
                url_produto=row["url_produto"],
                preco=row["preco"],
                preco_original=row["preco_original"],
                desconto_pct=row["desconto"],
                imagem=row["imagem"],
                cupom=row["cupom"],
                beneficio_cupom=row["beneficio_cupom"],
                tipo=row["tipo"] or "produto",
                extra=row["raw_data"],
            )

            # Tenta gerar o link de afiliado
            self.gerar_links_afiliado([oferta], bot=bot)

            if oferta.url_afiliado:
                # Passa pelos filtros existentes
                aprovadas = filtrar([oferta])
                if aprovadas and config.chat_id and bot:
                    try:
                        import asyncio
                        if asyncio.iscoroutinefunction(postar_oferta):
                            asyncio.run(postar_oferta(bot, oferta, config.chat_id))
                        else:
                            postar_oferta(bot, oferta, config.chat_id)
                        db.registrar(oferta)
                        total_publicadas += 1
                        log.info("[ML-AUTH] ✅ Oferta pendente '%s' publicada com sucesso!", oferta.titulo[:40])
                    except Exception as e:
                        log.error("[ML-AUTH] Falha ao postar oferta pendente: %s", e)
                db.remover_oferta_pendente_ml(uid)

        return total_publicadas


# Instância global singleton do serviço
ml_auth_service = MercadoLivreAuthService()
