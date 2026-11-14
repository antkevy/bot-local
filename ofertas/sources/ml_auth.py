"""Autenticação do Mercado Livre — exclusivamente por cookie.

O ``ML_COOKIE`` (ou o cookie validado salvo por ``/setcookie`` em
``data/ml_cookies.json``) autentica as duas coisas:

1. a API interna ``createLink`` (Linkbuilder), que gera os links ``meli.la``;
2. o Chromium temporário que coleta as páginas de ofertas (o HTTP puro é
   barrado pelo ML).

Não existe mais login pelo navegador nem perfil persistente. Sem cookie válido
a oferta vai para ``ofertas_pendentes_ml`` e o admin é avisado (com cooldown).

NUNCA publica ofertas do Mercado Livre sem link de afiliado válido.
NUNCA utiliza a URL original como affiliate_link.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
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


def normalizar_cookie(bruto: str) -> str:
    """Normaliza um cookie para o formato de header HTTP ``nome=valor; ...``.

    Aceita também o JSON exportado por extensões de navegador (Cookie-Editor,
    EditThisCookie): uma lista de objetos ``{"name": ..., "value": ...}``.
    Sem esta conversão, colar o JSON inteiro virava um header inválido e o
    Mercado Livre respondia HTTP 403 em toda chamada. É exatamente o formato que
    o usuário cola ao copiar os cookies da extensão.
    """
    if not bruto:
        return ""
    texto = bruto.strip()
    if texto[:1] not in ("[", "{"):
        return texto
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        return texto
    if isinstance(dados, dict):
        dados = [dados]
    if not isinstance(dados, list):
        return texto
    pares = [
        f"{c['name']}={c['value']}"
        for c in dados
        if isinstance(c, dict) and c.get("name") and c.get("value") is not None
    ]
    return "; ".join(pares) if pares else texto


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
                    return normalizar_cookie(c)
        except Exception as e:
            log.warning("[ML-AUTH] Erro ao ler cookie do arquivo local: %s", e)

    return normalizar_cookie(config.ml_cookie or "")


def salvar_cookie_local(cookie_str: str) -> None:
    """Salva o cookie validado de forma segura no diretório data/."""
    cookie_str = normalizar_cookie(cookie_str)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dados = {"cookie": cookie_str.strip(), "atualizado_em": time.time()}
    try:
        fd = os.open(COOKIE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2)
        try:
            os.chmod(COOKIE_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2)
        try:
            os.chmod(COOKIE_FILE, 0o600)
        except OSError:
            pass
    config.ml_cookie = cookie_str.strip()


def tem_cookie() -> bool:
    """Verifica se há um cookie configurado."""
    return bool(obter_cookie_configurado())


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
    """Gera links de afiliado do Mercado Livre usando apenas o cookie configurado."""

    def __init__(self):
        pass

    def gerar_links_afiliado(self, ofertas: list[Oferta], bot: Any = None) -> None:
        """Gera links de afiliado via cookie. Sem link válido, não publica."""
        pendentes = [o for o in ofertas if not o.url_afiliado and o.url_produto]
        if not pendentes:
            return

        # Antes de tentar autenticação, separa o que nunca poderia funcionar:
        # perfil público, lista, /sec/, feed, tracking. O createLink recusa
        # essas URLs com "URL Invalid" e, sem esta checagem, a falha virava
        # "autenticação expirada" e a URL entrava na fila de pendências.
        from . import mercadolivre as _ml
        invalidas = [o for o in pendentes if not _ml.e_url_de_produto(o.url_produto)]
        if invalidas:
            for o in invalidas:
                o.url_afiliado = ""
                log.warning("[ML-AUTH] Ignorando URL que não é de produto: %s",
                            (o.url_produto or "")[:80])
            ids = {id(o) for o in invalidas}
            pendentes = [o for o in pendentes if id(o) not in ids]
            if not pendentes:
                return

        etiqueta = config.ml_etiqueta or "fastpromo"
        cookie = obter_cookie_configurado()
        if not cookie:
            log.error("[ML-AUTH] ML_COOKIE não configurado — não é possível gerar links de afiliado.")
            for o in pendentes:
                o.url_afiliado = ""  # GARANTIA: Nunca usar URL original
                db.salvar_oferta_pendente_ml(o, status="aguardando_autenticacao")
            self.notificar_admin_se_necessario(bot)
            return

        try:
            urls = [o.url_produto for o in pendentes]
            links = _gerar_via_cookie_raw(urls, etiqueta, cookie)
            for o, link in zip(pendentes, links):
                o.url_afiliado = link
            log.info("[ML-AUTH] ✅ %d link(s) gerado(s) com sucesso via cookie.", len(pendentes))
            return
        except PermissionError as pe:
            log.warning("[ML-AUTH] Cookie do Mercado Livre expirado/inválido: %s", pe)
        except Exception as e:
            log.warning("[ML-AUTH] Erro ao gerar link via cookie: %s", e)

        log.error("[ML-AUTH] ❌ Falha ao autenticar no Mercado Livre pelo cookie. Bloqueando publicação.")
        for o in pendentes:
            o.url_afiliado = ""  # GARANTIA: Nunca usar URL original
            db.salvar_oferta_pendente_ml(o, status="aguardando_autenticacao")
        self.notificar_admin_se_necessario(bot)

    def testar_autenticacao(self, url_teste: str = URL_TESTE_DEFAULT) -> dict[str, Any]:
        """Testa se o cookie atual consegue gerar link de afiliado."""
        etiqueta = config.ml_etiqueta or "fastpromo"
        cookie = obter_cookie_configurado()
        if not cookie:
            return {
                "authenticated": False,
                "method": None,
                "affiliate_generation": False,
                "error": "authentication_expired",
                "detalhe": "ML_COOKIE não configurado",
            }
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
            return {
                "authenticated": False,
                "method": "cookie",
                "affiliate_generation": False,
                "error": "cookie_error",
                "detalhe": "O cookie não gerou um link válido.",
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

    def validar_e_salvar_novo_cookie(self, novo_cookie: str, bot: Any = None) -> dict[str, Any]:
        """Versão síncrona (CLI/testes). Dentro de um loop use a versão async."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.validar_e_salvar_novo_cookie_async(novo_cookie, bot=bot))
        # Bloquear o loop com asyncio.run() aqui levantava RuntimeError e, pior,
        # deixava o bot travado enquanto o teste real do cookie rodava. Quem
        # está num handler async tem de usar a variante `_async`.
        raise RuntimeError(
            "validar_e_salvar_novo_cookie() chamado de dentro de um event loop; "
            "use validar_e_salvar_novo_cookie_async().")

    async def validar_e_salvar_novo_cookie_async(
            self, novo_cookie: str, bot: Any = None) -> dict[str, Any]:
        """Testa o novo cookie antes de salvar. Se for válido, atualiza e processa pendências.

        A validação usa rede + Playwright (até ~12s) e por isso roda numa
        thread: feita direto no handler, congelava o bot inteiro — nenhum outro
        comando era atendido enquanto o teste acontecia.
        """
        cookie_limpo = normalizar_cookie(novo_cookie).strip()
        if not cookie_limpo:
            return {"ok": False, "erro": "Cookie fornecido está vazio."}

        etiqueta = config.ml_etiqueta or "fastpromo"
        try:
            links = await asyncio.to_thread(
                _gerar_via_cookie_raw, [URL_TESTE_DEFAULT], etiqueta, cookie_limpo,
                timeout=12)
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
                total_reprocessadas = await self.processar_ofertas_pendentes_async(bot)
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
            "Não foi possível gerar o link de afiliado de um ou mais produtos porque o "
            "cookie atual do Mercado Livre expirou ou está inválido.\n\n"
            "Para renovar, envie aqui no privado:\n"
            "🍪 <code>/setcookie &lt;cookie&gt;</code>\n\n"
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
        """Versão síncrona (CLI/testes). Dentro de um loop use a versão async."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.processar_ofertas_pendentes_async(bot))
        raise RuntimeError(
            "processar_ofertas_pendentes() chamado de dentro de um event loop; "
            "use processar_ofertas_pendentes_async().")

    async def processar_ofertas_pendentes_async(self, bot: Any) -> int:
        """Reprocessa ofertas do Mercado Livre que estavam aguardando autenticação.

        As etapas caras (reler preço, gerar link no Playwright, filtros) rodam
        em thread para não congelar o bot; a publicação é aguardada de verdade.
        """
        pendentes_db = db.listar_ofertas_pendentes_ml(status="aguardando_autenticacao")
        if not pendentes_db:
            return 0

        log.info("[ML-AUTH] 🔄 Reprocessando %d oferta(s) pendente(s) do Mercado Livre...", len(pendentes_db))
        total_publicadas = 0

        from ..pipeline import filtrar, postar_oferta
        from . import mercadolivre as _ml

        for row in pendentes_db:
            uid = row["uid"]
            # Pendência antiga pode ser de URL que não é de produto (perfil,
            # lista, tracking) — essas nunca vão gerar link. Remover é o que
            # impede a fila de crescer para sempre com lixo.
            if not _ml.e_url_de_produto(row["url_produto"]):
                log.info("[ML-AUTH] Removendo pendência que não é de produto: %s",
                         (row["url_produto"] or "")[:80])
                await asyncio.to_thread(db.remover_oferta_pendente_ml, uid)
                continue
            # Deduplicação: se já foi postada nesse intervalo, a pendência
            # cumpriu o papel dela e pode sair.
            if await asyncio.to_thread(db.ja_postada, uid, config.nao_repetir_dias):
                await asyncio.to_thread(db.remover_oferta_pendente_ml, uid)
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

            # O preço foi lido quando a oferta foi coletada, e pode ter sido
            # horas ou dias atrás — foi justamente o tempo de esperar o login
            # do ML. Relemos a página agora, senão a postagem vai ao ar com um
            # preço que já não existe.
            await asyncio.to_thread(self._atualizar_preco, oferta)

            # Tenta gerar o link de afiliado
            await asyncio.to_thread(self.gerar_links_afiliado, [oferta], bot)

            if not oferta.url_afiliado:
                # Sem link não há postagem (regra do projeto) e a oferta
                # continua na fila para a próxima tentativa.
                await asyncio.to_thread(
                    db.marcar_tentativa_pendente_ml, uid, "sem link de afiliado")
                continue

            if not (config.chat_id and bot):
                await asyncio.to_thread(
                    db.marcar_tentativa_pendente_ml, uid,
                    "sem canal de destino ou sem bot")
                continue

            # Passa pelos filtros existentes (reserva a oferta para este
            # processo; se outro estiver publicando, `aprovadas` vem vazio).
            aprovadas = await asyncio.to_thread(filtrar, [oferta])
            if not aprovadas:
                await asyncio.to_thread(
                    db.marcar_tentativa_pendente_ml, uid, "rejeitada pelos filtros")
                continue

            try:
                # `postar_oferta` é async no projeto, mas os testes injetam
                # tanto AsyncMock quanto MagicMock. Aguardar só o que for
                # awaitable mantém os dois contratos sem `asyncio.run`.
                resultado = postar_oferta(bot, oferta, config.chat_id)
                if inspect.isawaitable(resultado):
                    await resultado
                await asyncio.to_thread(db.registrar, oferta)
                await asyncio.to_thread(db.remover_oferta_pendente_ml, uid)
                total_publicadas += 1
                log.info("[ML-AUTH] ✅ Oferta pendente publicada: %s", oferta.titulo[:50])
            except Exception as e:
                # A reserva foi pega por filtrar() e nada foi publicado: devolve
                # ao limbo e mantém a pendência para nova tentativa.
                await asyncio.to_thread(db.liberar_reserva, uid)
                await asyncio.to_thread(
                    db.marcar_tentativa_pendente_ml, uid, f"falha ao postar: {e}")
                log.error("[ML-AUTH] Falha ao postar oferta pendente '%s': %s", oferta.uid, e)

        return total_publicadas

    @staticmethod
    def _atualizar_preco(oferta: Oferta) -> None:
        """Relê o preço na página e corrige a oferta se ele tiver mudado.

        Se a releitura não trouxer preço nenhum, o ML pode ter bloqueado a
        leitura em vez de o produto ter sumido. Nesse caso mantemos o preço
        guardado: descartar a oferta por uma leitura que falhou seria perder
        uma venda que ainda existe.
        """
        if not oferta.url_produto:
            return
        from . import mercadolivre
        preco_antigo = oferta.preco
        atual, anterior = mercadolivre.reler_preco(oferta.url_produto)
        if atual is None:
            log.warning("[ML-AUTH] Não consegui reler o preço de '%s'; mantendo o preço guardado.",
                        oferta.titulo[:50])
            return
        mudou = (preco_antigo is not None and abs(atual - preco_antigo) > 0.01)
        if mudou:
            log.info("[ML-AUTH] Preço mudou desde a coleta: %s -> %s (oferta '%s').",
                     preco_antigo, atual, oferta.titulo[:40])
        oferta.preco = atual
        if anterior is not None:
            oferta.preco_original = anterior
            oferta.desconto_pct = None      # recalcula a partir dos preços atuais
        elif mudou:
            # O preço mudou e a página não informa mais o "de". Manter o
            # preço original/desconto antigos anunciaria um desconto que não
            # existe mais.
            oferta.preco_original = None
            oferta.desconto_pct = None


# Instância global singleton do serviço
ml_auth_service = MercadoLivreAuthService()
