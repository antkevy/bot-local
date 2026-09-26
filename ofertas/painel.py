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
        self.linhas.append(f"▶ {rotulo}...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "ofertas", *args],
            cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
    perfil = DATA_DIR / "ml_profile"
    return perfil.exists() and any(perfil.iterdir())


def status() -> dict:
    env = ler_env()
    tem_navegador = bool(list((DATA_DIR / "pw-browsers").glob("chromium-*")))
    tem_sessao_ml = _sessao_ml_existe()
    tem_ml_etiqueta = bool(env.get("ML_ETIQUETA"))
    ml_conectado = tem_sessao_ml and tem_ml_etiqueta

    amz_conectado = bool(env.get("AMAZON_TAG"))
    shp_conectado = bool(env.get("SHOPEE_APP_ID") and env.get("SHOPEE_APP_SECRET"))
    total = total_postadas()

    from .config import config
    fontes = [nome for nome, f in (("Mercado Livre", config.fonte_ml),
                                   ("Shopee", config.fonte_shopee),
                                   ("Amazon", config.fonte_amazon)) if f.get("ativa")]

    return {
        "bot_rodando": bot.rodando(),
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
                "status": "Link Builder pronto" if ml_conectado else ("Sessão pendente" if not tem_sessao_ml else "Etiqueta não configurada"),
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
                "conectado": False,
                "disponivel": False,
                "status": "Integração indisponível",
            },
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
        elif "aliexpress.com" in url_lower:
            plat = "aliexpress"
        else:
            return {"erro": ("Não reconheci o marketplace deste link. "
                             "Escolha a plataforma manualmente em 'Plataforma'.")}

    if plat == "aliexpress":
        return {"erro": "O AliExpress ainda não tem integração neste projeto."}

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
                self._json(saida)
            elif rota == "/api/logs":
                fonte = urlparse(self.path).query
                alvo = acao if "acao" in fonte else bot
                self._json({"linhas": list(alvo.linhas)})
            elif rota == "/api/nichos":
                from .nichos import catalogo, ler_selecao
                self._json({"catalogo": catalogo(), "selecionados": ler_selecao()})
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
                    v = dados.get(chave, "")
                    if segredo and not v and atuais.get(chave):
                        continue
                    filtrados[chave] = v
                salvar_env(filtrados)
                self._json({"ok": True})
            elif rota == "/api/start":
                ok = bot.iniciar(["run"], "Bot")
                self._json({"ok": ok, "rodando": bot.rodando()})
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
                    "ciclo": (["ciclo"], "Executando ciclo de postagem"),
                }
                if nome not in mapa:
                    return self._json({"erro": "ação desconhecida"}, 400)
                if acao.rodando():
                    return self._json({"erro": f"Já rodando: {acao.rotulo}"}, 409)
                args, rotulo = mapa[nome]
                acao.linhas.clear()
                acao.iniciar(args, rotulo)
                self._json({"ok": True})
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
            elif rota == "/api/detectar-ids":
                self._json(detectar_ids())
            elif rota == "/api/nichos":
                from .nichos import salvar_selecao
                salvar_selecao(dados.get("selecionados") or [])
                self._json({"ok": True})
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
    try:
        bot.parar()
        servidor.server_close()
    except Exception:
        pass

