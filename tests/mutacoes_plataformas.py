"""Valida os testes da aba Plataformas por mutacao.

Cada mutacao abaixo e uma troca que a tela continuaria abrindo, o console
continuaria limpo e o servidor continuaria respondendo — e mesmo assim
estaria errada. E por isso que elas existem: uma verificacao que so
contaria `<input>` no HTML passaria com quase toda esta lista de fora.

A mutacao que mais importa e a (h): trocar o corpo do POST por tudo que a
pagina sabe. O servidor ignora o que nao veio, entao enviar o CFG inteiro
sobrescreveria a senha das outras plataformas com string vazia. E o tipo de
defeito que ninguem percebe ate a proxima publicacao sair sem link.
"""
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ARQ = Path("ofertas/painel_html.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")
ORFAO = Path("ofertas/painel_html.py.bak_mutacao")

# Arquivos de que o teste realmente precisa. Ele sobe o proprio servidor efemero
# em porta 0, entao nenhuma copia depende do .env, do config.yaml ou do data/.
# Por isso da para mutar em sandbox descartavel, sem tocar na arvore do projeto.
ARQUIVOS = ("ofertas/__init__.py", "ofertas/painel_html.py", "tests/test_plataformas_ui.py")
N_WORKERS = 4

MUTACOES = [
    (
        "gaveta perde o alinhamento a direita (especificidade do overlay)",
        "  .overlay.overlay-gaveta { place-items: stretch end; padding: 0; }",
        "  .overlay-gaveta { place-items: stretch end; padding: 0; }",
    ),
    (
        "mercado livre perde o estado 'sessao ativa, falta a etiqueta'",
        '      if (m.sessao_ativa) return ["erro", "Sessão ativa, falta a etiqueta"];\n',
        "",
    ),
    (
        "a lista do que falta volta a juntar tudo com ' e '",
        '      return "Falta " + (f.length === 1 ? f[0]\n'
        '        : f.slice(0, -1).join(", ") + " e " + f[f.length - 1]);',
        '      return "Falta " + f.join(" e ");',
    ),
    (
        "a repinta do /api/config passa a apagar o campo em edicao",
        "  return !!a && !!a.closest && !!a.closest(\"#gavetaCampos\") && a.tagName === \"INPUT\";",
        "  return false;",
    ),
    (
        "salvar deixa de repintar os inputs, e a marca 'definido' some",
        "    pintarCamposGaveta(chave);\n    dica.className = \"plato-dica ok\";",
        "    dica.className = \"plato-dica ok\";",
    ),
    (
        "os grupos de plataforma saem do formulario generico de novo",
        "  return new Set(BLOCOS.map(b => b.grupo));",
        "  return new Set();",
    ),
    (
        "salvar passa a mandar o CFG inteiro em vez dos campos da gaveta",
        "  $$(\"input\", form).forEach(el => { body[el.name] = el.value.trim(); });",
        "  Object.assign(body, CFG);",
    ),
    (
        "a gaveta para de ser marcada como dialogo modal",
        'role="dialog" aria-modal="true"\n         aria-labelledby="gavetaTitulo"',
        'role="group" aria-modal="false"\n         aria-labelledby="gavetaTitulo"',
    ),
    (
        "fechar a gaveta para de fechar",
        '  if (m && m.classList.contains("aberto")) fecharModal("gavetaPlataforma");',
        "  void m;",
    ),
    (
        "o selo de tres estados vira sempre 'conectado'",
        '  el.className = "selo selo-" + classe;',
        '  el.className = "selo selo-ok"; void classe;',
    ),
    (
        "o card do telegram fica sem nenhuma marca",
        ': icone("send", "plato-logo-img plato-logo-glyph")}',
        '"}',
    ),
    (
        "um card a mais na grade, para uma integracao que nao existe",
        '    chave: "telegram", nome: "Telegram", grupo: "Telegram",',
        '    chave: "tiktok", nome: "TikTok Shop", grupo: "Telegram",\n'
        '    cor: "var(--primaria-texto)", logo: "", sub: "Em breve",\n'
        '    resumoDe: () => "Em breve", estadoDe: () => ["neutro", "Desconectado"],\n'
        '    acoes: [],},\n'
        '    chave: "telegram", nome: "Telegram", grupo: "Telegram",',
    ),
    (
        "o status do servidor e cortado numa linha so",
        "  .plato-linha > span {\n    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;\n"
        "    overflow: hidden; overflow-wrap: anywhere;\n  }",
        "  .plato-linha > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
    ),
    (
        "o status do servidor deixa de ser o que o /api/status mandou",
        "    resumoDe: p => (p.amazon || {}).status || \"Não configurado\",",
        "    resumoDe: p => (p.amazon || {}).api_ativa ? \"Creators API ativa\" : \"Busca por scraping\",",
    ),
    (
        "a situacao da gaveta para de acompanhar o polling",
        "  // tem o guard de digitação e não pode ser atropelado por aqui.\n  pintarSituacaoGaveta();",
        "  // tem o guard de digitação e não pode ser atropelado por aqui.",
    ),
    (
        "a deteccao de ids volta a cair na aba Configuracoes",
        "detectarIds('#gavetaDeteccao', true)",
        "detectarIds()",
    ),
    (
        "escolher um id detectado para de preencher o campo da gaveta",
        '  const el = naGaveta ? $("#gav_" + campo) : $("#cfg_" + campo);',
        '  const el = $("#cfg_" + campo);',
    ),
    # ── Configurações ────────────────────────────────────────────────────
    (
        "a barra de secoes deixa de grudar no topo da pagina",
        "  .config-nav {\n    position: sticky; top: 0; z-index: 6;",
        "  .config-nav {\n    z-index: 6;",
    ),
    (
        "o aviso de 'falta salvar' deixa de aparecer",
        '  $("#formConfig").addEventListener("input", () => { configSuja = true; marcarConfigSuja(true); });',
        '  $("#formConfig").addEventListener("input", () => { configSuja = true; });',
    ),
    (
        "um link da barra aponta para uma secao que nao existe",
        '<a href="#sec-cadencia">',
        '<a href="#sec-cadência">',
    ),
    (
        "um emoji volta para um label",
        '<label for="filtroAvaliacao"><svg class="icone-sm" aria-hidden="true"><use href="#i-award"/></svg>Avaliação mínima</label>',
        '<label for="filtroAvaliacao">⭐ Avaliação mínima</label>',
    ),
    (
        "um card fica fora de qualquer secao",
        '<section class="config-secao" id="sec-cadencia"',
        '<section class="config-secao-perdida" id="sec-cadencia"',
    ),
    # ── as duas colunas ───────────────────────────────────────────────────
    #
    # Estas três são o grupo mais perigoso da lista, porque nenhuma delas
    # tira um elemento do DOM: os cards continuam lá, continuam dentro das
    # quatro seções, e o teste que verifica "todo card está em alguma seção"
    # continua passando sem dar um sinal. Só quem mede o lado na tela percebe.
    (
        "as secoes voltam a empilhar os cards um embaixo do outro",
        "  .config-secao {\n    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));\n    gap: 22px 24px; scroll-margin-top: 74px;\n  }",
        "  .config-secao {\n    display: flex; flex-direction: column; gap: 22px; scroll-margin-top: 74px;\n  }",
    ),
    (
        "o titulo da secao deixa de atravessar a pagina inteira",
        "  .config-secao-titulo {\n    grid-column: 1 / -1;",
        "  .config-secao-titulo {\n    grid-column: 1;",
    ),
    (
        "a tabela de fontes deixa de ocupar a linha inteira",
        "  .config-largo { grid-column: 1 / -1; }",
        "  .config-largo { }",
    ),
    # ── a cadência que o bot realmente usa ───────────────────────────────
    (
        "a tela para de ler a cadencia do servidor e fica no que esta no HTML",
        "  carregarFiltros();\n  carregarCadencia();",
        "  carregarFiltros();",
    ),
    (
        "o card de cadencia some da pagina",
        '      <div class="card" id="cardCadencia">',
        '      <div class="card-perdida" id="cardCadencia">',
    ),
    (
        "salvar a cadencia passa a postar na rota do bloco zerado",
        '    const r = await fetch("/api/cadencia", {\n      method: "POST",',
        '    const r = await fetch("/api/publicacao-controle", {\n      method: "POST",',
    ),
    (
        "a cadencia entra no repaint de 5s e apaga o que esta sendo digitado",
        "  setInterval(carregarPublicacao, 5000);",
        "  setInterval(carregarPublicacao, 5000);\n  setInterval(carregarCadencia, 5000);",
    ),
]


def preparar(base: Path) -> Path:
    """Copia o minimo necessario para um sandbox isolado."""
    sandbox = Path(tempfile.mkdtemp(prefix="w", dir=base))
    for rel in ARQUIVOS:
        destino = sandbox / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rel, destino)
    return sandbox


def rodar(sandbox: Path):
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_plataformas_ui"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(sandbox),
    )
    return proc.returncode, proc.stdout + proc.stderr


def primeiro_falha(saida: str) -> str:
    for linha in saida.splitlines():
        if linha.startswith(("FAIL:", "ERROR:")):
            return linha.split(" (")[0]
    return "?"


def worker(base: Path, fila):
    sandbox = preparar(base)
    alvo = sandbox / "ofertas" / "painel_html.py"
    resultados = []
    try:
        for nome, antes, depois in fila:
            alvo.write_text(ORIGINAL.replace(antes, depois, 1), encoding="utf-8")
            code, saida = rodar(sandbox)
            alvo.write_text(ORIGINAL, encoding="utf-8")
            achou = primeiro_falha(saida) if code != 0 else ""
            print(f"[{'ok   ' if code != 0 else 'FALHOU'}] {nome}", flush=True)
            if code != 0:
                print(f"          por {achou}", flush=True)
            resultados.append((nome, code != 0, achou))
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    return resultados


def main():
    # Auto-recuperacao: se uma execucao anterior morreu no meio de uma mutacao,
    # o `finally` nao rodou e o arquivo ficou quebrado. O backup orfao e o estado
    # bom, entao se restaura antes de qualquer outra coisa.
    if ORFAO.exists():
        shutil.copy2(ORFAO, ARQ)
        ORFAO.unlink()
        print(f"backup orfao restaurado em {ARQ}", flush=True)

    faltando = [n for n, a, _ in MUTACOES if a not in ORIGINAL]
    if faltando:
        for nome in faltando:
            print(f"[ERRO] anchor nao encontrado: {nome}", flush=True)
        return 2
    if ARQ.read_text(encoding="utf-8") != ORIGINAL:
        print("[ERRO] painel_html.py mudou durante a execucao; abortando", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutplat-"))
    try:
        primeiro = preparar(base)
        try:
            code, saida = rodar(primeiro)
        finally:
            shutil.rmtree(primeiro, ignore_errors=True)
        print(f"[base] codigo={code} -> {'PASSOU' if code == 0 else 'JA FALHA'}", flush=True)
        if code != 0:
            print(saida[-3000:], flush=True)
            return 1

        # Reparte as mutacoes entre os workers. Cada um tem o seu sandbox e a
        # porta efemera e diferente, entao as-suite roda em paralelo de verdade.
        n = min(N_WORKERS, len(MUTACOES))
        filas = [MUTACOES[i::n] for i in range(n)]
        print(f"rodando {len(MUTACOES)} mutacoes em {n} workers", flush=True)

        coletados = []
        with ThreadPoolExecutor(max_workers=n) as pool:
            for parte in pool.map(lambda f: worker(base, f), filas):
                coletados.extend(parte)

        por_nome = {nome: (achou, por) for nome, achou, por in coletados}
        print()
        falhas = 0
        for nome, _, _ in MUTACOES:
            if nome not in por_nome:
                print(f"[FALHOU] {nome}  (worker morreu antes de rodar)")
                falhas += 1
            elif not por_nome[nome][0]:
                print(f"[FALHOU] {nome}  (nenhum teste notou a mudanca)")
                falhas += 1
        if len(coletados) != len(MUTACOES):
            print(f"[ERRO] rodaram {len(coletados)} de {len(MUTACOES)}")
            falhas += 1

        print()
        print(f"mutacoes nao detectadas: {falhas} de {len(MUTACOES)}")
        return 1 if falhas else 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
