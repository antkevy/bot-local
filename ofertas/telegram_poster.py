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
    try:
        return await bot.send_photo(chat_id, oferta.imagem, caption=caption,
                                    parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        log.warning("send_photo falhou (%s) — pulando oferta (sem fallback para texto)", e)
        raise
