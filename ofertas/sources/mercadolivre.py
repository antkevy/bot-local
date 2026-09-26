"""Mercado Livre: scraping da página de ofertas + link de afiliado via Linkbuilder.

O ML não tem API pública para afiliados, mas o Linkbuilder do painel usa uma API
interna simples (createLink), autenticada só pelos cookies da sessão. O bot chama
essa API de dentro de uma página logada (perfil persistente do Chrome em
data/ml_profile). Faça login uma única vez com:

    uv run python -m ofertas ml-login
"""
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import USER_AGENT, parse_preco_br, sessao

log = logging.getLogger("ofertas.ml")

URL_OFERTAS = "https://www.mercadolivre.com.br/ofertas"
URL_LINKBUILDER = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
API_CREATELINK = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"
PERFIL_DIR = DATA_DIR / "ml_profile"

_RE_ID = re.compile(r"(MLB-?\d{6,})")


def e_link(url: str) -> bool:
    return any(d in url for d in ("mercadolivre.com", "mercadolibre.com", "meli.la/"))


def tem_sessao_linkbuilder() -> bool:
    """Verifica se há sessão autenticada real no perfil persistente do Link Builder."""
    cookie_file = PERFIL_DIR / "Default" / "Network" / "Cookies"
    if not cookie_file.exists():
        cookie_file = PERFIL_DIR / "Default" / "Cookies"
    if not cookie_file.exists():
        return False
    try:
        import sqlite3
        import tempfile
        import shutil
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
            tmp_path = tmp.name
        shutil.copyfile(cookie_file, tmp_path)
        conn = sqlite3.connect(tmp_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM cookies WHERE name IN ('org_user_id', 'ssid', 'c_user', 'user_id', '_mldataToken', 'cp')")
        rows = cur.fetchall()
        conn.close()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return len(rows) > 0
    except Exception:
        return cookie_file.stat().st_size > 50000


def tem_sessao() -> bool:
    """Verifica se há sessão ativa para o Mercado Livre (Link Builder ou Cookie)."""
    try:
        from .ml_auth import ml_auth_service
        if ml_auth_service.tem_cookie():
            return True
    except Exception:
        pass
    return tem_sessao_linkbuilder()


# ── Busca de ofertas (scraping, sem login) ───────────────────────────

def _categorias() -> dict[str, str]:
    """{id: nome} das categorias do config (aceita dict ou lista de ids); vazio = todas."""
    cats = config.fonte_ml.get("categorias") or {}
    return dict(cats) if isinstance(cats, dict) else {str(c): str(c) for c in cats}


def buscar_ofertas() -> list[Oferta]:
    """Página de ofertas do ML, filtrada pelas categorias do config (ofertas?category=MLB...)."""
    paginas = max(1, int(config.fonte_ml.get("paginas", 1)))
    categorias = _categorias() or {"": "todas"}
    s = sessao()
    ofertas: dict[str, Oferta] = {}
    for cat_id, nome in categorias.items():
        for pagina in range(1, paginas + 1):
            params = {}
            if cat_id:
                params["category"] = cat_id
            if pagina > 1:
                params["page"] = pagina
            r = s.get(URL_OFERTAS, params=params or None, timeout=30)
            r.raise_for_status()
            achadas = _parse_pagina(r.text)
            for o in achadas:
                ofertas.setdefault(o.id_produto, o)
            log.info("Mercado Livre %s: %d ofertas", nome, len(achadas))
            time.sleep(1)
    log.info("Mercado Livre: %d ofertas coletadas", len(ofertas))
    return list(ofertas.values())


def _preco_de(card, seletor_base: str) -> float | None:
    fracao = card.select_one(f"{seletor_base} .andes-money-amount__fraction")
    if not fracao:
        return None
    centavos = card.select_one(f"{seletor_base} .andes-money-amount__cents")
    texto = fracao.get_text(strip=True) + ("," + centavos.get_text(strip=True) if centavos else "")
    return parse_preco_br(texto)


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

    partes = []
    review = card.select_one(".poly-component__review-compacted")
    if review:
        partes.append("⭐ " + re.sub(r"\s*\|\s*", " · ", review.get_text(" ", strip=True)))
    if "Frete grátis" in card.get_text():
        partes.append("🚚 Frete grátis")
    pix = card.select_one(".poly-price__unit-description")
    if pix and "pix" in pix.get_text().lower():
        partes.append("💠 preço no Pix")

    return Oferta(
        plataforma="mercadolivre",
        id_produto=id_produto,
        titulo=titulo,
        url_afiliado="",  # preenchido depois pelo Linkbuilder
        url_produto=url,
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto,
        imagem=imagem,
        extra=" · ".join(partes) or None,
    )


def _parse_pagina(html: str) -> list[Oferta]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.poly-card")
    ofertas = [o for o in (_parse_card(c) for c in cards) if o]
    if cards and not ofertas:
        log.warning("Página de ofertas do ML mudou de layout? %d cards, 0 parseados", len(cards))
    return ofertas


def _limpar_locks_perfil():
    """Remove lockfiles residuais para evitar erro de ProcessSingleton no Windows."""
    try:
        (PERFIL_DIR / "lockfile").unlink(missing_ok=True)
        for lf in PERFIL_DIR.rglob("*LOCK*"):
            try:
                lf.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def _abrir_contexto(pw, headless: bool):
    """Abre contexto Chromium isolado para o Mercado Livre com proteção anti-automação."""
    _limpar_locks_perfil()
    kwargs = dict(
        headless=headless,
        locale="pt-BR",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
        ],
        ignore_default_args=["--enable-automation"],
    )
    if headless:
        kwargs["user_agent"] = USER_AGENT
    else:
        kwargs["no_viewport"] = True

    try:
        # Usa o Chromium isolado do projeto para nunca conflitar com instâncias abertas do usuário
        return pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)
    except Exception as e:
        log.warning("Falha ao abrir Chromium isolado (%s); tentando navegador do sistema...", e)
        try:
            chrome = _achar_chrome()
            kwargs["executable_path"] = chrome
            return pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)
        except Exception as e2:
            log.error("Erro fatal ao abrir navegador: %s", e2)
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


def ml_login() -> None:
    """Abre um navegador visível para o usuário fazer login no Mercado Livre."""
    from playwright.sync_api import sync_playwright
    PERFIL_DIR.mkdir(parents=True, exist_ok=True)
    print("\n➡️ Abrindo janela do navegador para login no Mercado Livre...")
    print("    1. Faça login na sua conta do Mercado Livre na janela que abriu.")
    print("    2. Acesse o Link Builder de afiliados.")
    print("    3. Quando concluir, você pode fechar a janela do navegador.\n")

    with sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL_LINKBUILDER)
        except Exception as e:
            log.warning("Aviso ao abrir Link Builder: %s", e)

        # Mantém aberto enquanto a janela estiver ativa
        try:
            while len(ctx.pages) > 0 and not page.is_closed():
                page.wait_for_timeout(1000)
        except Exception:
            pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass

    if tem_sessao_linkbuilder():
        print(f"✅ Login concluído! Perfil salvo em {PERFIL_DIR}.")
    else:
        print(f"ℹ️ Janela do navegador encerrada. Se não fez login via janela, você pode colar seu Cookie no painel.")


def _criar_links_api(page, urls: list[str], etiqueta: str) -> list[str]:
    """Chama a API interna do Linkbuilder de dentro da página logada; retorna os short links.

    Payload/resposta observados em 2026-08-21:
    POST createLink {"urls": [...], "tag": "<etiqueta>"} ->
    {"status": 200, "urls": [{"id", "created", "short_url": "https://meli.la/...", ...}]}
    """
    r = page.evaluate(
        """async ({api, urls, tag}) => {
            const resp = await fetch(api, {
                method: 'POST',
                headers: {'content-type': 'application/json'},
                body: JSON.stringify({urls, tag}),
            });
            const corpo = await resp.text();
            try { return {http: resp.status, dados: JSON.parse(corpo)}; }
            catch (e) { return {http: resp.status, texto: corpo.slice(0, 300)}; }
        }""",
        {"api": API_CREATELINK, "urls": urls, "tag": etiqueta},
    )
    if r.get("http") != 200 or not r.get("dados"):
        raise RuntimeError(f"createLink respondeu HTTP {r.get('http')}: {r.get('texto', '')}")
    itens = (r["dados"].get("urls")) or []
    links = [i.get("short_url") or "" for i in itens]
    if len(links) != len(urls) or not all(links):
        raise RuntimeError(f"createLink devolveu {sum(1 for l in links if l)} links "
                           f"para {len(urls)} URLs: {r['dados']}")
    return links


def _gerar_links_linkbuilder_batch(pendentes: list[Oferta], etiqueta: str) -> None:
    """Executa a geração de links via Playwright e perfil persistente do Linkbuilder."""
    from playwright.sync_api import sync_playwright

    if not tem_sessao():
        raise RuntimeError("Sessão do ML não encontrada — faça login via Linkbuilder")
    if not etiqueta:
        raise RuntimeError("ML_ETIQUETA não configurada")

    with sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL_LINKBUILDER, wait_until="domcontentloaded")
            if "login" in page.url or "registration" in page.url:
                raise RuntimeError("Sessão do ML expirou no Linkbuilder")
            page.wait_for_timeout(1500)
            for i in range(0, len(pendentes), 10):
                lote = pendentes[i:i + 10]
                links = _criar_links_api(page, [o.url_produto for o in lote], etiqueta)
                for o, link in zip(lote, links):
                    o.url_afiliado = link
            log.info("Mercado Livre: %d link(s) gerado(s) via Linkbuilder", len(pendentes))
        finally:
            ctx.close()


def gerar_links_afiliado(ofertas: list[Oferta], bot: Any = None) -> None:
    """Preenche oferta.url_afiliado via serviço em cascata: Link Builder -> Cookie -> Fallback seguro."""
    from .ml_auth import ml_auth_service
    ml_auth_service.gerar_links_afiliado(ofertas, bot=bot)


def converter(url: str) -> Oferta:
    """Link de produto -> Oferta com dados da página + link de afiliado."""
    url = url.split("#")[0]
    if "meli.la/" in url:  # link de afiliado encurtado: expande até o produto
        try:
            url = sessao().get(url, allow_redirects=True, timeout=20).url.split("#")[0]
        except Exception as e:
            log.warning("Não consegui expandir o link meli.la: %s", e)
    titulo = preco = preco_original = imagem = None
    try:
        r = sessao().get(url, timeout=25)
        soup = BeautifulSoup(r.text, "lxml")
        el = soup.select_one("h1.ui-pdp-title")
        titulo = el.get_text(strip=True) if el else None
        el = soup.select_one('meta[property="og:image"]')
        imagem = el.get("content") if el else None
        el = soup.select_one('meta[itemprop="price"]')
        if el and el.get("content"):
            preco = float(el["content"])
        else:
            el = soup.select_one(".ui-pdp-price__second-line .andes-money-amount__fraction")
            preco = parse_preco_br(el.get_text()) if el else None
        el = soup.select_one("s.andes-money-amount--previous .andes-money-amount__fraction")
        preco_original = parse_preco_br(el.get_text()) if el else None
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
        raise RuntimeError("Linkbuilder não devolveu o link de afiliado")
    return oferta
