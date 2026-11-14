"""Mercado Livre: scraping da página de ofertas + link de afiliado.

O ML não tem API pública para afiliados, mas a API interna do Linkbuilder
(`createLink`) gera links autenticada pelos cookies da sessão. A autenticação
do bot é **exclusivamente por cookie**: o valor de ``ML_COOKIE`` (ou o cookie
salvo em ``data/ml_cookies.json`` pelo /setcookie) é injetado em um Chromium
temporário, que coleta as ofertas e autentica a geração de links. Não existe
mais login pelo navegador nem perfil persistente.
"""
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup

from .. import parada
from ..config import config
from ..marketplaces import url_pertence
from ..models import Oferta
from ..utils import USER_AGENT, parse_preco_br, sessao

log = logging.getLogger("ofertas.ml")

URL_OFERTAS = "https://www.mercadolivre.com.br/ofertas"
API_CREATELINK = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"

_RE_ID = re.compile(r"(MLB-?\d{6,})")

# Um Chromium por vez: cada coleta sobe um navegador e o ML não gosta de duas
# sessões simultâneas com o mesmo cookie. Serializar também evita que a coleta
# e o teste de conexão abram dois navegadores ao mesmo tempo na VPS.
_NAVEGADOR_LOCK = threading.Lock()


_HOSTS_ML = frozenset({
    "mercadolivre.com",
    "mercadolivre.com.br",
    "mercadolibre.com",
    "meli.la",
})


def e_link(url: str) -> bool:
    return url_pertence(url, _HOSTS_ML)


def e_id_produto(id_produto: str | None) -> bool:
    """Diz se o id e de um anuncio, e nao de uma pagina do Mercado Livre.

    Mesmo motivo da Shopee: o `converter` cai no ultimo segmento do caminho
    quando a URL nao tem MLB, e essa pagina (loja, cupom) chega ao pipeline
    com a mesma cara de produto.
    """
    return bool(id_produto) and bool(re.fullmatch(r"MLB\d{6,}", str(id_produto)))


def tem_sessao() -> bool:
    """Diz se há cookie do Mercado Livre configurado (única autenticação)."""
    try:
        from . import ml_auth
        return ml_auth.tem_cookie()
    except Exception:
        return False


# ── Busca de ofertas (scraping, sem login) ───────────────────────────

def _categorias() -> dict[str, str]:
    """{id: nome} das categorias do config (aceita dict ou lista de ids); vazio = todas."""
    cats = config.fonte_ml.get("categorias") or {}
    return dict(cats) if isinstance(cats, dict) else {str(c): str(c) for c in cats}


# Caminhos que o Mercado Livre usa para páginas que NÃO são anúncio: perfil
# público, listas, encurtador, feed, verificação de conta. O createLink recusa
# todas com "URL Invalid" (error_code 100), mas a cascata de autenticação
# interpretava isso como sessão expirada e guardava a URL na fila de pendências
# do ML, onde ela nunca teria como funcionar.
_CAMINHOS_NAO_PRODUTO = (
    "/social/", "/sec/", "/scfeed", "/gz/", "/afiliados",
    "/jms/", "/cupons", "/perfil/", "/lists",
)
_HOSTS_NAO_PRODUTO = ("click1.", "click.")


def e_url_de_produto(url: str | None) -> bool:
    """Diz se a URL é de um anúncio (e não de perfil, lista ou link de tracking).

    Links de produto aparecem de duas formas: `www.mercadolivre.com.br/<slug>`
    ou `produto.mercadolivre.com.br/MLB-...` — a primeira não traz o id MLB no
    caminho, então não dá para exigir MLB. O critério aqui é o inverso: só
    recusa o que comprovadamente não é produto. `meli.la` conta como válido
    porque `converter` o expande antes de gerar o link.
    """
    if not url:
        return False
    if not e_link(url):
        return False
    partes = urlparse(url)
    host = (partes.netloc or "").lower()
    if any(host.startswith(p) for p in _HOSTS_NAO_PRODUTO):
        return False
    caminho = (partes.path or "/").lower()
    if caminho.rstrip("/") in ("/ofertas", "/scfeed"):
        return False
    if any(caminho.startswith(p) for p in _CAMINHOS_NAO_PRODUTO):
        return False
    return True


def _alvos_de_coleta() -> list[tuple[str, str]]:
    """[(url, nome da categoria)] para todas as páginas do config."""
    paginas = max(1, int(config.fonte_ml.get("paginas", 1)))
    categorias = _categorias() or {"": "todas"}
    alvos: list[tuple[str, str]] = []
    for cat_id, nome in categorias.items():
        for pagina in range(1, paginas + 1):
            params = {}
            if cat_id:
                params["category"] = cat_id
            if pagina > 1:
                params["page"] = pagina
            url = URL_OFERTAS + ("?" + urlencode(params) if params else "")
            alvos.append((url, nome))
    return alvos


# Quantas páginas de /ofertas por ciclo. Varria TODAS (12 categorias x 2 páginas
# a cada 25 min) e o ML respondeu com `/captcha/wall/logged`: 24 páginas em ~8
# minutos por ciclo é ritmo de robô. Com janela rotativa o catálogo continua
# sendo coberto em poucos ciclos, com ~1/4 das requisições.
PAGINAS_POR_CICLO_PADRAO = 6
_CURSOR_ROTACAO = 0

# Página alternativa quando /ofertas exige captcha. Validada em 13/11/2026:
# 196 cards, 196 ofertas parseadas, 0 sem preço. Não respeita as categorias do
# config, então é plano B — melhor postar fora do nicho do que ficar sem ML.
URL_MAIS_VENDIDOS = "https://www.mercadolivre.com.br/mais-vendidos"
_BLOQUEIO_SEGUNDOS = 3600
_BLOQUEIO_ATE = 0.0


def _paginas_por_ciclo() -> int:
    try:
        valor = int(config.fonte_ml.get("paginas_por_ciclo",
                                        PAGINAS_POR_CICLO_PADRAO))
    except (TypeError, ValueError):
        return PAGINAS_POR_CICLO_PADRAO
    return valor if valor > 0 else PAGINAS_POR_CICLO_PADRAO


def _alvos_do_ciclo() -> list[tuple[str, str]]:
    """Janela rotativa de páginas: cobre todas as categorias sem varrer tudo."""
    global _CURSOR_ROTACAO
    alvos = _alvos_de_coleta()
    limite = _paginas_por_ciclo()
    if limite >= len(alvos):
        _CURSOR_ROTACAO = 0
        return alvos
    inicio = _CURSOR_ROTACAO % len(alvos)
    janela = [alvos[(inicio + i) % len(alvos)] for i in range(limite)]
    _CURSOR_ROTACAO = (inicio + limite) % len(alvos)
    return janela


def _alvos_alternativos() -> list[tuple[str, str]]:
    return [(URL_MAIS_VENDIDOS, "mais vendidos")]


def _bloqueado() -> bool:
    return time.time() < _BLOQUEIO_ATE


def _registrar_bloqueio(motivo: str) -> None:
    global _BLOQUEIO_ATE
    _BLOQUEIO_ATE = time.time() + _BLOQUEIO_SEGUNDOS
    log.warning("Mercado Livre: /ofertas em verificação/captcha (%s). "
                "Usando a página alternativa por até %d min.",
                motivo[:110], _BLOQUEIO_SEGUNDOS // 60)


# Trechos da URL para onde o ML redireciona quando exige conta/verificação.
# Acontece com requisição HTTP anônima: a página de ofertas some e chega um
# "Olá! Para continuar, acesse sua conta" com zero cards.
_PADROES_VERIFICACAO = ("account-verification", "captcha", "web-risk-verification")


class _VerificacaoML(RuntimeError):
    """/ofertas caiu em verificação de conta/captcha, com o que já foi coletado."""

    def __init__(self, mensagem: str, ofertas: list[Oferta]):
        super().__init__(mensagem)
        self.ofertas = ofertas


def _coletar_no_navegador(pw, alvos: list[tuple[str, str]]) -> list[Oferta]:
    """Coleta as páginas de ofertas dentro de um Chromium autenticado por cookie.

    O scraping por HTTP puro é barrado pelo ML: sem sessão ele redireciona para
    `/gz/account-verification`, e com cookie o fingerprint do `requests` cai no
    captcha. No navegador com os cookies de `ML_COOKIE` a página abre normal
    (validado em 13/11/2026: 197 cards, 197 ofertas parseadas).
    """
    ofertas: dict[str, Oferta] = {}
    with _NAVEGADOR_LOCK:
        ctx = _abrir_contexto(pw, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            for url, nome in alvos:
                if parada.pedido():
                    log.info("Mercado Livre: parada pedida — interrompendo em %s", nome)
                    break
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                if any(p in page.url for p in _PADROES_VERIFICACAO):
                    # Devolve o que já foi coletado: perder 40 ofertas boas
                    # porque a 6ª página pediu captcha não faz sentido.
                    raise _VerificacaoML(
                        f"ML pediu verificação de conta ({page.url[:90]})",
                        list(ofertas.values()))
                try:
                    page.wait_for_selector("div.poly-card", timeout=8_000)
                except Exception:
                    pass        # página sem cards é válida; _parse_pagina decide
                achadas = _parse_pagina(page.content())
                for o in achadas:
                    ofertas.setdefault(o.id_produto, o)
                log.info("Mercado Livre %s: %d ofertas", nome, len(achadas))
        finally:
            ctx.close()
    return list(ofertas.values())


def _buscar_via_navegador(alvos: list[tuple[str, str]]) -> list[Oferta]:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        return _coletar_no_navegador(pw, alvos)


def _buscar_via_http(alvos: list[tuple[str, str]]) -> list[Oferta]:
    s = sessao()
    ofertas: dict[str, Oferta] = {}
    for url, nome in alvos:
        if parada.pedido():
            log.info("Mercado Livre: parada pedida — interrompendo em %s", nome)
            break
        r = s.get(url, timeout=30)
        r.raise_for_status()
        achadas = _parse_pagina(r.text)
        for o in achadas:
            ofertas.setdefault(o.id_produto, o)
        log.info("Mercado Livre %s: %d ofertas", nome, len(achadas))
        time.sleep(1)
    return list(ofertas.values())


def _coletar_alternativa() -> list[Oferta]:
    """Plano B sem categorias, para quando /ofertas está com captcha."""
    try:
        coletadas = _buscar_via_navegador(_alvos_alternativos())
    except Exception as e:
        log.warning("Mercado Livre: página alternativa também falhou (%s: %s)",
                    type(e).__name__, e)
        return []
    if coletadas:
        log.info("Mercado Livre: %d ofertas coletadas (mais vendidos)",
                 len(coletadas))
    return coletadas


def buscar_ofertas() -> list[Oferta]:
    """Ofertas do ML: /ofertas por categoria via navegador, com plano B.

    Ordem: janela rotativa de `/ofertas?category=` no Chromium autenticado por
    cookie → (se houver captcha, falha ou vazio) `/mais-vendidos`. Sem cookie
    configurado cai para HTTP direto, que o ML quase sempre barra mas ainda
    serve de rede de segurança.
    """
    if parada.pedido():
        log.info("Mercado Livre: parada pedida antes da coleta")
        return []
    alvos = _alvos_do_ciclo()

    if tem_sessao():
        if _bloqueado():
            # Não insiste no captcha a cada ciclo: ficaria esquentando o
            # bloqueio e gastando 30s por tentativa.
            return _coletar_alternativa()

        try:
            coletadas = _buscar_via_navegador(alvos)
            if coletadas:
                log.info("Mercado Livre: %d ofertas coletadas (navegador)", len(coletadas))
                return coletadas
            log.warning("Mercado Livre: navegador não devolveu ofertas; tentando página alternativa")
            return _coletar_alternativa()
        except _VerificacaoML as e:
            _registrar_bloqueio(str(e))
            if e.ofertas:
                log.warning("Mercado Livre: bloqueio no meio da coleta; "
                            "aproveitando %d ofertas já coletadas", len(e.ofertas))
                return e.ofertas
            return _coletar_alternativa()
        except Exception as e:
            log.warning("Mercado Livre: coleta pelo navegador falhou (%s: %s); tentando página alternativa",
                        type(e).__name__, e)
            return _coletar_alternativa()

    ofertas = _buscar_via_http(alvos)
    log.info("Mercado Livre: %d ofertas coletadas", len(ofertas))
    return ofertas


def _preco_de(card, seletor_base: str) -> float | None:
    fracao = card.select_one(f"{seletor_base} .andes-money-amount__fraction")
    if not fracao:
        return None
    centavos = card.select_one(f"{seletor_base} .andes-money-amount__cents")
    texto = fracao.get_text(strip=True) + ("," + centavos.get_text(strip=True) if centavos else "")
    return parse_preco_br(texto)


_RE_ARIA_PRECO = re.compile(
    r"(\d[\d.]*)\s*reais?\s+com\s+(\d{1,2})\s*centavos?", re.IGNORECASE
)


def _preco_do_bloco(el) -> float | None:
    """Preço de um bloco `.andes-money-amount`, lendo as partes que o ML marca.

    Três caminhos, do mais confiável ao menos:

    1. `aria-label="263 reais com 41 centavos"` — é o nome acessível do bloco
       de preço vigente, escrito por extenso, sem depender de layout nenhum;
    2. `__fraction` + `__cents` do próprio elemento;
    3. o texto do bloco, como último recurso.

    O terceiro caminho é o que não pode vir primeiro. O bloco do ML traz a
    vírgula dos centavos escondida num `<span class="andes-visually-hidden">`,
    então o texto lido é "R$ 419 , 90": o `parse_preco_br` descarta a vírgula e
    devolve 41990 — um preço de R$ 419,90 publicado como R$ 41.990,00. Foi
    exatamente o que aconteceu com os quatro produtos capturados em
    tests/fixtures/ml_precos_reais.json, todos lidos 100x acima do valor.

    Nos dois layouts do ML (card e página de produto) a divisão entre reais e
    centavos é o oposta do que os nomes sugerem: `__fraction` guarda a parte
    em reais e `__cents` os centavos.
    """
    if el is None:
        return None

    m = _RE_ARIA_PRECO.search(el.get("aria-label") or "")
    if m:
        try:
            return float(m.group(1).replace(".", "")) + int(m.group(2)) / 100
        except ValueError:
            pass

    fracao = el.select_one(".andes-money-amount__fraction")
    if fracao:
        centavos = el.select_one(".andes-money-amount__cents")
        texto = fracao.get_text(strip=True)
        if centavos:
            texto += "," + centavos.get_text(strip=True)
        return parse_preco_br(texto)

    return parse_preco_br(el.get_text(" ", strip=True))


def _avaliacao_e_vendas(card) -> tuple[float | None, int | None]:
    """(nota, vendidos) lidos do bloco de avaliação do card.

    O bloco do ML traz as duas coisas no mesmo elemento, separadas por "|".
    Medido em nove cards de uma listagem de verdade: '4.7 | +50mil vendidos',
    '4.9 | +1000 vendidos', '4.8 | +10mil vendidos'. Quando o produto tem nota
    e nenhuma venda, vem só a nota; quando não tem nota, o bloco não aparece.

    Duas coisas que o texto real obrigou a respeitar:

    - A nota vem com PONTO decimal (4.9). A Amazon usa vírgula (4,9). Ler as
      duas com a mesma receita faria uma delas dar None sempre.
    - As vendas vêm como "+10mil", com "mil" escrito. Isso é a unidade, não
      ruído — 10mil são 10.000. O "+" é o que a loja está dizendo, "mais de",
      e o formatador não tem como escrever isso; o número entra arredondado
      do jeito que a própria loja arredondou.
    """
    rev = card.select_one(".poly-component__review-compacted")
    if not rev:
        return None, None
    texto = rev.get_text(" ", strip=True)

    nota = None
    m = re.match(r"\s*([0-9]+(?:[.,][0-9]+)?)\b", texto)
    if m:
        bruto = m.group(1)
        try:
            v = float(bruto.replace(".", "").replace(",", ".")) if "," in bruto else float(bruto)
        except ValueError:
            v = 0.0
        nota = round(v, 1) if 0 < v <= 5 else None

    vendas = None
    m = re.search(r"([0-9][0-9.]*)\s*(mil)?\s*vendidos?", texto, re.I)
    if m:
        try:
            qtd = int(m.group(1).replace(".", ""))
        except ValueError:
            qtd = 0
        if m.group(2):
            qtd *= 1000
        vendas = qtd if qtd > 0 else None

    return nota, vendas


def _parse_card(card) -> Oferta | None:
    a = card.select_one("a.poly-component__title")
    if not (a and a.get("href")):
        return None
    titulo = a.get_text(strip=True)
    url = a["href"].split("#")[0].split("?")[0]

    m = _RE_ID.search(a["href"])
    id_produto = m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40]

    preco = _preco_de(card, ".poly-price__current")
    preco_original = _preco_de(card, "s.andes-money-amount--previous")

    desconto = None
    selo = card.select_one(".poly-price__discount-polylabel, .andes-money-amount__discount")
    if selo:
        m = re.search(r"(\d+)\s*%", selo.get_text())
        desconto = int(m.group(1)) if m else None

    img = card.select_one("img.poly-component__picture")
    imagem = (img.get("data-src") or img.get("src")) if img else None
    if imagem and imagem.startswith("data:"):
        imagem = None  # placeholder de lazy-load

    # Nota e vendidos vão nos campos próprios. Deixá-los também em `extra`
    # faria a legenda repetir "⭐ 4.7 · 🛒 50.000 vendidos" duas vezes: uma
    # pelos selos do formatador, outra pelo texto. Os selos de "Frete grátis"
    # e "preço no Pix" do card foram tirados a pedido — a postagem de oferta
    # não anuncia benefício de envio/pagamento, só o produto.
    avaliacao, vendas = _avaliacao_e_vendas(card)

    return Oferta(
        plataforma="mercadolivre",
        id_produto=id_produto,
        titulo=titulo,
        url_afiliado="",  # preenchido depois pela geração de link de afiliado
        url_produto=url,
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto,
        imagem=imagem,
        avaliacao=avaliacao,
        vendas=vendas,
        extra=None,
    )


def _parse_pagina(html: str) -> list[Oferta]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.poly-card")
    ofertas = [o for o in (_parse_card(c) for c in cards) if o]
    if cards and not ofertas:
        log.warning("Página de ofertas do ML mudou de layout? %d cards, 0 parseados", len(cards))
    return ofertas


def _cookies_para_playwright(cookie_str: str) -> list[dict[str, Any]]:
    """Converte o header ``nome=valor; ...`` nos cookies que o Playwright aceita."""
    from .ml_auth import normalizar_cookie
    cookies: list[dict[str, Any]] = []
    for parte in normalizar_cookie(cookie_str).split(";"):
        parte = parte.strip()
        if "=" not in parte:
            continue
        nome, valor = parte.split("=", 1)
        if nome.strip():
            cookies.append({
                "name": nome.strip(),
                "value": valor.strip(),
                "domain": ".mercadolivre.com.br",
                "path": "/",
            })
    return cookies


class _ContextoTemporario:
    """Contexto do Chromium + diretório temporário que ele usa como perfil.

    O chamador continua usando ``ctx.pages``, ``ctx.new_page()`` e
    ``ctx.close()``: fechar o contexto apaga o perfil descartável, sem deixar
    lixo em ``data/``.
    """

    def __init__(self, ctx, caminho: str):
        self._ctx = ctx
        self._caminho = caminho

    def __getattr__(self, nome):
        return getattr(self._ctx, nome)

    def close(self) -> None:
        try:
            self._ctx.close()
        finally:
            shutil.rmtree(self._caminho, ignore_errors=True)


def _abrir_contexto(pw, headless: bool) -> _ContextoTemporario:
    """Abre um Chromium limpo e injeta os cookies do Mercado Livre.

    Sem perfil persistente: cada chamada usa um diretório temporário próprio,
    então não existe ProcessSingleton para travar entre coletas concorrentes e
    a sessão não fica gravada em disco.
    """
    from . import ml_auth
    cookie = ml_auth.obter_cookie_configurado()
    if not cookie:
        raise RuntimeError("ML_COOKIE não configurado — cole o cookie do Mercado Livre no painel")

    kwargs = dict(
        headless=headless,
        locale="pt-BR",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            # Não passamos --disable-features aqui de propósito: o Playwright
            # já envia a dele e, no Chrome, o último --disable-features vence.
            # Sobrescrever a lista do Playwright removeria as proteções
            # anti-detecção e o ML passaria a tratar o bot como robô.
            "--disable-sync",
        ],
        ignore_default_args=["--enable-automation"],
        user_agent=USER_AGENT,
        # Sem isto, uma abertura travada faz o `launch` pendurar para sempre
        # (não levanta exceção); com o teto, ele falha e libera o lock.
        timeout=20_000,
    )
    if not headless:
        kwargs["no_viewport"] = True
        kwargs["args"] = kwargs["args"] + ["--start-maximized"]

    caminho = tempfile.mkdtemp(prefix="ml_navegador_")
    try:
        try:
            # Chromium isolado do projeto: nunca conflita com o navegador do usuário.
            ctx = pw.chromium.launch_persistent_context(caminho, **kwargs)
        except Exception as e:
            log.warning("Falha ao abrir Chromium isolado (%s); tentando navegador do sistema...", e)
            kwargs["executable_path"] = _achar_chrome()
            ctx = pw.chromium.launch_persistent_context(caminho, **kwargs)
        ctx.add_cookies(_cookies_para_playwright(cookie))
        return _ContextoTemporario(ctx, caminho)
    except Exception:
        shutil.rmtree(caminho, ignore_errors=True)
        raise


def _achar_chrome() -> str:
    """Caminho de um navegador baseado em Chromium (Chrome, Brave, Edge) instalado."""
    import shutil
    candidatos: list[str] = []

    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for exe in ("chrome.exe", "brave.exe", "msedge.exe"):
                    try:
                        chave = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}"
                        with winreg.OpenKey(hive, chave) as k:
                            candidatos.append(winreg.QueryValueEx(k, None)[0])
                    except OSError:
                        continue
        except ImportError:
            pass
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidatos += [
                    str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                    str(Path(base) / "BraveSoftware/Brave-Browser/Application/brave.exe"),
                    str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
                ]
    elif sys.platform == "darwin":
        candidatos += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux e afins
        for nome in ("google-chrome", "google-chrome-stable", "brave-browser", "brave",
                     "chromium", "chromium-browser", "microsoft-edge"):
            achado = shutil.which(nome)
            if achado:
                candidatos.append(achado)
        candidatos += [
            "/usr/bin/google-chrome",
            "/usr/bin/brave-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise RuntimeError("Nenhum navegador baseado em Chromium (Chrome, Brave ou Edge) encontrado.")


def gerar_links_afiliado(ofertas: list[Oferta], bot: Any = None) -> None:
    """Preenche oferta.url_afiliado via cookie do ML; sem link, não publica."""
    from .ml_auth import ml_auth_service
    ml_auth_service.gerar_links_afiliado(ofertas, bot=bot)


def _precos_da_pagina(soup) -> tuple[float | None, float | None]:
    """(preço atual, preço anterior) lidos da página de produto já aberta."""
    # O preço original era lido só pela "fração", então aparecia R$ 419 em vez
    # de R$ 419,90 — e o desconto derivado saía errado.
    anterior = _preco_do_bloco(soup.select_one("s.andes-money-amount--previous"))

    el = soup.select_one('meta[itemprop="price"]')
    if el and el.get("content"):
        try:
            return float(el["content"]), anterior
        except ValueError:
            pass                       # conteúdo ilegível: cai no bloco

    segunda_linha = soup.select_one(".ui-pdp-price__second-line")
    if segunda_linha is None:
        return None, anterior

    # Dentro da linha do preço há o bloco vigente e o `s` do preço original. O
    # vigente é o único com `aria-label` ("263 reais com 41 centavos"); sem ele,
    # vale o primeiro `.andes-money-amount` da linha.
    atual = (_preco_do_bloco(segunda_linha.select_one(".andes-money-amount[aria-label]"))
             or _preco_do_bloco(segunda_linha.select_one(".andes-money-amount")))
    return atual, anterior


def reler_preco(url: str) -> tuple[float | None, float | None]:
    """Relê o preço de um produto já conhecido. Devolve (atual, anterior).

    Oferta que ficou pendente (o ML estava sem autenticação) pode ter sido
    coletada horas ou dias antes. Publicá-la depois com o preço de então posta
    na mensagem um valor que não existe mais. Relendo a página na hora de
    publicar, o preço vai junto com a oferta; se o produto tiver saído do ar,
    volta None e a oferta é descartada em vez de ir ao ar com preço antigo.
    """
    try:
        r = sessao().get(url, timeout=20)
        r.raise_for_status()
        return _precos_da_pagina(BeautifulSoup(r.text, "lxml"))
    except Exception as e:
        log.warning("Não consegui reler o preço de '%s': %s", url[:60], e)
        return None, None


def converter(url: str) -> Oferta:
    """Link de produto -> Oferta com dados da página + link de afiliado."""
    url = url.split("#")[0]
    if "meli.la/" in url:  # link de afiliado encurtado: expande até o produto
        try:
            url = sessao().get(url, allow_redirects=True, timeout=20).url.split("#")[0]
        except Exception as e:
            log.warning("Não consegui expandir o link meli.la: %s", e)
    # Perfil público, lista, feed ou link de tracking não são anúncio: o
    # createLink responde "URL Invalid" e a oferta ia parar na fila de
    # pendências do ML como se o problema fosse autenticação. Melhor recusar
    # aqui, com a causa certa.
    if not e_url_de_produto(url):
        raise RuntimeError(f"Link do Mercado Livre não é de produto: {url[:80]}")
    titulo = preco = preco_original = imagem = None
    try:
        r = sessao().get(url, timeout=25)
        soup = BeautifulSoup(r.text, "lxml")
        el = soup.select_one("h1.ui-pdp-title")
        titulo = el.get_text(strip=True) if el else None
        el = soup.select_one('meta[property="og:image"]')
        imagem = el.get("content") if el else None
        preco, preco_original = _precos_da_pagina(soup)
    except Exception as e:
        log.warning("Não consegui ler a página do produto: %s", e)

    m = _RE_ID.search(url)
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto=m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40],
        titulo=titulo or "Oferta Mercado Livre",
        url_afiliado="",
        url_produto=url.split("?")[0],
        preco=preco,
        preco_original=preco_original,
        imagem=imagem,
    )
    gerar_links_afiliado([oferta])
    if not oferta.url_afiliado:
        raise RuntimeError("O Mercado Livre não devolveu o link de afiliado")
    return oferta
