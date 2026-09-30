"""Painel de controle gráfico (interface web local) para o bot de ofertas.

Roda um servidor só em 127.0.0.1 e abre no navegador. Dali dá para:
- preencher a configuração (.env) em formulário, sem mexer no Bloco de Notas;
- instalar o navegador, fazer login no Mercado Livre e testar as fontes por botões;
- descobrir os IDs do Telegram automaticamente;
- ligar/desligar o bot e acompanhar o log ao vivo — tudo sem terminal.

Sobe com:  uv run python -m ofertas painel   (ou dê 2 cliques em PAINEL.bat)
"""
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests

from . import db
from .config import BASE_DIR, DATA_DIR
from .db import contar_por_plataforma, listar_postadas, posts_por_dias, total_postadas
from .painel_html import PAGINA

HOST, PORT = "127.0.0.1", 8481  # 8478=split-app, 8479=ClipOS/cortes — evita colisão
ENV_PATH = BASE_DIR / ".env"

# (chave, rótulo, grupo, é_segredo, ajuda)
CAMPOS = [
    ("TELEGRAM_BOT_TOKEN", "Token do bot", "Telegram", True,
     "Crie no @BotFather com /newbot e cole o token aqui."),
    ("TELEGRAM_OWNER_ID", "Seu user ID", "Telegram", False,
     "Use o botão 'Detectar IDs' depois de colocar o token."),
    ("TELEGRAM_CHAT_ID", "ID do canal", "Telegram", False,
     "O canal onde o bot posta. Use 'Detectar IDs'."),
    ("ML_ETIQUETA", "Etiqueta do afiliado", "Mercado Livre", False,
     "A 'Etiqueta em uso' que aparece no Linkbuilder do painel de afiliados."),
    ("ML_COOKIE", "Cookie de sessão (Fallback / Alternativo)", "Mercado Livre", True,
     "Opcional. Cookie ssid/login do ML para autenticação em cascata caso o Link Builder falhe."),
    ("AMAZON_TAG", "Tag de associado", "Amazon", False,
     "Sua tag do Amazon Associados (ex: seunome-20)."),
    ("AMAZON_CREDENTIAL_ID", "Creators API — ID", "Amazon", False,
     "Opcional. Associates Central > Creators API > Aplicativos."),
    ("AMAZON_CREDENTIAL_SECRET", "Creators API — Secret", "Amazon", True,
     "Opcional. Aparece só uma vez, na criação da credencial."),
    ("SHOPEE_APP_ID", "App ID", "Shopee", False,
     "Painel de afiliados Shopee > menu 'Abrir API'."),
    ("SHOPEE_APP_SECRET", "App Secret", "Shopee", True,
     "Painel de afiliados Shopee > menu 'Abrir API'."),
    ("ALIEXPRESS_APP_KEY", "App Key", "AliExpress", False,
     "App Key da aplicação no AliExpress Open Platform / Portals."),
    ("ALIEXPRESS_APP_SECRET", "App Secret", "AliExpress", True,
     "App Secret gerado no AliExpress Open Platform."),
    ("ALIEXPRESS_TRACKING_ID", "Tracking ID", "AliExpress", False,
     "Seu Tracking ID de afiliado do AliExpress (ex: seunome_br)."),
    ("XAI_API_KEY", "Chave de API (xAI Grok)", "Inteligência Artificial (Grok)", True,
     "Opcional. Chave xai-... para otimização de títulos e detecção de cupons com Grok."),
]
CHAVES = [c[0] for c in CAMPOS]

# Login do painel NÃO é um campo de configuração comum: tem validação e
# confirmação própria, e é gerenciado pelo card "Acesso ao painel".
CHAVES_ACESSO = ["PAINEL_USUARIO", "PAINEL_SENHA"]
MIN_USUARIO, MIN_SENHA = 3, 8


# ── .env ──────────────────────────────────────────────────────────────

def ler_env() -> dict[str, str]:
    # CHAVES_ACESSO entra na lista de conhecidas: o filtro abaixo só aceita
    # chave já semeada, e sem isso a conta criada pelo painel nunca seria
    # lida de volta — o arquivo tinha, a memória não.
    valores = {k: "" for k in CHAVES + CHAVES_ACESSO}
    if ENV_PATH.exists():
        # utf-8-sig: um .env salvo pelo Bloco de Notas ou pelo PowerShell
        # costuma vir com BOM, e sem isso a PRIMEIRA variável da lista
        # seria lida como "﻿CHAVE" e ignorada em silêncio.
        for linha in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, _, v = linha.partition("=")
                if k.strip() in valores:
                    valores[k.strip()] = v.strip()
    return valores


def _linhas_env_extras(atual: dict[str, str]) -> list[str]:
    """Chaves que o painel não conhece (comentadas) — preservadas ao salvar."""
    extras: list[str] = []
    if ENV_PATH.exists():
        for linha in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            limpa = linha.strip()
            if not limpa or limpa.startswith("#") or "=" not in limpa:
                continue
            k, _, v = limpa.partition("=")
            if k.strip() not in CHAVES and k.strip() not in atual:
                atual[k.strip()] = v.strip()
                extras.append(linha)
    return extras


def salvar_env(novos: dict[str, str], acessos: dict[str, str] | None = None) -> None:
    atuais = ler_env()
    for k, v in novos.items():
        if k in atuais:
            atuais[k] = str(v).strip()
    for k, v in (acessos or {}).items():
        if k in CHAVES_ACESSO:
            atuais[k] = str(v).strip()
    extras = _linhas_env_extras(atuais)
    linhas = ["# Configuração do bot de ofertas (gerado pelo painel).",
              "# Não compartilhe este arquivo — ele guarda seus segredos.", ""]
    grupo_atual = None
    for chave, rotulo, grupo, *_ in CAMPOS:
        if grupo != grupo_atual:
            linhas.append(f"# ── {grupo} ──")
            grupo_atual = grupo
        linhas.append(f"{chave}={atuais.get(chave, '')}")
    # A conta do painel é sempre reescrita, mesmo ao salvar outra seção:
    # se ficasse de fora, um "Salvar credenciais" apagaria a senha.
    linhas += ["", "# ── Acesso ao painel ──"]
    for chave in CHAVES_ACESSO:
        linhas.append(f"{chave}={atuais.get(chave, '')}")
    if extras:
        linhas += ["", "# ── Mantidas do arquivo original ──", *extras]
    ENV_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")


# ── Autenticação ───────────────────────────────────────────────────────
# O painel mexe em segredos (.env), liga/desliga o bot e roda ações que
# abrem navegador. Enquanto ele fica em 127.0.0.1 isso não é exposto a
# ninguém — mas o dia que o HOST virar 0.0.0.0 (para acesso pela rede) o
# painel fica aberto. Por isso há login, e a ausência de credenciais
# NÃO significa "aberto": significa "só loopback", nunca "liberado".

COOKIE_SESSAO = "painel_sessao"
DURACAO_SESSAO = 8 * 3600          # 8 horas
MAX_TENTATIVAS = 5                 # por janela
JANELA_TENTATIVAS = 300            # 5 minutos
BLOQUEIO_TENTATIVAS = 900          # 15 minutos após estourar

_sessoes: dict[str, tuple[str, float]] = {}   # token -> (usuário, expira)
_tentativas: dict[str, list[float]] = {}      # ip -> [timestamps]
_lock = threading.Lock()


def _credenciais() -> tuple[str, str]:
    """(usuário, segredo) configurados. Vazio = painel sem login."""
    env = ler_env()
    return (env.get("PAINEL_USUARIO", "").strip(),
            env.get("PAINEL_SENHA", "").strip())


def _autenticado() -> bool:
    return bool(_credenciais()[1])


def _digest(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


def _ip_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return ip in ("localhost", "")


def _bloqueado(ip: str) -> float | None:
    """Segundos restantes de bloqueio, ou None se não estiver bloqueado."""
    agora = time.time()
    with _lock:
        tentativas = [t for t in _tentativas.get(ip, []) if agora - t < JANELA_TENTATIVAS]
        _tentativas[ip] = tentativas
        if len(tentativas) >= MAX_TENTATIVAS:
            return BLOQUEIO_TENTATIVAS - (agora - tentativas[0])
    return None


def _registrar_falha(ip: str) -> None:
    with _lock:
        _tentativas.setdefault(ip, []).append(time.time())


def _limpar_tentativas(ip: str) -> None:
    with _lock:
        _tentativas.pop(ip, None)


def _criar_sessao(usuario: str) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessoes[token] = (usuario, time.time() + DURACAO_SESSAO)
    return token


def _checar_sessao(token: str) -> str:
    """Usuário da sessão, ou string vazia se ausente/expirada."""
    if not token:
        # Guarda explícita: "" é o token de quem não mandou cookie. Se
        # alguma vez houver sessão gravada sob essa chave, ela valeria para
        # qualquer requisição anônima da internet. Melhor recusar sempre.
        return ""
    with _lock:
        dados = _sessoes.get(token)
        if not dados:
            return ""
        usuario, expira = dados
        if expira < time.time():
            _sessoes.pop(token, None)
            return ""
        return usuario


def _encerrar_sessao(token: str) -> None:
    with _lock:
        _sessoes.pop(token, None)


def _token_do_pedido(handler) -> str:
    bruto = handler.headers.get("Cookie", "")
    if not bruto:
        return ""
    try:
        c = SimpleCookie()
        c.load(bruto)
    except Exception:
        return ""
    m = c.get(COOKIE_SESSAO)
    return m.value if m else ""


# ── Processo do bot ───────────────────────────────────────────────────

class Processo:
    """Encapsula um subprocesso (o bot, ou uma ação) e guarda o log recente."""

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.linhas: deque[str] = deque(maxlen=500)
        self.rotulo = ""

    def rodando(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def iniciar(self, args: list[str], rotulo: str) -> bool:
        if self.rodando():
            return False
        self.rotulo = rotulo
        flags = 0
        if "ml-login" not in args and "telegram-user-login" not in args:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "ofertas", *args],
            cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=flags, env=env,
        )
        self.proc = proc
        # A thread guarda o processo localmente: se outra ação já tiver substituído
        # self.proc, esta leitura continua apontando para o processo dela.
        threading.Thread(target=self._ler, args=(proc,), daemon=True).start()
        return True

    def _ler(self, proc: subprocess.Popen):
        rotulo = self.rotulo
        try:
            for linha in proc.stdout:
                self.linhas.append(linha.rstrip())
        except (ValueError, OSError):
            pass          # pipe fechado durante encerramento
        cod = proc.wait()
        fim = "concluído com sucesso" if cod == 0 else f"terminou (código {cod})"
        self.linhas.append(f"[{rotulo}] {fim}")

    def parar(self):
        proc = self.proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
            self.linhas.append("Bot parado.")


bot = Processo()      # o bot (run), fica ligado
acao = Processo()     # ações pontuais (instalar, login, testar)


# ── Ações auxiliares ──────────────────────────────────────────────────

def _so_presentes(dados: dict, mapa: dict) -> dict:
    """Filtra `dados` para as chaves de `mapa` que vieram no corpo.

    Sem isso, um POST parcial gravava o default no lugar de tudo que o
    cliente não mandou: um `{}` em /api/filtros voltava avaliacao_minima
    para 0 e vendas_minimas para 0, apagando o ajuste do usuário. Chave
    ausente = "não mexe"; chave presente e vazia = grava o que veio.
    """
    saida = {}
    for chave, conversor in mapa.items():
        if chave in dados:
            saida[chave] = conversor(dados[chave])
    return saida


def _int(v):
    return int(v or 0)


def _float(v):
    return float(v or 0)


def _bool(v):
    return bool(v)


def _lista_de_palavras(v):
    return [str(p).strip().lower() for p in (v or []) if str(p).strip()]


def detectar_ids() -> dict:
    """Consulta o Telegram (getUpdates) e sugere owner id e chat id do canal."""
    token = ler_env().get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {"erro": "Preencha e salve o token do bot primeiro."}
    aviso = ""
    if bot.rodando():
        aviso = ("O bot está rodando e consome as atualizações antes do painel. "
                 "Mande /id no privado do bot e encaminhe um post do canal para ele — "
                 "a resposta dele já traz os dois IDs.")
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"limit": 100, "timeout": 0,
                    "allowed_updates": '["message","channel_post"]'},
            timeout=20)
        dados = r.json()
    except Exception as e:
        return {"erro": f"Não consegui falar com o Telegram: {e}"}
    if not dados.get("ok"):
        return {"erro": f"Telegram recusou o token: {dados.get('description', '?')}"}

    pessoas, canais = {}, {}
    for upd in dados.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") == "private" and chat.get("id"):
            nome = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            pessoas[chat["id"]] = nome or chat.get("username") or str(chat["id"])
        elif chat.get("type") in ("channel", "supergroup", "group") and chat.get("id"):
            canais[chat["id"]] = chat.get("title") or str(chat["id"])
        fwd = (msg.get("forward_from_chat") or {})
        if fwd.get("type") == "channel" and fwd.get("id"):
            canais[fwd["id"]] = fwd.get("title") or str(fwd["id"])
    return {
        "pessoas": [{"id": i, "nome": n} for i, n in pessoas.items()],
        "canais": [{"id": i, "nome": n} for i, n in canais.items()],
        "vazio": not pessoas and not canais,
        "aviso": aviso,
    }


import datetime as dt
import shutil
from .db import total_postadas, listar_postadas, contar_por_plataforma


def _sessao_ml_existe() -> bool:
    from .sources import mercadolivre
    return mercadolivre.tem_sessao()


def status() -> dict:
    env = ler_env()
    tem_navegador = bool(list((DATA_DIR / "pw-browsers").glob("chromium-*")))
    from .sources import mercadolivre
    from .sources.ml_auth import ml_auth_service
    tem_sessao_ml = mercadolivre.tem_sessao()
    tem_ml_etiqueta = bool(env.get("ML_ETIQUETA"))
    ml_conectado = tem_sessao_ml and tem_ml_etiqueta

    if tem_sessao_ml:
        if mercadolivre.tem_sessao_linkbuilder():
            status_ml = "Link Builder pronto" if tem_ml_etiqueta else "Etiqueta não configurada"
        else:
            status_ml = "Cookie manual ativo" if tem_ml_etiqueta else "Etiqueta não configurada"
    else:
        status_ml = "Sessão pendente (Faça login ou insira o Cookie)"

    amz_conectado = bool(env.get("AMAZON_TAG"))
    shp_conectado = bool(env.get("SHOPEE_APP_ID") and env.get("SHOPEE_APP_SECRET"))
    ali_conectado = bool(env.get("ALIEXPRESS_APP_KEY") and env.get("ALIEXPRESS_APP_SECRET"))
    total = total_postadas()

    from .config import config
    fontes = [nome for nome, f in (("Mercado Livre", config.fonte_ml),
                                   ("Shopee", config.fonte_shopee),
                                   ("Amazon", config.fonte_amazon),
                                   ("AliExpress", config.fonte_aliexpress),
                                   ("Nerd Ofertas", config.fonte_nerdofertas)) if f.get("ativa")]

    # A trava de instância diz se existe algum bot publicando, inclusive um
    # que este painel não iniciou (terminal, outro painel, execução anterior
    # que ficou viva). Sem isso o painel só enxergava o próprio filho.
    from . import instancia
    trava_bot = instancia.status("bot")
    bot_externo = bool(trava_bot.get("ocupado")) and not bot.rodando()

    return {
        "bot_rodando": bot.rodando(),
        "bot_externo": bot_externo,
        "bot_externo_pid": trava_bot.get("pid") if bot_externo else None,
        "acao_rodando": acao.rotulo if acao.rodando() else "",
        "preenchidos": {k: bool(env.get(k)) for k in CHAVES},
        "navegador": tem_navegador,
        "sessao_ml": tem_sessao_ml,
        "pronto": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")
                       and env.get("TELEGRAM_OWNER_ID")),
        "total_postadas": total,
        "fontes_ativas": fontes,
        "intervalo_minutos": config.intervalo_minutos,
        "max_posts_por_ciclo": config.max_posts_por_ciclo,
        "horario_ativo": config.horario_ativo or "24h",
        "nichos": config.nichos,
        "plataformas": {
            "mercadolivre": {
                "conectado": ml_conectado,
                "status": status_ml,
                "etiqueta": env.get("ML_ETIQUETA", ""),
                "sessao_ativa": tem_sessao_ml,
            },
            "amazon": {
                "conectado": amz_conectado,
                "status": "Tag configurada" if amz_conectado else "Não configurado",
                "tag": env.get("AMAZON_TAG", ""),
                "api_ativa": bool(env.get("AMAZON_CREDENTIAL_ID") and env.get("AMAZON_CREDENTIAL_SECRET")),
            },
            "shopee": {
                "conectado": shp_conectado,
                "status": "API configurada" if shp_conectado else "Não configurado",
                "app_id": env.get("SHOPEE_APP_ID", ""),
            },
            "aliexpress": {
                "conectado": ali_conectado,
                "disponivel": True,
                "status": "Open API pronta" if ali_conectado else "Não configurado",
                "app_key": env.get("ALIEXPRESS_APP_KEY", ""),
                "tracking_id": env.get("ALIEXPRESS_TRACKING_ID", ""),
            },
        },
        "grok": {
            "ativo": bool(env.get("XAI_API_KEY")),
            "modelo": config.grok_model,
            "configurado": bool(env.get("XAI_API_KEY")),
        },
    }



def gerar_link_afiliado(url: str, plataforma: str = "") -> dict:
    """Monta o link de afiliado.

    Devolve `erro` em vez de um link inventado: uma tag de exemplo no lugar da
    sua mandaria a comissão para outra pessoa, e dizer "ok" para um link que
    não é de afiliado engana o usuário.
    """
    env = ler_env()
    url = url.strip()
    if not url:
        return {"erro": "Cole o link do produto."}
    if not url.lower().startswith(("http://", "https://")):
        return {"erro": "O link precisa começar com http:// ou https://."}

    url_lower = url.lower()
    plat = plataforma.lower().strip()
    if plat in ("", "auto"):
        if "amazon.com" in url_lower or "amzn.to" in url_lower:
            plat = "amazon"
        elif "mercadolivre.com" in url_lower or "ml.com" in url_lower or "meli.la" in url_lower:
            plat = "mercadolivre"
        elif "shopee.com" in url_lower or "shp.ee" in url_lower:
            plat = "shopee"
        elif "aliexpress.com" in url_lower or "ali.ski" in url_lower:
            plat = "aliexpress"
        else:
            return {"erro": ("Não reconheci o marketplace deste link. "
                             "Escolha a plataforma manualmente em 'Plataforma'.")}

    sep = "&" if "?" in url else "?"
    if plat == "amazon":
        tag = env.get("AMAZON_TAG", "").strip()
        if not tag:
            return {"erro": "Configure a tag de associado do Amazon em Configurações "
                            "antes de gerar o link."}
        link_afiliado = url if "tag=" in url else f"{url}{sep}tag={tag}"
    elif plat == "mercadolivre":
        etiqueta = env.get("ML_ETIQUETA", "").strip()
        if not etiqueta:
            return {"erro": "Configure a etiqueta de afiliado do Mercado Livre em "
                            "Configurações antes de gerar o link."}
        link_afiliado = f"{url}{sep}matt_tool=35282054&matt_word={etiqueta}"
    elif plat == "shopee":
        app_id = env.get("SHOPEE_APP_ID", "").strip()
        if not app_id:
            return {"erro": "Configure o App ID da Shopee em Configurações "
                            "antes de gerar o link."}
        link_afiliado = f"{url}{sep}af_sub={app_id}"
    elif plat == "aliexpress":
        app_key = env.get("ALIEXPRESS_APP_KEY", "").strip()
        app_secret = env.get("ALIEXPRESS_APP_SECRET", "").strip()
        if not (app_key and app_secret):
            return {"erro": "Configure ALIEXPRESS_APP_KEY e ALIEXPRESS_APP_SECRET em "
                            "Configurações antes de gerar o link."}
        try:
            from .sources import aliexpress
            link_afiliado = aliexpress.gerar_link_afiliado(url)
        except Exception as e:
            return {"erro": f"Erro na API do AliExpress: {e}"}
    else:
        return {"erro": f"Plataforma desconhecida: {plat}."}

    return {
        "ok": True,
        "plataforma": plat,
        "url_original": url,
        "url_afiliado": link_afiliado,
        "criado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def _dt_br(valor: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


NOMES_PLATAFORMA = {
    "mercadolivre": "Mercado Livre",
    "amazon": "Amazon",
    "shopee": "Shopee",
    "aliexpress": "AliExpress",
}
CORES_PLATAFORMA = {
    # Espelham --e1..--e4 do CSS. São cor de ÍCONE sobre fundo tingido —
    # nunca fundo com texto branco, que reprovaria contraste. Os tons do
    # painel em produção (#2563eb / #ff9900 / #ee4d2d / #8b5cf6) foram
    # clareados porque o glifo fica sobre fundo escuro.
    "mercadolivre": "#60A5FA",
    "amazon": "#F0A93B",
    "shopee": "#F26A4D",
    "aliexpress": "#A78BFA",
}
ICONE_PLATAFORMA = {
    "mercadolivre": "handshake",
    "amazon": "package",
    "shopee": "shopping-bag",
    "aliexpress": "globe",
}


def obter_metricas() -> dict:
    """Só dados reais lidos do banco — nada de estimativa inventada."""
    postadas = listar_postadas(60)
    contagem = contar_por_plataforma()
    total = sum(contagem.values())

    # Série real dos últimos 7 dias (hoje por último)
    dias = [(dt.date.today() - dt.timedelta(days=i)) for i in range(6, -1, -1)]
    labels = [d.strftime("%d/%m") for d in dias]
    valores_dias = posts_por_dias(7)
    semana = sum(valores_dias)
    ontem = valores_dias[-2] if len(valores_dias) > 1 else 0
    hoje = valores_dias[-1] if valores_dias else 0

    # Comparação com o dia anterior — número real, não um "+X%" inventado
    if ontem > 0:
        variacao = f"{'+' if hoje >= ontem else ''}{round((hoje - ontem) / ontem * 100):.0f}%"
        variacao_ok = hoje >= ontem
    elif hoje > 0:
        variacao, variacao_ok = "novo", True
    else:
        variacao, variacao_ok = "estável", True

    ultima = next((p for p in postadas if _dt_br(p.get("postada_em"))), None)
    if ultima:
        quando = _dt_br(ultima["postada_em"])
        delta = dt.datetime.now() - quando
        minutos = int(delta.total_seconds() // 60)
        if minutos < 1:
            ultima_txt = "agora"
        elif minutos < 60:
            ultima_txt = f"ha {minutos} min"
        elif minutos < 60 * 24:
            ultima_txt = f"ha {minutos // 60} h"
        else:
            ultima_txt = f"ha {minutos // (60 * 24)} d"
    else:
        ultima_txt = "nenhuma ainda"

    ranking = sorted(contagem.items(), key=lambda kv: kv[1], reverse=True)
    top_plataformas = [
        {"nome": NOMES_PLATAFORMA.get(k, k.capitalize()),
         "chave": k, "cliques": v,
         "pct": round(v / total * 100, 1) if total else 0,
         "cor": CORES_PLATAFORMA.get(k, "#64748B"),
         "icone": ICONE_PLATAFORMA.get(k, "store")}
        for k, v in ranking
    ]

    atividades = [
        {"titulo": "Oferta publicada",
         "detalhe": (p.get("titulo") or "").strip() or "Produto sem título",
         "hora": (_dt_br(p["postada_em"]).strftime("%d/%m %H:%M")
                  if _dt_br(p.get("postada_em")) else ""),
         "plataforma": p.get("plataforma") or "mercadolivre"}
        for p in postadas[:6]
    ]

    # Links reais: só os que o bot gravou no banco. Sem link salvo, mostra o produto.
    links_rec = []
    for p in postadas:
        url = (p.get("url_afiliado") or "").strip()
        links_rec.append({
            "url": url,
            "data": (_dt_br(p["postada_em"]).strftime("%d/%m/%Y %H:%M")
                     if _dt_br(p.get("postada_em")) else ""),
            "titulo": (p.get("titulo") or "").strip(),
            "plataforma": p.get("plataforma") or "mercadolivre",
            "uid": p.get("uid") or "",
            "imagem": p.get("imagem") or "",
            "url_original": (p.get("url_produto") or "").strip(),
        })
        if len(links_rec) >= 12:
            break

    return {
        "total": total,
        "semana": semana,
        "hoje": hoje,
        "ultima": ultima_txt,
        "variacao": variacao,
        "variacao_ok": variacao_ok,
        "grafico_dias_labels": labels,
        "grafico_dias_valores": valores_dias,
        "top_plataformas": top_plataformas,
        "atividades": atividades,
        "links_recentes": links_rec,
    }



# ── Servidor HTTP ─────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    # Rotas liberadas mesmo sem sessão. "/" precisa estar aqui: é o HTML que
    # DESENHA a tela de login. Se fosse barrado, quem definisse uma senha
    # receberia 401 em tudo e não teria como entrar — painel inutilizável.
    # O HTML em si não tem segredo nenhum; os dados vêm de /api/, que é
    # barrado de verdade.
    ROTAS_PUBLICAS = {"/", "/api/auth-status", "/api/login"}

    def log_message(self, *_):
        pass  # silencia o log padrão

    def _ip(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def _permitido(self) -> bool:
        """Libera o pedido, ou já respondeu 401/403 e retorna False."""
        rota = urlparse(self.path).path
        if rota in self.ROTAS_PUBLICAS:
            return True
        if _checar_sessao(_token_do_pedido(self)):
            return True
        if not _autenticado():
            # Sem credenciais, o painel só funciona a partir da própria
            # máquina. Se algum dia o HOST virar 0.0.0.0, isso vira 403
            # em vez de exposure acidental.
            if _ip_loopback(self._ip()):
                return True
            self._json({
                "erro": "Painel sem credenciais. Defina PAINEL_USUARIO e "
                        "PAINEL_SENHA no .env antes de acessar pela rede."
            }, 403)
            return False
        self._json({"erro": "Não autenticado."}, 401)
        return False

    def _json(self, obj, code=200, cookie: str | None = None):
        corpo = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return {}

    def _cookie_criar(self, token: str) -> str:
        return (f"{COOKIE_SESSAO}={token}; Path=/; HttpOnly; SameSite=Strict; "
                f"Max-Age={DURACAO_SESSAO}")

    def _cookie_limpar(self) -> str:
        return f"{COOKIE_SESSAO}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"

    def _fazer_login(self, dados: dict):
        ip = self._ip()
        restante = _bloqueado(ip)
        if restante is not None:
            return self._json({
                "erro": f"Muitas tentativas. Tente de novo em {int(restante) // 60 + 1} min."
            }, 429)

        usuario_esperado, senha_esperada = _credenciais()
        if not senha_esperada:
            # Sem credenciais o painel já é liberado para loopback; um POST
            # de login aqui é só um no-op que devolve a sessão implícita.
            return self._json({
                "ok": True,
                "usuario": "",
                "aviso": "PAINEL_USUARIO/PAINEL_SENHA não definidos: o painel está "
                         "protegido apenas por rodar em 127.0.0.1."
            })

        usuario = str(dados.get("usuario", ""))
        senha = str(dados.get("senha", ""))
        ok_usuario = hmac.compare_digest(usuario, usuario_esperado)
        ok_senha = hmac.compare_digest(_digest(senha), _digest(senha_esperada))
        if not (ok_usuario and ok_senha):
            _registrar_falha(ip)
            return self._json({"erro": "Usuário ou senha inválidos."}, 401)

        _limpar_tentativas(ip)
        token = _criar_sessao(usuario_esperado)
        return self._json({"ok": True, "usuario": usuario_esperado},
                          cookie=self._cookie_criar(token))

    def _conta(self, dados: dict):
        """Cria a conta, ou troca a senha se ela já existir."""
        usuario = str(dados.get("usuario", "")).strip()
        senha = str(dados.get("senha", ""))
        atual = str(dados.get("senha_atual", ""))

        usuario_atual, senha_atual_real = _credenciais()
        if senha_atual_real:
            # Trocar senha exige a senha de agora. Só a sessão não basta:
            # uma sessão esquecida num navegador aberto resolveria a conta
            # inteira de quem estivesse na frente.
            #
            # 403 e não 401: aqui o usuário ESTÁ autenticado, só errou a
            # senha. O 401 é reservado para "sem sessão" — e é o que o
            # painel usa para mandar para a tela de login. Devolver 401
            # aqui jogaria a pessoa para fora no meio da troca de senha.
            if not hmac.compare_digest(_digest(atual), _digest(senha_atual_real)):
                _registrar_falha(self._ip())
                return self._json({"erro": "Senha atual incorreta."}, 403)
            if not usuario:
                usuario = usuario_atual          # manter o usuário é o normal
        else:
            _limpar_tentativas(self._ip())

        if len(usuario) < MIN_USUARIO:
            return self._json({
                "erro": f"O usuário precisa de pelo menos {MIN_USUARIO} caracteres."
            }, 400)
        if len(senha) < MIN_SENHA:
            return self._json({
                "erro": f"A senha precisa de pelo menos {MIN_SENHA} caracteres."
            }, 400)
        if senha == usuario:
            return self._json({"erro": "A senha não pode ser igual ao usuário."}, 400)
        confirmar = str(dados.get("confirmar", ""))
        if confirmar and confirmar != senha:
            return self._json({"erro": "A confirmação não bate com a senha."}, 400)

        salvar_env({}, acessos={"PAINEL_USUARIO": usuario, "PAINEL_SENHA": senha})

        # Trocar a senha derruba as outras sessões; a atual continua, senão
        # quem acabou de configurar a conta seria jogado para fora na hora.
        # Sem token (primeira criação, ainda sem login) entra com uma
        # sessão de verdade — nunca sob a chave "", que casaria com
        # qualquer requisição anônima.
        meu = _token_do_pedido(self)
        with _lock:
            for t in [t for t, (_, exp) in _sessoes.items() if t != meu and exp >= time.time()]:
                _sessoes.pop(t, None)
            if meu:
                _sessoes[meu] = (usuario, time.time() + DURACAO_SESSAO)
        # Fora do with: _criar_sessao() toma o mesmo lock, e Lock não é
        # reentrante — chamado de dentro, trava a request inteira.
        cookie = self._cookie_criar(_criar_sessao(usuario)) if not meu else None

        return self._json({
            "ok": True, "usuario": usuario,
            "criada": not senha_atual_real,
        }, cookie=cookie)

    def _conta_remover(self, dados: dict):
        """Volta ao modo loopback. Também exige a senha atual."""
        _usuario, senha_atual = _credenciais()
        if not senha_atual:
            return self._json({"erro": "Não há conta para remover."}, 400)
        if not hmac.compare_digest(_digest(str(dados.get("senha", ""))), _digest(senha_atual)):
            _registrar_falha(self._ip())
            return self._json({"erro": "Senha atual incorreta."}, 403)

        salvar_env({}, acessos={"PAINEL_USUARIO": "", "PAINEL_SENHA": ""})
        with _lock:
            _sessoes.clear()
        return self._json({"ok": True}, cookie=self._cookie_limpar())

    def do_GET(self):
        try:
            rota = urlparse(self.path).path
            if rota == "/api/auth-status":
                usuario = _checar_sessao(_token_do_pedido(self))
                return self._json({
                    "autenticado": bool(usuario) or (not _autenticado() and _ip_loopback(self._ip())),
                    "configurado": _autenticado(),
                    "user": usuario,
                })
            if rota.startswith("/assets/"):
                nome_arquivo = rota.split("/")[-1]
                caminho = BASE_DIR / "ofertas" / "assets" / nome_arquivo
                ext = caminho.suffix.lower()
                mimetypes_map = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".svg": "image/svg+xml",
                    ".webp": "image/webp",
                    ".ico": "image/x-icon"
                }
                if caminho.is_file() and ext in mimetypes_map:
                    conteudo = caminho.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mimetypes_map[ext])
                    self.send_header("Content-Length", str(len(conteudo)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    self.wfile.write(conteudo)
                    return
                else:
                    self._json({"erro": "asset não encontrado"}, 404)
                    return
            if not self._permitido():
                return
            if rota == "/":
                corpo = PAGINA.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                # Sem isto o navegador reusa o HTML anterior depois de um
                # deploy, e a tela nova nao aparece: foi o que fez a aba
                # Plataformas parecer nao ter mudado. O JSON ja mandava
                # no-store (linha 708); a pagina ficava de fora.
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(corpo)
            elif rota == "/api/status":
                self._json(status())
            elif rota == "/api/metricas":
                self._json(obter_metricas())
            elif rota == "/api/produtos":
                self._json({"produtos": listar_postadas(100)})
            elif rota == "/api/conta":
                # Nunca devolve a senha — só se existe e quem é.
                usuario, senha = _credenciais()
                self._json({
                    "existe": bool(senha),
                    "usuario": usuario if senha else "",
                    "min_usuario": MIN_USUARIO,
                    "min_senha": MIN_SENHA,
                })
            elif rota == "/api/config":
                env = ler_env()
                saida = {}
                for chave, _, _, segredo, _ in CAMPOS:
                    saida[chave] = "" if (segredo and env.get(chave)) else env.get(chave, "")
                    saida[chave + "__set"] = bool(env.get(chave))
                # Os metadados dos campos vêm junto. O JS mantinha uma cópia
                # hand-written dessa lista, que só coincidia com o Python por
                # coincidência — duas listas para a mesma verdade é o jeito
                # mais garantido de elas divergirem.
                saida["campos"] = [
                    {"chave": c[0], "rotulo": c[1], "grupo": c[2],
                     "segredo": bool(c[3]), "ajuda": c[4]}
                    for c in CAMPOS
                ]
                self._json(saida)
            elif rota == "/api/logs":
                fonte = urlparse(self.path).query
                alvo = acao if "acao" in fonte else bot
                self._json({"linhas": list(alvo.linhas)})
            elif rota == "/api/nichos":
                from .nichos import catalogo, ler_selecao
                self._json({"catalogo": catalogo(), "selecionados": ler_selecao()})
            elif rota == "/api/filtros":
                from .config import config
                self._json({
                    "avaliacao_minima": config.avaliacao_minima,
                    "vendas_minimas": config.vendas_minimas,
                    "desconto_minimo": config.desconto_minimo,
                    # A tela chamava este campo de desconto_minimo_pct. Como a
                    # chave antiga nunca era lida, o filtro de desconto ficava
                    # sempre em 0 sem o usuário perceber. Devolvemos os dois
                    # nomes para os dois lados do contrato fecharem.
                    "desconto_minimo_pct": config.desconto_minimo,
                    "permitir_sem_desconto": config.permitir_sem_desconto,
                    "permitir_sem_avaliacao": config.permitir_sem_avaliacao,
                    "permitir_sem_vendas": config.permitir_sem_vendas,
                    "preco_minimo": config.preco_minimo,
                    "preco_maximo": config.preco_maximo,
                    "palavras_bloqueadas": config.palavras_bloqueadas,
                })
            elif rota == "/api/cadencia":
                from .config import config
                # O bloco `geral` do config.yaml e o que realmente manda no
                # ritmo da publicacao: o intervalo do job que roda o ciclo
                # (bot_interativo), quantas ofertas o ciclo escolhe (pipeline)
                # e o sleep entre uma e outra. Ele era lido em todo lugar e nao
                # era gravavel de lugar nenhum do painel — a aba so expunha o
                # bloco `publicacao`, que esta zerado e por isso nao muda nada.
                # A rota existe para o que roda ter na tela o mesmo controle
                # que tem no arquivo.
                self._json({
                    "intervalo_minutos": config.intervalo_minutos,
                    "max_posts_por_ciclo": config.max_posts_por_ciclo,
                    "espacamento_segundos": config.espacamento_segundos,
                    "nao_repetir_dias": config.nao_repetir_dias,
                    # Vazio = 24h, que e como o config.py le. O /api/status
                    # devolve "24h" nesse caso (leitura); aqui devolvemos o
                    # valor cru para a tela poder mostrar o campo vazio.
                    "horario_ativo": config.horario_ativo,
                })
            elif rota == "/api/publicacao-controle":
                from . import config as config_mod
                from .publishing_control import publishing_controller
                cfg = config_mod.config
                # somente_leitura: este GET é polled a cada 5s pelo card de
                # status. Como a cadência agora é estado compartilhado com o
                # bot, consultar não pode iniciar a pausa de bloco nem
                # gravar nada — o card é um painel, não o dono do relógio.
                pode, motivo, restante = publishing_controller.pode_publicar(
                    somente_leitura=True)
                # Aninhado em "config"/"status" porque é o que o painel_js
                # consome (painel_html.py -> p.config / p.status). A resposta
                # era chapada, então o JS caía sempre no default ?? 300 e o
                # card de cadência mostrava zero falso a cada 5s.
                # Os tempos seguem em SEGUNDOS: quem converte para minutos é a
                # tela, e o config.yaml/pipeline continuam em segundos.
                self._json({
                    "config": {
                        "intervalo_entre_posts_segundos": cfg.intervalo_entre_posts_segundos,
                        "posts_antes_pausa": cfg.posts_antes_pausa,
                        "tempo_pausa_segundos": cfg.tempo_pausa_segundos,
                        "max_posts_periodo": cfg.max_posts_periodo,
                        "periodo_horas": cfg.periodo_horas,
                    },
                    "status": {
                        **publishing_controller.obter_status(),
                        "pode_publicar": pode,
                        "motivo_espera": motivo,
                        "restante_segundos": restante,
                    },
                })
            elif rota == "/api/fontes-telegram":
                self._json({
                    "fontes": db.listar_fontes_telegram(),
                    "total_processadas": db.total_msgs_telegram_processadas(),
                })
            elif rota == "/api/scraping-config":
                from .config import config
                self._json({
                    "ativo": bool(config.scraping_telegram_ativo),
                    "intervalo_segundos": config.scraping_intervalo_segundos,
                    "limite_mensagens_por_ciclo": config.scraping_max_msgs,
                })
            else:
                self._json({"erro": "rota desconhecida"}, 404)
        except Exception as e:
            try:
                self._json({"erro": str(e)}, 500)
            except Exception:
                pass

    def do_POST(self):
        try:
            rota = urlparse(self.path).path
            dados = self._corpo_json()

            if rota == "/api/login":
                return self._fazer_login(dados)
            if rota == "/api/logout":
                _encerrar_sessao(_token_do_pedido(self))
                return self._json({"ok": True}, cookie=self._cookie_limpar())
            if not self._permitido():
                return
            if rota == "/api/conta":
                return self._conta(dados)
            if rota == "/api/conta/remover":
                return self._conta_remover(dados)

            if rota == "/api/config":
                atuais = ler_env()
                filtrados = {}
                for chave, _, _, segredo, _ in CAMPOS:
                    if chave not in dados:
                        continue
                    v = dados[chave]
                    if segredo and not v and atuais.get(chave):
                        continue
                    filtrados[chave] = v
                salvar_env(filtrados)
                self._json({"ok": True})
            elif rota == "/api/filtros":
                from . import config as config_mod
                # A tela envia o desconto como "desconto_minimo_pct", mas quem
                # lê e grava é "desconto_minimo". Sem esta tradução o _so_presentes
                # descartava a chave e o filtro ficava travado em 0 para sempre.
                if "desconto_minimo_pct" in dados and "desconto_minimo" not in dados:
                    dados = dict(dados)
                    dados["desconto_minimo"] = dados["desconto_minimo_pct"]
                config_mod.salvar_yaml_secao("filtros", _so_presentes(dados, {
                    "avaliacao_minima": _float,
                    "vendas_minimas": _int,
                    "desconto_minimo": _int,
                    "permitir_sem_desconto": _bool,
                    "permitir_sem_avaliacao": _bool,
                    "permitir_sem_vendas": _bool,
                    "preco_minimo": _float,
                    "preco_maximo": _float,
                    "palavras_bloqueadas": _lista_de_palavras,
                }))
                # Lê o atributo só depois do save (ver /api/scraping-config).
                cfg = config_mod.config
                self._json({"ok": True, "filtros": {
                    "avaliacao_minima": cfg.avaliacao_minima,
                    "vendas_minimas": cfg.vendas_minimas,
                    "desconto_minimo": cfg.desconto_minimo,
                    "desconto_minimo_pct": cfg.desconto_minimo,
                }})
            elif rota == "/api/cadencia":
                from . import config as config_mod
                # Nenhum destes aceita negativo: o intervalo vira `sleep`, o
                # espacamento e comparado com um timestamp e a janela de nao
                # repetir entra em conta de dias. Negativo ali sai do controle
                # de cadencia em silencio, entao e recusado aqui.
                for chave, rotulo in (("intervalo_minutos",
                                       "O intervalo do ciclo"),
                                      ("max_posts_por_ciclo",
                                       "O máximo de posts por ciclo"),
                                      ("espacamento_segundos",
                                       "O espaçamento entre posts"),
                                      ("nao_repetir_dias",
                                       "A janela de não repetir")):
                    if chave in dados and int(dados[chave] or 0) < 0:
                        return self._json({"erro": f"{rotulo} não pode ser "
                                                   "negativo."}, 400)
                if "horario_ativo" in dados:
                    janela = str(dados["horario_ativo"] or "").strip()
                    if janela in ("24h", "24", ""):
                        # Vazio = 24h, que e como o config.py le. O
                        # /api/status devolve "24h" nesse caso; gravar a forma
                        # crua mantem o arquivo igual ao do projeto anterior e
                        # evita duas grafias para o mesmo estado.
                        janela = ""
                    elif not re.fullmatch(
                            r"([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d",
                            janela):
                        # A config.py tolera formato ruim devolvendo True, ou
                        # seja, libera a postagem o dia inteiro. Uma digitacao
                        # errada aqui passaria em silencio e a janela nunca
                        # valeria — e o usuario acharia que ela funciona.
                        return self._json({"erro": "O horário ativo precisa ser "
                                                   "HH:MM-HH:MM, ou 24h."}, 400)
                    dados = dict(dados)
                    dados["horario_ativo"] = janela
                config_mod.salvar_yaml_secao("geral", _so_presentes(dados, {
                    "intervalo_minutos": _int,
                    "max_posts_por_ciclo": _int,
                    "espacamento_segundos": _int,
                    "nao_repetir_dias": _int,
                    "horario_ativo": str,
                }))
                # Le o atributo so depois do save (ver /api/scraping-config):
                # `salvar_yaml_secao` recria o objeto de config.
                cfg = config_mod.config
                self._json({"ok": True, "cadencia": {
                    "intervalo_minutos": cfg.intervalo_minutos,
                    "max_posts_por_ciclo": cfg.max_posts_por_ciclo,
                    "espacamento_segundos": cfg.espacamento_segundos,
                    "nao_repetir_dias": cfg.nao_repetir_dias,
                    "horario_ativo": cfg.horario_ativo,
                }})
            elif rota == "/api/publicacao-controle":
                from . import config as config_mod
                if dados.get("reset_cadencia"):
                    from .publishing_control import publishing_controller
                    publishing_controller.reset()
                    return self._json({"ok": True})
                # A tela manda SEGUNDOS (converte minutos na borda). Valida
                # tempo negativo: o pipeline compara isso com um timestamp e
                # sairia do controle de cadência.
                for chave, rotulo in (("intervalo_entre_posts_segundos",
                                       "O intervalo entre posts"),
                                      ("tempo_pausa_segundos",
                                       "A duração da pausa")):
                    if chave in dados and int(dados[chave] or 0) < 0:
                        return self._json({"erro": f"{rotulo} não pode ser "
                                                   "negativo."}, 400)
                config_mod.salvar_yaml_secao("publicacao", _so_presentes(dados, {
                    "intervalo_entre_posts_segundos": _int,
                    "posts_antes_pausa": _int,
                    "tempo_pausa_segundos": _int,
                    "max_posts_periodo": _int,
                    "periodo_horas": _int,
                }))
                self._json({"ok": True})
            elif rota == "/api/start":
                from . import instancia
                # Bot que este painel não iniciou: se existir, o novo processo
                # vai encerrá-lo (trava de instância). Avisamos para o clique não
                # parecer um desligamento do nada.
                anterior = instancia.titular_vivo("bot")
                ok = bot.iniciar(["run"], "Bot")
                self._json({
                    "ok": ok,
                    "rodando": bot.rodando(),
                    "substituiu": (anterior or {}).get("pid") if anterior else None,
                })
            elif rota == "/api/stop":
                bot.parar()
                self._json({"ok": True, "rodando": bot.rodando()})
            elif rota == "/api/acao":
                nome = dados.get("nome", "")
                mapa = {
                    "instalar-navegador": (["instalar-navegador"], "Instalando navegador"),
                    "ml-login": (["ml-login"], "Login no Mercado Livre"),
                    "testar-ml": (["testar", "ml"], "Testando Mercado Livre"),
                    "testar-shopee": (["testar", "shopee"], "Testando Shopee"),
                    "testar-amazon": (["testar", "amazon"], "Testando Amazon"),
                    "testar-aliexpress": (["testar", "aliexpress"], "Testando AliExpress"),
                    "testar-grok": (["testar", "grok"], "Testando xAI / Grok"),
                    "ciclo": (["ciclo"], "Executando ciclo de postagem"),
                }
                if nome not in mapa:
                    return self._json({"erro": "ação desconhecida"}, 400)
                if acao.rodando():
                    # O botão de login do ML é o caso que mais trava: o
                    # navegador fica aberto até a pessoa fechá-lo, e durante
                    # esse tempo TODA ação é recusada — clicar de novo só
                    # repetia um toast rápido e passageiro. Por isso devolvemos
                    # o rótulo e explicitamos o caminho para destravar.
                    return self._json({
                        "erro": f"Já rodando: {acao.rotulo}. Clique em "
                                f"“Cancelar” na barra de ações para liberar.",
                        "acao_rodando": acao.rotulo,
                        "pode_cancelar": True,
                    }, 409)
                args, rotulo = mapa[nome]
                acao.linhas.clear()
                acao.iniciar(args, rotulo)
                self._json({"ok": True})
            elif rota == "/api/cancelar-acao":
                if acao.rodando():
                    rot = acao.rotulo
                    acao.parar()
                    self._json({"ok": True, "msg": f"Ação '{rot}' cancelada com sucesso."})
                else:
                    self._json({"ok": True, "msg": "Nenhuma ação em execução."})
            elif rota == "/api/gerar-link":
                url = dados.get("url", "")
                plat = dados.get("plataforma", "")
                self._json(gerar_link_afiliado(url, plat))
            elif rota == "/api/verificar-sessao":
                perfil = DATA_DIR / "ml_profile"
                tem = _sessao_ml_existe()
                self._json({
                    "sessao_ml": tem,
                    "arquivos": len(list(perfil.rglob("*"))) if tem else 0,
                    "caminho": str(perfil),
                })
            elif rota == "/api/limpar-log":
                alvo = acao if dados.get("alvo") == "acao" else bot
                alvo.linhas.clear()
                self._json({"ok": True})
            elif rota == "/api/limpar-sessao":
                perfil = DATA_DIR / "ml_profile"
                if perfil.exists():
                    try:
                        shutil.rmtree(perfil)
                        perfil.mkdir(exist_ok=True)
                    except Exception as e:
                        return self._json({"erro": f"Erro ao limpar: {e}"}, 500)
                self._json({"ok": True, "msg": "Sessão limpa com sucesso."})
            elif rota == "/api/nichos":
                from .nichos import salvar_selecao
                salvar_selecao(dados.get("selecionados") or [])
                self._json({"ok": True})
            elif rota == "/api/fontes-telegram":
                from .sources.telegram_scraper import normalizar_username_telegram
                chat_id_raw = str(dados.get("chat_id", "") or dados.get("username", "")).strip()
                nome = str(dados.get("nome", "")).strip()
                tipo = str(dados.get("tipo", "canal")).strip()
                ativa = bool(dados.get("ativa", dados.get("ativo", True)))
                if not chat_id_raw:
                    return self._json({"erro": "Username ou ID do canal/grupo é obrigatório."}, 400)
                norm = normalizar_username_telegram(chat_id_raw)
                nome = nome or f"Fonte {norm}"
                db.salvar_fonte_telegram(norm, nome, tipo, ativa)
                # "fonte" volta junto porque a tela mostra d.fonte?.username no
                # toast; sem a chave ele caía no fallback e mascarava o erro.
                self._json({"ok": True, "fonte": {"username": norm, "chat_id": norm, "nome": nome},
                            "fontes": db.listar_fontes_telegram()})
            elif rota == "/api/fontes-telegram/remover":
                # Aceita "chat_id" e "username": a coluna e a resposta da API
                # usam chat_id, mas a tela falava "username". Só esta rota e a
                # de status não tinham o "or username" que /fontes-telegram e
                # /testar já tinham — era essa assimetria que fazia o botão de
                # excluir responder "ID da fonte é obrigatório".
                chat_id = str(dados.get("chat_id", "") or dados.get("username", "")).strip()
                if not chat_id:
                    return self._json({"erro": "ID da fonte é obrigatório."}, 400)
                db.remover_fonte_telegram(chat_id)
                self._json({"ok": True, "fontes": db.listar_fontes_telegram()})
            elif rota == "/api/fontes-telegram/status":
                chat_id = str(dados.get("chat_id", "") or dados.get("username", "")).strip()
                if not chat_id:
                    return self._json({"erro": "ID da fonte é obrigatório."}, 400)
                # "ativa" (coluna) e "ativo" (tela) — mesma tolerância acima.
                ativa = bool(dados.get("ativa", dados.get("ativo", True)))
                db.atualizar_status_fonte_telegram(chat_id, ativa)
                self._json({"ok": True, "fontes": db.listar_fontes_telegram()})
            elif rota == "/api/fontes-telegram/testar":
                from .sources.telegram_scraper import testar_conexao_fonte
                fonte_str = str(dados.get("chat_id", "") or dados.get("username", "")).strip()
                if not fonte_str:
                    return self._json({"erro": "Informe o @username ou ID do canal/grupo."}, 400)
                import asyncio
                res = asyncio.run(testar_conexao_fonte(fonte_str))
                self._json(res)
            elif rota == "/api/scraping-config":
                from . import config as config_mod
                # A tela manda "limite_mensagens_por_ciclo"; o config.yaml usa
                # "max_mensagens_por_ciclo". A tradução fica aqui, no servidor,
                # para o JS não precisar saber o nome interno do YAML.
                if "intervalo_segundos" in dados:
                    v = int(dados["intervalo_segundos"] or 0)
                    if v < 5:
                        return self._json({"erro": "O intervalo mínimo é de 5 segundos."}, 400)
                if "limite_mensagens_por_ciclo" in dados:
                    v = int(dados["limite_mensagens_por_ciclo"] or 0)
                    if not 1 <= v <= 500:
                        return self._json({"erro": "O limite deve ser entre 1 e 500 mensagens."}, 400)
                novo = {}
                if "ativo" in dados:
                    novo["ativo"] = _bool(dados["ativo"])
                if "intervalo_segundos" in dados:
                    novo["intervalo_segundos"] = _int(dados["intervalo_segundos"])
                if "limite_mensagens_por_ciclo" in dados:
                    novo["max_mensagens_por_ciclo"] = _int(dados["limite_mensagens_por_ciclo"])
                config_mod.salvar_yaml_secao("scraping_telegram", novo)
                # Lê o atributo só DEPOIS do save: salvar_yaml_secao recria o
                # objeto global, então um "from .config import config" feito
                # antes devolveria a instância velha na resposta.
                cfg = config_mod.config
                self._json({
                    "ok": True,
                    "ativo": bool(cfg.scraping_telegram_ativo),
                    "intervalo_segundos": cfg.scraping_intervalo_segundos,
                    "limite_mensagens_por_ciclo": cfg.scraping_max_msgs,
                })
            elif rota == "/api/detectar-ids":
                # Sem try/except: detectar_ids() já devolve {"erro": ...} nos
                # três failure modes (sem token, Telegram fora do ar, token
                # recusado) e o JS sabe mostrar isso na caixa de detecção.
                self._json(detectar_ids())
            else:
                self._json({"erro": "rota desconhecida"}, 404)
        except Exception as e:
            try:
                self._json({"erro": str(e)}, 500)
            except Exception:
                pass


def painel():
    url = f"http://{HOST}:{PORT}/"
    ThreadingHTTPServer.allow_reuse_address = True
    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"\n  Painel de controle aberto em {url}")
    print("  (deixe esta janela aberta; feche-a para desligar o painel)\n")

    # O bot é filho deste painel. Sem isto, fechar o painel (ou matá-lo)
    # deixava o bot vivo e órfão, publicando sem ninguém no comando — foi
    # assim que se acumularam quatro cópias rodando ao mesmo tempo. atexit
    # cobre também o caminho de exceção e o Ctrl+C, em que o bloco do fim
    # nem chega a rodar.
    import atexit

    def _desligar_bot() -> None:
        try:
            if bot.rodando():
                print("  Painel encerrando: desligando o bot...")
                bot.parar()
        except Exception:
            pass

    atexit.register(_desligar_bot)

    try:
        webbrowser.open(url)
    except Exception:
        pass
    while True:
        try:
            servidor.serve_forever()
            break
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            print(f"Erro no servidor: {e}", file=sys.stderr)
            import time
            time.sleep(1)
    _desligar_bot()
    try:
        servidor.server_close()
    except Exception:
        pass

