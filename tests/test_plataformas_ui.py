"""Contrato da aba Plataformas: a grade de cards e a gaveta de configuracao.

Estes testes sobem a PAGINA num servidor local efemero e dirigem o Chromium
de verdade, porque o que precisa ser travado aqui e comportamento de
navegador: foco preso, gaveta fechando, polling nao apagando digitacao,
filtro de overflow. Um teste que so contaria occurrences no HTML passaria
com a tela inteira quebrada.

Nao toca no painel de producao, no .env nem no config.yaml: as respostas de
/api/status e /api/config sao fabricadas aqui mesmo, o que ainda permite
exercitar os estados desconectados — que os dados reais nao mostram, porque
nesta maquina esta tudo ligado.
"""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

CHAVES = [
    ("ML_ETIQUETA", "Mercado Livre", False),
    ("ML_COOKIE", "Mercado Livre", True),
    ("AMAZON_TAG", "Amazon", False),
    ("AMAZON_CREDENTIAL_ID", "Amazon", False),
    ("AMAZON_CREDENTIAL_SECRET", "Amazon", True),
    ("SHOPEE_APP_ID", "Shopee", False),
    ("SHOPEE_APP_SECRET", "Shopee", True),
    ("ALIEXPRESS_APP_KEY", "AliExpress", False),
    ("ALIEXPRESS_APP_SECRET", "AliExpress", True),
    ("ALIEXPRESS_TRACKING_ID", "AliExpress", False),
    ("TELEGRAM_BOT_TOKEN", "Telegram", True),
    ("TELEGRAM_OWNER_ID", "Telegram", False),
    ("TELEGRAM_CHAT_ID", "Telegram", False),
    ("XAI_API_KEY", "Inteligência Artificial (Grok)", True),
]

# Estado em que nada esta ligado. E' o ponto de partida de quase todo teste
# aqui: e' o unico estado que mostra os cards falando, e sem ele a tela
# "funciona" mesmo com a logica de estado errada.
STATUS_VAZIO = {
    "plataformas": {
        "mercadolivre": {"conectado": False, "status": "Sessão pendente (Faça login ou insira o Cookie)",
                         "sessao_ativa": False},
        "amazon": {"conectado": False, "status": "Não configurado", "api_ativa": False},
        "shopee": {"conectado": False, "status": "Não configurado"},
        "aliexpress": {"conectado": False, "status": "Não configurado"},
    },
    "preenchidos": {"TELEGRAM_BOT_TOKEN": False, "TELEGRAM_OWNER_ID": False, "TELEGRAM_CHAT_ID": False},
    "pronto": False, "navegador": False, "sessao_ml": False, "grok": {},
    "fontes_ativas": [], "nichos": [], "bot_rodando": False, "acao_rodando": "",
    "intervalo_minutos": 45, "max_posts_por_ciclo": 3, "horario_ativo": "24h",
}

STATUS_LIGADO = json.loads(json.dumps(STATUS_VAZIO))
STATUS_LIGADO["plataformas"]["mercadolivre"] = {
    "conectado": True, "status": "Link Builder pronto", "sessao_ativa": True}
STATUS_LIGADO["plataformas"]["amazon"] = {"conectado": True, "status": "Tag configurada", "api_ativa": True}
STATUS_LIGADO["plataformas"]["shopee"] = {"conectado": True, "status": "API configurada"}
STATUS_LIGADO["plataformas"]["aliexpress"] = {"conectado": True, "status": "Open API pronta"}
STATUS_LIGADO["preenchidos"] = {k: True for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID", "TELEGRAM_CHAT_ID")}
STATUS_LIGADO["pronto"] = True

# O que o painel real tem gravado nesta maquina, so para exercitar o caminho
# "ja configurado". Nenhum destes valores e usado fora do navegador de teste.
GRAVADO = {
    "ML_ETIQUETA": "fastpromo", "AMAZON_TAG": "afiliadohub-20",
    "SHOPEE_APP_ID": "18318020080", "ALIEXPRESS_APP_KEY": "545506",
    "ALIEXPRESS_TRACKING_ID": "bot-ofertas", "TELEGRAM_OWNER_ID": "1382089335",
    "TELEGRAM_CHAT_ID": "-1003942213987",
}
SEGREDOS_GRAVADOS = ["ML_COOKIE", "AMAZON_CREDENTIAL_SECRET", "SHOPEE_APP_SECRET",
                     "ALIEXPRESS_APP_SECRET", "TELEGRAM_BOT_TOKEN", "XAI_API_KEY"]

# O bloco `geral` do config.yaml, que e o ritmo real do bot. Sao os mesmos
# valores que o projeto anterior usava, e o que esta gravado nesta maquina.
#
# Dois campos NAO batem com o que o HTML traz embutido (120 e 7) de proposito:
# se o stub devolvesse os mesmos numeros, o teste passaria mesmo com
# `carregarCadencia` nunca sendo chamada, porque o campo ja nasceria
# preenchido. Divergir e o que prova que o valor veio do servidor.
CADENCIA_GERAL = {
    "intervalo_minutos": 45,
    "max_posts_por_ciclo": 3,
    "espacamento_segundos": 90,
    "nao_repetir_dias": 5,
    "horario_ativo": "",
}

# Estado do servidor espelhado, trocado por teste antes de abrir a pagina.
RESPOSTAS: dict[str, object] = {}


def _config_com_gravados(grupos_gravados: set[str]) -> dict:
    corpo = {"campos": [{"chave": k, "rotulo": k, "grupo": g, "segredo": s, "ajuda": f"ajuda de {k}"}
                        for k, g, s in CHAVES]}
    for chave, _grupo, _seg in CHAVES:
        grupo = next(g for k, g, _ in CHAVES if k == chave)
        tem = grupo in grupos_gravados and (chave in GRAVADO or chave in SEGREDOS_GRAVADOS)
        corpo[chave + "__set"] = tem
        corpo[chave] = GRAVADO.get(chave, "")
    return corpo


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silencia o log do http.server
        pass

    def _responder(self, corpo: bytes, tipo: str, cod: int = 200):
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        caminho = urlparse(self.path).path
        if caminho == "/":
            from ofertas.painel_html import PAGINA
            return self._responder(PAGINA.encode("utf-8"), "text/html; charset=utf-8")
        if caminho in RESPOSTAS:
            return self._responder(json.dumps(RESPOSTAS[caminho]).encode("utf-8"), "application/json")
        # Qualquer outra rota que a pagina chame no boot: resposta vazia e
        # 200, senao o console acusa erro de rede e polui o teste de ruído.
        return self._responder(b"{}", "application/json")

    def do_POST(self):
        caminho = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(n) if n else b"{}"
        if caminho in ("/api/config", "/api/cadencia") and caminho in RESPOSTAS:
            # O /api/config de mentira precisa lembrar do que foi salvo. Sem
            # isto, salvar repinta o campo com o valor velho da resposta e o
            # teste acusaria perda de dado onde nao houve. A cadencia entra
            # na mesma lista porque o card novo nao tem o valor de origem em
            # lugar nenhum: so o POST revela que o dado chegou.
            atual = dict(RESPOSTAS[caminho])
            try:
                enviado = json.loads(bruto)
            except ValueError:
                enviado = {}
            for chave, valor in enviado.items():
                if valor:
                    atual[chave] = valor
                    atual[chave + "__set"] = True
            RESPOSTAS[caminho] = atual
        return self.do_GET()


class TestAbaPlataformas(unittest.TestCase):
    navegador = None
    servidor = None
    porta = 0

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("playwright não instalado")
        try:
            cls._pw = sync_playwright().start()
            cls.navegador = cls._pw.chromium.launch(headless=True)
        except Exception as e:  # navegador baixado, porem ausente
            try:
                cls._pw.stop()
            except Exception:
                pass
            raise unittest.SkipTest(f"Chromium indisponível: {e}")
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.porta = cls.servidor.server_address[1]
        cls._thread = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls.navegador:
            cls.navegador.close()
        if cls._pw:
            cls._pw.stop()
        if cls.servidor:
            cls.servidor.shutdown()
            cls.servidor.server_close()

    # ── infraestrutura de cada teste ──────────────────────────────
    def abrir(self, status=None, gravados=frozenset(), hash="#plataformas"):
        RESPOSTAS.clear()
        RESPOSTAS["/api/status"] = STATUS_LIGADO if status is None else status
        RESPOSTAS["/api/config"] = _config_com_gravados(set(gravados))
        RESPOSTAS["/api/cadencia"] = dict(CADENCIA_GERAL)
        self.console = []
        self.pagina = self.navegador.new_page(viewport={"width": 1440, "height": 980})
        self.pagina.on("console", lambda m: self.console.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        self.pagina.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
        self.pagina.goto(f"http://127.0.0.1:{self.porta}/{hash}", wait_until="networkidle")
        self.pagina.wait_for_timeout(1200)
        return self.pagina

    def fechar(self):
        self.pagina.close()

    def cards(self):
        return self.pagina.evaluate("""() => [...document.querySelectorAll('#blocosPlataforma > section.plato')]
            .map(c => ({
                chave: c.id.replace('plato-', ''),
                nome: c.querySelector('h3').textContent,
                sub: c.querySelector('small').textContent,
                selo: c.querySelector('.selo').textContent.trim(),
                classe: c.querySelector('.selo').className.replace('selo selo-', ''),
                rotulo: c.querySelector('.plato-linha').textContent,
                resumo: c.querySelector('.plato-linha').textContent.trim(),
                botoes: [...c.querySelectorAll('.plato-rodape button')].map(b => b.textContent.trim()),
                inputs: c.querySelectorAll('input').length,
            }))""")

    def abrir_gaveta(self, chave):
        self.pagina.click(f"#plato-{chave} .plato-rodape button")
        self.pagina.wait_for_timeout(500)
        return self.pagina.evaluate("""() => {
            const ov = document.querySelector('#gavetaPlataforma');
            const g = document.querySelector('#gaveta');
            return {
                aberta: ov.classList.contains('aberto'),
                titulo: document.querySelector('#gavetaTitulo').textContent,
                sub: document.querySelector('#gavetaSub').textContent,
                campos: [...document.querySelectorAll('#gavetaCampos input')].map(i => ({
                    nome: i.name, tipo: i.type, valor: i.value, ph: i.placeholder })),
                marcas: [...document.querySelectorAll('#gavetaCampos .marca-ok')].length,
                situacao: document.querySelector('#gavetaResumo').textContent.replace(/\\s+/g, ' ').trim(),
                seloGaveta: (document.querySelector('#gavetaResumo .selo') || {}).textContent || '',
                statusGaveta: (document.querySelector('#gavetaResumo .gaveta-status') || {}).textContent || '',
                acoes: [...document.querySelectorAll('#gavetaAcoesBloco button')].map(b => b.textContent.trim()),
                salvar: !!document.querySelector('#gavetaSalvar'),
                dica: document.querySelector('#gavetaDica').textContent,
                noPe: (() => { const r = g.getBoundingClientRect();
                    return { direita: Math.round(window.innerWidth - r.right),
                             largura: Math.round(r.width), altura: Math.round(r.height),
                             topo: Math.round(r.top) }; })(),
            };
        }""")

    def gaveta_aberta(self):
        return self.pagina.evaluate(
            "() => document.querySelector('#gavetaPlataforma').classList.contains('aberto')")


class TestGradePlataformas(TestAbaPlataformas):
    """A grade: cinco integracoes, um botao cada, nenhuma credencial exposta."""

    def tearDown(self):
        self.fechar()

    def test_cinco_cards_na_ordem_dos_blocos(self):
        pg = self.abrir()
        esperado = ["mercadolivre", "amazon", "shopee", "aliexpress", "telegram"]
        self.assertEqual([c["chave"] for c in self.cards()], esperado)
        self.assertEqual([c["nome"] for c in self.cards()],
                         ["Mercado Livre", "Amazon", "Shopee", "AliExpress", "Telegram"])
        self.assertEqual(self.console, [], f"erro de console: {self.console}")

    def test_nenhum_cartao_expoe_campo_de_credencial(self):
        """A mudanca central: o campo saiu do cartao e foi para a gaveta.

        Sem esta verificacao a tela volta a ser a de antes sem ninguem
        perceber, porque continua "funcionando" — so que empurrando quem
        configurava para a rolagem de uma pagina de formularios.
        """
        pg = self.abrir(gravados={"Mercado Livre", "Amazon", "Shopee", "AliExpress", "Telegram"})
        for c in self.cards():
            self.assertEqual(c["inputs"], 0, f"{c['chave']} ainda tem {c['inputs']} input na grade")

    def test_um_botao_configurar_por_cartao(self):
        pg = self.abrir()
        for c in self.cards():
            self.assertEqual(c["botoes"], ["Configurar"], f"{c['chave']}: {c['botoes']}")

    def test_resumo_e_o_texto_do_servidor(self):
        """O resumo nao e reescrito pela pagina: e o `status` que veio do
        /api/status, copiado. Um texto proprio aqui viraria mentira assim
        que o servidor mudasse de nomenclatura — e o servidor e a fonte."""
        pg = self.abrir()
        por_chave = {c["chave"]: c for c in self.cards()}
        status = pg.evaluate("() => statusAtual.plataformas")
        for chave, entrada in status.items():
            self.assertEqual(por_chave[chave]["resumo"], entrada["status"],
                             f"{chave}: card diz {por_chave[chave]['resumo']!r}, "
                             f"servidor mandou {entrada['status']!r}")

    def test_telegram_tem_resumo_mesmo_sem_entrada_no_status(self):
        """`plataformas` nao tem chave telegram no /api/status. O card mesmo
        assim precisa de uma linha util, derivada do que o servidor expoe
        em `preenchidos` — senao ficaria com "—" para sempre."""
        pg = self.abrir()
        tg = next(c for c in self.cards() if c["chave"] == "telegram")
        self.assertNotEqual(tg["resumo"], "—")
        self.assertIn("Token", tg["resumo"])

    def test_status_longo_ocupa_duas_linhas_sem_cortar(self):
        """O status do ML sem sessão carrega a instrução que resolve o
        problema, e ela chega no fim da frase.

        Medir `scrollHeight <= clientHeight` não separa nada aqui: com o
        limite de duas linhas o `scrollHeight` já é a altura de duas linhas,
        e com `nowrap` também. `getClientRects()` tampouco - devolve 2 nos
        dois casos. As duas afirmações antigas passavam com as duas regras e
        a mutação escapou. O que separa é a ALTURA: 36px com o limite, 18px
        sem ele. E para a altura variar, o texto precisa ocupar as duas
        linhas, senão as regras são idênticas na prática."""
        status = ("Sessão pendente (Faça login ou insira o Cookie) antes de "
                  "publicar ofertas no canal, e confira também a etiqueta "
                  "de afiliado no painel")
        st = json.loads(json.dumps(STATUS_VAZIO))
        st["plataformas"]["mercadolivre"] = {
            "conectado": False, "sessao_ativa": False, "status": status}
        pg = self.abrir(st)
        medida = pg.evaluate("""() => {
            const txt = document.querySelector('#plato-mercadolivre .plato-linha > span');
            const lh = parseFloat(getComputedStyle(txt).lineHeight) || 1;
            const linhas = Math.round(txt.getBoundingClientRect().height / lh);
            // quanto o texto precisaria, na MESMA largura, sem o limite.
            // Mede no proprio elemento: um clone vira mais um flex item e
            // divide a largura com o original, medindo a coisa errada.
            const css = txt.style.cssText;
            const largura = txt.getBoundingClientRect().width;
            txt.style.flex = 'none';
            txt.style.width = largura + 'px';
            txt.style.display = 'block';
            txt.style.lineClamp = 'none';
            txt.style.webkitLineClamp = 'none';
            txt.style.whiteSpace = 'normal';
            const necessarias = Math.round(txt.getBoundingClientRect().height / lh);
            txt.style.cssText = css;
            return {linhas: linhas, necessarias: necessarias,
                    texto: txt.textContent};
        }""")
        self.assertEqual(medida["texto"], status)
        self.assertEqual(medida["necessarias"], 2,
                         "o texto de teste deveria ocupar 2 linhas sem limite; "
                         f"ocupou {medida['necessarias']} - se mudou, ele deixou "
                         "de exercitar o limite e o teste virou decorativo")
        self.assertEqual(medida["linhas"], 2,
                         "o status deveria ocupar 2 linhas e ocupou "
                         f"{medida['linhas']}")
        self.assertGreaterEqual(medida["linhas"], medida["necessarias"],
                                "o status foi cortado: o texto precisa de "
                                f"{medida['necessarias']} linhas e coube "
                                f"{medida['linhas']}")

    def test_layout_sem_estouro_e_altura_uniforme(self):
        """`margin-top:auto` no rodape e o que alinha os botoes dos cinco
        cards. Sem ele, um card com resumo curto e outro com resumo longo
        desalinham a coluna, e nao ha como ver isso no diff."""
        pg = self.abrir()
        medida = pg.evaluate("""() => {
            const cards = [...document.querySelectorAll('#blocosPlataforma > section.plato')];
            const dentro = (a, c) => a.left >= c.left - 1 && a.right <= c.right + 1
                                  && a.top >= c.top - 1 && a.bottom <= c.bottom + 1;
            return {
                alturas: cards.map(c => Math.round(c.getBoundingClientRect().height)),
                colunas: [...new Set(cards.map(c => Math.round(c.getBoundingClientRect().x)))].sort(),
                estouro: cards.flatMap(c => {
                    const cb = c.getBoundingClientRect();
                    return [...c.querySelectorAll('*')].filter(e => !dentro(e.getBoundingClientRect(), cb))
                        .map(e => e.className || e.tagName);
                }),
                cortado: cards.flatMap(c => [...c.querySelectorAll('*')]
                    // So texto. `scrollWidth > clientWidth` numa <img> quebrada
                    // (que e o caso aqui: o servidor de teste nao serve
                    // /assets) acusa um corte que nao existe na tela real.
                    .filter(e => e.textContent.trim() && !['IMG', 'SVG', 'USE'].includes(e.tagName))
                    .filter(e => e.scrollWidth > e.clientWidth + 1)
                    .map(e => (e.className || e.tagName) + ': ' + e.textContent.trim().slice(0, 40))),
            };
        }""")
        self.assertEqual(len(set(medida["alturas"])), 1,
                         f"cards com alturas diferentes: {medida['alturas']}")
        self.assertEqual(len(medida["colunas"]), 2, f"esperava 2 colunas, achei {medida['colunas']}")
        self.assertEqual(medida["estouro"], [], f"conteudo vazando do card: {medida['estouro']}")
        self.assertEqual(medida["cortado"], [], f"texto cortado: {medida['cortado']}")

    def test_uma_coluna_abaixo_do_ponto_de_quebra(self):
        pg = self.abrir()
        for largura, colunas in [(1440, 2), (1000, 2), (900, 1), (420, 1)]:
            pg.set_viewport_size({"width": largura, "height": 900})
            pg.wait_for_timeout(350)
            posicoes = sorted({round(x) for x in pg.evaluate(
                "() => [...document.querySelectorAll('#blocosPlataforma > section.plato')]"
                ".map(e => e.getBoundingClientRect().x)")})
            self.assertEqual(len(posicoes), colunas,
                             f"{largura}px: {len(posicoes)} coluna(s) em {posicoes}, esperava {colunas}")

    def test_logo_do_telegram_e_o_glifo_do_conjunto_de_icones(self):
        """Nao ha telegram.png em /assets. Sem este glifo o card mostraria
        a caixa vazia, e o teste de "nenhum erro" nao pegaria: uma imagem
        quebrada e um svg faltando sao silenciosos."""
        pg = self.abrir()
        medida = pg.evaluate("""() => {
            const svg = document.querySelector('#plato-telegram .plato-logo-glyph');
            const img = document.querySelector('#plato-mercadolivre .plato-logo-img');
            if (!svg || !img) return null;
            const a = svg.getBoundingClientRect(), b = img.getBoundingClientRect();
            return {svg: [Math.round(a.width), Math.round(a.height)],
                    img: [Math.round(b.width), Math.round(b.height)],
                    href: svg.querySelector('use').getAttribute('href'),
                    cor: getComputedStyle(svg).color};
        }""")
        self.assertIsNotNone(medida, "telegram sem glifo, ou ML sem logo")
        self.assertEqual(medida["svg"], medida["img"], "glifo e imagem com tamanhos diferentes")
        self.assertEqual(medida["href"], "#i-send")
        self.assertNotEqual(medida["cor"], "rgb(0, 0, 0)", "glifo preto sobre card escuro")


class TestGavetaPlataforma(TestAbaPlataformas):
    """A gaveta: os campos que sairam da grade, e o comportamento de janela."""

    def tearDown(self):
        self.fechar()

    def test_gaveta_abre_com_o_grupo_de_campos_certo(self):
        pg = self.abrir()
        esperado = {
            "mercadolivre": ["ML_ETIQUETA", "ML_COOKIE"],
            "amazon": ["AMAZON_TAG", "AMAZON_CREDENTIAL_ID", "AMAZON_CREDENTIAL_SECRET"],
            "shopee": ["SHOPEE_APP_ID", "SHOPEE_APP_SECRET"],
            "aliexpress": ["ALIEXPRESS_APP_KEY", "ALIEXPRESS_APP_SECRET", "ALIEXPRESS_TRACKING_ID"],
            "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID", "TELEGRAM_CHAT_ID"],
        }
        for chave, campos in esperado.items():
            g = self.abrir_gaveta(chave)
            self.assertTrue(g["aberta"], f"{chave}: gaveta nao abriu")
            self.assertEqual([c["nome"] for c in g["campos"]], campos, chave)
            self.assertTrue(g["salvar"], f"{chave}: sem botao de salvar")
            self.pagina.keyboard.press("Escape")
            self.pagina.wait_for_timeout(300)
        self.assertEqual(self.console, [], f"erro de console: {self.console}")

    def test_cada_plataforma_so_tem_as_ações_que_existem_no_servidor(self):
        """Cada botao chama uma acao declarada no /api/acao. Um botao
        apontando para nome inexistente so falha quando alguem clica — e
        nesse momento a pessoa ja digitou a credencial."""
        pg = self.abrir()
        acoes_por_chave = {
            "mercadolivre": ["Fazer login", "Testar conexão", "Detalhes da sessão", "Limpar sessão"],
            "amazon": ["Testar conexão"],
            "shopee": ["Testar conexão"],
            "aliexpress": ["Testar conexão"],
            "telegram": ["Detectar IDs"],
        }
        for chave, esperado in acoes_por_chave.items():
            g = self.abrir_gaveta(chave)
            self.assertEqual(g["acoes"], esperado, chave)
            self.pagina.keyboard.press("Escape")
            self.pagina.wait_for_timeout(300)

    def test_segredo_nunca_aparece_e_avisado_para_manter(self):
        """O valor do segredo nao volta do servidor. Repintar o input com
        string vazia enquanto ele estava em edicao apagaria o que a pessoa
        digitou; mostrar o valor vazio sem aviso faria parecer que o
        campo sumiu."""
        pg = self.abrir(gravados={"Mercado Livre", "Shopee"})
        g = self.abrir_gaveta("mercadolivre")
        cookie = next(c for c in g["campos"] if c["nome"] == "ML_COOKIE")
        self.assertEqual(cookie["tipo"], "password")
        self.assertEqual(cookie["valor"], "", "o segredo voltou para a tela")
        self.assertIn("manter", cookie["ph"].lower())
        etiqueta = next(c for c in g["campos"] if c["nome"] == "ML_ETIQUETA")
        self.assertEqual(etiqueta["valor"], "fastpromo", "campo de texto nao voltou preenchido")
        self.assertEqual(g["marcas"], 2, "as duas metades estao gravadas, e as duas deviam estar marcadas")

    def test_foco_vai_para_o_primeiro_campo(self):
        pg = self.abrir()
        self.abrir_gaveta("shopee")
        foco = self.pagina.evaluate("() => document.activeElement.id")
        self.assertEqual(foco, "gav_SHOPEE_APP_ID")

    def test_tab_fica_preso_dentro_da_gaveta(self):
        pg = self.abrir()
        self.abrir_gaveta("amazon")
        for i in range(40):
            self.pagina.keyboard.press("Tab")
            self.pagina.wait_for_timeout(20)
            dentro = self.pagina.evaluate(
                "() => document.querySelector('#gavetaPlataforma').contains(document.activeElement)")
            self.assertTrue(dentro, f"foco escapou da gaveta no {i + 1}o Tab")

    def test_escape_clique_fora_e_o_botao_fecham(self):
        pg = self.abrir()
        for fechar in ("escape", "fora", "botao"):
            self.abrir_gaveta("amazon")
            self.assertTrue(self.gaveta_aberta(), f"{fechar}: nao abriu antes")
            if fechar == "escape":
                self.pagina.keyboard.press("Escape")
            elif fechar == "fora":
                self.pagina.mouse.click(60, 500)
            else:
                self.pagina.click('#gavetaPlataforma .gaveta-topo .btn-icone')
            self.pagina.wait_for_timeout(400)
            self.assertFalse(self.gaveta_aberta(), f"{fechar}: nao fechou")

    def test_gaveta_entra_pela_direita_e_cabe_na_tela(self):
        pg = self.abrir()
        g = self.abrir_gaveta("aliexpress")
        self.assertEqual(g["noPe"]["direita"], 0, f"gaveta nao encostou na borda: {g['noPe']}")
        self.assertLessEqual(g["noPe"]["largura"], 480)
        self.assertEqual(g["noPe"]["topo"], 0, "gaveta nao ocupa a altura toda")
        self.assertGreaterEqual(g["noPe"]["altura"], 900)

    def test_a11y_de_dialogo(self):
        pg = self.abrir()
        self.abrir_gaveta("telegram")
        self.assertEqual(self.pagina.get_attribute("#gavetaPlataforma", "role"), "dialog")
        self.assertEqual(self.pagina.get_attribute("#gavetaPlataforma", "aria-modal"), "true")
        alvo = self.pagina.get_attribute("#gavetaPlataforma", "aria-labelledby")
        self.assertEqual(alvo, "gavetaTitulo")
        self.assertEqual(self.pagina.text_content("#gavetaTitulo").strip(), "Telegram")

    def test_mudanca_de_aba_durante_o_polling_nao_quebra_o_foco(self):
        """O status chega a cada 2,5s e a gaveta esta em cima de tudo. Se a
        volta do polling reescrever o formulario, o cursor volta pro
        inicio do campo a cada 2,5 segundos e a credencial fica impossível
        de digitar."""
        pg = self.abrir()
        self.abrir_gaveta("amazon")
        self.pagina.fill("#gav_AMAZON_TAG", "digitando-aqui")
        self.pagina.click("#gavetaTitulo")  # tira o foco do campo
        self.pagina.wait_for_timeout(8000)  # tres voltas do polling
        self.assertEqual(self.pagina.input_value("#gav_AMAZON_TAG"), "digitando-aqui")
        self.assertTrue(self.gaveta_aberta(), "a gaveta fechou sozinha")

    def test_config_que_chega_durante_a_digitacao_nao_apaga_o_campo(self):
        """`/api/config` não é polled — os `setInterval` do rodapé são de
        status, métricas, logs e publicação. Mas a resposta chega por outros
        caminhos: trocar para a aba Configurações, ou salvar lá, chamam
        carregarConfig(). Se a repinta da gaveta não respeitar o campo em
        edição, a credencial que estava sendo escrita some da tela sem erro
        nenhum e sem ninguém perceber.

        Por isso o teste acima, que só espera o polling, não alcança este
        defeito: o que repinta o formulário é o /api/config. Aqui o caminho
        é disparado de propósito.
        """
        pg = self.abrir()
        self.abrir_gaveta("amazon")
        self.pagina.fill("#gav_AMAZON_TAG", "digitando-aqui")
        # Se o foco não estiver no campo, o guard é irrelevante e o teste
        # passaria sem provar nada.
        self.assertTrue(pg.evaluate("() => gavetaDigitando()"),
                        "o foco não ficou no campo da gaveta")
        pg.evaluate("() => carregarConfig()")
        pg.wait_for_timeout(1200)
        self.assertEqual(self.pagina.input_value("#gav_AMAZON_TAG"), "digitando-aqui")
        self.assertEqual(self.console, [], f"erro de console: {self.console}")

    def test_config_que_chega_sem_digitacao_atualiza_a_gaveta(self):
        """A outra ponta do guard: sem ninguém digitando, a resposta nova
        precisa mesmo entrar.

        Sem este teste, a proteção contra apagar o que está sendo escrito se
        resolve simplesmente parando de repintar — e a gaveta passaria a
        mostrar credencial velha para sempre, com o único sintoma de o botão
        "Salvar" não fazer nada.
        """
        pg = self.abrir()
        self.abrir_gaveta("amazon")
        novo = dict(RESPOSTAS["/api/config"])
        novo["AMAZON_TAG"] = "tag-nova"
        RESPOSTAS["/api/config"] = novo
        self.pagina.click("#gavetaTitulo")  # tira o foco dos campos
        self.assertFalse(pg.evaluate("() => gavetaDigitando()"))
        pg.evaluate("() => carregarConfig(true)")
        pg.wait_for_timeout(1200)
        self.assertEqual(self.pagina.input_value("#gav_AMAZON_TAG"), "tag-nova")
        self.assertEqual(self.console, [], f"erro de console: {self.console}")

    def test_gaveta_repete_o_estado_do_cartao(self):
        pg = self.abrir()
        cartoes = {c["chave"]: c for c in self.cards()}
        for chave in ("mercadolivre", "telegram"):
            g = self.abrir_gaveta(chave)
            self.assertEqual(g["seloGaveta"].strip(), cartoes[chave]["selo"], chave)
            self.assertIn(cartoes[chave]["resumo"], g["situacao"], chave)
            self.pagina.keyboard.press("Escape")
            self.pagina.wait_for_timeout(300)

    def test_gaveta_aberta_acompanha_o_polling(self):
        """A "Situação" da gaveta não é retrato do instante da abertura.

        Sem o repinto no polling, abrir a gaveta antes do primeiro
        /api/status (ou logo depois de um "Testar conexão") deixava a
        pessoa lendo "Desconectado" dentro da gaveta enquanto o card,
        logo atrás, já anunciava "Conectado" — e a gaveta não voltava a
        falar sozinho sem fechar e reabrir.
        """
        pg = self.abrir(status=STATUS_VAZIO)
        g = self.abrir_gaveta("mercadolivre")
        self.assertIn("Sessão pendente", g["situacao"], "partiu sem o status do servidor")

        # O servidor muda de estado. É a mesma troca de /api/status que o
        # painel real faz quando um "Testar conexão" dá certo.
        RESPOSTAS["/api/status"] = STATUS_LIGADO
        pg.wait_for_timeout(4200)  # o polling roda a cada 2500ms

        # Primeiro o card: se ele não mudou, o polling parou e a falha
        # seguinte seria culpa do transporte, não da gaveta.
        cartao = next(c for c in self.cards() if c["chave"] == "mercadolivre")
        self.assertEqual(cartao["selo"], "Conectado", "o card não acompanhou o status")
        self.assertEqual(cartao["resumo"], "Link Builder pronto")

        g = self.abrir_gaveta_aberta()
        self.assertEqual(g["seloGaveta"].strip(), "Conectado",
                         "a gaveta continuou com o retrato da abertura")
        self.assertIn("Link Builder pronto", g["situacao"])
        self.assertNotIn("Sessão pendente", g["situacao"])
        self.assertEqual(self.console, [], f"erro de console: {self.console}")

    def abrir_gaveta_aberta(self):
        """Lê a gaveta sem clicar — para conferir o repinto do polling."""
        return self.pagina.evaluate("""() => {
            const r = document.querySelector('#gavetaResumo');
            return {
                situacao: r.textContent.replace(/\\s+/g, ' ').trim(),
                seloGaveta: (r.querySelector('.selo') || {}).textContent || '',
                statusGaveta: (r.querySelector('.gaveta-status') || {}).textContent || '',
            };
        }""")

    def test_deteccao_de_ids_da_gaveta_aparece_nela_e_preenche_o_campo_dela(self):
        """O botão "Detectar IDs" mora na gaveta, então é na gaveta que o
        resultado tem que aparecer — e é num campo da gaveta que o id
        escolhido tem que cair.

        A função escrevia sempre em #caixaDeteccao, que mora na aba
        Configurações: o resultado aparecia fora da tela de quem pediu. E
        `setCampoId` preenchia #cfg_, que deixou de existir quando os campos
        de plataforma saíram do formulário genérico — o clique não fazia
        nada, e saía em silêncio, sem erro no console."""
        pg = self.abrir()
        RESPOSTAS["/api/detectar-ids"] = {
            "pessoas": [{"id": 777, "nome": "Eu mesmo"}],
            "canais": [{"id": -888, "nome": "Canal de ofertas"}],
        }
        self.abrir_gaveta("telegram")
        pg.click("#gavetaAcoesBloco button:has-text('Detectar IDs')")
        pg.wait_for_timeout(900)

        onde = pg.evaluate("""() => ({
            gaveta: (document.querySelector('#gavetaDeteccao') || {}).textContent || '',
            fora: (document.querySelector('#caixaDeteccao') || {}).textContent || '',
        })""")
        self.assertIn("Eu mesmo", onde["gaveta"],
                      "o resultado da detecção não apareceu dentro da gaveta")
        self.assertEqual(onde["fora"].strip(), "",
                         "o resultado foi para #caixaDeteccao, que fica na aba "
                         "Configurações: quem pediu na gaveta não vê nada")

        pg.click("#gavetaDeteccao button:has-text('Eu mesmo')")
        pg.wait_for_timeout(400)
        dono = pg.evaluate("() => (document.querySelector('#gav_TELEGRAM_OWNER_ID') "
                           "|| {}).value || ''")
        self.assertEqual(dono, "777",
                         "escolher o id detectado não preencheu o campo da gaveta")
        self.fechar()


class TestEstadosPlataforma(TestAbaPlataformas):
    """Os tres estados que o servidor distingue, e a frase do que falta."""

    def tearDown(self):
        self.fechar()

    def _com_mercadolivre(self, entrada):
        st = json.loads(json.dumps(STATUS_VAZIO))
        st["plataformas"]["mercadolivre"] = entrada
        return st

    def test_mercado_livre_tem_tres_estados_distintos(self):
        """O /api/status separa 'a sessao existe mas a etiqueta nao' de
        'nao existe nada'. Com dois estados so, o primeiro vira
        'Desconectado' e a pessoa vai caçar um problema de sessao que nao
        existe — o defeito e a etiqueta."""
        casos = [
            ({"conectado": True, "status": "Link Builder pronto", "sessao_ativa": True},
             "ok", "Conectado"),
            ({"conectado": False, "status": "Etiqueta não configurada", "sessao_ativa": True},
             "erro", "Sessão ativa, falta a etiqueta"),
            ({"conectado": False, "status": "Sessão pendente", "sessao_ativa": False},
             "neutro", "Desconectado"),
        ]
        for entrada, classe, selo in casos:
            pg = self.abrir(self._com_mercadolivre(entrada))
            card = next(c for c in self.cards() if c["chave"] == "mercadolivre")
            self.assertEqual(card["classe"], classe, entrada)
            self.assertEqual(card["selo"], selo, entrada)
            self.pagina.close()

    def test_frase_do_que_falta_lista_cada_campo(self):
        """Telegram nao tem `status` no /api/status, entao a frase e
        derivada do `preenchidos`. Ela precisa nomear o campo, e nao
        categorias: "Falta o token e o canal" diz o que preencher, e o
        campo esta logo abaixo, na propria gaveta."""
        pg = self.abrir(STATUS_VAZIO)
        tg = next(c for c in self.cards() if c["chave"] == "telegram")
        self.assertEqual(tg["resumo"], "Falta o token, o seu ID e o canal")

    def test_a_frase_diz_somente_o_que_falta(self):
        """Com o ID ja definido, ele sai da lista. "Falta o token, o seu ID
        e o canal" mandaria a pessoa abrir um campo que ja esta certo."""
        st = json.loads(json.dumps(STATUS_VAZIO))
        st["preenchidos"]["TELEGRAM_OWNER_ID"] = True
        pg = self.abrir(st)
        tg = next(c for c in self.cards() if c["chave"] == "telegram")
        self.assertEqual(tg["resumo"], "Falta o token e o canal")

    def test_telegram_usa_a_mesma_frase_das_outras(self):
        """Telegram tira o estado de `preenchidos`, as outras de CFG. Sao
        duas fontes, mas a tela e uma: se cada uma escrever do seu jeito,
        aparecem duas gramáticas na mesma coluna. Com tres campos a lista
        leva virgula antes do ultimo ("o token, o seu ID e o canal"); com
        um so, nao pode sobrar nada de lista."""
        pg = self.abrir(STATUS_VAZIO)
        tg = next(c for c in self.cards() if c["chave"] == "telegram")
        self.assertEqual(tg["resumo"], "Falta o token, o seu ID e o canal")
        pg.close()
        # (token, id, canal) -> frase. A ordem dos tres casos é a que produz
        # "a, b e c", "a e b" e "a" — a progressão de uma lista em português.
        for presentes, esperado in [
            ((False, False, False), "Falta o token, o seu ID e o canal"),
            ((True, False, False), "Falta o seu ID e o canal"),
            ((True, True, False), "Falta o canal"),
        ]:
            st = json.loads(json.dumps(STATUS_VAZIO))
            (st["preenchidos"]["TELEGRAM_BOT_TOKEN"],
             st["preenchidos"]["TELEGRAM_OWNER_ID"],
             st["preenchidos"]["TELEGRAM_CHAT_ID"]) = presentes
            self.abrir(st)
            tg = next(c for c in self.cards() if c["chave"] == "telegram")
            self.assertEqual(tg["resumo"], esperado, f"presentes={presentes}")

    def test_resumo_completo_diz_que_esta_definido(self):
        pg = self.abrir()
        tg = next(c for c in self.cards() if c["chave"] == "telegram")
        self.assertEqual(tg["resumo"], "Token, ID e canal definidos")


class TestCredenciais(TestAbaPlataformas):
    """Salvar, e a promessa de que a credencial da outra plataforma fica."""

    def tearDown(self):
        self.fechar()

    def test_salvar_manda_so_os_campos_da_gaveta(self):
        """O servidor ignora o que nao veio no corpo, entao enviar o CFG
        inteiro sobrescreveria as senhas dos outros com string vazia. E
        o erro mais caro desta tela: apagaria credencial em silencio."""
        enviados = []
        pg = self.abrir()
        pg.on("request", lambda req: enviados.append(req.post_data)
              if req.method == "POST" and req.url.endswith("/api/config") else None)
        self.abrir_gaveta("shopee")
        pg.fill("#gav_SHOPEE_APP_ID", "999")
        pg.click("#gavetaSalvar")
        pg.wait_for_timeout(1500)
        self.assertEqual(len(enviados), 1, f"esperava 1 POST, houve {len(enviados)}")
        corpo = json.loads(enviados[0])
        self.assertEqual(sorted(corpo), ["SHOPEE_APP_ID", "SHOPEE_APP_SECRET"])
        for proibido in ("ML_ETIQUETA", "ML_COOKIE", "AMAZON_TAG", "TELEGRAM_BOT_TOKEN", "XAI_API_KEY"):
            self.assertNotIn(proibido, corpo, f"{proibido} foi junto no corpo")

    def test_salvar_confirma_e_traz_a_marca_definido(self):
        pg = self.abrir()
        g = self.abrir_gaveta("amazon")
        self.assertEqual(g["marcas"], 0, "nada gravado ainda, e ja veio marcado")
        pg.fill("#gav_AMAZON_TAG", "tag-nova")
        pg.click("#gavetaSalvar")
        pg.wait_for_timeout(1800)
        self.assertIn("salvas", pg.text_content("#gavetaDica").lower())
        self.assertEqual(pg.input_value("#gav_AMAZON_TAG"), "tag-nova",
                         "o valor salvo sumiu do campo")
        marcas = pg.evaluate("() => document.querySelectorAll('#gavetaCampos .marca-ok').length")
        self.assertEqual(marcas, 1, "a marca 'definido' nao apareceu depois de salvar")
        self.assertEqual(self.console, [], f"erro de console: {self.console}")

    def test_erro_do_servidor_vai_para_a_dica_e_nao_destrai_o_formulario(self):
        pg = self.abrir()
        self.abrir_gaveta("shopee")
        pg.route("**/api/config", lambda r: r.fulfill(status=200, content_type="application/json",
                                                     body=json.dumps({"erro": "valor inválido"})))
        pg.click("#gavetaSalvar")
        pg.wait_for_timeout(1200)
        self.assertIn("inválido", pg.text_content("#gavetaDica"))
        self.assertFalse(pg.is_disabled("#gavetaSalvar"), "o botao ficou travado depois do erro")

    def test_telegram_some_do_formulario_generico(self):
        """O grupo que tem card proprio nao entra no formulario de
        Credenciais. Com os dois, salvar num apagaria o valor que o outro
        exibiu — e a pessoa so descobriria na proxima publicacao."""
        pg = self.abrir(hash="#config")
        nomes = pg.eval_on_selector_all("#formConfig input", "els => els.map(e => e.name)")
        for telegram in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID", "TELEGRAM_CHAT_ID"):
            self.assertNotIn(telegram, nomes, f"{telegram} duplicado no formulario")
        for outra in ("SHOPEE_APP_ID", "ML_COOKIE", "ALIEXPRESS_APP_KEY"):
            self.assertNotIn(outra, nomes, f"{outra} nao deveria estar no formulario generico")
        self.assertIn("XAI_API_KEY", nomes, "o que nao tem card precisa continuar no formulario")
        self.pagina.close()

        # ...e continua acessivel pela gaveta, que e o unico caminho agora.
        self.abrir(hash="#plataformas")
        g = self.abrir_gaveta("telegram")
        self.assertEqual([c["nome"] for c in g["campos"]],
                         ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID", "TELEGRAM_CHAT_ID"])

    def test_botao_configurar_do_dashboard_abre_a_gaveta(self):
        """O botao diz "Configurar". Levar a pessoa para outra aba antes de
        mostrar o campo e uma navegacao a mais para um cadastro de um
        campo so."""
        pg = self.abrir(hash="#dashboard")
        aba = pg.evaluate("() => document.querySelector('.view.ativa').id")
        pg.click("article.mp-card:has(#seloMl) button")
        pg.wait_for_timeout(600)
        self.assertTrue(self.gaveta_aberta())
        self.assertEqual(pg.text_content("#gavetaTitulo").strip(), "Mercado Livre")
        self.assertEqual(pg.evaluate("() => document.querySelector('.view.ativa').id"), aba,
                         "trocou de aba ao abrir a gaveta")


class TestConfiguracoes(TestAbaPlataformas):
    """A pagina de Configuracoes: seis cards soltos viraram quatro secoes,
    com barra no topo e aviso de alteracao nao salva.

    O que estes testes defendem nao e o desenho, e tres coisas que a pagina
   做到了 e que nao apareceriam em nenhum diff: os cards continuarem
    todos dentro de alguma secao, a barra continuar apontando para secoes
    que existem, e o estado "falta salvar" deixar de ser invisivel."""

    def abrir_config(self):
        return self.abrir(hash="#config")

    def test_todos_os_cards_ficam_dentro_de_alguma_secao(self):
        """A pagina empilhava seis cards sem grupo. Com as secoes, um card
        novo nasce dentro de uma - mas so enquanto alguem lembrar de
        colocar la dentro. Este teste e o que lembra por ele."""
        pg = self.abrir_config()
        m = pg.evaluate("""() => {
            const v = document.querySelector('#view-config');
            const cards = [...v.querySelectorAll('.card')];
            return {
                secoes: v.querySelectorAll('.config-secao').length,
                cards: cards.length,
                fora: cards.filter(c => !c.closest('.config-secao')).map(c => c.id || c.className),
            };
        }""")
        self.assertEqual(m["secoes"], 4, f"esperava 4 seções, achei {m['secoes']}")
        self.assertEqual(m["fora"], [], "cards fora de qualquer seção")
        self.assertGreaterEqual(m["cards"], 6,
                                f"só {m['cards']} cards na página: agrupar não pode "
                                "apagar nenhum dos seis")
        self.fechar()

    def test_a_barra_aponta_para_secoes_que_existem(self):
        """Um `href="#algo"` quebrado nao dá erro nenhum: o clique simplesmente
        nao move a pagina. Só a checagem do alvo pega isso."""
        pg = self.abrir_config()
        m = pg.evaluate("""() => {
            const links = [...document.querySelectorAll('#configNav a')];
            return {
                ids: [...document.querySelectorAll('#view-config .config-secao')].map(s => s.id),
                hrefs: links.map(a => a.getAttribute('href')),
                quebrados: links.map(a => a.getAttribute('href'))
                    .filter(h => !h.startsWith('#') || !document.querySelector(h)),
            };
        }""")
        self.assertEqual(m["hrefs"], ["#" + i for i in m["ids"]],
                         f"a barra aponta para {m['hrefs']} e as seções são {m['ids']}")
        self.assertEqual(m["quebrados"], [], "links da barra sem destino na página")
        self.fechar()

    def test_a_barra_gruda_no_topo_durante_a_rolagem(self):
        """Barra no topo que sai junto com a rolagem e enfeite. Sem
        `position: sticky` ela some na primeira rolagem, e o teste passa
        se a gente só conferir que ela existe no DOM."""
        pg = self.abrir_config()
        pg.evaluate("() => window.scrollTo(0, 900)")
        pg.wait_for_timeout(400)
        m = pg.evaluate("""() => {
            const n = document.querySelector('#configNav').getBoundingClientRect();
            return {top: Math.round(n.top), rolou: Math.round(window.scrollY),
                    visivel: n.bottom > 0 && n.top < window.innerHeight};
        }""")
        self.assertGreater(m["rolou"], 100,
                           f"a página não rolou (scrollY={m['rolou']}): o teste "
                           "não mediu nada")
        self.assertTrue(m["visivel"], "a barra de seções saiu da tela ao rolar")
        self.assertLessEqual(abs(m["top"]), 4,
                             f"a barra deveria estar grudada no topo, está em {m['top']}")
        self.fechar()

    def test_editar_credencial_marca_que_falta_salvar(self):
        """`configSuja` já era lido no JS desde antes - mas só para pular a
        repinta do formulário. O estado era mantido e nunca aparecia: dava
        para editar a chave, clicar em outro card e perder a alteração sem
        nenhum aviso."""
        pg = self.abrir_config()
        inicio = pg.evaluate(
            "() => document.querySelector('#configNav').classList.contains('sujo')")
        self.assertFalse(inicio, "a barra já começa marcando alteração pendente")

        pg.fill("#cfg_XAI_API_KEY", "xai-uma-chave-de-teste")
        pg.wait_for_timeout(300)
        durante = pg.evaluate("""() => {
            const chip = document.querySelector('#configPendente');
            return {sujo: document.querySelector('#configNav').classList.contains('sujo'),
                    visivel: getComputedStyle(chip).display !== 'none'
                             && chip.getBoundingClientRect().width > 0,
                    texto: chip.textContent.replace(/\\s+/g, ' ').trim()};
        }""")
        self.assertTrue(durante["sujo"],
                        "digitar na credencial não marcou a barra como pendente")
        self.assertTrue(durante["visivel"], "o aviso de 'falta salvar' não apareceu")
        self.assertIn("salvar", durante["texto"].lower())

        pg.click("#btnSalvarConfig")
        pg.wait_for_timeout(1000)
        depois = pg.evaluate("""() => ({
            sujo: document.querySelector('#configNav').classList.contains('sujo'),
            salvando: document.querySelector('#btnSalvarConfig').disabled,
        })""")
        self.assertFalse(depois["salvando"], "o botão ficou travado depois de salvar")
        self.assertFalse(depois["sujo"], "salvar não limpou o aviso de pendência")
        # O aviso some junto com o valor: o que prova que o salvamento
        # aconteceu de verdade é a chave ter chegado no servidor. E o botão
        # ter voltado é o que prova que o POST terminou - um erro de rede
        # deixaria os dois parados.
        self.assertEqual(RESPOSTAS["/api/config"].get("XAI_API_KEY"),
                         "xai-uma-chave-de-teste",
                         "a credencial editada não chegou ao servidor")
        self.fechar()

    def test_os_labels_usam_o_sprite_e_nao_emoji(self):
        """A docstring do proprio arquivo diz "nada de emoji, que muda de
        desenho conforme o sistema e não segue o tema" - e a página tinha
        treze. Setas e traços de texto não contam: o que se proíbe é o
        pictograma, não a pontuação."""
        pg = self.abrir_config()
        # A faixa vem do Python como texto, e não escrita aqui: escapada de
        # barra invertida dentro de três aspas é o jeito mais fácil de o
        # teste passar medindo outra coisa sem nenhum sinal.
        # U+2300-27BF e U+2B00-2BFF são os pictogramas; setas (U+2190-21FF)
        # e traços ficam de fora porque são tipografia, não desenho.
        m = pg.evaluate("""(pictograma) => {
            const v = document.querySelector('#view-config');
            const rx = new RegExp(pictograma, 'g');
            // Pelo id do próprio symbol, e não pelo do container: o sprite da
            // página é um <svg width="0"> sem id nenhum, apesar de o comentário
            // do arquivo falar em <svg id="icones">.
            const simbolos = new Set(
                [...document.querySelectorAll('symbol[id^="i-"]')].map(s => '#' + s.id));
            const uses = [...v.querySelectorAll(
                'label use, .config-secao-titulo use, #configNav use')];
            return {
                emojis: (v.textContent.match(rx) || []),
                icones: uses.length,
                quebrados: [...new Set(uses.map(u => u.getAttribute('href'))
                    .filter(h => !simbolos.has(h)))],
            };
        }""", r"[\u2300-\u27BF\u2B00-\u2BFF\u23E9-\u23FF\uFE0F]|[\uD83C-\uDBFF][\uDC00-\uDFFF]")
        self.assertEqual(m["emojis"], [], f"a página ainda tem emoji: {m['emojis']}")
        self.assertGreaterEqual(m["icones"], 12,
                                f"só {m['icones']} ícones: os labels perderam os seus")
        self.assertEqual(m["quebrados"], [],
                         f"ícones apontando para símbolo que não existe: {m['quebrados']}")
        self.fechar()

    # ── as duas colunas ──────────────────────────────────────────────
    def test_os_cards_de_cada_secao_ficam_lado_a_lado(self):
        """A aba Plataformas põe os cards lado a lado e a de Configurações
        empilhava os seis num scroll só. Medir os lados é o que prova: um
        `display: flex` no lugar da grade continuaria com todos os cards no
        DOM, continuaria com as quatro seções, e o teste de "todo card está
        em alguma seção" passaria sem dar nenhum sinal."""
        pg = self.abrir_config()
        m = pg.evaluate("""() => [...document.querySelectorAll('#view-config .config-secao')].map(s => {
            const box = e => { const b = e.getBoundingClientRect();
                               return {l: Math.round(b.left), r: Math.round(b.right),
                                       w: Math.round(b.width)}; };
            return {
                id: s.id,
                colunas: getComputedStyle(s).gridTemplateColumns.split(' ').length,
                titulo: box(s.querySelector('.config-secao-titulo')),
                cards: [...s.querySelectorAll(':scope > .card')].map(c => box(c)),
            };
        })""")
        self.assertEqual(len(m), 4, f"esperava 4 seções, achei {len(m)}")
        for s in m:
            self.assertEqual(s["colunas"], 2,
                             f"{s['id']} não está em duas colunas: {s['colunas']}")
            # O título atravessa a página inteira; se ele ficasse na primeira
            # coluna, o card da direita ficaria abaixo dele e a seção
            # pareceria um card só com um título torto.
            maisLargo = max(c["r"] for c in s["cards"])
            self.assertAlmostEqual(
                s["titulo"]["r"], maisLargo, delta=2,
                msg=f"em {s['id']} o título para em {s['titulo']['r']} mas o "
                    f"card mais à direita vai até {maisLargo}")
        # Nenhuma seção com dois cards pode deixá-los empilhados: o segundo
        # tem de estar à direita do primeiro, e não abaixo dele.
        for s in m:
            if len(s["cards"]) != 2:
                continue
            (a, b) = s["cards"]
            self.assertGreater(b["l"], a["l"] + a["w"] - 2,
                               f"em {s['id']} os dois cards estão empilhados: "
                               f"o segundo começa em {b['l']}, o primeiro termina em {a['r']}")
        self.fechar()

    def test_a_tabela_de_fontes_ocupa_a_linha_inteira(self):
        """A tabela tem cinco colunas de dados. Espremida em meia largura ela
        vira um garrancho ilegível, e o `config-largo` é o que a devolve à
        linha inteira. Um card por linha, sem medir, não pega isso."""
        pg = self.abrir_config()
        m = pg.evaluate("""() => {
            const t = document.querySelector('#cardFontesTelegram .tabela');
            const c = document.querySelector('#cardFontesTelegram');
            const s = document.querySelector('#sec-fontes');
            const meia = (s.querySelector(':scope > .card:not(.config-largo)')).getBoundingClientRect();
            return {largura: Math.round(t.getBoundingClientRect().width),
                    card: Math.round(c.getBoundingClientRect().width),
                    meia: Math.round(meia.width),
                    colunas: t.querySelectorAll('thead th').length};
        }""")
        self.assertEqual(m["colunas"], 5, "a tabela perdeu colunas")
        self.assertGreater(m["largura"], m["meia"] * 1.5,
                           f"a tabela tem {m['largura']}px e um card de meia linha "
                           f"tem {m['meia']}px: ela espremeu na coluna")
        self.fechar()

    # ── a cadência que o bot realmente usa ──────────────────────────
    def test_a_cadencia_mostra_o_bloco_geral_e_nao_o_publicacao(self):
        """O card de cadência é o bloco `geral` do config.yaml — o intervalo do
        job, quantas ofertas o ciclo escolhe, o sleep entre elas, a janela de
        deduplicação e o portão de horário. O card ao lado é o bloco
        `publicacao`, que está zerado e não muda nada no bot.

        O stub devolve 90 s de espaçamento e 5 dias, e o HTML traz 120 e 7
        embutidos. Divergir de propósito é o que prova que o valor veio do
        servidor: se batesse, o teste passaria com `carregarCadencia` nunca
        sendo chamada, porque o campo já nasceria preenchido."""
        pg = self.abrir_config()
        m = pg.evaluate("""() => ({
            cad: {
                campos: document.querySelectorAll('#formCadencia .campo').length,
                intervalo: (document.querySelector('#cadIntervalo') || {}).value,
                maxCiclo: (document.querySelector('#cadMaxPosts') || {}).value,
                espacamento: (document.querySelector('#cadEspacamento') || {}).value,
                naoRepetir: (document.querySelector('#cadNaoRepetir') || {}).value,
            },
            publico: {
                intervalo: (document.querySelector('#pubIntervalo') || {}).value,
                maxPeriodo: (document.querySelector('#pubMaxPosts') || {}).value,
            },
        })""")
        self.assertEqual(m["cad"]["campos"], 5,
                         f"o card de cadência tem {m['cad']['campos']} campos, "
                         "esperava os 5 do bloco geral")
        self.assertEqual(m["cad"]["intervalo"], "45",
                         "o intervalo entre ciclos não veio do servidor")
        self.assertEqual(m["cad"]["maxCiclo"], "3", "máximo por ciclo não veio do servidor")
        # 90 e 5, não os 120 e 7 que o HTML traz embutido: é a divergência
        # proposital do stub que transforma este teste em prova de leitura.
        self.assertEqual(m["cad"]["espacamento"], "90",
                         f"o espaçamento ficou {m['cad']['espacamento']}: veio do "
                         "HTML em vez do servidor (o stub manda 90)")
        self.assertEqual(m["cad"]["naoRepetir"], "5",
                         f"a janela de não repetir ficou {m['cad']['naoRepetir']}: "
                         "veio do HTML em vez do servidor (o stub manda 5)")
        # Os dois cards precisam ser diferentes, senão um deles é o outro.
        self.assertNotEqual(m["cad"]["intervalo"], m["publico"]["intervalo"],
                            "cadência e blocos/pausas mostram o mesmo número: "
                            "um dos dois cards está no lugar errado")
        self.fechar()

    def test_salvar_a_cadencia_chega_ao_servidor(self):
        """O bloco `geral` não tinha rota que gravasse: era lido em todo
        lugar e ajustável em lugar nenhum. Só o POST prova que a tecla
        escreve onde o bot lê — o botão responder "ok" sem o valor chegar
        seria exatamente o defeito antigo."""
        # Todos os cinco valores digitados sao diferentes do que o servidor
        # tinha: se algum fosse igual, a assercao passaria mesmo sem o POST.
        pg = self.abrir_config()
        pg.fill("#cadIntervalo", "20")
        pg.fill("#cadMaxPosts", "5")
        pg.fill("#cadEspacamento", "150")
        pg.fill("#cadNaoRepetir", "3")
        pg.fill("#cadHorario", "08:00-23:00")
        pg.click("#cardCadencia .acoes-form button")
        pg.wait_for_timeout(900)
        enviado = RESPOSTAS["/api/cadencia"]
        # Os quatro numéricos vão como número (a tela manda parseInt e o
        # backend faz int() de qualquer jeito); a janela de horário é texto.
        for chave, valor in (("intervalo_minutos", 20), ("max_posts_por_ciclo", 5),
                             ("espacamento_segundos", 150), ("nao_repetir_dias", 3),
                             ("horario_ativo", "08:00-23:00")):
            self.assertEqual(enviado.get(chave), valor,
                             f"{chave} não chegou ao servidor: {enviado.get(chave)!r}")
        self.fechar()

    def test_o_polling_de_cinco_segundos_nao_apaga_a_cadencia_digitada(self):
        """O card ao lado é repintado a cada 5s e, se alguém copiar o mesmo
        tratamento para o card de cadência, o que a pessoa estiver digitando
        desaparece no meio da frase. Esperar o intervalo de verdade é o que
        pega isso; conferir o `setInterval` no código não pegaria."""
        pg = self.abrir_config()
        pg.click("#cadIntervalo")
        pg.fill("#cadIntervalo", "77")
        pg.wait_for_timeout(5600)
        self.assertEqual(
            pg.input_value("#cadIntervalo"), "77",
            "o valor digitado foi apagado pelo repaint automático: quem digita "
            "perde o que escreveu no meio da frase")
        self.fechar()


if __name__ == "__main__":
    unittest.main()
