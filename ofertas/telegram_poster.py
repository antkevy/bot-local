import asyncio
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode

from .formatter import montar_caption
from .models import Oferta

log = logging.getLogger("ofertas.poster")


def teclado_oferta(o: Oferta) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Pegar oferta", url=o.url_afiliado)]])


async def postar_oferta(bot: Bot, oferta: Oferta, chat_id: str | int,
                        teclado: InlineKeyboardMarkup | None = None) -> Message:
    caption = montar_caption(oferta)
    markup = teclado or teclado_oferta(oferta)
    if not oferta.imagem:
        raise RuntimeError("oferta sem imagem — regra: não publicar sem foto")

    ultimo_erro: Exception | None = None
    for tentativa in range(3):
        try:
            return await bot.send_photo(chat_id, oferta.imagem, caption=caption,
                                        parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception as e:
            ultimo_erro = e
            nome = e.__class__.__name__
            transient = (
                isinstance(e, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError))
                or nome in {"TimedOut", "NetworkError", "RetryAfter"}
            )
            if transient and tentativa < 2:
                espera = getattr(e, "retry_after", None)
                try:
                    espera_s = float(espera) if espera is not None else float(2 * (tentativa + 1))
                except Exception:
                    espera_s = float(2 * (tentativa + 1))
                espera_s = min(max(espera_s, 1.0), 15.0)
                log.warning("send_photo falhou (tentativa %d/3, %s: %s) — nova tentativa em %.1fs",
                            tentativa + 1, nome, e, espera_s)
                await asyncio.sleep(espera_s)
                continue
            log.warning("send_photo falhou (%s) — pulando oferta (sem fallback para texto)", e)
            raise
    if ultimo_erro:
        raise ultimo_erro
    raise RuntimeError("falha desconhecida ao postar oferta")
