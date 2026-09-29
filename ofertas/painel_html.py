"""Interface web do painel Ofertas Pro (servida localmente por painel.py).

Uma página só, sem build e sem CDN: a fonte cai para a system-ui se o
computador estiver sem internet. Ícones são SVG inline (ver <svg id="icones">)
— nada de emoji, que muda de desenho conforme o sistema e não segue o tema.
"""
PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Ofertas Pro — Painel de Afiliados</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23087BFF'/%3E%3Cpath d='M16 6l7 5v10l-7 5-7-5V11z' fill='none' stroke='%23fff' stroke-width='2' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  /* ══ Tokens ══════════════════════════════════════════════════════════
     Paleta alinhada ao painel em produção (193.123.112.175:8481): fundo
     azul-marinho quase preto, cards um tom acima, azul de marca #1a68ff
     e as mesmas fontes (Plus Jakarta Sans + JetBrains Mono).

     Três tons saem do valor de origem de propósito, por contraste:
     - --primaria-solida-hover escurece (o #2975ff do deploy daria 4,1:1
       com texto branco, abaixo de 4,5:1);
     - --primaria-texto clareia (#1a68ff sobre card dá 3,8:1);
     - as cores de plataforma são versões claras das de origem, porque
       os glifos da marca ficam sobre um fundo escuro. */
  :root {
    color-scheme: dark;

    --fundo:          #070D1D;
    --fundo-sidebar:  #081024;
    --fundo-card:     #0D1730;   /* base dos contrastes abaixo */
    --fundo-card-hi:  #0F1D3D;
    --fundo-sub:      #0A1227;
    --fundo-inset:    #0A1227;
    --card-hover:     #122246;

    --borda:          rgba(37, 99, 235, 0.24);
    --borda-forte:    rgba(37, 99, 235, 0.42);
    --borda-sutil:    rgba(255, 255, 255, 0.07);

    --texto:          #FFFFFF;
    --texto-2:        #CBD5E1;   /* secundário — 12,0:1 no card */
    --texto-3:        #8294B0;   /* terciário  —  5,8:1 no card */

    --primaria:       #1A68FF;   /* anéis, bordas, gráficos  */
    --primaria-forte: #2975FF;   /* brilhos e acentos, sem texto */
    --primaria-solida:        #1A68FF;        /* branco 4,7:1 */
    --primaria-solida-hover:  #1557D6;        /* branco 6,2:1 */
    --primaria-fundo: rgba(26, 104, 255, 0.14);
    --primaria-borda: rgba(26, 104, 255, 0.45);
    --primaria-texto: #6BA5FF;  /* links sobre card — 7,1:1 */

    --ok:             #10B981;   /* 7,0:1 no card */
    --ok-fundo:       rgba(16, 185, 129, 0.13);
    --ok-borda:       rgba(16, 185, 129, 0.32);
    --alerta:         #F59E0B;   /* 8,3:1 no card */
    --alerta-fundo:   rgba(245, 158, 11, 0.13);
    --alerta-borda:   rgba(245, 158, 11, 0.32);
    --erro:           #EF4444;   /* 4,7:1 no card */
    --erro-fundo:     rgba(239, 68, 68, 0.13);
    --erro-borda:     rgba(239, 68, 68, 0.36);

    /* Original do deploy: ml #2563eb / amz #ff9900 / shp #ee4d2d /
       ali #ff4747 / prm #8b5cf6. Clareadas para os glifos sobre fundo
       escuro — conferidas por medição, não no olho. */
    --e1: #60A5FA; --e2: #F0A93B; --e3: #F26A4D; --e4: #A78BFA;
    --mut: #4B5D78;  /* só bordas e elementos decorativos: 2,7:1 */

    --fonte: 'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --mono:  'JetBrains Mono', ui-monospace, 'Cascadia Mono', Consolas, monospace;

    --r-sm: 8px; --r-md: 12px; --r-lg: 16px; --r-full: 9999px;

    --sombra-1: 0 1px 2px rgba(2, 6, 18, 0.5);
    --sombra-2: 0 10px 30px -10px rgba(0, 0, 0, 0.7);
    --sombra-3: 0 24px 60px -12px rgba(0, 0, 0, 0.8);
    --anel: 0 0 0 3px rgba(26, 104, 255, 0.45);

    --z-base: 1; --z-sticky: 20; --z-overlay: 100; --z-toast: 200;

    --t-rapida: 130ms; --t-media: 200ms; --t-lenta: 320ms;
    --ease: cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* ══ Base ═══════════════════════════════════════════════════════════ */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html { scroll-behavior: smooth; }

  body {
    min-height: 100vh;
    background-color: var(--fundo);
    background-image:
      radial-gradient(900px 480px at 12% -8%, rgba(26, 104, 255, 0.16), transparent 62%),
      radial-gradient(760px 420px at 92% 104%, rgba(16, 185, 129, 0.07), transparent 60%);
    background-attachment: fixed;
    color: var(--texto);
    font: 400 14px/1.55 var(--fonte);
    display: flex;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
  }

  ::-webkit-scrollbar { width: 9px; height: 9px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--borda); border-radius: var(--r-full); }
  ::-webkit-scrollbar-thumb:hover { background: var(--borda-forte); }

  /* Foco visível em TUDO que é clicável — antes não havia nenhum. */
  :where(a, button, input, select, textarea, [tabindex]):focus-visible {
    outline: 2px solid var(--primaria-forte);
    outline-offset: 2px;
    border-radius: var(--r-sm);
  }
  :where(button, a, input, select, .nicho, [role="button"]):focus:not(:focus-visible) { outline: none; }

  .pular-para-conteudo {
    position: absolute; left: 8px; top: -80px; z-index: var(--z-toast);
    background: var(--primaria-solida); color: #fff; padding: 10px 18px;
    border-radius: var(--r-sm); font-weight: 700; text-decoration: none;
    transition: top var(--t-media) var(--ease);
  }
  .pular-para-conteudo:focus { top: 8px; }

  .so-leitor {
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
  }

  .icone { width: 18px; height: 18px; flex: none; stroke: currentColor; }
  .icone-sm { width: 15px; height: 15px; }
  .icone-lg { width: 22px; height: 22px; }
  .icone-xl { width: 26px; height: 26px; }

  /* ══ Estrutura ══════════════════════════════════════════════════════ */
  .app-layout { display: flex; width: 100%; min-height: 100vh; }

  /* ── Sidebar ── */
  .sidebar {
    width: 236px; flex: none;
    background: var(--fundo-sidebar);
    border-right: 1px solid var(--borda-sutil);
    display: flex; flex-direction: column;
    padding: 20px 12px 16px;
    position: sticky; top: 0; height: 100vh;
    z-index: var(--z-sticky);
  }

  .brand {
    display: flex; align-items: center; gap: 11px;
    padding: 0 8px 22px; text-decoration: none; border-radius: var(--r-md);
  }
  .brand-icone {
    width: 36px; height: 36px; border-radius: var(--r-md); flex: none;
    background: linear-gradient(145deg, #1E90FF, #0A5BC7);
    display: grid; place-items: center; color: #fff;
    box-shadow: 0 4px 16px rgba(26, 104, 255, 0.45), inset 0 1px 0 rgba(255,255,255,0.25);
  }
  .brand-texto h1 {
    font-size: 15.5px; font-weight: 800; letter-spacing: -0.35px;
    line-height: 1.15; color: var(--texto);
  }
  .brand-texto span { font-size: 11px; font-weight: 500; color: var(--texto-3); }

  .nav-menu { display: flex; flex-direction: column; gap: 2px; list-style: none; }
  .nav-item {
    display: flex; align-items: center; gap: 11px;
    padding: 9px 12px; min-height: 40px;
    border-radius: var(--r-sm); border: 1px solid transparent;
    color: var(--texto-2); text-decoration: none;
    font-size: 13.5px; font-weight: 600; cursor: pointer;
    transition: background var(--t-rapida) var(--ease),
                color var(--t-rapida) var(--ease),
                border-color var(--t-rapida) var(--ease);
  }
  .nav-item:hover { background: rgba(255, 255, 255, 0.05); color: var(--texto); }
  .nav-item[aria-current="page"] {
    background: var(--primaria-fundo); color: #fff;
    border-color: var(--primaria-borda);
  }
  .nav-item[aria-current="page"] .icone { color: var(--primaria-forte); }
  .nav-badge {
    margin-left: auto; font-size: 11px; font-weight: 700;
    min-width: 22px; text-align: center;
    padding: 1px 7px; border-radius: var(--r-full);
    background: var(--fundo-sub); color: var(--texto-3);
    border: 1px solid var(--borda-sutil); font-variant-numeric: tabular-nums;
  }
  .nav-item[aria-current="page"] .nav-badge {
    background: var(--primaria); color: #fff; border-color: transparent;
  }

  .sidebar-rodape { margin-top: auto; }

  .bot-cartao {
    display: flex; align-items: center; gap: 10px; width: 100%;
    margin-top: 14px; padding: 11px 12px; min-height: 56px;
    background: var(--fundo-card); border: 1px solid var(--borda);
    border-radius: var(--r-md); cursor: pointer; text-align: left;
    font: inherit; color: inherit;
    transition: border-color var(--t-media) var(--ease),
                background var(--t-media) var(--ease),
                transform var(--t-rapida) var(--ease);
  }
  .bot-cartao:hover { border-color: var(--borda-forte); background: var(--fundo-card-hi); }
  .bot-cartao:active { transform: scale(0.985); }
  .ponto {
    width: 8px; height: 8px; border-radius: 50%; flex: none;
    background: var(--texto-3); transition: background var(--t-media) var(--ease);
  }
  .ponto.ativo { background: var(--ok); box-shadow: 0 0 0 3px var(--ok-fundo); }
  .ponto.ocupado { background: var(--alerta); box-shadow: 0 0 0 3px var(--alerta-fundo); }
  .ponto.erro { background: var(--erro); box-shadow: 0 0 0 3px var(--erro-fundo); }
  .bot-cartao-texto { flex: 1; min-width: 0; line-height: 1.25; }
  .bot-cartao-texto b { display: block; font-size: 13px; font-weight: 700; }
  .bot-cartao-texto small {
    display: block; font-size: 11px; color: var(--texto-3);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .bot-cartao .icone { color: var(--texto-3); }

  .sidebar-nota { padding: 14px 8px 0; font-size: 11px; color: var(--texto-3); line-height: 1.5; }
  .sidebar-nota strong { color: var(--texto-2); font-weight: 600; }

  /* ── Coluna principal ── */
  .main-wrapper { flex: 1; min-width: 0; display: flex; flex-direction: column; }

  .top-header {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 24px; flex-wrap: wrap;
    padding: 22px 32px 14px;
  }
  .saudacao h2 {
    font-size: 24px; font-weight: 800; letter-spacing: -0.6px; line-height: 1.18;
    display: flex; align-items: center; gap: 9px;
  }
  .saudacao h2 .icone { color: var(--primaria-forte); }
  .saudacao p { font-size: 13px; color: var(--texto-2); margin-top: 5px; max-width: 60ch; }

  .header-acoes { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }

  .status-pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 5px 12px 5px 10px; min-height: 32px;
    font-size: 12.5px; font-weight: 600; color: var(--texto-2);
    background: var(--fundo-card); border: 1px solid var(--borda);
    border-radius: var(--r-full);
  }
  .status-pill[data-ligado="1"] { color: var(--ok); border-color: var(--ok-borda); background: var(--ok-fundo); }

  .relogio { text-align: right; line-height: 1.3; }
  .relogio .hora {
    font: 700 15px/1.2 var(--mono); color: var(--texto);
    font-variant-numeric: tabular-nums; letter-spacing: -0.3px;
  }
  .relogio .data { font-size: 11px; color: var(--texto-3); font-variant-numeric: tabular-nums; }

  .perfil { display: flex; align-items: center; gap: 10px; padding-left: 14px; border-left: 1px solid var(--borda-sutil); }
  .avatar {
    width: 34px; height: 34px; border-radius: var(--r-md); flex: none;
    background: linear-gradient(145deg, #12456F, #0B2B48);
    border: 1px solid var(--borda);
    display: grid; place-items: center; color: #9CC9FF;
  }
  .perfil-texto { line-height: 1.25; }
  .perfil-texto b { display: block; font-size: 13px; font-weight: 700; }
  .perfil-texto small { font-size: 11px; color: var(--texto-3); }

  /* ══ Botões ════════════════════════════════════════════════════════ */
  .btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    padding: 9px 15px; min-height: 40px;
    font-family: inherit; font-size: 13.5px; font-weight: 600; line-height: 1.2;
    border-radius: var(--r-sm); border: 1px solid transparent;
    cursor: pointer; text-decoration: none; white-space: nowrap;
    transition: background var(--t-rapida) var(--ease),
                border-color var(--t-rapida) var(--ease),
                color var(--t-rapida) var(--ease),
                transform var(--t-rapida) var(--ease),
                box-shadow var(--t-rapida) var(--ease);
  }
  .btn:active:not(:disabled) { transform: translateY(1px); }
  .btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .btn-primario {
    background: var(--primaria-solida); color: #fff; border-color: rgba(255,255,255,0.18);
    font-weight: 700; box-shadow: 0 2px 12px rgba(10, 110, 219, 0.40);
  }
  .btn-primario:hover:not(:disabled) {
    background: var(--primaria-solida-hover);
    box-shadow: 0 4px 18px rgba(26, 104, 255, 0.48);
  }
  .btn-neutro {
    background: var(--fundo-card); color: var(--texto-2);
    border-color: var(--borda); font-weight: 600;
  }
  .btn-neutro:hover:not(:disabled) { background: var(--fundo-card-hi); color: var(--texto); border-color: var(--borda-forte); }
  .btn-perigo {
    background: transparent; color: var(--erro); border-color: var(--erro-borda);
    font-weight: 600;
  }
  .btn-perigo:hover:not(:disabled) { background: var(--erro-fundo); border-color: var(--erro); }
  .btn-fantasma {
    background: transparent; color: var(--primaria-texto);
    border-color: transparent; font-weight: 600; min-height: 36px; padding: 6px 12px;
  }
  .btn-fantasma:hover:not(:disabled) { background: var(--primaria-fundo); }
  .btn-sm { font-size: 12.5px; padding: 7px 12px; min-height: 36px; }
  .btn-bloco { width: 100%; }

  /* Botão só de ícone — 40px, alvo confortável mesmo com glifo pequeno. */
  .btn-icone {
    padding: 0; width: 40px; height: 40px; min-height: 40px; flex: none;
    background: transparent; color: var(--texto-3);
    border-color: transparent; border-radius: var(--r-sm);
  }
  .btn-icone:hover:not(:disabled) { background: rgba(255, 255, 255, 0.08); color: var(--texto); }

  .girando { animation: girar 900ms linear infinite; }
  @keyframes girar { to { transform: rotate(360deg); } }

  /* ══ Cartões e grades ══════════════════════════════════════════════ */
  .view {
    display: none;
    flex: 1;
    flex-direction: column;
    gap: 22px;
    padding: 18px 32px 32px;
  }
  .view.ativa { display: flex; animation: entrar var(--t-media) var(--ease); }
  @keyframes entrar { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }

  .card {
    background: var(--fundo-card);
    border: 1px solid var(--borda);
    border-radius: var(--r-lg);
    padding: 20px 22px;
    box-shadow: var(--sombra-2);
  }
  .card-titulo { display: flex; align-items: center; gap: 9px; }
  .card-titulo .icone { color: var(--primaria-forte); }
  .card-titulo h3 { font-size: 15.5px; font-weight: 700; letter-spacing: -0.2px; }
  .card-titulo h4 { font-size: 14px; font-weight: 700; }
  .card-sub { font-size: 12.5px; color: var(--texto-2); margin-top: 5px; }
  .card-topo {
    display: flex; align-items: center; justify-content: space-between;
    gap: 14px; flex-wrap: wrap; margin-bottom: 14px;
  }

  .grade-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .grade-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

  /* ══ Cartões de marketplace ════════════════════════════════════════ */
  .mp-card {
    background: var(--fundo-card); border: 1px solid var(--borda);
    border-radius: var(--r-lg); padding: 18px 16px;
    display: flex; flex-direction: column; align-items: center; text-align: center;
    gap: 8px; box-shadow: var(--sombra-1);
    transition: transform var(--t-media) var(--ease), border-color var(--t-media) var(--ease);
  }
  .mp-card:hover { transform: translateY(-2px); border-color: var(--borda-forte); }
  .mp-icone {
    width: 44px; height: 44px; border-radius: var(--r-md);
    display: grid; place-items: center; color: #fff;
  }
  .mp-icone.ml { background: var(--e1); }
  .mp-icone.amz { background: var(--e2); color: #241701; }
  .mp-icone.shp { background: var(--e3); }
  .mp-icone.ali { background: var(--e4); }
  .mp-card h4 { font-size: 14.5px; font-weight: 700; }
  .mp-sub { font-size: 12px; color: var(--texto-3); min-height: 17px; }
  .mp-card .btn { width: 100%; margin-top: auto; }

  /* Logos das plataformas */
  .mp-logo-caixa {
    width: 48px; height: 48px; border-radius: var(--r-md);
    display: grid; place-items: center; overflow: hidden;
    background: var(--fundo-card-hi); border: 1px solid var(--borda);
    box-shadow: var(--sombra-1); flex: none;
  }
  .mp-logo-img {
    width: 100%; height: 100%; object-fit: cover; display: block;
  }
  .top-logo-caixa {
    width: 22px; height: 22px; border-radius: 6px; overflow: hidden;
    background: var(--fundo-card-hi); display: grid; place-items: center; flex: none;
    border: 1px solid var(--borda-sutil);
  }
  .top-logo-img {
    width: 100%; height: 100%; object-fit: cover; display: block;
  }
  .ativ-logo-caixa {
    width: 32px; height: 32px; border-radius: var(--r-sm); overflow: hidden;
    background: var(--fundo-card-hi); display: grid; place-items: center; flex: none;
    border: 1px solid var(--borda-sutil); box-shadow: var(--sombra-1);
  }
  .ativ-logo-img {
    width: 100%; height: 100%; object-fit: cover; display: block;
  }
  .tab-logo-caixa {
    width: 20px; height: 20px; border-radius: 4px; overflow: hidden;
    background: var(--fundo-card-hi); display: inline-grid; place-items: center;
    vertical-align: middle; border: 1px solid var(--borda-sutil); margin-right: 4px;
  }
  .tab-logo-img {
    width: 100%; height: 100%; object-fit: cover; display: block;
  }

  /* Selo de estado — cor + ponto, nunca só cor. */
  .selo {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 2px 9px; border-radius: var(--r-full);
    font-size: 11px; font-weight: 600; white-space: nowrap;
  }
  .selo .ponto { width: 5px; height: 5px; background: currentColor; }
  .selo-ok { color: var(--ok); background: var(--ok-fundo); border: 1px solid var(--ok-borda); }
  .selo-espera { color: var(--alerta); background: var(--alerta-fundo); border: 1px solid var(--alerta-borda); }
  .selo-erro { color: var(--erro); background: var(--erro-fundo); border: 1px solid var(--erro-borda); }
  .selo-neutro { color: var(--texto-3); background: var(--fundo-sub); border: 1px solid var(--borda); }
  .selo-fora { color: var(--texto-3); background: transparent; border: 1px dashed var(--borda); }

  /* ══ Dashboard ═════════════════════════════════════════════════════ */
  .dash-grade { display: grid; grid-template-columns: minmax(0, 1fr) 344px; gap: 20px; align-items: start; }
  .coluna { display: flex; flex-direction: column; gap: 20px; min-width: 0; }

  .metricas { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
  .metrica-topo { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
  .metrica-valor {
    font: 800 26px/1.05 var(--fonte); letter-spacing: -0.9px;
    font-variant-numeric: tabular-nums;
  }
  .metrica-valor.txt { font-size: 17px; letter-spacing: -0.2px; }
  .metrica-delta {
    display: inline-flex; align-items: center; gap: 3px;
    font-size: 11.5px; font-weight: 700; margin-top: 3px;
    font-variant-numeric: tabular-nums;
  }
  .metrica-delta.ok { color: var(--ok); }
  .metrica-delta.parado { color: var(--texto-3); }
  .metrica-rotulo { font-size: 11.5px; color: var(--texto-3); margin-top: 1px; }

  .grafico-caixa { position: relative; width: 100%; height: 132px; margin-top: 8px; }
  .grafico-caixa canvas { display: block; width: 100%; height: 100%; }

  .vazio {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 26px 16px; text-align: center;
    color: var(--texto-3); font-size: 12.5px;
  }
  .vazio .icone { width: 24px; height: 24px; opacity: 0.5; }
  .vazio strong { color: var(--texto-2); font-size: 13px; font-weight: 600; }

  /* Top plataformas — colunas fixas curtas para a barra sempre aparecer. */
  .top-lista { display: flex; flex-direction: column; gap: 11px; margin-top: 4px; }
  .top-item { display: grid; grid-template-columns: 22px minmax(0, 1fr) 34px; gap: 8px 10px; align-items: center; }
  .top-marca {
    width: 22px; height: 22px; border-radius: 6px; display: grid; place-items: center;
    /* Fundo tingido + ícone na cor da plataforma. A cor de marca pura como
       fundo deixava o ícone branco em 2,1:1 na Amazon (#FF9900). */
    background: var(--fundo-card-hi);
    background: color-mix(in srgb, var(--c, var(--primaria)) 18%, transparent);
    color: var(--c, var(--primaria-forte));
  }
  .top-nome { font-size: 12.5px; font-weight: 600; color: var(--texto); min-width: 0;
              overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .top-num { font-size: 12.5px; font-weight: 700; text-align: right;
             font-variant-numeric: tabular-nums; }
  .top-barra-linha { grid-column: 2 / -1; }
  .barra { height: 6px; background: var(--fundo-inset); border-radius: var(--r-full); overflow: hidden; }
  .barra > i { display: block; height: 100%; border-radius: var(--r-full);
               background: linear-gradient(90deg, var(--primaria), var(--primaria-forte));
               transition: width var(--t-lenta) var(--ease); }

  .atividade { display: flex; flex-direction: column; gap: 12px; }
  .ativ-item { display: flex; align-items: center; gap: 11px; font-size: 12.5px; }
  .ativ-icone {
    width: 30px; height: 30px; border-radius: var(--r-sm); flex: none;
    display: grid; place-items: center; background: var(--primaria-fundo); color: var(--primaria-forte);
  }
  .ativ-icone.amz { background: rgba(245, 166, 35, 0.15); color: var(--e2); }
  .ativ-icone.shp { background: rgba(242, 88, 59, 0.15); color: var(--e3); }
  .ativ-icone.ali { background: rgba(139, 92, 246, 0.15); color: #A78BFA; }
  .ativ-texto { flex: 1; min-width: 0; }
  .ativ-texto b { display: block; font-weight: 600; color: var(--texto);
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ativ-texto small { display: block; font-size: 11.5px; color: var(--texto-3);
                      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ativ-hora { font-size: 11px; color: var(--texto-3); font-variant-numeric: tabular-nums; flex: none; }

  /* Lista de links */
  .link-lista { display: flex; flex-direction: column; gap: 9px; margin-top: 4px; }
  .link-item {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 11px; background: var(--fundo-sub);
    border: 1px solid var(--borda-sutil); border-radius: var(--r-md);
    transition: border-color var(--t-rapida) var(--ease);
  }
  .link-item:hover { border-color: var(--borda-forte); }
  .link-corpo { flex: 1; min-width: 0; line-height: 1.35; }
  /* min-height 26px: o link abre a oferta, então o alvo precisa ter pelo
     menos 24px de altura (WCAG 2.5.8) mesmo com texto de 12px. */
  .link-url {
    display: block; min-height: 26px; padding: 5px 0; margin: -5px 0;
    font: 500 12px var(--mono); color: var(--primaria-texto);
    text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .link-url:hover { text-decoration: underline; }
  .link-meta { font-size: 11px; color: var(--texto-3); white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }
  /* 34px: a linha inteira do link é o alvo; o botão é o alvo secundário. */
  .link-item .btn-icone { width: 34px; height: 34px; min-height: 34px; }

  /* == Plataformas =================================================
     Grade de cards compactos: logo, nome, uma linha de status, uma linha
     de resumo e o botao "Configurar". Nenhum campo de credencial na grade —
     quem abre e o drawer lateral, e a pagina principal continua limpa.
     A altura e a mesma em todos os cards porque o rodape usa
     `margin-top:auto` e o resumo tem altura reservada. */
  .plato-grade {
    display: grid; gap: 14px; align-items: stretch;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .plato {
    --cor: var(--primaria);
    position: relative; display: flex; flex-direction: column; gap: 11px;
    padding: 16px 18px 15px; background: var(--fundo-card);
    border: 1px solid var(--borda); border-radius: var(--r-lg);
    box-shadow: var(--sombra-1); overflow: hidden; scroll-margin-top: 20px;
    transition: border-color var(--t-media) var(--ease),
                box-shadow var(--t-media) var(--ease),
                transform var(--t-media) var(--ease);
  }
  /* Fio da cor da marca no topo: identifica o marketplace sem depender de
     legenda, e da a cada card a identidade que a lista achatava. */
  .plato::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--cor), transparent 82%);
  }
  .plato:hover { border-color: var(--borda-forte); transform: translateY(-2px); }
  .plato.destaque {
    border-color: var(--cor);
    box-shadow: var(--sombra-2), 0 0 0 1px var(--cor);
  }

  .plato-topo { display: flex; align-items: center; gap: 12px; }
  .plato-logo {
    width: 40px; height: 40px; border-radius: var(--r-md); flex: none;
    overflow: hidden; background: var(--fundo-card-hi);
    border: 1px solid var(--borda-sutil); box-shadow: var(--sombra-1);
  }
  /* A classe vai no img, como nas outras logos do painel (mp-logo-img,
     ativ-logo-img) — e' o que permite conferir as quatro por seletor
     sem depender do elemento que as envolve. */
  .plato-logo-img { width: 100%; height: 100%; object-fit: cover; display: block; }
  /* Telegram não tem PNG em /assets: o mesmo slot recebe um ícone. Sem
     centralizar, o traço encosta na borda da caixa. */
  .plato-logo-glyph { padding: 9px; color: var(--cor, var(--primaria-texto)); }
  .plato-id { min-width: 0; flex: 1; }
  .plato-id h3 { font-size: 15px; font-weight: 700; letter-spacing: -0.2px; }
  .plato-id small {
    display: block; margin-top: 1px; font-size: 11.5px; color: var(--texto-3);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  /* A linha de status: uma caixa com o texto que o servidor mandou.
     Duas linhas reservadas, nao uma: "Sessão pendente (Faça login ou
     insira o Cookie)" é o status do Mercado Livre sem sessão, e cortar
     no meio esconderia justamente a instrução que resolve o problema.
     A altura é fixa nos cinco cards, então o rodape de todos continua
     na mesma linha mesmo com textos de comprimentos diferentes. */
  .plato-estado { min-height: 24px; display: flex; align-items: stretch; }
  .plato-linha {
    display: flex; align-items: center; width: 100%;
    min-height: 50px; padding: 7px 11px; border-radius: var(--r-sm);
    background: var(--fundo-sub); border: 1px solid var(--borda-sutil);
    font-size: 12.5px; line-height: 1.45; color: var(--texto-2); font-weight: 600;
  }
  .plato-linha > span {
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; overflow-wrap: anywhere;
  }

  .plato-dica { font-size: 12px; color: var(--texto-3); }
  .plato-dica.ok { color: var(--ok); }

  /* So o botao de configurar na grade: um unico caminho para as credenciais,
     em vez de tres botoes disputando o mesmo cartao. */
  .plato-rodape {
    display: flex; align-items: center; gap: 9px;
    margin-top: auto; padding-top: 12px; border-top: 1px solid var(--borda-sutil);
  }
  .plato-rodape .btn { flex: none; }

  @media (max-width: 980px) {
    .plato-grade { grid-template-columns: 1fr; }
  }

  /* == Drawer de configuracao =========================================
     Painel lateral que entra pela direita, por cima da grade. Reaproveita
     o overlay e o `aoTeclarModal` dos modais: os dois ficam empilhados no
     DOM e o `pop()` de `.overlay.aberto` pega o de cima, que e o drawer
     quando um modal e aberto de dentro dele.

     O seletor leva as duas classes de proposito. `.overlay` (0,1,0) vem
     depois no arquivo e declara `place-items:center` com 20px de padding —
     com uma classe só, a gaveta saia centrada e recuada 480px da borda,
     parecendo um modal largo. */
  .overlay.overlay-gaveta { place-items: stretch end; padding: 0; }
  .gaveta {
    width: 100%; max-width: 460px; height: 100%;
    display: flex; flex-direction: column;
    background: var(--fundo-card); border-left: 1px solid var(--borda-forte);
    box-shadow: var(--sombra-3);
    transform: translateX(100%);
    transition: transform var(--t-media) var(--ease);
  }
  .overlay.aberto .gaveta { transform: none; }
  @media (min-width: 561px) { .gaveta { max-width: 480px; } }

  .gaveta-topo {
    display: flex; align-items: center; gap: 12px; flex: none;
    padding: 16px 18px; border-bottom: 1px solid var(--borda);
  }
  .gaveta-id { min-width: 0; flex: 1; }
  .gaveta-id h3 { font-size: 15.5px; font-weight: 700; letter-spacing: -0.2px; }
  .gaveta-id small { display: block; margin-top: 2px; font-size: 12px; color: var(--texto-3); }
  .gaveta-corpo {
    flex: 1; min-height: 0; overflow-y: auto; padding: 18px;
    display: flex; flex-direction: column; gap: 18px;
  }
  .gaveta-pe {
    display: flex; align-items: center; gap: 10px; flex: none;
    padding: 13px 18px; background: var(--fundo-sub); border-top: 1px solid var(--borda);
  }
  .gaveta-pe .btn-primario { margin-left: auto; }
  .gaveta-secao-titulo {
    display: flex; align-items: center; gap: 7px;
    font-size: 11.5px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.9px; color: var(--primaria-texto);
    padding-bottom: 7px; border-bottom: 1px solid var(--borda-sutil);
  }
  .gaveta-campos { display: flex; flex-direction: column; gap: 15px; }
  .gaveta-acoes { display: flex; flex-wrap: wrap; gap: 9px; }
  .gaveta-acoes .btn-perigo { margin-left: auto; }
  .gaveta-status { font-size: 12.5px; color: var(--texto-2); }

  /* ══ Formulário ════════════════════════════════════════════════════ */
  .config-grade { display: grid; grid-template-columns: 1fr 1fr; gap: 20px 24px; }

  /* ── Seções de Configurações ──────────────────────────────────────────
     A página empilhava seis cards num scroll só, todos com o mesmo peso
     visual: não dava para saber o que era o mais usado. As seções agrupam
     por intenção, e a barra no topo pula direto para cada uma.

     Dentro de cada seção os cards vão lado a lado, na mesma grade de duas
     colunas da aba Plataformas: assim a comparação entre plataformas e entre
     campos de configuração fica igual. O gap de 22px na vertical repete o da
     .view de propósito — sem isso, embrulhar os cards mudaria o espaçamento
     e nenhum diff mostraria por que a página afrouxou. */
  .config-secao {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 22px 24px; scroll-margin-top: 74px;
  }
  .config-secao-titulo {
    grid-column: 1 / -1;
    display: flex; align-items: center; gap: 9px;
    font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.9px; color: var(--primaria-texto);
    padding-bottom: 8px; border-bottom: 1px solid var(--borda-sutil);
  }
  /* Card que não cabe em meia coluna — a tabela de fontes tem cinco colunas
     de dados e espremida em meia tela vira um garrancho. Ocupa a linha
     inteira, que é o mesmo truque do .grupo-titulo, e é o que evita que o
     último card de cada seção deixe um buraco na coluna da direita. */
  .config-largo { grid-column: 1 / -1; }
  .config-secao-titulo .icone { color: var(--primaria-forte); }
  .config-nav {
    position: sticky; top: 0; z-index: 6;
    display: flex; gap: 6px; flex-wrap: wrap;
    padding: 9px; margin-bottom: 2px;
    background: rgba(13, 23, 48, 0.92);
    backdrop-filter: blur(8px);
    border: 1px solid var(--borda); border-radius: var(--r-md);
  }
  .config-nav a {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 7px 12px; border-radius: var(--r-sm);
    font-size: 12.5px; font-weight: 600; color: var(--texto-2);
    text-decoration: none; white-space: nowrap;
    transition: background var(--t-rapida) var(--ease), color var(--t-rapida) var(--ease);
  }
  .config-nav a:hover { background: var(--fundo-card-hi); color: var(--texto); }
  .config-nav a.ativo { background: var(--primaria-fundo); color: var(--primaria-texto); }
  .config-nav a:focus-visible { outline: 2px solid var(--primaria-texto); outline-offset: 2px; }

  /* Salvo e não salvo. `configSuja` já era lida no JS, mas só para pular a
     repinta: o estado existia e não aparecia em lugar nenhum da tela. */
  .config-nav .pendente {
    display: none; align-items: center; gap: 6px;
    margin-left: auto; padding: 7px 12px; border-radius: var(--r-sm);
    font-size: 12.5px; font-weight: 700; color: #FCD34D;
    background: rgba(252, 211, 77, 0.12);
    border: 1px solid rgba(252, 211, 77, 0.34);
  }
  .config-nav.sujo .pendente { display: inline-flex; }
  .config-nav .pendente .icone { color: #FCD34D; }
  .grupo-titulo {
    grid-column: 1 / -1; display: flex; align-items: center; gap: 8px;
    font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.9px; color: var(--primaria-texto);
    margin-top: 8px; padding-bottom: 7px; border-bottom: 1px solid var(--borda-sutil);
  }
  .grupo-titulo:first-child { margin-top: 0; }
  .campo { margin-bottom: 2px; }
  .campo label { display: flex; align-items: center; gap: 7px; font-size: 13px;
                 font-weight: 600; color: var(--texto); margin-bottom: 7px; }
  .campo input, .campo select {
    width: 100%; padding: 10px 13px; min-height: 40px;
    border-radius: var(--r-sm); border: 1px solid var(--borda);
    background: var(--fundo-inset); color: var(--texto);
    font-family: inherit; font-size: 13.5px;
    transition: border-color var(--t-rapida) var(--ease), box-shadow var(--t-rapida) var(--ease);
  }
  .campo input::placeholder { color: var(--texto-3); }
  .campo input:focus, .campo select:focus { outline: none; border-color: var(--primaria); box-shadow: var(--anel); }
  .campo .ajuda { font-size: 12px; color: var(--texto-3); margin-top: 5px; line-height: 1.45; }
  .marca-ok { display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
              font-weight: 600; color: var(--ok); margin-left: auto; }

  .acoes-form {
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
    margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--borda-sutil);
  }

  /* Nichos */
  .nichos { display: grid; grid-template-columns: repeat(auto-fill, minmax(178px, 1fr)); gap: 10px; }
  .nicho {
    display: flex; align-items: center; gap: 10px; width: 100%;
    padding: 11px 13px; min-height: 52px; text-align: left;
    background: var(--fundo-sub); border: 1px solid var(--borda);
    border-radius: var(--r-md); color: var(--texto-2);
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
    transition: background var(--t-rapida) var(--ease),
                border-color var(--t-rapida) var(--ease),
                color var(--t-rapida) var(--ease);
  }
  .nicho:hover { border-color: var(--borda-forte); color: var(--texto); }
  .nicho .icone { color: var(--texto-3); transition: color var(--t-rapida) var(--ease); }
  .nicho .rot { flex: 1; min-width: 0; line-height: 1.3; }
  .nicho[aria-checked="true"] {
    background: var(--primaria-fundo); border-color: var(--primaria-borda); color: #fff;
  }
  .nicho[aria-checked="true"] .icone { color: var(--primaria-forte); }
  .nicho-caixa {
    width: 17px; height: 17px; flex: none; border-radius: 5px;
    border: 1.5px solid var(--borda-forte); display: grid; place-items: center;
    color: transparent; transition: background var(--t-rapida) var(--ease),
                                   border-color var(--t-rapida) var(--ease),
                                   color var(--t-rapida) var(--ease);
  }
  .nicho[aria-checked="true"] .nicho-caixa {
    background: var(--primaria); border-color: var(--primaria); color: #fff;
  }

  /* ══ Tabelas e terminais ═══════════════════════════════════════════ */
  .tabela-caixa { overflow-x: auto; border: 1px solid var(--borda); border-radius: var(--r-md); }
  table.tabela { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
  .tabela th {
    background: var(--fundo-sub); padding: 11px 16px;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.6px; color: var(--texto-3);
    border-bottom: 1px solid var(--borda); white-space: nowrap;
  }
  .tabela td { padding: 11px 16px; border-bottom: 1px solid var(--borda-sutil); color: var(--texto-2); }
  .tabela tbody tr:last-child td { border-bottom: 0; }
  .tabela tbody tr:hover td { background: rgba(255, 255, 255, 0.025); }
  .tabela .tit { color: var(--texto); font-weight: 600; max-width: 460px; }
  .tabela .preco { color: var(--ok); font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .tabela .quando { color: var(--texto-3); font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; }

  .logs-grade { display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
                height: calc(100vh - 250px); min-height: 420px; }
  .terminal {
    display: flex; flex-direction: column; min-height: 0; overflow: hidden;
    background: var(--fundo-inset); border: 1px solid var(--borda);
    border-radius: var(--r-lg); box-shadow: var(--sombra-2);
  }
  .terminal-topo {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    padding: 10px 14px; background: var(--fundo-sub);
    border-bottom: 1px solid var(--borda);
    font-size: 12.5px; font-weight: 700; color: var(--texto);
  }
  .terminal-topo .rot { display: flex; align-items: center; gap: 8px; }
  .terminal-corpo {
    flex: 1; min-height: 0; overflow-y: auto;
    padding: 14px 16px; font: 400 12px/1.65 var(--mono);
    color: #9FB6CC; white-space: pre-wrap; word-break: break-word;
  }
  .terminal-corpo .vazio-terminal { font-family: var(--fonte); color: var(--texto-3); }

  /* ══ Suporte ══════════════════════════════════════════════════════ */
  .faq { display: flex; flex-direction: column; gap: 10px; }
  .faq details {
    background: var(--fundo-sub); border: 1px solid var(--borda);
    border-radius: var(--r-md); overflow: hidden;
  }
  .faq summary {
    display: flex; align-items: center; gap: 10px;
    padding: 13px 16px; cursor: pointer; font-size: 13.5px; font-weight: 600;
    list-style: none;
  }
  .faq summary::-webkit-details-marker { display: none; }
  .faq summary .icone:last-child { margin-left: auto; color: var(--texto-3); transition: transform var(--t-media) var(--ease); }
  .faq details[open] summary .icone:last-child { transform: rotate(180deg); }
  .faq summary:hover { background: var(--fundo-card-hi); }
  .faq-corpo { padding: 0 16px 15px 46px; font-size: 13px; color: var(--texto-2); line-height: 1.6; }

  code {
    font: 500 12.5px var(--mono); background: var(--fundo-inset);
    border: 1px solid var(--borda-sutil); border-radius: 5px;
    padding: 1px 5px; color: var(--primaria-texto);
  }

  .diagnostico { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; margin-top: 4px; }
  .diag-item {
    display: flex; align-items: center; gap: 9px; padding: 11px 13px;
    background: var(--fundo-sub); border: 1px solid var(--borda);
    border-radius: var(--r-md); font-size: 12.5px; font-weight: 600;
  }
  .diag-item .icone-ok { color: var(--ok); }
  .diag-item .icone-falta { color: var(--texto-3); }
  .diag-item b { font-weight: 700; }
  .diag-item span { color: var(--texto-3); font-weight: 500; }

  /* ══ Rodapé ════════════════════════════════════════════════════════ */
  .rodape {
    display: flex; align-items: center; justify-content: space-between;
    gap: 14px; flex-wrap: wrap;
    margin-top: auto; padding: 15px 32px;
    background: var(--fundo-sidebar); border-top: 1px solid var(--borda-sutil);
    font-size: 12px; color: var(--texto-3);
  }
  .rodape .esq, .rodape .dir { display: flex; align-items: center; gap: 7px; }
  .rodape .icone { color: var(--ok); }

  /* ══ Modal ═════════════════════════════════════════════════════════ */
  /* `display` aqui tem especificidade (0,1,0) e vencia o `display:none` do
     atributo `hidden` vindo do navegador — os dois modais ficavam SEMPRE no
     layout (invisíveis, mas focáveis por Tab e lidos por leitores de tela).
     A regra do `[hidden]` abaixo tem (0,2,0) e realmente esconde.          */
  .overlay[hidden] { display: none; }
  .overlay {
    position: fixed; inset: 0; z-index: var(--z-overlay);
    display: grid; place-items: center; padding: 20px;
    background: rgba(2, 9, 18, 0.72);
    backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
    opacity: 0; visibility: hidden; pointer-events: none;
    transition: opacity var(--t-media) var(--ease), visibility var(--t-media) var(--ease);
  }
  .overlay.aberto { opacity: 1; visibility: visible; pointer-events: auto; }
  .modal {
    width: 100%; max-width: 540px; max-height: calc(100vh - 40px);
    display: flex; flex-direction: column;
    background: var(--fundo-card); border: 1px solid var(--borda-forte);
    border-radius: var(--r-lg); box-shadow: var(--sombra-3); overflow: hidden;
    transform: scale(0.96) translateY(8px);
    transition: transform var(--t-media) var(--ease);
  }
  .overlay.aberto .modal { transform: none; }
  .modal-topo {
    display: flex; align-items: center; gap: 10px;
    padding: 16px 18px; border-bottom: 1px solid var(--borda);
  }
  .modal-topo h3 { flex: 1; font-size: 15.5px; font-weight: 700; letter-spacing: -0.2px; }
  .modal-topo .icone { color: var(--primaria-forte); }
  .modal-corpo { padding: 18px; overflow-y: auto; }
  .modal-pe { display: flex; justify-content: flex-end; gap: 9px;
              padding: 13px 18px; background: var(--fundo-sub); border-top: 1px solid var(--borda); }

  .saida-link {
    display: flex; gap: 8px; align-items: stretch; margin-top: 6px;
  }
  .saida-link input {
    flex: 1; min-width: 0; padding: 10px 12px; min-height: 40px;
    background: var(--fundo-inset); border: 1px solid var(--borda);
    border-radius: var(--r-sm); color: var(--texto);
    font: 500 12.5px var(--mono);
  }
  .saida-link input:focus { border-color: var(--primaria); box-shadow: var(--anel); }
  .resultado-caixa {
    margin-top: 16px; padding: 13px 15px;
    background: var(--primaria-fundo); border: 1px solid var(--primaria-borda);
    border-radius: var(--r-md);
  }
  .resultado-caixa .rot {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.7px; color: var(--primaria-texto); margin-bottom: 7px;
    display: flex; align-items: center; gap: 6px;
  }
  .painel-info {
    padding: 13px 15px; background: var(--fundo-sub);
    border: 1px solid var(--borda); border-radius: var(--r-md);
    font-size: 13px; line-height: 1.6;
  }
  .painel-info p + p { margin-top: 7px; }
  .painel-info dl { display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; align-items: baseline; }
  .painel-info dt { color: var(--texto-3); font-size: 12.5px; }
  .painel-info dd { margin: 0; font-weight: 600; }
  .painel-info .caminho { grid-column: 1 / -1; font: 400 11px var(--mono);
                         color: var(--texto-3); word-break: break-all; }

  /* ══ Aviso dentro da página ═══════════════════════════════════════ */
  .alerta {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 12px 14px; border-radius: var(--r-md); font-size: 13px; line-height: 1.5;
  }
  .alerta .icone { flex: none; margin-top: 1px; }
  .alerta strong { display: block; margin-bottom: 2px; }
  .alerta-info { background: var(--primaria-fundo); border: 1px solid var(--primaria-borda); color: var(--texto-2); }
  .alerta-info .icone { color: var(--primaria-forte); }
  .alerta-espera { background: var(--alerta-fundo); border: 1px solid var(--alerta-borda); color: var(--texto-2); }
  .alerta-espera .icone { color: var(--alerta); }
  .alerta-erro { background: var(--erro-fundo); border: 1px solid var(--erro-borda); color: var(--texto-2); }
  .alerta-erro .icone { color: var(--erro); }

  /* Botões de escolha do Telegram detectado */
  .escolhas { display: flex; flex-direction: column; gap: 8px; }
  .escolha-rot { font-size: 12px; font-weight: 700; text-transform: uppercase;
                 letter-spacing: 0.6px; color: var(--texto-3); }
  .escolha {
    display: flex; align-items: center; gap: 10px; width: 100%;
    padding: 10px 13px; min-height: 44px; text-align: left;
    background: var(--fundo-sub); border: 1px solid var(--borda);
    border-radius: var(--r-md); color: var(--texto);
    font: inherit; font-size: 13px; cursor: pointer;
    transition: border-color var(--t-rapida) var(--ease), background var(--t-rapida) var(--ease);
  }
  .escolha:hover { border-color: var(--primaria); background: var(--fundo-card-hi); }
  .escolha .icone { color: var(--primaria-forte); flex: none; }
  .escolha b { font-weight: 600; }
  .escolha code { margin-left: auto; }

  /* ══ Toasts ════════════════════════════════════════════════════════ */
  .toasts {
    position: fixed; right: 20px; bottom: 20px; z-index: var(--z-toast);
    display: flex; flex-direction: column; gap: 9px;
    max-width: min(400px, calc(100vw - 40px)); pointer-events: none;
  }
  .toast {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 12px 15px; pointer-events: auto;
    background: var(--fundo-card-hi); border: 1px solid var(--borda-forte);
    border-radius: var(--r-md); box-shadow: var(--sombra-3);
    font-size: 13px; font-weight: 500; color: var(--texto);
    transform: translateY(14px) scale(0.97); opacity: 0;
    transition: transform var(--t-lenta) var(--ease), opacity var(--t-lenta) var(--ease);
  }
  .toast.entrou { transform: none; opacity: 1; }
  .toast .icone { flex: none; margin-top: 1px; }
  .toast-ok { border-color: var(--ok-borda); }
  .toast-ok .icone { color: var(--ok); }
  .toast-erro { border-color: var(--erro-borda); }
  .toast-erro .icone { color: var(--erro); }
  .toast-espera { border-color: var(--alerta-borda); }
  .toast-espera .icone { color: var(--alerta); }
  .toast-alerta { border-color: var(--alerta-borda); }
  .toast-alerta .icone { color: var(--alerta); }
  .toast-info { border-color: var(--primaria-borda); }
  .toast-info .icone { color: var(--primaria-forte); }

  /* ══ Responsivo ════════════════════════════════════════════════════ */
  @media (max-width: 1240px) {
    .dash-grade { grid-template-columns: 1fr; }
    .grade-4 { grid-template-columns: repeat(2, 1fr); }
  }
  @media (max-width: 1000px) {
    .metricas { grid-template-columns: 1fr; }
    .config-grade { grid-template-columns: 1fr; }
    /* As duas grades de Configurações caem juntas: meia coluna de card com
       meia coluna de campo dentro vira um campo de 140px, e aí é melhor a
       página inteira virar uma coluna. */
    .config-secao { grid-template-columns: 1fr; }
    .logs-grade { grid-template-columns: 1fr; height: auto; }
    .terminal { height: 300px; }
  }
  @media (max-width: 860px) {
    .app-layout { flex-direction: column; }
    .sidebar {
      position: static; width: 100%; height: auto; flex-direction: row;
      align-items: center; gap: 14px; overflow-x: auto;
      border-right: 0; border-bottom: 1px solid var(--borda-sutil);
      padding: 10px 14px;
    }
    .brand { padding: 0; flex: none; }
    .brand-texto { display: none; }
    .nav-menu { flex-direction: row; margin: 0; }
    .nav-item span.rot { display: none; }
    .nav-item { padding: 9px; }
    .nav-badge { display: none; }
    .sidebar-rodape { margin: 0 0 0 auto; display: flex; align-items: center; gap: 10px; }
    .bot-cartao { margin: 0; width: auto; min-height: 44px; }
    .bot-cartao-texto small { display: none; }
    .sidebar-nota { display: none; }
    .top-header, .view { padding-left: 18px; padding-right: 18px; }
    .saudacao h2 { font-size: 20px; }
    .perfil { display: none; }
    .grade-2 { grid-template-columns: 1fr; }
  }
  @media (max-width: 560px) {
    .grade-4 { grid-template-columns: 1fr; }
    .top-header { padding-top: 16px; }
    .header-acoes { width: 100%; }
    .btn-primario { width: 100%; }
  }

  @media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
    *, *::before, *::after {
      animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }

  /* ══ Impressão ══════════════════════════════════════════════════════
     Sem isso o painel imprime como um retângulo azul-escuro com letras
     claras — quase nada de tinta e ilegível. Aqui vira papel.            */
  @media print {
    :root {
      --fundo: #fff; --fundo-sidebar: #fff; --fundo-card: #fff; --fundo-card-hi: #fff;
      --fundo-sub: #fff; --fundo-inset: #fff;
      --borda: #c8d0d8; --borda-forte: #8b98a5; --borda-sutil: #dde3e9;
      --texto: #000; --texto-2: #26313c; --texto-3: #4a5764;
      --primaria: #0A6EDB; --primaria-forte: #0A6EDB;
      --primaria-texto: #0A4E9B; --ok: #0d7a52; --alerta: #8a5a00; --erro: #b3261e;
      --e1: #0d4a80; --e2: #a06a00; --e3: #a8331f; --e4: #6b3fd4;
      --sombra-1: none; --sombra-2: none; --sombra-3: none; --anel: none;
    }
    html, body { background: #fff !important; color: #000; }
    .sidebar, .top-header, .rodape, .toasts, .overlay,
    .pular-para-conteudo, .btn, .btn-icone, .acoes-form, .plato-rodape { display: none !important; }
    .app-layout { display: block; }
    .view { display: none !important; padding: 0; }
    .view.ativa { display: block !important; }
    .plato-grade { display: block !important; }
    .card, .plato, .mp-card, .plato-linha {
      break-inside: avoid; page-break-inside: avoid;
      box-shadow: none !important; border-color: #c8d0d8 !important;
    }
    .tabela-caixa { overflow: visible; }
    a[href]::after { content: " (" attr(href) ")"; font-size: 10px; color: #4a5764; }
    .link-url { white-space: normal; word-break: break-all; min-height: 0; padding: 0; margin: 0; }
  }

  /* ══ Conta do painel ═══════════════════════════════════════════════ */
  .forca { display: flex; align-items: center; gap: 10px; margin: 4px 0 0; }
  .forca[hidden] { display: none; }
  .forca-barra {
    flex: 1; max-width: 220px; height: 5px; border-radius: var(--r-full);
    background: var(--fundo-inset); border: 1px solid var(--borda-sutil);
    overflow: hidden;
  }
  .forca-barra span {
    display: block; height: 100%; width: 0;
    border-radius: var(--r-full);
    background: var(--erro);
    transition: width var(--t-media) var(--ease), background var(--t-media) var(--ease);
  }
  .forca-texto { font-size: 12.5px; color: var(--texto-3); white-space: nowrap; }
  .forca[data-nivel="2"] .forca-barra span { background: var(--alerta); }
  .forca[data-nivel="3"] .forca-barra span,
  .forca[data-nivel="4"] .forca-barra span { background: var(--ok); }
  .forca[data-nivel="2"] .forca-texto { color: var(--alerta); }
  .forca[data-nivel="3"] .forca-texto,
  .forca[data-nivel="4"] .forca-texto { color: var(--ok); }

  /* ══ Tela de login ══════════════════════════════════════════════════ */
  /* Cobre tudo e some do tab order enquanto o app estiver bloqueado —
     o conteúdo continua no DOM porque é ele que carrega o script. */
  .tela-login {
    position: fixed; inset: 0; z-index: calc(var(--z-overlay) + 10);
    display: grid; place-items: center;
    padding: 24px;
    background:
      radial-gradient(760px 420px at 50% -10%, rgba(26, 104, 255, 0.18), transparent 65%),
      var(--fundo);
    overflow-y: auto;
  }
  .tela-login[hidden] { display: none; }

  .login-cartao {
    width: min(400px, 100%);
    background: var(--fundo-card);
    border: 1px solid var(--borda);
    border-radius: var(--r-lg);
    box-shadow: var(--sombra-3);
    padding: 32px 28px 28px;
    display: flex; flex-direction: column;
  }
  .login-icone {
    width: 48px; height: 48px; display: grid; place-items: center;
    border-radius: var(--r-md);
    background: var(--primaria-fundo);
    border: 1px solid var(--primaria-borda);
    color: var(--primaria-forte);
    margin-bottom: 16px;
  }
  .login-titulo { font-size: 21px; font-weight: 800; letter-spacing: -0.02em; }
  .login-sub    { color: var(--texto-3); font-size: 13.5px; margin: 4px 0 22px; }

  .login-rotulo {
    font-size: 12.5px; font-weight: 600; color: var(--texto-2);
    margin-bottom: 6px;
  }
  .login-campo {
    width: 100%; height: 42px;
    padding: 0 13px; margin-bottom: 16px;
    background: var(--fundo-inset);
    border: 1px solid var(--borda);
    border-radius: var(--r-md);
    color: var(--texto);
    font: 400 14px/1 var(--fonte);
    transition: border-color var(--t-rapida) var(--ease), box-shadow var(--t-rapida) var(--ease);
  }
  .login-campo::placeholder { color: var(--texto-3); }
  .login-campo:focus-visible {
    outline: none;
    border-color: var(--primaria);
    box-shadow: var(--anel);
  }
  .login-erro:empty, .login-aviso:empty { display: none; }
  .login-erro {
    margin: -4px 0 14px; font-size: 13px;
    color: var(--erro); background: var(--erro-fundo);
    border: 1px solid var(--erro-borda); border-radius: var(--r-sm);
    padding: 9px 11px;
  }
  .login-aviso {
    margin: -4px 0 14px; font-size: 12.5px;
    color: var(--alerta); background: var(--alerta-fundo);
    border: 1px solid var(--alerta-borda); border-radius: var(--r-sm);
    padding: 9px 11px;
  }
  .login-btn { width: 100%; height: 44px; justify-content: center; margin-top: 2px; }

  /* Com o login aberto, nada do app deve ser alcançável pelo teclado. */
  body.travado .app-layout,
  body.travado .toasts,
  body.travado .pular-para-conteudo { visibility: hidden; }

  @media print {
    .tela-login { display: none !important; }
  }
</style>
</head>
<body>

<!-- ══ Conjunto de ícones (Lucide, 24×24, traço 2) ══════════════════════
     Um <symbol> por ícone; usar com <svg class="icone"><use href="#i-nome"/></svg>.
     Substitui todos os emojis e glifos de texto do painel. -->
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
  <symbol id="i-dashboard" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></symbol>
  <symbol id="i-tag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.2"/></symbol>
  <symbol id="i-link" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7L11.7 5.2"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></symbol>
  <symbol id="i-link-off" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 17H7A5 5 0 0 1 7 7"/><path d="M15 7h2a5 5 0 0 1 3.5 8.5"/><path d="M8 12h4"/><path d="M3 3l18 18"/></symbol>
  <symbol id="i-store" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l1.5-5h15L21 9"/><path d="M4 9v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9"/><path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/><path d="M9 21v-6h6v6"/></symbol>
  <symbol id="i-layers" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="7" rx="2"/><rect x="2" y="14" width="20" height="7" rx="2"/><path d="M6 6.5h.01M6 17.5h.01"/></symbol>
  <symbol id="i-sliders" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></symbol>
  <symbol id="i-terminal" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 9l3 3-3 3M12 15h5"/></symbol>
  <symbol id="i-headset" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17v-5a9 9 0 0 1 18 0v5"/><path d="M21 18a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 18a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></symbol>
  <symbol id="i-play" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4l14 8-14 8z"/></symbol>
  <symbol id="i-stop" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2"/></symbol>
  <symbol id="i-power" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v9"/><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5l5.5 5.5L20 7"/></symbol>
  <symbol id="i-check-circle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.2l2.6 2.6 4.4-4.6"/></symbol>
  <symbol id="i-alert" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.4h.01"/></symbol>
  <symbol id="i-alert-triangle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9L2 18.5A2 2 0 0 0 3.7 21.5h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4M12 17.4h.01"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></symbol>
  <symbol id="i-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></symbol>
  <symbol id="i-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M7 11l5 5 5-5"/><path d="M4 20h16"/></symbol>
  <symbol id="i-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 4v6h-6"/><path d="M3.5 15a9 9 0 1 0 2-9.4L3 10"/></symbol>
  <symbol id="i-key" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15" r="4"/><path d="M10.8 12.2L20 3l1.5 1.5-1.5 1.5 1.5 1.5-2 2-1.5-1.5-2 2"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.7-4.7"/></symbol>
  <symbol id="i-zoom" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.7-4.7M8 10.5h5M10.5 8v5"/></symbol>
  <symbol id="i-trash" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/><path d="M6 7l1 12.2A2 2 0 0 0 9 21h6a2 2 0 0 0 2-1.8L18 7"/><path d="M10 11.5v5M14 11.5v5"/></symbol>
  <symbol id="i-save" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/></symbol>
  <symbol id="i-send" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2.5L11 13"/><path d="M21.5 2.5l-6.8 19-3.7-8.5L2.5 9.3z"/></symbol>
  <symbol id="i-handshake" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 15h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 17"/><path d="M7 21l1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.8-2.8L15 14"/></symbol>
  <symbol id="i-package" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 7.5L12 3 3.5 7.5v9L12 21l8.5-4.5z"/><path d="M3.5 7.5L12 12l8.5-4.5M12 12v9"/></symbol>
  <symbol id="i-shopping-bag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14l1 14H4z"/><path d="M9 7V5.5a3 3 0 0 1 6 0V7"/></symbol>
  <symbol id="i-globe" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3.2 9.5h17.6M3.2 14.5h17.6"/><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z"/></symbol>
  <symbol id="i-chart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v17a1 1 0 0 0 1 1h17"/><path d="M7 15l4-5 3.5 3L20 6"/></symbol>
  <symbol id="i-bar-chart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v17a1 1 0 0 0 1 1h17"/><path d="M7.5 16v-4M12 16V8M16.5 16v-6"/></symbol>
  <symbol id="i-clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.2 2"/></symbol>
  <symbol id="i-history" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 15a9 9 0 1 0 2-9.4L3 10"/><path d="M3 4v6h6"/><path d="M12 8v4.4l3 1.8"/></symbol>
  <symbol id="i-award" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="9" r="6"/><path d="M8.2 14.2L7 22l5-2.6L17 22l-1.2-7.8"/></symbol>
  <symbol id="i-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-3.6 8-9.5V5.2L12 2.4 4 5.2v7.3C4 18.4 12 22 12 22z"/><path d="M9 12l2.2 2.2L15.5 10"/></symbol>
  <symbol id="i-user" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1.5A5.5 5.5 0 0 1 9.5 14h5a5.5 5.5 0 0 1 5.5 5.5V21"/></symbol>
  <symbol id="i-users" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20v-1A4.5 4.5 0 0 1 7 14.5h4a4.5 4.5 0 0 1 4.5 4.5v1"/><path d="M16 5.2a3.5 3.5 0 0 1 0 6.6M18 14.8a4.5 4.5 0 0 1 3.5 4.4V20"/></symbol>
  <symbol id="i-megaphone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11v2a2 2 0 0 0 2 2h2l8 5V4L7 9H5a2 2 0 0 0-2 2z"/><path d="M19 8.5a4.5 4.5 0 0 1 0 7"/></symbol>
  <symbol id="i-wave" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h3l2.5-6 3 12 3-9 2 3h3.5"/></symbol>
  <symbol id="inbox" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h5l1.5 3h5L16 12h5"/><path d="M5.4 5.2L3 12v6a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6l-2.4-6.8A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.9 1.2z"/></symbol>
  <symbol id="i-inbox" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h5l1.5 3h5L16 12h5"/><path d="M5.4 5.2L3 12v6a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6l-2.4-6.8A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.9 1.2z"/></symbol>
  <symbol id="i-chevron-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9.5l6 6 6-6"/></symbol>
  <symbol id="i-chevron-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 6l6 6-6 6"/></symbol>
  <symbol id="i-external" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-8.5 8.5"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></symbol>
  <symbol id="i-sparkles" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 4.6L18.5 9.5 13.9 11.4 12 16l-1.9-4.6L5.5 9.5l4.6-1.9z"/><path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/></symbol>
  <symbol id="i-cpu" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/></symbol>
  <symbol id="i-smartphone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M10.5 18.5h3"/></symbol>
  <symbol id="i-gamepad" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 12h4M9 10v4"/><circle cx="15.5" cy="11" r=".8"/><circle cx="17.5" cy="13" r=".8"/><path d="M6.5 6h11a5 5 0 0 1 5 5v3a4 4 0 0 1-7 2.4l-.6-.9H9.1l-.6.9A4 4 0 0 1 1.5 14v-3a5 5 0 0 1 5-5z"/></symbol>
  <symbol id="i-sofa" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11V8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v3"/><path d="M2 13a2 2 0 0 1 4 0v3h12v-3a2 2 0 0 1 4 0v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z"/><path d="M6 19v2M18 19v2"/></symbol>
  <symbol id="i-plug" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2v6M15 2v6"/><path d="M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v5"/></symbol>
  <symbol id="i-shirt" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3a3 3 0 0 1-6 0L4.5 5 3 9l3 1.5V21h12V10.5L21 9l-1.5-4z"/></symbol>
  <symbol id="i-heart-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20.5S3.5 15 3.5 9.2A4.7 4.7 0 0 1 12 6.4a4.7 4.7 0 0 1 8.5 2.8c0 5.8-8.5 11.3-8.5 11.3z"/><path d="M3.8 12.5h3l1.4-2.4 2 4.4 1.6-3 1.2 1h3.2"/></symbol>
  <symbol id="i-baby" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9 10.5h.01M15 10.5h.01"/><path d="M9 15a4 4 0 0 0 6 0"/><path d="M12 3c-1-1.5-3-1.5-4 0"/></symbol>
  <symbol id="i-paw" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="6" cy="9.5" rx="2.1" ry="2.6"/><ellipse cx="18" cy="9.5" rx="2.1" ry="2.6"/><ellipse cx="9.7" cy="5.6" rx="1.9" ry="2.4"/><ellipse cx="14.3" cy="5.6" rx="1.9" ry="2.4"/><path d="M12 13.5c3 0 5.5 2.2 5.5 4.6 0 1.7-1.4 2.9-3 2.9-1.1 0-1.8-.5-2.5-.5s-1.4.5-2.5.5c-1.6 0-3-1.2-3-2.9 0-2.4 2.5-4.6 5.5-4.6z"/></symbol>
  <symbol id="i-car" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l1.4-4.4A2 2 0 0 1 8.3 7.2h7.4a2 2 0 0 1 1.9 1.4L19 13"/><path d="M3.5 13h17a1.5 1.5 0 0 1 1.5 1.5V17a1 1 0 0 1-1 1H15v-2H9v2H4a1 1 0 0 1-1-1v-2.5A1.5 1.5 0 0 1 3.5 13z"/><path d="M6.5 16h.01M17.5 16h.01"/></symbol>
  <symbol id="i-book" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H19v18H5.5A1.5 1.5 0 0 1 4 19.5z"/><path d="M8 3v18M11 8h4M11 12h4"/></symbol>
  <symbol id="i-dumbbell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 6.5v11M3.5 9v6M17.5 6.5v11M20.5 9v6M6.5 12h11"/></symbol>
  <symbol id="i-log-in" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h3.5A2.5 2.5 0 0 1 21 5.5v13a2.5 2.5 0 0 1-2.5 2.5H15"/><path d="M10 16.5l4.5-4.5L10 7.5"/><path d="M14.5 12H3.5"/></symbol>
</svg>

<a href="#conteudo" class="pular-para-conteudo">Pular para o conteúdo</a>

<!-- ══ Tela de login ══════════════════════════════════════════════════
     Cobre o app inteiro enquanto não houver sessão. O conteúdo do painel
     segue no DOM (é ele que carrega este script), mas fica escondido e
     fora do tab order — sem sessão nenhuma chamada /api/ passa. -->
<div class="tela-login" id="telaLogin" hidden>
  <form class="login-cartao" id="loginForm" novalidate>
    <span class="login-icone" aria-hidden="true">
      <svg class="icone"><use href="#i-tag"/></svg>
    </span>
    <h2 class="login-titulo">Ofertas Pro</h2>
    <p class="login-sub">Entre para acessar o painel.</p>

    <label class="login-rotulo" for="loginUsuario">Usuário</label>
    <input class="login-campo" id="loginUsuario" name="usuario" type="text"
           autocomplete="username" autocapitalize="none" spellcheck="false"
           required>

    <label class="login-rotulo" for="loginSenha">Senha</label>
    <input class="login-campo" id="loginSenha" name="senha" type="password"
           autocomplete="current-password" required>

    <p class="login-erro" id="loginErro" role="alert" aria-live="polite"></p>
    <p class="login-aviso" id="loginAviso"></p>

    <button type="submit" class="btn btn-primario login-btn" id="loginEntrar">
      <svg class="icone" aria-hidden="true"><use href="#i-log-in"/></svg>
      Entrar
    </button>
  </form>
</div>

<div class="app-layout">

  <!-- ══ Sidebar ══════════════════════════════════════════════════════ -->
  <aside class="sidebar">
    <a href="#dashboard" class="brand" data-ir="dashboard">
      <span class="brand-icone" aria-hidden="true">
        <svg class="icone"><use href="#i-tag"/></svg>
      </span>
      <span class="brand-texto">
        <h1>Ofertas Pro</h1>
        <span>Painel de afiliados</span>
      </span>
    </a>

    <nav class="nav-menu" aria-label="Seções do painel">
      <a class="nav-item" href="#dashboard" data-view="dashboard" aria-current="page">
        <svg class="icone" aria-hidden="true"><use href="#i-dashboard"/></svg>
        <span class="rot">Dashboard</span>
      </a>
      <a class="nav-item" href="#produtos" data-view="produtos">
        <svg class="icone" aria-hidden="true"><use href="#i-tag"/></svg>
        <span class="rot">Produtos</span>
      </a>
      <a class="nav-item" href="#links" data-view="links">
        <svg class="icone" aria-hidden="true"><use href="#i-link"/></svg>
        <span class="rot">Links</span>
        <span class="nav-badge" id="navLinkCount">0</span>
      </a>
      <a class="nav-item" href="#plataformas" data-view="plataformas">
        <svg class="icone" aria-hidden="true"><use href="#i-layers"/></svg>
        <span class="rot">Plataformas</span>
      </a>
      <a class="nav-item" href="#config" data-view="config">
        <svg class="icone" aria-hidden="true"><use href="#i-sliders"/></svg>
        <span class="rot">Configurações</span>
      </a>
      <a class="nav-item" href="#logs" data-view="logs">
        <svg class="icone" aria-hidden="true"><use href="#i-terminal"/></svg>
        <span class="rot">Logs</span>
      </a>
      <a class="nav-item" href="#suporte" data-view="suporte">
        <svg class="icone" aria-hidden="true"><use href="#i-headset"/></svg>
        <span class="rot">Suporte</span>
      </a>
    </nav>

    <div class="sidebar-rodape">
      <button type="button" class="bot-cartao" id="botCartao" aria-live="polite">
        <span class="ponto" id="ladoPonto" aria-hidden="true"></span>
        <span class="bot-cartao-texto">
          <b id="ladoTitulo">Bot parado</b>
          <small id="ladoSub">Aguardando início</small>
        </span>
        <svg class="icone icone-sm" aria-hidden="true"><use id="ladoIcone" href="#i-play"/></svg>
      </button>
      <p class="sidebar-nota">
        <strong>Ofertas Pro 2.0</strong><br>
        <span id="ladoSessao">Servidor local — nada sai do seu PC.</span>
      </p>
      <button type="button" class="btn btn-fantasma btn-bloco" id="btnSair"
              hidden onclick="sair()">
        <svg class="icone icone-sm" aria-hidden="true"><use href="#i-log-in"/></svg>
        Sair do painel
      </button>
    </div>
  </aside>

  <!-- ══ Conteúdo ════════════════════════════════════════════════════ -->
  <main class="main-wrapper" id="conteudo">

    <header class="top-header">
      <div class="saudacao">
        <h2>
          <svg class="icone" aria-hidden="true"><use href="#i-wave"/></svg>
          Olá, por aqui
        </h2>
        <p>Acompanhe o que o bot postou, ligue e desligue o serviço e ajuste suas credenciais — tudo neste painel.</p>
      </div>

      <div class="header-acoes">
        <span class="status-pill" id="headerPill" data-ligado="0">
          <span class="ponto" id="headerPonto" aria-hidden="true"></span>
          <span id="headerTexto">Bot parado</span>
        </span>

        <div class="relogio">
          <div class="hora" id="relogioHora">--:--</div>
          <div class="data" id="relogioData">--/--/----</div>
        </div>

        <div class="perfil">
          <span class="avatar" aria-hidden="true"><svg class="icone"><use href="#i-user"/></svg></span>
          <span class="perfil-texto">
            <b>Você</b>
            <small id="perfilDono">ID não detectado</small>
          </span>
        </div>

        <button type="button" class="btn btn-primario" onclick="abrirModalLink()">
          <svg class="icone icone-sm" aria-hidden="true"><use href="#i-link"/></svg>
          Gerar link
        </button>
      </div>
    </header>

    <!-- ── Dashboard ──────────────────────────────────────────────── -->
    <section class="view ativa" id="view-dashboard" aria-labelledby="t-dash">
      <h2 class="so-leitor" id="t-dash">Dashboard</h2>

      <section class="grade-4" aria-label="Marketplaces">
        <article class="mp-card">
          <div class="mp-logo-caixa">
            <img src="/assets/mercadolivre.png" alt="Mercado Livre" class="mp-logo-img">
          </div>
          <h4>Mercado Livre</h4>
          <span class="selo selo-espera" id="seloMl"><span class="ponto" aria-hidden="true"></span>Não configurado</span>
          <span class="mp-sub" id="subMl">Sem credenciais</span>
          <button type="button" class="btn btn-neutro" onclick="gerenciarPlataforma('mercadolivre')">Configurar</button>
        </article>

        <article class="mp-card">
          <div class="mp-logo-caixa">
            <img src="/assets/amazon.png" alt="Amazon" class="mp-logo-img">
          </div>
          <h4>Amazon</h4>
          <span class="selo selo-espera" id="seloAmz"><span class="ponto" aria-hidden="true"></span>Não configurado</span>
          <span class="mp-sub" id="subAmz">Sem tag de associado</span>
          <button type="button" class="btn btn-neutro" onclick="gerenciarPlataforma('amazon')">Configurar</button>
        </article>

        <article class="mp-card">
          <div class="mp-logo-caixa">
            <img src="/assets/shopee.png" alt="Shopee" class="mp-logo-img">
          </div>
          <h4>Shopee</h4>
          <span class="selo selo-espera" id="seloShp"><span class="ponto" aria-hidden="true"></span>Não configurado</span>
          <span class="mp-sub" id="subShp">Sem credenciais de API</span>
          <button type="button" class="btn btn-neutro" onclick="gerenciarPlataforma('shopee')">Configurar</button>
        </article>

        <article class="mp-card">
          <div class="mp-logo-caixa">
            <img src="/assets/aliexpress.png" alt="AliExpress" class="mp-logo-img">
          </div>
          <h4>AliExpress</h4>
          <span class="selo selo-espera" id="seloAli"><span class="ponto" aria-hidden="true"></span>Não configurado</span>
          <span class="mp-sub" id="subAli">Sem credenciais de API</span>
          <button type="button" class="btn btn-neutro" onclick="gerenciarPlataforma('aliexpress')">Configurar</button>
        </article>
      </section>

      <div class="dash-grade">
        <div class="coluna">
          <section class="metricas" aria-label="Indicadores">
            <article class="card">
              <div class="metrica-topo">
                <div>
                  <div class="card-titulo">
                    <svg class="icone icone-sm" aria-hidden="true"><use href="#i-bar-chart"/></svg>
                    <h4>Ofertas postadas</h4>
                  </div>
                  <div class="metrica-rotulo">Últimos 7 dias</div>
                </div>
                <div>
                  <div class="metrica-valor" id="valSemana">0</div>
                  <div class="metrica-delta parado" id="deltaSemana">estável</div>
                </div>
              </div>
              <div class="grafico-caixa">
                <canvas id="graficoSemana" role="img"
                        aria-label="Ofertas postadas por dia nos últimos 7 dias"></canvas>
              </div>
            </article>

            <article class="card">
              <div class="metrica-topo">
                <div>
                  <div class="card-titulo">
                    <svg class="icone icone-sm" aria-hidden="true"><use href="#i-award"/></svg>
                    <h4>Histórico total</h4>
                  </div>
                  <div class="metrica-rotulo">Tudo que já foi publicado</div>
                </div>
                <div>
                  <div class="metrica-valor" id="valTotal">0</div>
                  <div class="metrica-delta parado">no banco</div>
                </div>
              </div>
              <div class="metrica-topo" style="margin:0; padding-top:12px; border-top:1px solid var(--borda-sutil);">
                <div>
                  <div class="metrica-rotulo">Última publicação</div>
                  <div style="font-size:17px; font-weight:800; letter-spacing:-0.3px; margin-top:2px;" id="valUltima">nenhuma ainda</div>
                </div>
                <div style="text-align:right">
                  <div class="metrica-rotulo">Hoje</div>
                  <div style="font-size:17px; font-weight:800; margin-top:2px;" id="valHoje">0</div>
                </div>
              </div>
            </article>
          </section>

          <section class="card" aria-labelledby="t-top">
            <div class="card-topo">
              <div>
                <div class="card-titulo">
                  <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chart"/></svg>
                  <h4 id="t-top">Ofertas por plataforma</h4>
                </div>
                <div class="metrica-rotulo">Distribuição de tudo que já foi postado</div>
              </div>
              <button type="button" class="btn btn-fantasma" onclick="switchView('produtos')">
                Ver produtos
                <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-right"/></svg>
              </button>
            </div>
            <div class="top-lista" id="topLista"></div>
          </section>

          <section class="card" aria-labelledby="t-ativ">
            <div class="card-topo">
              <div>
                <div class="card-titulo">
                  <svg class="icone icone-sm" aria-hidden="true"><use href="#i-history"/></svg>
                  <h4 id="t-ativ">Publicações recentes</h4>
                </div>
                <div class="metrica-rotulo">Últimas ofertas que chegaram ao canal</div>
              </div>
              <button type="button" class="btn btn-fantasma" onclick="switchView('logs')">
                Ver logs
                <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-right"/></svg>
              </button>
            </div>
            <div class="atividade" id="atividadeLista"></div>
          </section>
        </div>

        <div class="coluna">
          <section class="card" aria-labelledby="t-builder">
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-link"/></svg>
              <h4 id="t-builder">Link builder</h4>
            </div>
            <p class="card-sub" style="margin:7px 0 14px;">
              Transforme qualquer link de produto em link com a sua tag de afiliado.
            </p>
            <button type="button" class="btn btn-primario btn-bloco" onclick="abrirModalLink()">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-sparkles"/></svg>
              Abrir link builder
            </button>
            <button type="button" class="btn btn-neutro btn-bloco" style="margin-top:8px;"
                    onclick="executarCiclo()" id="btnCiclo">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-refresh"/></svg>
              Rodar um ciclo agora
            </button>
          </section>

          <section class="card" aria-labelledby="t-links">
            <div class="card-topo" style="margin-bottom:10px">
              <div class="card-titulo">
                <svg class="icone icone-sm" aria-hidden="true"><use href="#i-link"/></svg>
                <h4 id="t-links">Links do canal</h4>
              </div>
              <button type="button" class="btn btn-fantasma" onclick="switchView('links')">
                Ver todos
                <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-right"/></svg>
              </button>
            </div>
            <div class="link-lista" id="linksRecentes"></div>
          </section>
        </div>
      </div>
    </section>

    <!-- ── Produtos ──────────────────────────────────────────────── -->
    <section class="view" id="view-produtos" aria-labelledby="t-prod">
      <div class="card">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-tag"/></svg>
              <h3 id="t-prod">Produtos publicados</h3>
            </div>
            <p class="card-sub">Tudo que o bot postou no canal, do mais novo para o mais antigo.</p>
          </div>
          <button type="button" class="btn btn-neutro" onclick="carregarProdutos()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-refresh"/></svg>
            Atualizar
          </button>
        </div>
        <div class="tabela-caixa">
          <table class="tabela">
            <thead>
              <tr>
                <th scope="col">Plataforma</th>
                <th scope="col">Título</th>
                <th scope="col">Preço</th>
                <th scope="col">Publicado em</th>
                <th scope="col">Link</th>
              </tr>
            </thead>
            <tbody id="produtosCorpo">
              <tr><td colspan="5"><div class="vazio">Carregando…</div></td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ── Links ─────────────────────────────────────────────────── -->
    <section class="view" id="view-links" aria-labelledby="t-links2">
      <div class="card">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-link"/></svg>
              <h3 id="t-links2">Links de afiliado</h3>
            </div>
            <p class="card-sub">Os links reais gravados a cada postagem. Clique para abrir ou copie.</p>
          </div>
          <button type="button" class="btn btn-primario" onclick="abrirModalLink()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-link"/></svg>
            Gerar link
          </button>
        </div>
        <div class="link-lista" id="linksTodos"></div>
      </div>
    </section>

    <!-- ── Plataformas ──────────────────────────────────────────── -->
    <section class="view" id="view-plataformas" aria-labelledby="t-plat">
      <div class="card">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-layers"/></svg>
              <h3 id="t-plat">Plataformas</h3>
            </div>
            <p class="card-sub">Configure suas contas e mantenha suas conexões ativas.</p>
          </div>
          <div style="display:flex; gap:8px; flex-wrap:wrap">
            <button type="button" class="btn btn-neutro" id="btnInstalarNav" onclick="executarAcao('instalar-navegador')">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-download"/></svg>
              <span id="btnInstalarNavTxt">Instalar navegador</span>
            </button>
            <button type="button" class="btn btn-primario" id="btnCicloPlat" onclick="executarCiclo()">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-play"/></svg>
              Rodar um ciclo
            </button>
          </div>
        </div>
        <div class="alerta alerta-info">
          <svg class="icone" aria-hidden="true"><use href="#i-alert"/></svg>
          <div id="resumoAmbiente">Aguardando o diagnóstico do ambiente…</div>
        </div>
      </div>

      <div class="plato-grade" id="blocosPlataforma"></div>

      <div class="card">
        <div class="card-topo" style="margin-bottom:10px">
          <div class="card-titulo">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-terminal"/></svg>
            <h4>Saída dos testes</h4>
          </div>
          <button type="button" class="btn btn-neutro btn-sm" onclick="limparTerminal('acao')">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-trash"/></svg>
            Limpar
          </button>
        </div>
        <div class="terminal" style="height:210px">
          <div class="terminal-corpo" id="terminalAcaoPlataformas"></div>
        </div>
      </div>
    </section>

    <!-- Drawer de configuracao. Fica antes dos dois modais no DOM de
         proposito: `aoTeclarModal` fecha e prende o foco no ultimo
         `.overlay.aberto`, e assim um modal aberto de dentro do drawer
         (Detalhes da sessao) e o que ganha o Escape. -->
    <div class="overlay overlay-gaveta" id="gavetaPlataforma" role="dialog" aria-modal="true"
         aria-labelledby="gavetaTitulo" tabindex="-1" hidden>
      <aside class="gaveta" id="gaveta">
        <div class="gaveta-topo">
          <span class="plato-logo" id="gavetaLogoCaixa">
            <img class="plato-logo-img" id="gavetaLogo" src="/assets/mercadolivre.png" alt="" width="40" height="40">
          </span>
          <div class="gaveta-id">
            <h3 id="gavetaTitulo">Configurar</h3>
            <small id="gavetaSub"></small>
          </div>
          <button type="button" class="btn-icone" onclick="fecharGaveta()" aria-label="Fechar">
            <svg class="icone" aria-hidden="true"><use href="#i-x"/></svg>
          </button>
        </div>
        <div class="gaveta-corpo">
          <div id="gavetaResumo"></div>
          <div id="gavetaCamposBloco"></div>
          <div id="gavetaAcoesBloco"></div>
          <!-- O resultado da deteccao precisa cair aqui. A funcao escreveria
               em #caixaDeteccao, que esta na aba Configuracoes: quem clica
               em "Detectar IDs" dentro da gaveta veria o resultado em outra
               aba, fora da tela. -->
          <div id="gavetaDeteccao"></div>
        </div>
        <div class="gaveta-pe">
          <span class="plato-dica" id="gavetaDica" role="status"></span>
          <button type="button" class="btn btn-primario" id="gavetaSalvar"
                  onclick="salvarPlataforma(gavetaChave)">Salvar</button>
        </div>
      </aside>
    </div>

    <!-- ── Configurações ────────────────────────────────────────── -->
    <section class="view" id="view-config" aria-labelledby="t-config">
      <nav class="config-nav" id="configNav" aria-label="Seções de Configurações">
        <a href="#sec-conta"><svg class="icone-sm" aria-hidden="true"><use href="#i-shield"/></svg>Conta</a>
        <a href="#sec-oferta"><svg class="icone-sm" aria-hidden="true"><use href="#i-package"/></svg>O que posta</a>
        <a href="#sec-cadencia"><svg class="icone-sm" aria-hidden="true"><use href="#i-clock"/></svg>Cadência</a>
        <a href="#sec-fontes"><svg class="icone-sm" aria-hidden="true"><use href="#i-megaphone"/></svg>Fontes</a>
        <span class="pendente" id="configPendente" role="status">
          <svg class="icone-sm" aria-hidden="true"><use href="#i-alert-triangle"/></svg>
          Falta salvar
        </span>
      </nav>

      <section class="config-secao" id="sec-conta" aria-labelledby="t-sec-conta">
        <h2 class="config-secao-titulo" id="t-sec-conta">
          <svg class="icone-sm" aria-hidden="true"><use href="#i-shield"/></svg>Conta e integrações
        </h2>

      <div class="card">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-sliders"/></svg>
              <h3 id="t-config">Credenciais</h3>
            </div>
            <p class="card-sub">Salvas no arquivo <code>.env</code> da pasta do projeto. Campos de segredo nunca são enviados de volta para a tela.</p>
          </div>
        </div>

        <form id="formConfig" class="config-grade" novalidate>
          <div class="vazio" style="grid-column:1/-1">Carregando campos…</div>
        </form>

        <div class="acoes-form">
          <button type="submit" form="formConfig" class="btn btn-primario" id="btnSalvarConfig">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
            Salvar credenciais
          </button>
          <span id="configAviso" aria-live="polite"></span>
        </div>

        <!-- Saida da deteccao de ids. O botao que a disparava foi da pagina:
             a gaveta do Telegram faz isso agora, e um botao aqui duplicava a
             mesma acao em dois lugares. A tecla "?" continua usando esta
             caixa, e por isso ela continua aqui. -->
        <div id="caixaDeteccao" style="margin-top:16px"></div>
      </div>

      <div class="card" id="cardConta">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-shield"/></svg>
              <h3>Acesso ao painel</h3>
            </div>
            <p class="card-sub" id="contaSub">Verificando…</p>
          </div>
          <span id="contaEstado"></span>
        </div>

        <form id="formConta" class="config-grade" novalidate>
          <div class="vazio" style="grid-column:1/-1">Carregando…</div>
        </form>

        <div class="forca" id="forcaCaixa" hidden>
          <div class="forca-barra"><span id="forcaFill"></span></div>
          <span class="forca-texto" id="forcaTexto"></span>
        </div>

        <div class="acoes-form">
          <button type="submit" form="formConta" class="btn btn-primario" id="btnSalvarConta">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-shield"/></svg>
            <span id="btnSalvarContaTexto">Criar conta</span>
          </button>
          <button type="button" class="btn btn-perigo" id="btnRemoverConta" hidden>
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-trash"/></svg>
            Remover acesso
          </button>
          <span id="contaAviso" aria-live="polite"></span>
        </div>
      </div>
      </section>

      <section class="config-secao" id="sec-oferta" aria-labelledby="t-sec-oferta">
        <h2 class="config-secao-titulo" id="t-sec-oferta">
          <svg class="icone-sm" aria-hidden="true"><use href="#i-package"/></svg>O que o bot posta
        </h2>

      <div class="card">
        <div class="card-titulo">
          <svg class="icone" aria-hidden="true"><use href="#i-store"/></svg>
          <h3>Categorias do canal</h3>
        </div>
        <p class="card-sub">
          Marque os nichos que o bot deve buscar. <strong style="color:var(--texto)">Nada marcado = todas as categorias.</strong>
        </p>
        <div class="nichos" id="nichosGrade" role="group" aria-label="Nichos de produto"></div>
        <div class="acoes-form">
          <button type="button" class="btn btn-primario" onclick="salvarNichos()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
            Salvar categorias
          </button>
          <button type="button" class="btn btn-neutro" onclick="limparNichos()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-x"/></svg>
            Limpar seleção
          </button>
          <span id="nichosContador" class="metrica-rotulo" aria-live="polite"></span>
        </div>
      </div>

      <!-- Filtros de Produtos -->
      <div class="card" id="cardFiltros">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-sliders"/></svg>
              <h3>Filtros de Produtos</h3>
            </div>
            <p class="card-sub">Critérios de qualidade aplicados no pipeline de captura (scraping e APIs). Produtos reprovados são ignorados com log do motivo.</p>
          </div>
        </div>

        <form id="formFiltros" class="config-grade" novalidate>
          <div class="campo">
            <label for="filtroAvaliacao"><svg class="icone-sm" aria-hidden="true"><use href="#i-award"/></svg>Avaliação mínima</label>
            <select id="filtroAvaliacao" name="avaliacao_minima">
              <option value="0">Desativado (qualquer nota)</option>
              <option value="4">4.0 ou mais</option>
              <option value="4.2">4.2 ou mais</option>
              <option value="4.5">4.5 ou mais (Recomendado)</option>
              <option value="4.7">4.7 ou mais</option>
              <option value="5">5.0 (nota máxima)</option>
            </select>
            <p class="ajuda">AliExpress (96% → 4.8) e demais plataformas com nota real.</p>
          </div>

          <div class="campo">
            <label for="filtroVendas"><svg class="icone-sm" aria-hidden="true"><use href="#i-shopping-bag"/></svg>Vendas mínimas</label>
            <select id="filtroVendas" name="vendas_minimas">
              <option value="0">Desativado (qualquer volume)</option>
              <option value="10">10+ vendas</option>
              <option value="50">50+ vendas</option>
              <option value="100">100+ vendas (Recomendado)</option>
              <option value="500">500+ vendas</option>
              <option value="1000">1.000+ vendas</option>
              <option value="5000">5.000+ vendas</option>
              <option value="10000">10.000+ vendas</option>
            </select>
            <p class="ajuda">Volume comprovado de vendas da oferta.</p>
          </div>

          <div class="campo">
            <label for="filtroDesconto"><svg class="icone-sm" aria-hidden="true"><use href="#i-tag"/></svg>Desconto mínimo (%)</label>
            <input id="filtroDesconto" name="desconto_minimo_pct" type="number" min="0" max="99" value="0" placeholder="0">
            <p class="ajuda">Percentual mínimo de desconto real quando fornecido.</p>
          </div>

          <div class="campo">
            <label for="filtroPrecoMin"><svg class="icone-sm" aria-hidden="true"><use href="#i-tag"/></svg>Faixa de preço (R$)</label>
            <div style="display:flex; gap:8px; align-items:center;">
              <input id="filtroPrecoMin" name="preco_minimo" type="number" step="0.5" min="0" placeholder="Mín (ex: 5)" style="flex:1">
              <span style="color:var(--texto-3)">até</span>
              <input id="filtroPrecoMax" name="preco_maximo" type="number" step="1" min="0" placeholder="Máx (ex: 5000)" style="flex:1">
            </div>
            <p class="ajuda">Deixe em branco para não limitar por valor.</p>
          </div>

          <div class="campo">
            <label for="filtroSemAvaliacao">Política: Sem informação de estrelas</label>
            <select id="filtroSemAvaliacao" name="permitir_sem_avaliacao">
              <option value="true">Permitir produto (não descartar)</option>
              <option value="false">Ignorar produto (exigir estrelas)</option>
            </select>
            <p class="ajuda">Quando o marketplace não informa a avaliação.</p>
          </div>

          <div class="campo">
            <label for="filtroSemVendas">Política: Sem informação de vendas</label>
            <select id="filtroSemVendas" name="permitir_sem_vendas">
              <option value="true">Permitir produto (não descartar)</option>
              <option value="false">Ignorar produto (exigir vendas)</option>
            </select>
            <p class="ajuda">Quando o marketplace não informa quantidade vendida.</p>
          </div>

          <div class="campo" style="grid-column:1/-1">
            <label for="filtroSemDesconto">Política: Produto sem desconto explícito</label>
            <select id="filtroSemDesconto" name="permitir_sem_desconto">
              <option value="true">Permitir e postar preço atual / cupom (não inventar preço "De / Por")</option>
              <option value="false">Ignorar produtos sem desconto real</option>
            </select>
            <p class="ajuda">Se aprovado sem preço anterior, o bot posta direto: R$ 49,90 e cupom, sem inventar percentuais falsos.</p>
          </div>
        </form>

        <div class="acoes-form">
          <button type="button" class="btn btn-primario" onclick="salvarFiltros()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
            Salvar filtros de produtos
          </button>
          <span id="filtrosAviso" class="metrica-rotulo" aria-live="polite"></span>
        </div>
      </div>
      </section>

      <section class="config-secao" id="sec-cadencia" aria-labelledby="t-sec-cadencia">
        <h2 class="config-secao-titulo" id="t-sec-cadencia">
          <svg class="icone-sm" aria-hidden="true"><use href="#i-clock"/></svg>Com que frequência posta
        </h2>

      <!-- A cadência que roda de verdade. Estes cinco campos são o bloco
           `geral` do config.yaml: o intervalo do job que dispara o ciclo, quantas
           ofertas o ciclo escolhe, o sleep entre uma e outra, a janela de não
           repetir e o portão de horário. A página só expunha o bloco
           `publicacao` (o card ao lado, que está zerado e por isso não muda
           nada no bot) — ou seja, o ritmo que o bot usava aparecia só dentro de
           uma frase de status e não tinha onde ser ajustado. -->
      <div class="card" id="cardCadencia">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-wave"/></svg>
              <h3>Cadência das publicações</h3>
            </div>
            <p class="card-sub">O ritmo que o bot segue de verdade. O bot em execução lê estes valores quando sobe: mudar aqui vale no próximo start, sem precisar reiniciar o painel.</p>
          </div>
        </div>

        <form id="formCadencia" class="config-grade" novalidate>
          <div class="campo">
            <label for="cadIntervalo"><svg class="icone-sm" aria-hidden="true"><use href="#i-clock"/></svg>Intervalo entre ciclos (minutos)</label>
            <input id="cadIntervalo" name="intervalo_minutos" type="number" min="0" step="1" value="45" placeholder="45">
            <p class="ajuda">De quanto em quanto tempo o bot roda um ciclo. 0 = não roda sozinho.</p>
          </div>

          <div class="campo">
            <label for="cadMaxPosts"><svg class="icone-sm" aria-hidden="true"><use href="#i-package"/></svg>Máximo de ofertas por ciclo</label>
            <input id="cadMaxPosts" name="max_posts_por_ciclo" type="number" min="0" step="1" value="3" placeholder="3">
            <p class="ajuda">Quantas ofertas ele pode escolher no ciclo. 0 = nenhuma.</p>
          </div>

          <div class="campo">
            <label for="cadEspacamento"><svg class="icone-sm" aria-hidden="true"><use href="#i-wave"/></svg>Espaçamento entre posts (segundos)</label>
            <input id="cadEspacamento" name="espacamento_segundos" type="number" min="0" step="1" value="120" placeholder="120">
            <p class="ajuda">Pausa entre uma oferta e a seguinte. É o que evita o Telegram derrubar a conta.</p>
          </div>

          <div class="campo">
            <label for="cadNaoRepetir"><svg class="icone-sm" aria-hidden="true"><use href="#i-history"/></svg>Não repetir a mesma oferta (dias)</label>
            <input id="cadNaoRepetir" name="nao_repetir_dias" type="number" min="0" step="1" value="7" placeholder="7">
            <p class="ajuda">Janela de deduplicação. 7 = não reposta a mesma oferta por uma semana.</p>
          </div>

          <div class="campo">
            <label for="cadHorario"><svg class="icone-sm" aria-hidden="true"><use href="#i-power"/></svg>Horário ativo</label>
            <input id="cadHorario" name="horario_ativo" type="text" value="" placeholder="24h" autocomplete="off" spellcheck="false">
            <p class="ajuda">Janela em que posta: <code>08:00-23:00</code>. Vazio ou <code>24h</code> = a qualquer hora.</p>
          </div>
        </form>

        <div class="acoes-form">
          <button type="button" class="btn btn-primario" onclick="salvarCadencia()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
            Salvar cadência
          </button>
          <span id="cadAviso" class="metrica-rotulo" aria-live="polite"></span>
        </div>
      </div>

      <!-- Controle de Publicação e Agendamento -->
      <div class="card" id="cardPublicacao">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-clock"/></svg>
              <h3>Blocos e pausas automáticas</h3>
            </div>
            <p class="card-sub">Camada extra por cima da cadência: posting em rajada, com pausa depois de N posts, e um teto por período. Está zerado, então hoje não muda nada no bot.</p>
          </div>
        </div>

        <form id="formPublicacao" class="config-grade" novalidate>
          <div class="campo">
            <label for="pubIntervalo"><svg class="icone-sm" aria-hidden="true"><use href="#i-clock"/></svg>Intervalo mínimo entre posts (minutos)</label>
            <input id="pubIntervalo" name="intervalo_entre_posts_minutos" type="number" min="0" step="1" value="5" placeholder="5">
            <p class="ajuda">Ex: 5 = 5 minutos entre uma oferta e outra (0 = sem intervalo).</p>
          </div>

          <div class="campo">
            <label for="pubPostsAntesPausa"><svg class="icone-sm" aria-hidden="true"><use href="#i-layers"/></svg>Posts antes da pausa</label>
            <input id="pubPostsAntesPausa" name="posts_antes_pausa" type="number" min="0" value="5" placeholder="5">
            <p class="ajuda">Quantidade de posts num bloco antes de entrar em pausa (0 = desativado).</p>
          </div>

          <div class="campo">
            <label for="pubTempoPausa"><svg class="icone-sm" aria-hidden="true"><use href="#i-stop"/></svg>Duração da pausa (minutos)</label>
            <input id="pubTempoPausa" name="tempo_pausa_minutos" type="number" min="0" step="1" value="30" placeholder="30">
            <p class="ajuda">Ex: 30 = 30 minutos de descanso antes do próximo bloco (0 = sem pausa).</p>
          </div>

          <div class="campo">
            <label for="pubMaxPosts"><svg class="icone-sm" aria-hidden="true"><use href="#i-bar-chart"/></svg>Limite máximo de posts por período</label>
            <input id="pubMaxPosts" name="max_posts_periodo" type="number" min="0" value="20" placeholder="20">
            <p class="ajuda">Ex: 20 posts no período de segurança (0 = sem limite).</p>
          </div>

          <div class="campo">
            <label for="pubPeriodoHoras"><svg class="icone-sm" aria-hidden="true"><use href="#i-history"/></svg>Janela do período (horas)</label>
            <input id="pubPeriodoHoras" name="periodo_horas" type="number" min="1" value="24" placeholder="24">
            <p class="ajuda">Período de rotação do limite (padrão: 24 horas).</p>
          </div>

          <div class="campo">
            <label><svg class="icone-sm" aria-hidden="true"><use href="#i-wave"/></svg>Status da Cadência em Tempo Real</label>
            <div id="pubStatusCadencia" class="painel-info" style="font-size:12.5px; padding:10px 14px;">
              Carregando estado de publicação…
            </div>
          </div>
        </form>

        <div class="acoes-form">
          <button type="button" class="btn btn-primario" onclick="salvarPublicacao()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
            Salvar controle de publicação
          </button>
          <button type="button" class="btn btn-neutro" onclick="resetarCadenciaPublicacao()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-refresh"/></svg>
            Zerar contadores de cadência
          </button>
          <span id="pubAviso" class="metrica-rotulo" aria-live="polite"></span>
        </div>
      </div>
      </section>

      <section class="config-secao" id="sec-fontes" aria-labelledby="t-sec-fontes">
        <h2 class="config-secao-titulo" id="t-sec-fontes">
          <svg class="icone-sm" aria-hidden="true"><use href="#i-megaphone"/></svg>De onde vêm as ofertas
        </h2>

      <!-- Fontes de Scraping Telegram. Era um card so com as tres coisas
           dentro (adicionar, tabela e configuracao do robo). Na grade de duas
           colunas isso dava um card altissimo e meio vazio, entao virou tres:
           dois de meia linha e a tabela na linha inteira — cinco colunas de
           dados espremidas em meia tela viram um garrancho. -->
      <div class="card" id="cardNovaFonteTelegram">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-send"/></svg>
              <h3>Adicionar fonte Telegram</h3>
            </div>
            <p class="card-sub">Canais e supergrupos públicos de ofertas, por @username. O scraper extrai, filtra e joga na fila de publicação.</p>
          </div>
        </div>

        <form id="formNovaFonteTelegram" class="config-grade" novalidate onsubmit="adicionarFonteTelegram(event)">
          <div class="campo">
            <label for="novaFonteUsername">@username ou link público</label>
            <input id="novaFonteUsername" name="username" type="text" placeholder="@canal_ofertas ou t.me/canal_ofertas" autocomplete="off" spellcheck="false" required>
            <p class="ajuda">Canais públicos e supergrupos compatíveis.</p>
          </div>
          <div class="campo">
            <label for="novaFonteNome">Nome amigável</label>
            <input id="novaFonteNome" name="nome" type="text" placeholder="Ex: Canal Ofertas Promo" autocomplete="off" spellcheck="false">
            <p class="ajuda">Identificação nos logs e relatórios.</p>
          </div>
          <div class="acoes-form" style="grid-column:1/-1; margin-top:6px; padding-top:10px;">
            <button type="submit" class="btn btn-primario btn-sm">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
              Salvar fonte
            </button>
            <button type="button" class="btn btn-neutro btn-sm" onclick="testarConexaoFonteNova()">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-search"/></svg>
              Testar conexão
            </button>
            <span id="novaFonteAviso" class="metrica-rotulo" aria-live="polite"></span>
          </div>
        </form>
      </div>

      <div class="card" id="cardScraping">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-cpu"/></svg>
              <h3>Robô de scraping</h3>
            </div>
            <p class="card-sub">Com que frequência ele varre os canais cadastrados e quantas mensagens leva por rodada.</p>
          </div>
        </div>

        <form id="formScrapingCfg" class="config-grade" novalidate>
          <div class="campo">
            <label for="scrapingAtivo">Status do Scraper</label>
            <select id="scrapingAtivo" name="ativo">
              <option value="true">Scraping Ativo</option>
              <option value="false">Scraping Desativado</option>
            </select>
          </div>
          <div class="campo">
            <label for="scrapingIntervalo">Intervalo de varredura (segundos)</label>
            <input id="scrapingIntervalo" name="intervalo_segundos" type="number" min="5" value="30" placeholder="30">
          </div>
          <div class="campo">
            <label for="scrapingLimiteMsg">Máx. mensagens por ciclo</label>
            <!-- teto 500: é o que o backend aceita e valida. Com max=100 a
                 tela recusava valores válidos e o usuário não conseguia
                 aumentar o ciclo. -->
            <input id="scrapingLimiteMsg" name="limite_mensagens_por_ciclo" type="number" min="1" max="500" value="20" placeholder="20">
          </div>
        </form>
        <div class="acoes-form">
          <button type="button" class="btn btn-neutro btn-sm" onclick="salvarConfigScraping()">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-save"/></svg>
            Salvar configurações do scraper
          </button>
          <span id="scrapingCfgAviso" class="metrica-rotulo" aria-live="polite"></span>
        </div>
      </div>

      <div class="card config-largo" id="cardFontesTelegram">
        <div class="card-topo">
          <div>
            <div class="card-titulo">
              <svg class="icone" aria-hidden="true"><use href="#i-megaphone"/></svg>
              <h3>Fontes cadastradas</h3>
            </div>
            <p class="card-sub">O que o robô está lendo agora, e quando foi a última vez que cada canal entregou oferta.</p>
          </div>
        </div>

        <div class="tabela-caixa">
          <table class="tabela">
            <thead>
              <tr>
                <th>Fonte / Nome</th>
                <th>@Username</th>
                <th>Status</th>
                <th>Última Captura</th>
                <th style="text-align:right">Ações</th>
              </tr>
            </thead>
            <tbody id="tabelaFontesTelegramCorpo">
              <tr><td colspan="5" style="text-align:center; padding:18px;">Carregando fontes…</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      </section>
    </section>

    <!-- ── Logs ─────────────────────────────────────────────────── -->
    <section class="view" id="view-logs" aria-labelledby="t-logs">
      <h2 class="so-leitor" id="t-logs">Logs</h2>
      <div class="logs-grade">
        <div class="terminal">
          <div class="terminal-topo">
            <span class="rot">
              <span class="ponto" id="logBotPonto" aria-hidden="true"></span>
              Log do bot
            </span>
            <button type="button" class="btn btn-neutro btn-sm" onclick="limparTerminal('bot')">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-trash"/></svg>
              Limpar
            </button>
          </div>
          <div class="terminal-corpo" id="terminalBot" tabindex="0" role="log" aria-live="off" aria-label="Log contínuo do bot"></div>
        </div>
        <div class="terminal">
          <div class="terminal-topo">
            <span class="rot">
              <span class="ponto" id="logAcaoPonto" aria-hidden="true"></span>
              Ações e testes
            </span>
            <button type="button" class="btn btn-neutro btn-sm" onclick="limparTerminal('acao')">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-trash"/></svg>
              Limpar
            </button>
          </div>
          <div class="terminal-corpo" id="terminalAcao" tabindex="0" role="log" aria-live="off" aria-label="Log de ações e testes"></div>
        </div>
      </div>
    </section>

    <!-- ── Suporte ──────────────────────────────────────────────── -->
    <section class="view" id="view-suporte" aria-labelledby="t-sup">
      <div class="card">
        <div class="card-titulo">
          <svg class="icone" aria-hidden="true"><use href="#i-headset"/></svg>
          <h3 id="t-sup">Central de ajuda</h3>
        </div>
        <p class="card-sub">As dúvidas que mais aparecem, e o diagnóstico do seu ambiente.</p>

        <h4 style="font-size:12px; text-transform:uppercase; letter-spacing:0.7px; color:var(--texto-3); margin:20px 0 10px">Diagnóstico</h4>
        <div class="diagnostico" id="diagnostico"></div>

        <h4 style="font-size:12px; text-transform:uppercase; letter-spacing:0.7px; color:var(--texto-3); margin:22px 0 10px">Perguntas frequentes</h4>
        <div class="faq">
          <details>
            <summary>
              <svg class="icone icone-sm" style="color:var(--primaria-forte)" aria-hidden="true"><use href="#i-key"/></svg>
              Como pego o token do bot?
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-down"/></svg>
            </summary>
            <div class="faq-corpo">
              No Telegram, procure por <code>@BotFather</code>, envie <code>/newbot</code> e siga os passos.
              Ele devolve um token — cole em <strong>Token do bot</strong> e salve. Guarde esse token em
              lugar seguro: quem tem ele controla o bot.
            </div>
          </details>
          <details>
            <summary>
              <svg class="icone icone-sm" style="color:var(--primaria-forte)" aria-hidden="true"><use href="#i-search"/></svg>
              Como descubro meu ID e o ID do canal?
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-down"/></svg>
            </summary>
            <div class="faq-corpo">
              Adicione o bot como administrador do canal. Mande <code>/id</code> no privado dele e
              encaminhe qualquer post do canal para o mesmo chat — as duas respostas trazem os IDs.
              Depois use <strong>Detectar IDs do Telegram</strong> em Configurações para preencher os campos.
            </div>
          </details>
          <details>
            <summary>
              <svg class="icone icone-sm" style="color:var(--primaria-forte)" aria-hidden="true"><use href="#i-lock"/></svg>
              Como funciona o login do Mercado Livre?
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-down"/></svg>
            </summary>
            <div class="faq-corpo">
              Em Plataformas, use <strong>Fazer login</strong>. Abre um navegador na sua tela para você
              entrar na conta de afiliado. A sessão fica salva em <code>data/ml_profile</code> e é usada
              só pelo link builder — nada é enviado para fora do seu computador.
            </div>
          </details>
          <details>
            <summary>
              <svg class="icone icone-sm" style="color:var(--primaria-forte)" aria-hidden="true"><use href="#i-alert-triangle"/></svg>
              O bot posta nada. O que verifico?
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-chevron-down"/></svg>
            </summary>
            <div class="faq-corpo">
              Na ordem: o <strong>horário ativo</strong> no <code>config.yaml</code> (por padrão só posta das
              08:00 às 23:00); se o token do canal está certo; e a aba <strong>Logs</strong>, que mostra o motivo
              de cada ciclo pulado. Se aparecer “sem link de afiliado”, refaça o login do Mercado Livre.
            </div>
          </details>
        </div>
      </div>
    </section>

    <footer class="rodape">
      <span class="esq">
        <svg class="icone icone-sm" aria-hidden="true"><use href="#i-shield"/></svg>
        Servidor local — suas credenciais não saem deste computador
      </span>
      <span class="dir">
        <svg class="icone icone-sm" aria-hidden="true"><use href="#i-refresh"/></svg>
        Atualizado em <span id="rodapeHora">--/--/---- --:--</span>
      </span>
    </footer>
  </main>
</div>

<!-- ══ Modal: link builder ═════════════════════════════════════════════ -->
<div class="overlay" id="modalLink" role="dialog" aria-modal="true" aria-labelledby="modalLinkTitulo" tabindex="-1" hidden>
  <div class="modal">
    <div class="modal-topo">
      <svg class="icone" aria-hidden="true"><use href="#i-link"/></svg>
      <h3 id="modalLinkTitulo">Gerar link de afiliado</h3>
      <button type="button" class="btn btn-icone" data-fechar="modalLink" aria-label="Fechar">
        <svg class="icone" aria-hidden="true"><use href="#i-x"/></svg>
      </button>
    </div>
    <div class="modal-corpo">
      <form id="formLink" novalidate>
        <div class="campo">
          <label for="entradaUrl">Link do produto</label>
          <input type="url" id="entradaUrl" name="url" placeholder="https://www.mercadolivre.com.br/…" autocomplete="off" spellcheck="false">
          <p class="ajuda" id="erroUrl" role="alert"></p>
        </div>
        <div class="campo">
          <label for="entradaPlataforma">Plataforma</label>
          <select id="entradaPlataforma" name="plataforma">
            <option value="">Detectar pelo link</option>
            <option value="mercadolivre">Mercado Livre</option>
            <option value="amazon">Amazon</option>
            <option value="shopee">Shopee</option>
            <option value="aliexpress">AliExpress</option>
          </select>
        </div>
        <div class="resultado-caixa" id="caixaResultado" hidden>
          <div class="rot">
            <svg class="icone icone-sm" aria-hidden="true"><use href="#i-check-circle"/></svg>
            Link pronto para postar
          </div>
          <div class="saida-link">
            <input type="text" id="saidaUrl" readonly aria-label="Link de afiliado gerado">
            <button type="button" class="btn btn-neutro" onclick="copiarSaida()">
              <svg class="icone icone-sm" aria-hidden="true"><use href="#i-copy"/></svg>
              Copiar
            </button>
          </div>
          <p class="ajuda" id="saidaInfo"></p>
        </div>
      </form>
    </div>
    <div class="modal-pe">
      <button type="button" class="btn btn-neutro" data-fechar="modalLink">Fechar</button>
      <button type="submit" form="formLink" class="btn btn-primario" id="btnGerarLink">
        <svg class="icone icone-sm" aria-hidden="true"><use href="#i-sparkles"/></svg>
        Gerar link
      </button>
    </div>
  </div>
</div>

<!-- ══ Modal: sessão do Mercado Livre ══════════════════════════════════ -->
<div class="overlay" id="modalSessao" role="dialog" aria-modal="true" aria-labelledby="modalSessaoTitulo" tabindex="-1" hidden>
  <div class="modal">
    <div class="modal-topo">
      <svg class="icone" aria-hidden="true"><use href="#i-shield"/></svg>
      <h3 id="modalSessaoTitulo">Sessão local do Mercado Livre</h3>
      <button type="button" class="btn btn-icone" data-fechar="modalSessao" aria-label="Fechar">
        <svg class="icone" aria-hidden="true"><use href="#i-x"/></svg>
      </button>
    </div>
    <div class="modal-corpo" id="modalSessaoCorpo">
      <div class="vazio">Verificando a sessão…</div>
    </div>
    <div class="modal-pe">
      <button type="button" class="btn btn-neutro" data-fechar="modalSessao">Fechar</button>
      <button type="button" class="btn btn-primario" onclick="abrirLoginMl()">
        <svg class="icone icone-sm" aria-hidden="true"><use href="#i-key"/></svg>
        Refazer login
      </button>
    </div>
  </div>
</div>

<div class="toasts" id="caixaToasts" role="status" aria-live="polite" aria-atomic="false"></div>

<script>
"use strict";

/* ══ Utilidades ═══════════════════════════════════════════════════════ */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

/** Escapa texto antes de entrar em innerHTML — títulos de produto vêm de fora. */
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const icone = (nome, classe = "icone-sm") =>
  `<svg class="${classe}" aria-hidden="true"><use href="#i-${esc(nome)}"/></svg>`;

const vazio = (titulo, sub = "", ic = "inbox") => `
  <div class="vazio">
    ${icone(ic, "icone")}
    <strong>${esc(titulo)}</strong>
    ${sub ? `<span>${esc(sub)}</span>` : ""}
  </div>`;

const NOME_PLATAFORMA = {
  mercadolivre: "Mercado Livre", amazon: "Amazon",
  shopee: "Shopee", aliexpress: "AliExpress"
};
const ICONE_PLATAFORMA = {
  mercadolivre: "handshake", amazon: "package", shopee: "shopping-bag", aliexpress: "globe"
};
const LOGO_PLATAFORMA = {
  mercadolivre: "/assets/mercadolivre.png",
  "Mercado Livre": "/assets/mercadolivre.png",
  ml: "/assets/mercadolivre.png",
  amazon: "/assets/amazon.png",
  Amazon: "/assets/amazon.png",
  amz: "/assets/amazon.png",
  shopee: "/assets/shopee.png",
  Shopee: "/assets/shopee.png",
  shp: "/assets/shopee.png",
  aliexpress: "/assets/aliexpress.png",
  AliExpress: "/assets/aliexpress.png",
  ali: "/assets/aliexpress.png"
};
const NOME_ICONE_NICHO = {
  cpu: "cpu", smartphone: "smartphone", gamepad: "gamepad", sofa: "sofa", plug: "plug",
  shirt: "shirt", sparkles: "sparkles", dumbbell: "dumbbell", "heart-pulse": "heart-pulse",
  baby: "baby", paw: "paw", car: "car", book: "book"
};

/* ══ Campos de configuração ═══════════════════════════════════════════
   A lista de campos NÃO mora aqui. O painel.py é o dono e manda os
   metadados dentro de /api/config. Ela já existiu duplicada nos dois
   arquivos, e duas listas para a mesma verdade só coincidem por acaso:
   no dia que uma crescesse, o formulário ofereceria um campo que o
   servidor nem valida. */
let CFG = null;         // última resposta de /api/config
let CAMPOS_META = [];   // metadados dos campos, vindos do servidor

async function lerConfig(forcar = false) {
  if (CFG && !forcar) return CFG;
  const r = await fetch("/api/config", { cache: "no-store" });
  CFG = await r.json();
  CAMPOS_META = CFG.campos || [];
  return CFG;
}

/* Campos de uma plataforma, na ordem em que o servidor declarou. */
function camposDaPlataforma(grupo) {
  return CAMPOS_META.filter(c => c.grupo === grupo);
}

/* Grupos que têm card próprio em Plataformas. Não entram no formulário
   genérico de Configurações: mesma credencial em dois lugares, e salvar
   num apagando o valor que o outro mostrou. */
function gruposDePlataforma() {
  return new Set(BLOCOS.map(b => b.grupo));
}

let statusAtual = {};
let metricasAtual = {};
let configCarregada = false;
let configSuja = false;
let ultimoFoco = null;
const NICHOS_SEL = new Set();
const TERMINAIS_LIMPOS = { bot: true, acao: true };

/* ══ Ícones extras usados via <use> ═══════════════════════════════════ */
/* Dois ícones não estão no <symbol> estático do corpo; entram por JS para
   não duplicar o mesmo traço em dois lugares do arquivo.                */
function injetarIconesFaltantes() {
  const FALTANDO = {
    "i-wand": "M14.7 6.3a2 2 0 0 1 2.8 2.8L10 16.6l-3.7 1 1-3.7zM18 2v3M21.5 5.5h-3M3 21l7-7",
    "i-lock": "M6 10.5V7.8a6 6 0 0 1 12 0v2.7M5 10.5h14a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 21.5H5A1.5 1.5 0 0 1 3.5 20v-8A1.5 1.5 0 0 1 5 10.5z",
  };
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.querySelector("body > svg");
  if (!svg) return;
  for (const [id, d] of Object.entries(FALTANDO)) {
    if (document.getElementById(id)) continue;
    const s = document.createElementNS(NS, "symbol");
    s.setAttribute("id", id);
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("fill", "none");
    s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", "2");
    s.setAttribute("stroke-linecap", "round");
    s.setAttribute("stroke-linejoin", "round");
    s.innerHTML = d.split("M").filter(Boolean).map(p => `<path d="M${p}"/>`).join("");
    svg.appendChild(s);
  }
}

/* ══ Barra de seções de Configurações ══════════════════════════════
   Dois estados que a tela nao mostrava: qual das quatro secoes esta a
   vista, e que o formulario de credenciais tem alteracao nao salva. O
   `configSuja` ja existia desde antes, so que lido apenas para pular a
   repinta - o estado era mantido e nunca exibido. */
function marcarSecaoAtiva() {
  const nav = $("#configNav");
  if (!nav) return;
  const secoes = $$("#view-config .config-secao");
  if (!secoes.length) return;
  // 140px: a barra tem ~46px e fica grudada no topo. O que passou dessa
  // marca conta como "a secao atual", e nao a que ainda esta chegando.
  let atual = null;
  for (const s of secoes) {
    if (s.getBoundingClientRect().top <= 140) atual = s.id;
  }
  if (!atual) atual = secoes[0].id;
  $$("#configNav a").forEach(a =>
    a.classList.toggle("ativo", a.getAttribute("href") === "#" + atual));
}

function marcarConfigSuja(sujo) {
  const nav = $("#configNav");
  if (nav) nav.classList.toggle("sujo", !!sujo);
}

let scrollMarcado = false;
window.addEventListener("scroll", () => {
  if (scrollMarcado) return;
  scrollMarcado = true;
  requestAnimationFrame(() => { scrollMarcado = false; marcarSecaoAtiva(); });
}, { passive: true });

/* ══ Navegação entre abas ════════════════════════════════════════════ */
function switchView(nome) {
  if (!$("#view-" + nome)) return;
  $$(".nav-item").forEach(el => {
    const ativo = el.dataset.view === nome;
    if (ativo) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  $$(".view").forEach(v => v.classList.toggle("ativa", v.id === "view-" + nome));
  // "instant" ignora o `scroll-behavior: smooth` do html; "auto" respeitaria
  // e a troca de aba viraria uma animação longa.
  window.scrollTo({ top: 0, left: 0, behavior: "instant" });

  if (location.hash.slice(1) !== nome) history.replaceState(null, "", "#" + nome);

  if (nome === "produtos") carregarProdutos();
  if (nome === "config") { carregarConfig(); carregarNichos(); carregarConta(); marcarSecaoAtiva(); }
  // O resumo dos cards de plataforma depende de /api/config, não só do
  // status. No boot isso já aconteceu, mas ir direto pela URL precisa
  // funcionar — e a gaveta só tem campo depois dessa mesma resposta.
  if (nome === "plataformas" && !CAMPOS_META.length) {
    lerConfig().then(() => pintarResumoPlataforma()).catch(() => {});
  }
  if (nome === "dashboard") desenharGraficos();   // o canvas precisa de largura real
  if (nome === "suporte") renderDiagnostico();
}

function irPara(view) {
  switchView(view);
  const link = $(`.nav-item[data-view="${view}"]`);
  if (link) link.focus({ preventScroll: true });
}

/* Abre a gaveta de configuração de uma plataforma. É o mesmo caminho para
   o botão "Configurar" da grade e para o do Dashboard: a gaveta é global,
   então não faz sentido obrigar quem cliqueu no Dashboard a mudar de aba
   antes de preencher a credencial. */
function gerenciarPlataforma(chave) {
  abrirGaveta(chave);
}

/* ══ Relógio ══════════════════════════════════════════════════════════ */
function tickRelogio() {
  const d = new Date();
  const p = n => String(n).padStart(2, "0");
  const hora = `${p(d.getHours())}:${p(d.getMinutes())}`;
  const data = `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
  $("#relogioHora").textContent = hora;
  $("#relogioData").textContent = data;
  $("#rodapeHora").textContent = `${data} ${hora}`;
}

/* ══ Status ═══════════════════════════════════════════════════════════ */
function selo(el, ok, texto) {
  if (!el) return;
  el.className = "selo " + (ok ? "selo-ok" : "selo-espera");
  el.innerHTML = `<span class="ponto" aria-hidden="true"></span>${esc(texto)}`;
}

async function atualizarStatus() {
  try {
    const s = await (await fetch("/api/status", { cache: "no-store" })).json();
    statusAtual = s;
    const on = !!s.bot_rodando;
    const acao = s.acao_rodando || "";

    // Cartão da sidebar
    $("#ladoPonto").className = "ponto" + (acao ? " ocupado" : on ? " ativo" : "");
    $("#ladoTitulo").textContent = acao ? "Ação em curso" : on ? "Bot ativo" : "Bot parado";
    if (acao) {
      $("#ladoSub").innerHTML = `${esc(acao)} <br><span class="link-acao" style="color:var(--perigo, #ef4444); cursor:pointer; font-weight:600; text-decoration:underline; font-size:11px;" onclick="event.stopPropagation(); cancelarAcao();">✕ Cancelar ação</span>`;
    } else {
      $("#ladoSub").textContent = on ? "Postando normalmente" : "Clique para ligar";
    }
    $("#ladoIcone").setAttribute("href", on ? "#i-stop" : "#i-play");

    // Selo do cabeçalho
    $("#headerPill").dataset.ligado = on ? "1" : "0";
    $("#headerPonto").className = "ponto" + (on ? " ativo" : "");
    $("#headerTexto").textContent = on ? "Bot rodando" : "Bot parado";

    // Ações ficam travadas enquanto algo roda — evita clique repetido e erro 409.
    const ocupado = !!acao;
    ["#btnInstalarNav", "#btnCiclo", "#btnCicloPlat"].forEach(sel => {
      const b = $(sel);
      if (b) b.disabled = ocupado;
    });
    $("#btnInstalarNavTxt").textContent =
      s.navegador ? "Navegador instalado" : "Instalar navegador";

    if (s.plataformas) {
      const ml = s.plataformas.mercadolivre || {};
      selo($("#seloMl"), ml.conectado, ml.conectado ? "Conectado" : "Não configurado");
      $("#subMl").textContent = ml.conectado ? "Link builder pronto"
        : ml.sessao_ativa ? "Falta a etiqueta" : "Falta fazer o login";

      const amz = s.plataformas.amazon || {};
      selo($("#seloAmz"), amz.conectado, amz.conectado ? "Conectado" : "Não configurado");
      $("#subAmz").textContent = amz.conectado
        ? (amz.api_ativa ? "Creators API ativa" : "Tag + busca por scraping") : "Sem tag de associado";

      const shp = s.plataformas.shopee || {};
      selo($("#seloShp"), shp.conectado, shp.conectado ? "Conectado" : "Não configurado");
      $("#subShp").textContent = shp.conectado ? "Open API pronta" : "Sem credenciais de API";

      const ali = s.plataformas.aliexpress || {};
      selo($("#seloAli"), ali.conectado, ali.conectado ? "Conectado" : "Não configurado");
      $("#subAli").textContent = ali.conectado ? "Open API pronta" : "Sem credenciais de API";
    }

    const dono = s.preenchidos && s.preenchidos.TELEGRAM_OWNER_ID;
    $("#perfilDono").textContent = dono ? "Dono configurado" : "ID não detectado";

    const fontes = (s.fontes_ativas || []).join(", ") || "nenhuma";
    const ciclo = s.horario_ativo && s.horario_ativo !== "24h"
      ? `Posta entre ${esc(s.horario_ativo)}, a cada ${s.intervalo_minutos} min, até ${s.max_posts_por_ciclo} por ciclo.`
      : `Posta a cada ${s.intervalo_minutos} min, até ${s.max_posts_por_ciclo} por ciclo.`;
    $("#resumoAmbiente").innerHTML =
      `Fontes automáticas: <strong>${esc(fontes)}</strong> · Nichos: <strong>${(s.nichos || []).length || "todos"}</strong><br>${ciclo}`;

    renderPlataformas(s);
    renderDiagnostico(s);
  } catch (e) {
    $("#headerTexto").textContent = "Servidor sem resposta";
    $("#headerPonto").className = "ponto erro";
  }
}

/* ═══ Blocos de plataforma (gerados a partir dos dados) ═════════════ */
/* Cada card da grade. `grupo` e o mesmo rotulo que o servidor usa em
   /api/config, e e por ele que os campos de credencial sao buscados —
   por isso o nome precisa bater com CAMPOS no painel.py.

   `resumoDe` le a unica linha informativa do card direto do `status` que o
   servidor mandou em /api/status. A pagina nao reescreve esse texto: se o
   servidor trocar "Open API pronta" por outra coisa, o card mostra a coisa
   nova sozinho, e ninguem precisa lembrar de atualizar dois lugares.
   `acoes` sao os botoes que ficam na gaveta, nunca na grade. */
const BLOCOS = [
  {
    chave: "mercadolivre", nome: "Mercado Livre", grupo: "Mercado Livre",
    cor: "var(--e1)", logo: "/assets/mercadolivre.png",
    sub: "Linkbuilder com sessão local",
    resumoDe: p => (p.mercadolivre || {}).status || "Não configurado",
    // Três estados, e não dois: o servidor distingue a sessão pendente de
    // uma credencial que existe mas nunca foi testada. Tratar os dois como
    // "desconectado" esconde exatamente o que a pessoa precisa corrigir.
    estadoDe: p => {
      const m = p.mercadolivre || {};
      if (m.conectado) return ["ok", "Conectado"];
      if (m.sessao_ativa) return ["erro", "Sessão ativa, falta a etiqueta"];
      return ["neutro", "Desconectado"];
    },
    acoes: [
      ["ml-login", "Fazer login", "btn-primario", "key"],
      ["testar-ml", "Testar conexão", "btn-neutro", "search"],
      // "Detalhes da sessão" e não só "Detalhes": ao lado de "Limpar
      // sessão", um rótulo sozinho não diz do que o botão trata.
      ["sessao", "Detalhes da sessão", "btn-neutro", "zoom"],
    ],
    extra: [["Limpar sessão", "btn-perigo", "trash", "limparSessao()"]],
  },
  {
    chave: "amazon", nome: "Amazon", grupo: "Amazon",
    cor: "var(--e2)", logo: "/assets/amazon.png",
    sub: "Associados e Creators API",
    resumoDe: p => (p.amazon || {}).status || "Não configurado",
    estadoDe: p => (p.amazon || {}).conectado
      ? ["ok", "Conectado"] : ["neutro", "Desconectado"],
    acoes: [
      ["testar-amazon", "Testar conexão", "btn-neutro", "search"],
    ],
  },
  {
    chave: "shopee", nome: "Shopee", grupo: "Shopee",
    cor: "var(--e3)", logo: "/assets/shopee.png",
    sub: "Open API oficial de afiliados",
    resumoDe: p => (p.shopee || {}).status || "Não configurado",
    estadoDe: p => (p.shopee || {}).conectado
      ? ["ok", "Conectado"] : ["neutro", "Desconectado"],
    acoes: [
      ["testar-shopee", "Testar conexão", "btn-neutro", "search"],
    ],
  },
  {
    chave: "aliexpress", nome: "AliExpress", grupo: "AliExpress",
    cor: "var(--e4)", logo: "/assets/aliexpress.png",
    sub: "Open Platform / Affiliate API",
    resumoDe: p => (p.aliexpress || {}).status || "Não configurado",
    estadoDe: p => (p.aliexpress || {}).conectado
      ? ["ok", "Conectado"] : ["neutro", "Desconectado"],
    acoes: [
      ["testar-aliexpress", "Testar conexão", "btn-neutro", "search"],
    ],
  },
  {
    chave: "telegram", nome: "Telegram", grupo: "Telegram",
    cor: "var(--primaria-texto)", logo: "",
    sub: "Bot, canal e fontes monitoradas",
    // O /api/status nao tem entrada de Telegram em `plataformas`: ele
    // expoe os tres campos como `preenchidos` e um `pronto` derivado.
    // Nao ha status para copiar aqui, entao a frase traduz o booleano.
    // "Falta o token, o seu ID e o canal", e nao "Faltam identificadores":
    // o nome do campo e o que a pessoa procura na gaveta logo abaixo.
    resumoDe: (p, s) => {
      const pg = (s && s.preenchidos) || {};
      const f = [["o token", pg.TELEGRAM_BOT_TOKEN], ["o seu ID", pg.TELEGRAM_OWNER_ID],
                 ["o canal", pg.TELEGRAM_CHAT_ID]].filter(([, tem]) => !tem).map(([rot]) => rot);
      if (!f.length) return "Token, ID e canal definidos";
      // Virgula antes do último, como se escreve em português. Juntar tudo
      // com " e " daria "o token e o seu ID e o canal" com tres campos, e
      // com " e " sem virgula ficaria ambíguo a partir de dois.
      return "Falta " + (f.length === 1 ? f[0]
        : f.slice(0, -1).join(", ") + " e " + f[f.length - 1]);
    },
    estadoDe: (p, s) => (s && s.pronto)
      ? ["ok", "Conectado"] : ["neutro", "Desconectado"],
    acoes: [
      ["ids", "Detectar IDs", "btn-neutro", "search"],
    ],
  },
];

/* O status chega a cada poucos segundos. Recriar o HTML dos cards a cada
   volta apagaria o que a pessoa estivesse digitando no drawer, então a
   montagem acontece uma vez e daqui para frente so repinta o texto. */
function renderPlataformas(s) {
  const alvo = $("#blocosPlataforma");
  if (!alvo) return;
  if (!alvo.children.length) montarCardsPlataforma();
  if (s && s.plataformas) pintarEstadoPlataforma(s);
  pintarResumoPlataforma();
}

/* Card compacto: logo, nome, o selo de estado, a linha de status do
   servidor e o botao de configurar. Os campos de credencial nao entram
   aqui — moram na gaveta. */
function montarCardsPlataforma() {
  $("#blocosPlataforma").innerHTML = BLOCOS.map(b => `
    <section class="plato" id="plato-${b.chave}" style="--cor:${b.cor}" aria-labelledby="tit-${b.chave}">
      <div class="plato-topo">
        <span class="plato-logo">
          ${b.logo
            ? `<img class="plato-logo-img" src="${b.logo}" alt="Logo ${esc(b.nome)}" width="40" height="40" loading="lazy">`
            : icone("send", "plato-logo-img plato-logo-glyph")}
        </span>
        <div class="plato-id">
          <h3 id="tit-${b.chave}">${esc(b.nome)}</h3>
          <small>${esc(b.sub)}</small>
        </div>
        <span class="selo selo-neutro" id="seloPb-${b.chave}"><span class="ponto" aria-hidden="true"></span>Verificando</span>
      </div>

      <div class="plato-estado">
        <p class="plato-linha"><span id="res-${b.chave}">—</span></p>
      </div>

      <div class="plato-rodape">
        <button type="button" class="btn btn-neutro" onclick="abrirGaveta('${b.chave}')">
          ${icone("sliders")} Configurar
        </button>
      </div>
    </section>`).join("");
}

/* Selo com três estados, e não dois. O `selo()` antigo só sabia dizer
   conectado ou não; aqui o servidor distingue "a credencial existe mas a
   sessão não" de "não existe nada", e achatar os dois esconde justamente o
   que a pessoa precisa corrigir. */
function seloDe(el, [classe, txt]) {
  if (!el) return;
  el.className = "selo selo-" + classe;
  el.innerHTML = `<span class="ponto" aria-hidden="true"></span>${esc(txt)}`;
}

/* Uma volta do polling repinta selo e resumo de todos os cards. As duas
   coisas saem de BLOCOS: cada bloco sabe o que é estar conectado e de
   onde vem a linha de resumo, então acrescentar uma plataforma é uma
   entrada nova e nada mais. */
function pintarEstadoPlataforma(s) {
  const p = s.plataformas || {};
  for (const b of BLOCOS) {
    seloDe($("#seloPb-" + b.chave), b.estadoDe(p, s));
  }
  pintarResumoPlataforma();
  // A gaveta aberta mostra o mesmo par selo + status, logo entra na mesma
  // volta. Só o texto que muda — os inputs são de `pintarCamposGaveta`, que
  // tem o guard de digitação e não pode ser atropelado por aqui.
  pintarSituacaoGaveta();
}

/* O resumo e o status do servidor, sem rótulo: "Status | Link Builder
   pronto" repete a mesma palavra duas vezes, e o valor sozinho ja diz do
   que se trata. Chega em duas respostas separadas — o status primeiro, o
   /api/config depois — entao e repintado de qualquer uma delas. */
function pintarResumoPlataforma() {
  const s = statusAtual;
  if (!s || !s.plataformas) return;
  for (const b of BLOCOS) {
    const el = $("#res-" + b.chave);
    if (el) el.textContent = b.resumoDe(s.plataformas, s);
  }
}

/* ══ Gaveta de configuração ═════════════════════════════════════════════
   Um container só, montado no momento de abrir. Cinco formulários
   permanentes pareceriam mais baratos, mas cada resposta de /api/config
   repassaria por cima do que estivesse sendo digitado em qualquer gaveta
   fechada. Aqui o form existe só enquanto a gaveta está aberta — e fechar
   descarta o que não foi salvo, que é o que o botão "Descartar" do teclado
   promete. */
let gavetaChave = null;

/* A "Situação" da gaveta é o mesmo par selo + status dos cards, e por isso
   mora em BLOCOS igual: acrescentar uma plataforma continua sendo uma
   entrada. Precisa ser função à parte porque o polling repinta os cards a
   cada volta, mas a gaveta ficaria num retrato do instante em que foi
   aberta — aberta antes do primeiro /api/status, ela continuaria anunciando
   "Desconectado" mesmo depois de a credencial estar salva. */
function pintarSituacaoGaveta() {
  const alvo = $("#gavetaResumo");
  const b = BLOCOS.find(x => x.chave === gavetaChave);
  if (!alvo || !b) return;
  const p = statusAtual.plataformas || {};
  const [classe, txt] = b.estadoDe(p, statusAtual);
  alvo.innerHTML = `
    <div class="gaveta-secao-titulo">${icone("sliders")} Situação</div>
    <div style="display:flex; align-items:center; gap:9px; margin-top:11px; flex-wrap:wrap">
      <span class="selo selo-${classe}"><span class="ponto" aria-hidden="true"></span>${esc(txt)}</span>
      <span class="gaveta-status">${esc(b.resumoDe(p, statusAtual))}</span>
    </div>`;
}

async function abrirGaveta(chave) {
  const b = BLOCOS.find(x => x.chave === chave);
  if (!b) return;
  gavetaChave = chave;

  $("#gavetaTitulo").textContent = b.nome;
  $("#gavetaSub").textContent = b.sub;
  // O glifo do Telegram não tem PNG em /assets; entra o ícone do mesmo
  // conjunto dos botões, com a cor da marca em vez da imagem.
  $("#gavetaLogoCaixa").innerHTML = b.logo
    ? `<img class="plato-logo-img" src="${esc(b.logo)}" alt="Logo ${esc(b.nome)}" width="40" height="40">`
    : icone("send", "plato-logo-img plato-logo-glyph");
  $("#gaveta").style.setProperty("--cor", b.cor);

  // O estado e as ações são os mesmos dos cards, para a gaveta não virar
  // uma tela separada: quem abre lê o mesmo texto e age sobre o mesmo par.
  pintarSituacaoGaveta();

  $("#gavetaAcoesBloco").innerHTML = `
    <div class="gaveta-secao-titulo">${icone("play")} Ações</div>
    <div class="gaveta-acoes" style="margin-top:11px">
      ${b.acoes.map(([acao, rot, cls, ic]) => `<button type="button" class="btn ${cls}"
          onclick="${acao === "sessao" ? "abrirModalSessao()" : acao === "ids" ? "detectarIds('#gavetaDeteccao', true)" : `executarAcao('${acao}')`}">
          ${icone(ic)} ${esc(rot)}</button>`).join("")}
      ${(b.extra || []).map(([rot, cls, ic, js]) =>
        `<button type="button" class="btn ${cls}" onclick="${js}">${icone(ic)} ${esc(rot)}</button>`).join("")}
    </div>`;

  $("#gavetaCamposBloco").innerHTML = `<div class="gaveta-campos" id="gavetaCampos"></div>`;
  $("#gavetaDica").textContent = "";
  $("#gavetaDica").className = "plato-dica";
  $("#gavetaSalvar").disabled = false;

  abrirModal("gavetaPlataforma");

  // Os metadados dos campos vêm de /api/config. Em geral já chegaram no
  // boot, mas chegar pela gaveta direto (botão do Dashboard) não pode
  // mostrar um formulário vazio enquanto a resposta está a caminho.
  if (!CAMPOS_META.length) {
    $("#gavetaCampos").innerHTML = vazio("Carregando campos…", "", "refresh");
    try { await lerConfig(); } catch (e) { /* a linha abaixo mostra o erro */ }
  }
  pintarCamposGaveta(chave);
}

function pintarCamposGaveta(chave) {
  const alvo = $("#gavetaCampos");
  if (!alvo) return;
  const b = BLOCOS.find(x => x.chave === chave);
  const campos = b ? camposDaPlataforma(b.grupo) : [];
  if (!CAMPOS_META.length) {
    alvo.innerHTML = `<div class="alerta alerta-erro" role="alert">${icone("alert", "icone")}<div>Não consegui carregar os campos. Recarregue a página.</div></div>`;
    return;
  }
  alvo.innerHTML = `
    <div class="gaveta-secao-titulo">${icone("key")} Credenciais</div>
    <div style="margin-top:13px">
      ${campos.length ? campos.map(c => {
        const definido = !!(CFG && CFG[c.chave + "__set"]);
        const marca = definido ? `<span class="marca-ok">${icone("check")} definido</span>` : "";
        const valor = c.segredo ? "" : esc((CFG && CFG[c.chave]) || "");
        const ph = c.segredo && definido ? "Já preenchido — deixe em branco para manter" : "";
        return `
          <div class="campo" style="margin-bottom:15px">
            <label for="gav_${esc(c.chave)}">${esc(c.rotulo)} ${marca}</label>
            <input id="gav_${esc(c.chave)}" name="${esc(c.chave)}" type="${c.segredo ? "password" : "text"}"
                   value="${valor}" placeholder="${esc(ph)}" autocomplete="off" spellcheck="false"
                   aria-describedby="gaba_${esc(c.chave)}">
            <p class="ajuda" id="gaba_${esc(c.chave)}">${esc(c.ajuda)}</p>
          </div>`;
      }).join("") : `<p class="ajuda">Esta integração não usa credencial.</p>`}
    </div>`;
  const primeiro = $("input", alvo);
  if (primeiro) primeiro.focus({ preventScroll: true });
}

function fecharGaveta() {
  const m = $("#gavetaPlataforma");
  const g = $("#gavetaCampos");
  if (g) g.innerHTML = "";
  if (m && m.classList.contains("aberto")) fecharModal("gavetaPlataforma");
  gavetaChave = null;
}

/* Há edição em curso? O polling do status passa a cada poucos segundos e
   o /api/config pode responder no meio da digitação. Sem esta checagem, um
   campo de senha em edição seria reescrito com o valor do servidor. */
function gavetaDigitando() {
  const a = document.activeElement;
  return !!a && !!a.closest && !!a.closest("#gavetaCampos") && a.tagName === "INPUT";
}

/* Salva só os campos que estão no formulário. O servidor ignora o que não
   veio no corpo, então mexer numa plataforma não toca na credencial das
   outras quatro. */
async function salvarPlataforma(chave) {
  const form = $("#gavetaCampos");
  if (!form || !chave) return;
  const btn = $("#gavetaSalvar");
  const dica = $("#gavetaDica");
  const body = {};
  $$("input", form).forEach(el => { body[el.name] = el.value.trim(); });

  btn.disabled = true;
  dica.className = "plato-dica";
  dica.textContent = "Salvando…";
  try {
    const r = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.erro) { dica.textContent = d.erro; return; }
    await lerConfig(true);
    // Repinta os inputs para trazer a marca "definido" sem perder o que
    // acabou de ser salvo, e o resumo dos cards com os campos já gravados.
    pintarCamposGaveta(chave);
    dica.className = "plato-dica ok";
    dica.textContent = "Credenciais salvas";
    await atualizarStatus();
  } catch (e) {
    dica.textContent = "Não consegui salvar. O .env continua como estava.";
  } finally {
    btn.disabled = false;
  }
}

function renderDiagnostico(s = statusAtual) {
  const alvo = $("#diagnostico");
  if (!alvo || !s) return;
  const itens = [
    ["Token do bot", s.preenchidos && s.preenchidos.TELEGRAM_BOT_TOKEN],
    ["ID do dono", s.preenchidos && s.preenchidos.TELEGRAM_OWNER_ID],
    ["ID do canal", s.preenchidos && s.preenchidos.TELEGRAM_CHAT_ID],
    ["Navegador do Playwright", s.navegador],
    ["Sessão do Mercado Livre", s.sessao_ml],
  ];
  alvo.innerHTML = itens.map(([rot, ok]) => `
    <div class="diag-item">
      ${ok ? icone("check-circle", "icone icone-ok") : icone("alert", "icone icone-falta")}
      <span>${esc(rot)}: <b>${ok ? "pronto" : "falta"}</b></span>
    </div>`).join("");
}

/* ══ Métricas e gráficos ═════════════════════════════════════════════ */
function ajustarCanvas(canvas) {
  // Canvas com a view oculta tem rect 0 — desenhar assim apaga o gráfico para sempre.
  const r = canvas.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) return null;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.round(r.width * dpr), h = Math.round(r.height * dpr);
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, r.width, r.height);
  return { ctx, w: r.width, h: r.height };
}

function desenharGraficoSemana() {
  const canvas = $("#graficoSemana");
  if (!canvas) return;
  const m = metricasAtual;
  const rot = ajustarCanvas(canvas);
  if (!rot) return;                       // view oculta: desenha quando voltar
  const { ctx, w, h } = rot;
  const valores = m.grafico_dias_valores || [];
  const labels = m.grafico_dias_labels || [];
  if (!valores.length) return;

  const padT = 12, padB = 20, padL = 24, padR = 8;
  const pw = w - padL - padR, ph = h - padT - padB;
  const max = Math.max(...valores, 4);
  const passo = pw / (valores.length - 1 || 1);

  // Grade + eixo Y
  ctx.font = "10px 'JetBrains Mono', monospace";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 2; i++) {
    const y = padT + (ph / 2) * i;
    const v = Math.round(max - (max / 2) * i);
    ctx.strokeStyle = "#183B58"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, y + 0.5); ctx.lineTo(w - padR, y + 0.5); ctx.stroke();
    ctx.fillStyle = "#7E9CB8"; ctx.textAlign = "right";
    ctx.fillText(String(v), padL - 6, y);
  }

  const pts = valores.map((v, i) => ({
    x: padL + passo * i,
    y: padT + ph - (v / max) * ph,
    v,
  }));

  // Área
  const g = ctx.createLinearGradient(0, padT, 0, padT + ph);
  g.addColorStop(0, "rgba(26,104,255,0.34)");
  g.addColorStop(1, "rgba(26,104,255,0)");
  ctx.beginPath();
  ctx.moveTo(pts[0].x, padT + ph);
  pts.forEach((p, i) => {
    if (i === 0) { ctx.lineTo(p.x, p.y); return; }
    const a = pts[i - 1], cx = (a.x + p.x) / 2;
    ctx.bezierCurveTo(cx, a.y, cx, p.y, p.x, p.y);
  });
  ctx.lineTo(pts[pts.length - 1].x, padT + ph);
  ctx.closePath(); ctx.fillStyle = g; ctx.fill();

  // Linha
  ctx.beginPath();
  pts.forEach((p, i) => {
    if (i === 0) { ctx.moveTo(p.x, p.y); return; }
    const a = pts[i - 1], cx = (a.x + p.x) / 2;
    ctx.bezierCurveTo(cx, a.y, cx, p.y, p.x, p.y);
  });
  ctx.strokeStyle = "#0B84FF"; ctx.lineWidth = 2.2; ctx.lineJoin = "round"; ctx.stroke();

  // Pontos — o último destacado
  pts.forEach((p, i) => {
    const ultimo = i === pts.length - 1;
    ctx.beginPath(); ctx.arc(p.x, p.y, ultimo ? 4 : 2.6, 0, Math.PI * 2);
    ctx.fillStyle = ultimo ? "#fff" : "#0B84FF"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = "#0B84FF"; ctx.stroke();
  });

  // Eixo X — a cada 2 dias para os rótulos não se sobreporem
  ctx.fillStyle = "#7E9CB8";
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  pts.forEach((p, i) => {
    if (i % 2 !== 0 && i !== pts.length - 1) return;
    ctx.fillText(labels[i] || "", p.x, padT + ph + 6);
  });
}

function desenharGraficos() { desenharGraficoSemana(); }

async function atualizarMetricas() {
  try {
    const d = await (await fetch("/api/metricas", { cache: "no-store" })).json();
    metricasAtual = d;

    $("#valSemana").textContent = d.semana ?? 0;
    $("#valTotal").textContent = d.total ?? 0;
    $("#valHoje").textContent = d.hoje ?? 0;
    $("#valUltima").textContent = d.ultima || "nenhuma ainda";
    const delta = $("#deltaSemana");
    delta.textContent = `${d.variacao || "estável"} vs. ontem`;
    delta.className = "metrica-delta " + (d.variacao_ok ? "ok" : "parado");
    $("#navLinkCount").textContent = d.total ?? 0;

    desenharGraficos();

    // Plataformas
    const tl = $("#topLista");
    tl.innerHTML = (d.top_plataformas || []).length
      ? d.top_plataformas.map(p => {
          const logoSrc = LOGO_PLATAFORMA[p.nome] || LOGO_PLATAFORMA[(p.nome || "").toLowerCase().replace(/\s+/g, "")] || "";
          const iconeEl = logoSrc
            ? `<div class="top-logo-caixa"><img src="${logoSrc}" alt="${esc(p.nome)}" class="top-logo-img"></div>`
            : `<span class="top-marca" style="--c:${esc(p.cor)}" aria-hidden="true">${icone(p.icone)}</span>`;
          return `
        <div class="top-item">
          ${iconeEl}
          <span class="top-nome">${esc(p.nome)}</span>
          <span class="top-num">${p.cliques}</span>
          <span class="top-barra-linha">
            <span class="barra"><i style="width:${Math.max(p.pct, 2)}%"></i></span>
          </span>
        </div>`;
        }).join("")
      : vazio("Nada postado ainda", "Assim que o bot rodar um ciclo, os números aparecem aqui.", "chart");

    // Atividade
    const al = $("#atividadeLista");
    al.innerHTML = (d.atividades || []).length
      ? d.atividades.map(a => {
          const plat = a.plataforma || "mercadolivre";
          const logoSrc = LOGO_PLATAFORMA[plat] || LOGO_PLATAFORMA[NOME_PLATAFORMA[plat]] || "";
          const iconeEl = logoSrc
            ? `<div class="ativ-logo-caixa"><img src="${logoSrc}" alt="${esc(plat)}" class="ativ-logo-img"></div>`
            : `<span class="ativ-icone ${plat === 'mercadolivre' ? 'ml' : plat === 'aliexpress' ? 'ali' : plat}" aria-hidden="true">${icone(ICONE_PLATAFORMA[plat] || "tag")}</span>`;
          return `
          <div class="ativ-item">
            ${iconeEl}
            <span class="ativ-texto">
              <b>${esc(NOME_PLATAFORMA[plat] || plat)}</b>
              <small>${esc(a.detalhe)}</small>
            </span>
            <span class="ativ-hora">${esc(a.hora)}</span>
          </div>`;
        }).join("")
      : vazio("Nenhuma publicação ainda", "Ligue o bot ou rode um ciclo pela aba Plataformas.", "history");

    // Links — só os reais, gravados no banco
    const html = (d.links_recentes || []).map(l => itemLink(l, false)).join("");
    $("#linksRecentes").innerHTML = html || vazio("Nenhum link ainda", "Os links aparecem aqui depois do primeiro post.", "link");
    $("#linksTodos").innerHTML = html || vazio("Nenhum link ainda", "Use o link builder para gerar o primeiro.", "link");
  } catch (e) {
    $("#linksRecentes").innerHTML = vazio("Não consegui carregar", "O servidor local não respondeu.", "alert");
  }
}

function itemLink(l, completo) {
  const tit = esc(l.titulo || "Produto sem título");
  const url = esc(l.url || "");
  const quando = esc(l.data || "");
  const copiar = url
    ? `<button type="button" class="btn btn-icone" title="Copiar link" aria-label="Copiar link"
         onclick="copiarTexto(this.dataset.url)"><svg class="icone icone-sm" aria-hidden="true"><use href="#i-copy"/></svg></button>`
    : `<span class="selo selo-neutro" title="O bot ainda não gravou o link deste produto">sem link salvo</span>`;
  const abrir = url
    ? `<a class="link-url" href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`
    : `<span class="link-url" style="color:var(--texto-3)">${tit}</span>`;
  return `
    <div class="link-item">
      <div class="link-corpo">
        ${abrir}
        <div class="link-meta">${completo ? tit + " · " : ""}${quando}</div>
      </div>
      ${copiar}
    </div>`;
}

/* ══ Logs ═════════════════════════════════════════════════════════════ */
async function puxarLogs() {
  try {
    const [lb, la] = await Promise.all([
      fetch("/api/logs?bot", { cache: "no-store" }).then(r => r.json()),
      fetch("/api/logs?acao", { cache: "no-store" }).then(r => r.json()),
    ]);
    pintarTerminal("bot", lb && lb.linhas);
    pintarTerminal("acao", la && la.linhas);
    const rodando = !!statusAtual.bot_rodando;
    $("#logBotPonto").className = "ponto" + (rodando ? " ativo" : "");
    $("#logAcaoPonto").className = "ponto" + (statusAtual.acao_rodando ? " ocupado" : "");
  } catch (e) { /* servidor fora do ar: tenta de novo no próximo ciclo */ }
}

function pintarTerminal(alvo, linhas) {
  const vazioTxt = alvo === "bot"
    ? "O bot está pronto. Ligue pelo cartão ao lado para acompanhar o log em tempo real."
    : "Nenhuma ação executada ainda. Os testes de conexão aparecem aqui.";
  // Depois de limpar, o terminal fica vazio até chegar log novo.
  if (TERMINAIS_LIMPOS[alvo] && !(linhas && linhas.length)) return;
  if (linhas && linhas.length) TERMINAIS_LIMPOS[alvo] = false;
  const mapa = alvo === "bot"
    ? { "#terminalBot": vazioTxt }
    : { "#terminalAcao": vazioTxt, "#terminalAcaoPlataformas": vazioTxt };
  const texto = linhas && linhas.length ? linhas.join("\n") : vazioTxt;
  Object.entries(mapa).forEach(([sel, padrao]) => {
    const el = $(sel);
    if (!el) return;
    const t = linhas && linhas.length ? texto : padrao;
    if (el.dataset.texto === t) return;
    el.dataset.texto = t;
    const noFim = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
    el.textContent = t;
    if (noFim) el.scrollTop = el.scrollHeight;
  });
}

async function limparTerminal(alvo) {
  TERMINAIS_LIMPOS[alvo] = true;
  const mapa = alvo === "bot"
    ? { "#terminalBot": "Terminal limpo." }
    : { "#terminalAcao": "Terminal limpo.", "#terminalAcaoPlataformas": "Terminal limpo." };
  Object.entries(mapa).forEach(([sel, txt]) => {
    const el = $(sel);
    if (!el) return;
    el.textContent = txt;
    el.dataset.texto = txt;
  });
  try {
    await fetch("/api/limpar-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alvo }),
    });
  } catch (e) { /* só cosmetic */ }
}

/* ══ Ações do bot ═════════════════════════════════════════════════════ */
async function alternarBot() {
  const ligando = !statusAtual.bot_rodando;
  const cartao = $("#botCartao");
  cartao.disabled = true;
  try {
    const r = await (await fetch(ligando ? "/api/start" : "/api/stop", { method: "POST" })).json();
    if (r.erro) toast(r.erro, "erro");
    else toast(ligando ? "Bot iniciado. Acompanhe o log na aba Logs." : "Bot desligado.", ligando ? "ok" : "info");
    await atualizarStatus();
  } catch (e) {
    toast("Não consegui falar com o painel.", "erro");
  } finally {
    cartao.disabled = false;
  }
}

const ROTULOS_ACAO = {
  "instalar-navegador": "instalando o navegador",
  "ml-login": "abrindo o login do Mercado Livre",
  "testar-ml": "testando o Mercado Livre",
  "testar-shopee": "testando a Shopee",
  "testar-amazon": "testando a Amazon",
  "testar-aliexpress": "testando o AliExpress",
  "testar-grok": "testando o xAI / Grok",
};

async function executarAcao(nome) {
  try {
    const r = await (await fetch("/api/acao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome }),
    })).json();
    if (r.erro) {
      if (r.pode_cancelar) {
        // Uma ação já em execução trava o botão de login do ML, e um toast
        // passageiro some antes de a pessoa perceber que precisa cancelar.
        // Por isso o aviso fica mais tempo e leva direto ao terminal.
        toast(r.erro, "alerta", 9000);
        const alvo = $("#view-plataformas").classList.contains("ativa")
          ? "#view-plataformas" : "#view-logs";
        switchView(alvo.slice(1));
      } else {
        toast(r.erro, "erro");
      }
      return;
    }
    TERMINAIS_LIMPOS.acao = false;
    // Não sequestra a navegação: a saída da ação aparece nas duas abas que
    // têm terminal (Plataformas e Logs), então o toast só diz onde olhar.
    const onde = $("#view-plataformas").classList.contains("ativa") ? "logo abaixo"
      : $("#view-logs").classList.contains("ativa") ? "no terminal desta aba"
      : "na aba Logs";
    toast(`${ROTULOS_ACAO[nome] || "Ação"} — a saída aparece ${onde}.`, "info");
    await atualizarStatus();
  } catch (e) {
    toast("Não consegui executar a ação.", "erro");
  }
}

async function cancelarAcao() {
  try {
    const r = await (await fetch("/api/cancelar-acao", { method: "POST" })).json();
    toast(r.msg || "Ação cancelada.", "info");
    await atualizarStatus();
  } catch (e) {
    toast("Não foi possível cancelar a ação.", "erro");
  }
}

async function executarCiclo() {
  if (statusAtual.acao_rodando) { toast(`Já rodando: ${statusAtual.acao_rodando}`, "espera"); return; }
  if (!(statusAtual.preenchidos || {}).TELEGRAM_BOT_TOKEN) {
    toast("Salve o token do bot antes de rodar um ciclo.", "espera");
    switchView("config");
    return;
  }
  await executarAcao("ciclo");
}

/* ══ Configurações ═══════════════════════════════════════════════════ */
async function carregarConfig(forcar = false) {
  // Só recarrega do servidor se nunca foi lida ou se o usuário não tem edições em curso.
  if (configCarregada && !forcar && configSuja) return;
  const form = $("#formConfig");
  if (!form) return;
  if (!form.querySelector("input")) form.innerHTML = '<div class="vazio" style="grid-column:1/-1">Carregando campos…</div>';
  try {
    const cfg = await lerConfig(forcar);
    // Os grupos de plataforma não entram aqui: cada um tem card próprio em
    // Plataformas, com o campo dentro. Deixá-los nos dois lugares só
    // criaria duas cópias da mesma credencial — e salvar uma apagaria o
    // valor que a outra exibiu.
    const dasPlataformas = gruposDePlataforma();
    let html = "", grupo = "";
    for (const c of CAMPOS_META) {
      const { chave: k, rotulo: rot, grupo: grp, segredo, ajuda } = c;
      if (dasPlataformas.has(grp)) continue;
      if (grp !== grupo) {
        html += `<div class="grupo-titulo">${icone("sliders")} ${esc(grp)}</div>`;
        grupo = grp;
      }
      const set = !!cfg[k + "__set"];
      const marca = set ? `<span class="marca-ok">${icone("check")} definido</span>` : "";
      const valor = segredo ? "" : esc(cfg[k] || "");
      const ph = segredo && set ? "Já preenchido — deixe em branco para manter" : "";
      html += `
        <div class="campo">
          <label for="cfg_${esc(k)}">${esc(rot)} ${marca}</label>
          <input id="cfg_${esc(k)}" name="${esc(k)}" type="${segredo ? "password" : "text"}"
                 value="${valor}" placeholder="${esc(ph)}" autocomplete="off" spellcheck="false"
                 aria-describedby="aj_${esc(k)}">
          <p class="ajuda" id="aj_${esc(k)}">${esc(ajuda)}</p>
        </div>`;
    }
    form.innerHTML = html;
    configCarregada = true;
    configSuja = false;
    // O resumo dos cards de Plataformas sai dos mesmos campos, então precisa
    // de um repinto: o status costuma chegar antes e anunciaria "falta tudo"
    // até a volta seguinte. A gaveta é repintada só quando ninguém está
    // digitando nela — reescrever os inputs apagaria o que está em edição.
    pintarResumoPlataforma();
    if (gavetaChave && !gavetaDigitando()) pintarCamposGaveta(gavetaChave);
  } catch (e) {
    form.innerHTML = '<div class="alerta alerta-erro" style="grid-column:1/-1">' +
      icone("alert", "icone") + "<div>Não consegui carregar as credenciais do servidor.</div></div>";
  }
}

async function salvarConfig(event) {
  if (event) event.preventDefault();
  const body = {};
  $$("#formConfig input").forEach(el => { body[el.name] = el.value.trim(); });
  const btn = $("#btnSalvarConfig");
  btn.disabled = true;
  try {
    const r = await (await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })).json();
    if (r.erro) { toast(r.erro, "erro"); return; }
    configSuja = false;
    marcarConfigSuja(false);
    await carregarConfig(true);
    toast("Credenciais salvas no arquivo .env.", "ok");
    await atualizarStatus();
  } catch (e) {
    toast("Não consegui salvar. O arquivo .env continua como estava.", "erro");
  } finally {
    btn.disabled = false;
  }
}

/* ══ Conta do painel ═════════════════════════════════════════════════
   Criar conta é diferente de salvar uma credência: tem senha atual a
   confirmar, senha a repetir e nível de força. O card inteiro é
   redesenhado por `carregarConta` conforme exista conta ou não. */
let contaAtual = { existe: false, usuario: "", min_usuario: 3, min_senha: 8 };

/* Devolve 0..4. Não é criptografia — é só para a pessoa ver, antes de
   salvar, se escolheu algo que adivinha fácil. */
function forcaSenha(s) {
  if (!s) return 0;
  let p = 0;
  if (s.length >= 8) p++;
  if (s.length >= 12) p++;
  if (/[a-z]/.test(s) && /[A-Z]/.test(s)) p++;
  if (/\d/.test(s) && /[^\w\s]/.test(s)) p++;
  if (s.length < contaAtual.min_senha) p = Math.min(p, 1);
  return p;
}

function pintarForca() {
  const s = ($("#contaSenha") || {}).value || "";
  const caixa = $("#forcaCaixa");
  caixa.hidden = !s;
  if (!s) return;
  const n = forcaSenha(s);
  const rotulos = ["Muito fraca", "Fraca", "Razoável", "Boa", "Forte"];
  caixa.dataset.nivel = String(n);
  $("#forcaFill").style.width = (n * 25) + "%";
  $("#forcaTexto").textContent = rotulos[n];
}

function campo(id, rotulo, tipo, ajuda, autocomplete) {
  return `
    <div class="campo">
      <label for="${id}">${esc(rotulo)}</label>
      <input id="${id}" type="${tipo}" autocomplete="${autocomplete}" spellcheck="false"
             aria-describedby="aj_${id}">
      <p class="ajuda" id="aj_${id}">${esc(ajuda)}</p>
    </div>`;
}

async function carregarConta() {
  const form = $("#formConta");
  try {
    const r = await fetch("/api/conta", { cache: "no-store" });
    contaAtual = await r.json();
  } catch (e) {
    form.innerHTML = `<div class="alerta alerta-erro" style="grid-column:1/-1">${
      icone("alert", "icone")}<div>Não consegui falar com o servidor.</div></div>`;
    return;
  }

  const existe = contaAtual.existe;
  $("#contaEstado").innerHTML = existe
    ? `<span class="marca-ok">${icone("check")} conta ativa</span>`
    : `<span class="selo selo-espera"><span class="ponto" aria-hidden="true"></span>sem conta</span>`;

  $("#contaSub").textContent = existe
    ? `Uma conta já existe (${contaAtual.usuario}). Trocar a senha exige a senha atual.`
    : "Hoje o painel só responde à sua própria máquina. Crie uma conta para poder abrir de outro computador com segurança.";

  $("#btnSalvarContaTexto").textContent = existe ? "Trocar senha" : "Criar conta";
  $("#btnRemoverConta").hidden = !existe;

  if (existe) {
    form.innerHTML =
      campo("contaSenhaAtual", "Senha atual", "password", "Confirma que é você.", "current-password") +
      campo("contaSenha", "Nova senha", "password",
            `Mínimo de ${contaAtual.min_senha} caracteres.`, "new-password") +
      campo("contaConfirmar", "Repetir a nova senha", "password", "Os dois campos precisam bater.", "new-password");
  } else {
    form.innerHTML =
      campo("contaUsuario", "Usuário", "text", `Mínimo de ${contaAtual.min_usuario} caracteres.`, "username") +
      campo("contaSenha", "Senha", "password",
            `Mínimo de ${contaAtual.min_senha} caracteres. Misture letras, números e símbolos.`, "new-password") +
      campo("contaConfirmar", "Repetir a senha", "password", "Os dois campos precisam bater.", "new-password");
  }

  const senha = $("#contaSenha");
  senha?.addEventListener("input", pintarForca);
  $("#forcaCaixa").hidden = true;
}

async function salvarConta(event) {
  if (event) event.preventDefault();
  const btn = $("#btnSalvarConta");
  const body = {
    senha: ($("#contaSenha") || {}).value || "",
    confirmar: ($("#contaConfirmar") || {}).value || "",
  };
  if (contaAtual.existe) {
    body.senha_atual = ($("#contaSenhaAtual") || {}).value || "";
  } else {
    body.usuario = (($("#contaUsuario") || {}).value || "").trim();
  }
  btn.disabled = true;
  try {
    const r = await fetch("/api/conta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.erro) { toast(d.erro, "erro"); return; }
    await carregarConta();
    toast(d.criada ? `Conta "${d.usuario}" criada. Ela vale já na próxima abertura.`
                   : "Senha trocada. As outras sessões foram encerradas.", "ok");
  } catch (e) {
    toast("Não consegui falar com o servidor.", "erro");
  } finally {
    btn.disabled = false;
  }
}

async function removerConta() {
  // Reaproveita o campo "Senha atual" em vez de abrir um prompt() do
  // navegador: diálogo nativo quebra o visual do painel e não mostra
  // o que está acontecendo. Se o campo estiver vazio, é só pedir.
  const campoAtual = $("#contaSenhaAtual");
  const senha = (campoAtual?.value || "").trim();
  if (!senha) {
    campoAtual?.focus();
    toast("Digite a senha atual no campo acima para remover o acesso.", "erro");
    return;
  }
  const btn = $("#btnRemoverConta");
  btn.disabled = true;
  try {
    const r = await fetch("/api/conta/remover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ senha }),
    });
    const d = await r.json();
    if (d.erro) { toast(d.erro, "erro"); return; }
    // Recarrega para a tela sair do estado "logado" com um cookie morto.
    location.reload();
  } catch (e) {
    toast("Não consegui falar com o servidor.", "erro");
  } finally {
    btn.disabled = false;
  }
}

/* `alvoSel` e onde o resultado aparece e `naGaveta` diz de qual formulario os
   ids detectados sao escritos. Sem os dois, o botao da gaveta desenhava o
   resultado na aba Configuracoes - fora da tela - e os ids escolhidos nao
   preenchiam campo nenhum, porque o #cfg_ sumiu do DOM quando os campos de
   plataforma sairam do formulario generico. */
async function detectarIds(alvoSel, naGaveta) {
  const caixa = $(alvoSel || "#caixaDeteccao");
  if (!caixa) return;
  const onde = naGaveta ? "true" : "false";
  caixa.innerHTML = `<div class="alerta alerta-info">${icone("search", "icone")}<div>Consultando o Telegram…</div></div>`;
  try {
    const r = await (await fetch("/api/detectar-ids", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    })).json();

    if (r.erro) {
      caixa.innerHTML = `<div class="alerta alerta-espera" role="alert">${icone("alert", "icone")}<div>${esc(r.erro)}</div></div>`;
      return;
    }
    if (r.aviso) {
      caixa.innerHTML = `<div class="alerta alerta-espera">${icone("alert-triangle", "icone")}<div>${esc(r.aviso)}</div></div>`;
      return;
    }
    if (r.vazio || !(r.pessoas || []).length && !(r.canais || []).length) {
      caixa.innerHTML = `<div class="alerta alerta-info">${icone("search", "icone")}<div>
        Nada encontrado ainda. No Telegram envie <code>/id</code> para o bot no privado e
        <code>encaminhe um post do canal</code> para ele. Depois clique aqui de novo.
      </div></div>`;
      return;
    }

    let h = '<div class="escolhas">';
    (r.pessoas || []).forEach(p => {
      h += `<div class="escolha-rot">Quem é você</div>
        <button type="button" class="escolha" onclick="setCampoId('TELEGRAM_OWNER_ID', ${esc(JSON.stringify(String(p.id)))}, ${onde})">
          ${icone("user", "icone")} <b>${esc(p.nome)}</b> <code>${esc(p.id)}</code>
        </button>`;
    });
    (r.canais || []).forEach(c => {
      h += `<div class="escolha-rot">Canais e grupos</div>
        <button type="button" class="escolha" onclick="setCampoId('TELEGRAM_CHAT_ID', ${esc(JSON.stringify(String(c.id)))}, ${onde})">
          ${icone("megaphone", "icone")} <b>${esc(c.nome)}</b> <code>${esc(c.id)}</code>
        </button>`;
    });
    caixa.innerHTML = h + "</div>";
  } catch (e) {
    caixa.innerHTML = `<div class="alerta alerta-erro" role="alert">${icone("alert", "icone")}<div>Erro ao consultar o Telegram.</div></div>`;
  }
}

function setCampoId(campo, valor, naGaveta) {
  /* Os ids da gaveta vivem em #gav_ e os do formulario de Configuracoes em
     #cfg_. Antes these dois caminhos eram o mesmo elemento; quando os campos
     de plataforma foram para a gaveta, o #cfg_ deixou de existir para eles e
     esta funcao passou a sair em silencio, sem preencher nada. */
  const el = naGaveta ? $("#gav_" + campo) : $("#cfg_" + campo);
  if (!el) {
    toast("Campo " + campo + " não está na tela para preencher.", "erro");
    return;
  }
  el.value = valor;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  if (naGaveta) {
    // A gaveta nao tem aviso proprio: #gavetaDica e reescrito pelo polling a
    // cada 2,5s. O toast e global, entao e ele quem avisa.
    toast("Campo preenchido. Clique em Salvar para gravar.", "ok");
  } else {
    const aviso = $("#configAviso");
    aviso.textContent = "Campo preenchido - não esqueça de salvar.";
    toast("Campo preenchido. Salve para gravar no .env.", "ok");
  }
  el.focus();
}

/* ══ Nichos ═══════════════════════════════════════════════════════════ */
async function carregarNichos() {
  const grade = $("#nichosGrade");
  if (!grade) return;
  if (grade.children.length) return;          // não redesenha: preserva a seleção
  try {
    const r = await (await fetch("/api/nichos", { cache: "no-store" })).json();
    (r.selecionados || []).forEach(c => NICHOS_SEL.add(c));
    grade.innerHTML = (r.catalogo || []).map(n => `
      <button type="button" class="nicho" role="checkbox" data-chave="${esc(n.chave)}"
              aria-checked="${NICHOS_SEL.has(n.chave)}"
              onclick="alternarNicho(this)">
        ${icone(NOME_ICONE_NICHO[n.icone] || n.icone || "store", "icone")}
        <span class="rot">${esc(n.nome)}</span>
        <span class="nicho-caixa" aria-hidden="true">${icone("check")}</span>
      </button>`).join("");
    atualizarContadorNichos();
  } catch (e) {
    grade.innerHTML = vazio("Não consegui carregar as categorias", "Tente recarregar a página.", "alert");
  }
}

function alternarNicho(el) {
  const chave = el.dataset.chave;
  const marcado = el.getAttribute("aria-checked") === "true";
  el.setAttribute("aria-checked", marcado ? "false" : "true");
  if (marcado) NICHOS_SEL.delete(chave); else NICHOS_SEL.add(chave);
  atualizarContadorNichos();
}

function atualizarContadorNichos() {
  const n = NICHOS_SEL.size;
  $("#nichosContador").textContent = n === 0
    ? "Buscando em todas as categorias"
    : `${n} categoria${n > 1 ? "s" : ""} marcada${n > 1 ? "s" : ""}`;
}

async function salvarNichos() {
  try {
    await fetch("/api/nichos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selecionados: [...NICHOS_SEL] }),
    });
    toast(NICHOS_SEL.size
      ? `${NICHOS_SEL.size} categoria(s) salvas. Reinicie o bot para aplicar.`
      : "Seleção limpa: o bot voltará a buscar em todas as categorias.", "ok");
    await atualizarStatus();
  } catch (e) {
    toast("Não consegui salvar as categorias.", "erro");
  }
}

function limparNichos() {
  NICHOS_SEL.clear();
  $$(".nicho").forEach(el => el.setAttribute("aria-checked", "false"));
  atualizarContadorNichos();
}

/* ══ Produtos ════════════════════════════════════════════════════════ */
async function carregarProdutos() {
  const corpo = $("#produtosCorpo");
  if (!corpo) return;
  try {
    const r = await (await fetch("/api/produtos", { cache: "no-store" })).json();
    const lista = r.produtos || [];
    if (!lista.length) {
      corpo.innerHTML = `<tr><td colspan="5">${vazio("Nenhuma oferta publicada",
        "Rode um ciclo na aba Plataformas para o bot começar a postar.", "inbox")}</td></tr>`;
      return;
    }
    corpo.innerHTML = lista.map(p => {
      const plat = p.plataforma || "mercadolivre";
      const preco = p.preco ? `R$ ${Number(p.preco).toFixed(2).replace(".", ",")}` : "—";
      const acao = p.url_afiliado
        ? `<a class="btn btn-neutro btn-sm" href="${esc(p.url_afiliado)}" target="_blank" rel="noopener noreferrer">
             ${icone("external")} Abrir</a>`
        : `<span class="selo selo-neutro">sem link</span>`;
      const logoSrc = LOGO_PLATAFORMA[plat] || LOGO_PLATAFORMA[NOME_PLATAFORMA[plat]] || "";
      const platBadge = logoSrc
        ? `<span class="selo selo-neutro" style="display:inline-flex; align-items:center; gap:6px;"><div class="tab-logo-caixa"><img src="${logoSrc}" alt="" class="tab-logo-img"></div> ${esc(NOME_PLATAFORMA[plat] || plat)}</span>`
        : `<span class="selo selo-neutro">${icone(ICONE_PLATAFORMA[plat] || "tag")} ${esc(NOME_PLATAFORMA[plat] || plat)}</span>`;
      return `
        <tr>
          <td>${platBadge}</td>
          <td class="tit">${esc(p.titulo || "Produto sem título")}</td>
          <td class="preco">${esc(preco)}</td>
          <td class="quando">${esc(p.postada_em ? p.postada_em.replace("T", " ") : "—")}</td>
          <td>${acao}</td>
        </tr>`;
    }).join("");
  } catch (e) {
    corpo.innerHTML = `<tr><td colspan="5"><div class="alerta alerta-erro">${icone("alert", "icone")}<div>Erro ao carregar os produtos.</div></div></td></tr>`;
  }
}

/* ══ Modais ══════════════════════════════════════════════════════════ */
const FOCO_RAIZ = "botCartao";
const FOCAVEIS = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function abrirModal(id) {
  const m = $("#" + id);
  if (!m) return;
  ultimoFoco = document.activeElement;
  m.hidden = false;
  m.classList.add("aberto");
  document.addEventListener("keydown", aoTeclarModal, true);
  // O foco só pega no quadro seguinte: enquanto o overlay está em
  // display:none, qualquer .focus() dentro dele é ignorado em silêncio.
  requestAnimationFrame(() => {
    // Prioridade: marcador explícito > primeiro campo útil > botão do rodapé.
    const foco = m.querySelector("[data-foco-inicial]")
      || m.querySelector("input:not([type=hidden]), select, textarea")
      || $$("button:not([data-fechar])", m).pop()
      || m.querySelector("[data-fechar]")
      || m;
    foco.focus();
  });
}

function fecharModal(id) {
  const m = $("#" + id);
  if (!m) return;
  m.classList.remove("aberto");
  document.removeEventListener("keydown", aoTeclarModal, true);
  setTimeout(() => { m.hidden = true; }, 200);
  if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  else { const alt = $("#" + FOCO_RAIZ); if (alt) alt.focus(); }
}

function aoTeclarModal(ev) {
  const aberta = $$(".overlay.aberto").pop();
  if (!aberta) return;
  if (ev.key === "Escape") { ev.preventDefault(); fecharModal(aberta.id); return; }
  if (ev.key !== "Tab") return;
  const focaveis = $$(FOCAVEIS, aberta).filter(el => el.offsetParent !== null);
  if (!focaveis.length) return;
  const primeiro = focaveis[0], ultimo = focaveis[focaveis.length - 1];
  const dentro = aberta.contains(document.activeElement);
  // Não basta tratar as pontas: se o foco escapou, traz de volta.
  if (ev.shiftKey && (!dentro || document.activeElement === primeiro)) {
    ev.preventDefault(); ultimo.focus();
  } else if (!ev.shiftKey && (!dentro || document.activeElement === ultimo)) {
    ev.preventDefault(); primeiro.focus();
  }
}

function abrirModalLink() {
  abrirModal("modalLink");
}

function abrirModalSessao() {
  abrirModal("modalSessao");
  carregarSessaoModal();
}

async function carregarSessaoModal() {
  const corpo = $("#modalSessaoCorpo");
  corpo.innerHTML = vazio("Verificando a sessão…", "", "refresh");
  try {
    const r = await (await fetch("/api/verificar-sessao", { method: "POST" })).json();
    corpo.innerHTML = `
      <div class="painel-info">
        <dl>
          <dt>Status</dt>
          <dd style="color:${r.sessao_ml ? "var(--ok)" : "var(--alerta)"}">
            ${r.sessao_ml ? "Ativa e persistente" : "Pendente — faça o login"}
          </dd>
          <dt>Arquivos no perfil</dt>
          <dd>${r.arquivos}</dd>
          <dd class="caminho">${esc(r.caminho)}</dd>
        </dl>
      </div>
      <p class="ajuda" style="margin-top:10px">
        A sessão fica só neste computador e é usada pelo link builder do Mercado Livre.
        Se as ofertas pararem de virar link, limpe a sessão e faça o login de novo.
      </p>`;
  } catch (e) {
    corpo.innerHTML = `<div class="alerta alerta-erro" role="alert">${icone("alert", "icone")}<div>Não consegui verificar a sessão.</div></div>`;
  }
}

function abrirLoginMl() { fecharModal("modalSessao"); executarAcao("ml-login"); }

async function limparSessao() {
  if (!confirm("Apagar a sessão local do Mercado Livre? Você vai precisar fazer login de novo.")) return;
  try {
    const r = await (await fetch("/api/limpar-sessao", { method: "POST" })).json();
    if (r.erro) { toast(r.erro, "erro"); return; }
    toast(r.msg || "Sessão apagada.", "ok");
    await atualizarStatus();
  } catch (e) {
    toast("Não consegui apagar a sessão.", "erro");
  }
}

/* ══ Link builder ════════════════════════════════════════════════════ */
async function gerarLink(event) {
  event.preventDefault();
  const url = $("#entradaUrl").value.trim();
  const err = $("#erroUrl");
  err.textContent = "";
  if (!url) { err.textContent = "Cole o link do produto."; $("#entradaUrl").focus(); return; }
  if (!/^https?:\/\/\S+$/i.test(url)) { err.textContent = "O link precisa começar com http:// ou https://."; $("#entradaUrl").focus(); return; }

  const btn = $("#btnGerarLink");
  btn.disabled = true;
  try {
    const r = await (await fetch("/api/gerar-link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, plataforma: $("#entradaPlataforma").value }),
    })).json();
    if (!r.ok || !r.url_afiliado) { toast(r.erro || "Não consegui gerar o link.", "erro"); return; }

    $("#caixaResultado").hidden = false;
    $("#saidaUrl").value = r.url_afiliado;
    $("#saidaInfo").textContent =
      `Plataforma: ${NOME_PLATAFORMA[r.plataforma] || r.plataforma} · gerado em ${r.criado_em}`;
    $("#saidaUrl").focus();
    $("#saidaUrl").select();
    toast("Link de afiliado gerado.", "ok");
  } catch (e) {
    toast("Erro de rede ao gerar o link.", "erro");
  } finally {
    btn.disabled = false;
  }
}

function copiarSaida() {
  const el = $("#saidaUrl");
  if (el) copiarTexto(el.value);
}

function copiarTexto(txt) {
  if (!txt) return;
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(txt)
      .then(() => toast("Copiado.", "ok"))
      .catch(() => copiarLegado(txt));
  } else {
    copiarLegado(txt);
  }
}

function copiarLegado(txt) {
  const ta = document.createElement("textarea");
  ta.value = txt;
  ta.setAttribute("readonly", "");
  ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  document.body.removeChild(ta);
  toast(ok ? "Copiado." : "Não consegui copiar — selecione e copie manualmente.", ok ? "ok" : "espera");
}

/* ══ Toasts ══════════════════════════════════════════════════════════ */
const TOAST_ICONE = { ok: "check-circle", erro: "alert", espera: "alert-triangle", alerta: "alert-triangle", info: "alert" };

function toast(msg, tipo = "info", duracao = 4200) {
  const caixa = $("#caixaToasts");
  if (!caixa) return;
  const t = document.createElement("div");
  // tipo desconhecido caía em "toast-<tipo>" sem estilo nenhum; agora normaliza.
  const classe = TOAST_ICONE[tipo] ? tipo : "info";
  t.className = `toast toast-${classe}`;
  t.innerHTML = icone(TOAST_ICONE[classe]) + `<span>${esc(msg)}</span>`;
  caixa.appendChild(t);
  const sair = () => { t.classList.remove("entrou"); setTimeout(() => t.remove(), 320); };
  setTimeout(() => t.classList.add("entrou"), 20);
  setTimeout(sair, duracao);
  t.addEventListener("click", sair);
}

/* ══ Ligações de eventos ═════════════════════════════════════════════ */
function ligarEventos() {
  // Conta do painel. O <form> é trocado de conteúdo por carregarConta(),
  // mas o elemento em si continua o mesmo — por isso o ouvinte sobrevive.
  $("#formConta")?.addEventListener("submit", ev => {
    ev.preventDefault();
    salvarConta();
  });
  $("#btnRemoverConta")?.addEventListener("click", removerConta);

  // Navegação (delegação — os itens nascem junto com o HTML)
  $$(".nav-item").forEach(el => el.addEventListener("click", ev => {
    ev.preventDefault();
    switchView(el.dataset.view);
  }));
  $(".brand").addEventListener("click", ev => { ev.preventDefault(); irPara("dashboard"); });
  $("#botCartao").addEventListener("click", alternarBot);

  // Fechar modais
  $$("[data-fechar]").forEach(b => b.addEventListener("click", () => fecharModal(b.dataset.fechar)));
  $$(".overlay").forEach(o => o.addEventListener("mousedown", ev => {
    if (ev.target === o) fecharModal(o.id);
  }));

  // Formulários
  $("#formConfig").addEventListener("submit", salvarConfig);
  $("#formLink").addEventListener("submit", gerarLink);

  // Marca o formulário como editado para não perder o que foi digitado
  $("#formConfig").addEventListener("input", () => { configSuja = true; marcarConfigSuja(true); });

  // Digitar Enter no link builder já gera
  $("#entradaUrl").addEventListener("keydown", ev => {
    if (ev.key === "Enter") { ev.preventDefault(); gerarLink(ev); }
  });

  // Atalhos: 1..7 trocam de aba, "?" abre a busca de IDs
  document.addEventListener("keydown", ev => {
    if (ev.target.matches("input, select, textarea") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if ($$(".overlay.aberto").length) return;
    const ordem = $$(".nav-item").map(n => n.dataset.view);
    const n = Number(ev.key);
    if (n >= 1 && n <= ordem.length) { ev.preventDefault(); switchView(ordem[n - 1]); }
    if (ev.key === "?") { ev.preventDefault(); switchView("config"); detectarIds(); }
  });

  // Redesenha o gráfico quando a caixa muda de tamanho (resize, zoom, sidebar)
  let tmr = null;
  const redraw = () => { clearTimeout(tmr); tmr = setTimeout(desenharGraficos, 140); };
  window.addEventListener("resize", redraw);
  if (window.ResizeObserver) {
    new ResizeObserver(redraw).observe($(".grafico-caixa") || document.body);
  }

  // Recarrega a aba inicial vindo da URL
  window.addEventListener("hashchange", () => {
    const alvo = location.hash.slice(1);
    if (alvo && $("#view-" + alvo)) switchView(alvo);
  });
}

/* ══ Autenticação ═════════════════════════════════════════════════════
   O painel mexe em segredos e liga/desliga o bot, então tudo abaixo de
   /api/ responde 401 sem sessão. Em vez de tratar isso em cada uma das
   16 chamadas, o fetch global observa a resposta: qualquer 401 abre a
   tela de login e para o painel. */
const _fetchReal = window.fetch.bind(window);
let _loginAberto = false;

function abrirLogin(motivo = "") {
  if (_loginAberto) return;
  _loginAberto = true;
  const tela = $("#telaLogin");
  if (motivo) $("#loginAviso").textContent = motivo;
  tela.hidden = false;
  tela.classList.add("aberto");
  document.body.classList.add("travado");
  requestAnimationFrame(() => $("#loginUsuario")?.focus());
}

/* "Sair" só faz sentido se o painel estiver protegido por senha — sem
   credenciais não existe sessão para encerrar. Chamado tanto no boot
   quanto depois de entrar, senão o botão ficaria oculto justamente
   quando o usuário entrou por senha. */
function ajustarBotaoSair(configurado, usuario) {
  const b = $("#btnSair");
  if (b) b.hidden = !configurado;
  if (configurado) $("#ladoSessao").textContent = "Sessão de " + (usuario || "usuário");
}

function fecharLogin() {
  _loginAberto = false;
  const tela = $("#telaLogin");
  tela.hidden = true;
  tela.classList.remove("aberto");
  document.body.classList.remove("travado");
  $("#loginErro").textContent = "";
  $("#loginSenha").value = "";
}

window.fetch = async (...args) => {
  const resp = await _fetchReal(...args);
  const url = String(args[0] || "");
  if (resp.status === 401 && !url.includes("/api/login") && !url.includes("/api/auth-status")) {
    abrirLogin("Sua sessão expirou. Entre de novo para continuar.");
  }
  return resp;
};

async function entrar() {
  const usuario = $("#loginUsuario").value.trim();
  const senha = $("#loginSenha").value;
  const erro = $("#loginErro");
  erro.textContent = "";
  if (!usuario || !senha) {
    erro.textContent = "Preencha usuário e senha.";
    return;
  }
  const btn = $("#loginEntrar");
  btn.disabled = true;
  try {
    const r = await _fetchReal("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, senha }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.erro || "Não foi possível entrar.");
    ajustarBotaoSair(true, d.usuario);
    fecharLogin();
    await iniciar();               // app nunca tinha subido: agora sobe
  } catch (e) {
    erro.textContent = e.message;
    $("#loginSenha").select();
  } finally {
    btn.disabled = false;
  }
}

async function sair() {
  await _fetchReal("/api/logout", { method: "POST" });
  location.reload();
}

async function abrirLoginSePrecisar() {
  try {
    const r = await _fetchReal("/api/auth-status", { cache: "no-store" });
    const d = await r.json();
    if (d.autenticado) {
      ajustarBotaoSair(d.configurado, d.user);
      return true;
    }
    if (d.configurado) {
      abrirLogin();
      return false;
    }
    // Sem credenciais: liberado por estar em 127.0.0.1. Avisa, mas não trava.
    ajustarBotaoSair(false, "");
    toast("PAINEL_USUARIO/PAINEL_SENHA não definidos: este painel só está " +
          "protegido por rodar em 127.0.0.1.", "alerta", 7000);
    return true;
  } catch (e) {
    abrirLogin("Não consegui falar com o painel.");
    return false;
  }
}

/* ══ Filtros de Produtos ═════════════════════════════════════════════ */

/* O config guarda avaliacao_minima como float. Um <select> só casa por
   igualdade de string, e String(4.0) é "4" — não "4.0". Quando não havia
   option correspondente, o select ficava vazio, caía no primeiro item
   ("Desativado") e o salvar seguinte gravava 0.0: o filtro de avaliação era
   apagado sem nenhuma mensagem. Injetamos a option que falta para que
   qualquer valor gravado continue visível. */
function definirSelectComFallback(sel, valor) {
  if (!sel) return;
  const bruto = String(valor ?? 0);
  if (![...sel.options].some(o => o.value === bruto)) {
    const extra = document.createElement("option");
    extra.value = bruto;
    extra.textContent = `${Number(bruto).toFixed(1)} (valor salvo)`;
    sel.appendChild(extra);
  }
  sel.value = bruto;
}

async function carregarFiltros() {
  try {
    const r = await fetch("/api/filtros", { cache: "no-store" });
    const f = await r.json();
    definirSelectComFallback($("#filtroAvaliacao"), f.avaliacao_minima ?? 0);
    if ($("#filtroVendas")) $("#filtroVendas").value = String(f.vendas_minimas ?? 0);
    // Aceita os dois nomes: o backend agora devolve ambos.
    if ($("#filtroDesconto")) $("#filtroDesconto").value = f.desconto_minimo_pct ?? f.desconto_minimo ?? 0;
    if ($("#filtroPrecoMin")) $("#filtroPrecoMin").value = f.preco_minimo ?? "";
    if ($("#filtroPrecoMax")) $("#filtroPrecoMax").value = f.preco_maximo ?? "";
    if ($("#filtroSemAvaliacao")) $("#filtroSemAvaliacao").value = String(f.permitir_sem_avaliacao !== false);
    if ($("#filtroSemVendas")) $("#filtroSemVendas").value = String(f.permitir_sem_vendas !== false);
    if ($("#filtroSemDesconto")) $("#filtroSemDesconto").value = String(f.permitir_sem_desconto !== false);
  } catch (e) {
    console.error("Erro ao carregar filtros:", e);
  }
}

async function salvarFiltros() {
  const body = {
    avaliacao_minima: parseFloat($("#filtroAvaliacao")?.value || 0),
    vendas_minimas: parseInt($("#filtroVendas")?.value || 0, 10),
    desconto_minimo_pct: parseFloat($("#filtroDesconto")?.value || 0),
    preco_minimo: $("#filtroPrecoMin")?.value ? parseFloat($("#filtroPrecoMin").value) : null,
    preco_maximo: $("#filtroPrecoMax")?.value ? parseFloat($("#filtroPrecoMax").value) : null,
    permitir_sem_avaliacao: $("#filtroSemAvaliacao")?.value === "true",
    permitir_sem_vendas: $("#filtroSemVendas")?.value === "true",
    permitir_sem_desconto: $("#filtroSemDesconto")?.value === "true",
  };
  try {
    const r = await fetch("/api/filtros", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.ok) {
      toast("Filtros de produtos atualizados com sucesso!", "ok");
    } else {
      toast(d.erro || "Erro ao salvar filtros.", "erro");
    }
  } catch (e) {
    toast("Erro ao comunicar com o servidor.", "erro");
  }
}

/* ══ Controle de Publicação e Cadência ═══════════════════════════════ */
/* A tela trabalha em MINUTOS; a API, o config.yaml e o pipeline continuam
   em SEGUNDOS. A conversão fica estes dois helpers e em mais lugar nenhum —
   foi o que evitou o config voltar em segundos depois de um round-trip. */
const SEG_POR_MIN = 60;
const segParaMin = (s, padrao) => (s == null ? padrao : Math.round(Number(s) / SEG_POR_MIN));
const minParaSeg = (m, padrao) => (m == null ? padrao : Math.max(0, Math.round(Number(m) * SEG_POR_MIN)));

/* ══ Cadência das publicações ═══════════════════════════════════════════
   O bloco `geral` do config.yaml — o que o bot realmente segue.

   Diferente do card ao lado, este NÃO é recarregado a cada 5s: repintar o
   formulário enquanto a pessoa digita apagaria o que ela estava escrevendo.
   Carrega uma vez na abertura e depois de salvar. */
async function carregarCadencia() {
  try {
    const r = await fetch("/api/cadencia", { cache: "no-store" });
    if (!r.ok) return;
    const c = await r.json();
    if ($("#cadIntervalo")) $("#cadIntervalo").value = c.intervalo_minutos ?? 45;
    if ($("#cadMaxPosts")) $("#cadMaxPosts").value = c.max_posts_por_ciclo ?? 3;
    if ($("#cadEspacamento")) $("#cadEspacamento").value = c.espacamento_segundos ?? 120;
    if ($("#cadNaoRepetir")) $("#cadNaoRepetir").value = c.nao_repetir_dias ?? 7;
    if ($("#cadHorario")) $("#cadHorario").value = c.horario_ativo ?? "";
  } catch (e) {
    console.error("Erro ao carregar cadência:", e);
  }
}

async function salvarCadencia() {
  const body = {
    intervalo_minutos: parseInt($("#cadIntervalo")?.value || 0, 10),
    max_posts_por_ciclo: parseInt($("#cadMaxPosts")?.value || 0, 10),
    espacamento_segundos: parseInt($("#cadEspacamento")?.value || 0, 10),
    nao_repetir_dias: parseInt($("#cadNaoRepetir")?.value || 0, 10),
    horario_ativo: ($("#cadHorario")?.value || "").trim(),
  };
  const aviso = $("#cadAviso");
  try {
    const r = await fetch("/api/cadencia", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.ok) {
      // O aviso fica na tela porque o efeito é diferido: o bot em execução
      // já tem os valores na memória e só relê no próximo start.
      if (aviso) aviso.textContent = "Salvo. Vale para o bot no próximo start.";
      toast("Cadência salva!", "ok");
      await carregarCadencia();
    } else {
      const msg = d.erro || "Erro ao salvar a cadência.";
      if (aviso) aviso.textContent = msg;
      toast(msg, "erro");
    }
  } catch (e) {
    toast("Erro ao comunicar com o servidor.", "erro");
  }
}

async function carregarPublicacao() {
  try {
    const r = await fetch("/api/publicacao-controle", { cache: "no-store" });
    const p = await r.json();
    const cfg = p.config || {};
    const st = p.status || {};
    if ($("#pubIntervalo")) $("#pubIntervalo").value = segParaMin(cfg.intervalo_entre_posts_segundos, 5);
    if ($("#pubPostsAntesPausa")) $("#pubPostsAntesPausa").value = cfg.posts_antes_pausa ?? 5;
    if ($("#pubTempoPausa")) $("#pubTempoPausa").value = segParaMin(cfg.tempo_pausa_segundos, 30);
    if ($("#pubMaxPosts")) $("#pubMaxPosts").value = cfg.max_posts_periodo ?? 20;
    if ($("#pubPeriodoHoras")) $("#pubPeriodoHoras").value = cfg.periodo_horas ?? 24;

    const elSt = $("#pubStatusCadencia");
    if (elSt) {
      let txt = `Posts no bloco atual: <b>${st.posts_no_bloco_atual ?? 0}</b> / ${cfg.posts_antes_pausa || '∞'} | `;
      txt += `Total no período: <b>${st.posts_no_periodo_atual ?? 0}</b> / ${cfg.max_posts_periodo || '∞'}`;
      if (st.em_pausa) {
        txt += ` <span class="selo selo-espera"><span class="ponto"></span>Em pausa até ${st.pausa_ate ? new Date(st.pausa_ate * 1000).toLocaleTimeString() : ''}</span>`;
      } else if (st.limite_atingido) {
        txt += ` <span class="selo selo-espera"><span class="ponto"></span>Limite do período atingido</span>`;
      } else {
        txt += ` <span class="selo selo-ok"><span class="ponto"></span>Pronto para postar</span>`;
      }
      /* motivo_espera/restante_segundos já vinham na API e não eram lidos em
         lugar nenhum. Agora que a tela é em minutos, mostrar "faltam N min"
         é o que fecha a conta com os campos de cima. */
      const motivo = st.motivo_espera || "";
      const restante = Number(st.restante_segundos || 0);
      if (motivo && motivo !== "pronto" && restante > 0) {
        const min = Math.ceil(restante / SEG_POR_MIN);
        txt += ` <span class="selo selo-espera"><span class="ponto"></span>${esc(motivo)} — faltam ~${min} min</span>`;
      }
      elSt.innerHTML = txt;
    }
  } catch (e) {
    console.error("Erro ao carregar publicação:", e);
  }
}

async function salvarPublicacao() {
  const body = {
    intervalo_entre_posts_segundos: minParaSeg($("#pubIntervalo")?.value, 300),
    posts_antes_pausa: parseInt($("#pubPostsAntesPausa")?.value || 5, 10),
    tempo_pausa_segundos: minParaSeg($("#pubTempoPausa")?.value, 1800),
    max_posts_periodo: parseInt($("#pubMaxPosts")?.value || 20, 10),
    periodo_horas: parseInt($("#pubPeriodoHoras")?.value || 24, 10),
  };
  try {
    const r = await fetch("/api/publicacao-controle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.ok) {
      toast("Controle de publicação salvo com sucesso!", "ok");
      await carregarPublicacao();
    } else {
      toast(d.erro || "Erro ao salvar publicação.", "erro");
    }
  } catch (e) {
    toast("Erro ao comunicar com o servidor.", "erro");
  }
}

async function resetarCadenciaPublicacao() {
  try {
    const r = await fetch("/api/publicacao-controle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset_cadencia: true }),
    });
    const d = await r.json();
    if (d.ok) {
      toast("Contadores de cadência zerados!", "ok");
      await carregarPublicacao();
    }
  } catch (e) {
    toast("Erro ao resetar contadores.", "erro");
  }
}

/* ══ Fontes de Scraping Telegram ═════════════════════════════════════ */
async function carregarFontesTelegram() {
  try {
    const [rFontes, rCfg] = await Promise.all([
      fetch("/api/fontes-telegram", { cache: "no-store" }).then(r => r.json()),
      fetch("/api/scraping-config", { cache: "no-store" }).then(r => r.json()).catch(() => ({})),
    ]);

    const corpo = $("#tabelaFontesTelegramCorpo");
    if (corpo) {
      const fontes = rFontes.fontes || [];
      if (!fontes.length) {
        corpo.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:18px; color:var(--texto-3);">Nenhuma fonte cadastrada ainda. Adicione acima.</td></tr>`;
      } else {
        corpo.innerHTML = fontes.map(f => {
          /* Estes são os nomes reais das colunas: chat_id / ativa /
             ultimo_processamento. A tela usava username / ativo /
             ultima_captura, que não existem — daí o "undefined" nos botões
             e o "ID da fonte é obrigatório" ao excluir. */
          const chatId = f.chat_id ?? f.username ?? "";
          const ativo = f.ativa === 1 || f.ativa === true;
          const statusSelo = ativo
            ? `<span class="selo selo-ok"><span class="ponto"></span>Ativo</span>`
            : `<span class="selo selo-neutro"><span class="ponto"></span>Inativo</span>`;
          const ultima = f.ultimo_processamento || f.ultima_captura || "—";
          return `
            <tr>
              <td><b>${esc(f.nome || chatId)}</b></td>
              <td><code>${esc(chatId)}</code></td>
              <td>${statusSelo}</td>
              <td class="quando">${esc(ultima === "—" ? ultima : ultima.replace("T", " "))}</td>
              <td style="text-align:right;">
                <button type="button" class="btn btn-neutro btn-sm" onclick="testarConexaoFonteItem('${esc(chatId)}', this)" title="Testar acesso">
                  ${icone("refresh")} Testar
                </button>
                <button type="button" class="btn btn-neutro btn-sm" onclick="alternarStatusFonteTelegram('${esc(chatId)}', ${!ativo})">
                  ${ativo ? "Desativar" : "Ativar"}
                </button>
                <button type="button" class="btn btn-perigo btn-sm" onclick="removerFonteTelegram('${esc(chatId)}')">
                  ${icone("trash")}
                </button>
              </td>
            </tr>`;
        }).join("");
      }
    }

    if (rCfg) {
      if ($("#scrapingAtivo")) $("#scrapingAtivo").value = String(rCfg.ativo !== false);
      if ($("#scrapingIntervalo")) $("#scrapingIntervalo").value = rCfg.intervalo_segundos || 30;
      if ($("#scrapingLimiteMsg")) $("#scrapingLimiteMsg").value = rCfg.limite_mensagens_por_ciclo || 20;
    }
  } catch (e) {
    console.error("Erro ao carregar fontes Telegram:", e);
  }
}

async function adicionarFonteTelegram(event) {
  if (event) event.preventDefault();
  const username = ($("#novaFonteUsername")?.value || "").trim();
  const nome = ($("#novaFonteNome")?.value || "").trim();
  if (!username) {
    toast("Informe o @username ou link do canal/grupo.", "espera");
    return;
  }
  try {
    const r = await fetch("/api/fontes-telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, nome, ativo: true }),
    });
    const d = await r.json();
    if (d.ok) {
      toast(`Fonte ${d.fonte?.username || username} adicionada!`, "ok");
      if ($("#novaFonteUsername")) $("#novaFonteUsername").value = "";
      if ($("#novaFonteNome")) $("#novaFonteNome").value = "";
      await carregarFontesTelegram();
    } else {
      toast(d.erro || "Erro ao adicionar fonte.", "erro");
    }
  } catch (e) {
    toast("Erro de conexão ao salvar fonte.", "erro");
  }
}

async function testarConexaoFonteNova() {
  const username = ($("#novaFonteUsername")?.value || "").trim();
  if (!username) {
    toast("Informe o @username para testar.", "espera");
    return;
  }
  await testarConexaoFonte(username);
}

async function testarConexaoFonteItem(username, btnEl) {
  if (btnEl) btnEl.disabled = true;
  try {
    await testarConexaoFonte(username);
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

async function testarConexaoFonte(username) {
  toast(`Testando acesso a ${username}…`, "info");
  try {
    const r = await fetch("/api/fontes-telegram/testar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    const d = await r.json();
    if (d.ok) {
      toast(`Conexão OK com ${d.titulo || d.username} (${d.tipo || 'canal/grupo'})!`, "ok");
    } else {
      toast(d.erro || `Falha ao acessar ${username}. Verifique se é público ou se o bot é membro.`, "erro");
    }
  } catch (e) {
    toast("Erro ao testar conexão com Telegram.", "erro");
  }
}

async function alternarStatusFonteTelegram(chatId, novoAtivo) {
  try {
    const r = await fetch("/api/fontes-telegram/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, ativo: novoAtivo }),
    });
    const d = await r.json();
    if (d.ok) {
      toast(`Fonte ${novoAtivo ? 'ativada' : 'desativada'}.`, "ok");
      await carregarFontesTelegram();
    } else {
      toast(d.erro || "Erro ao alterar status.", "erro");
    }
  } catch (e) {
    toast("Erro de comunicação com o servidor.", "erro");
  }
}

async function removerFonteTelegram(chatId) {
  if (!confirm(`Deseja realmente remover a fonte ${chatId}?`)) return;
  try {
    const r = await fetch("/api/fontes-telegram/remover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId }),
    });
    const d = await r.json();
    if (d.ok) {
      toast(`Fonte ${chatId} removida.`, "ok");
      await carregarFontesTelegram();
    } else {
      toast(d.erro || "Erro ao remover fonte.", "erro");
    }
  } catch (e) {
    toast("Erro ao comunicar com o servidor.", "erro");
  }
}

async function salvarConfigScraping() {
  const body = {
    ativo: $("#scrapingAtivo")?.value === "true",
    intervalo_segundos: parseInt($("#scrapingIntervalo")?.value || 30, 10),
    limite_mensagens_por_ciclo: parseInt($("#scrapingLimiteMsg")?.value || 20, 10),
  };
  try {
    const r = await fetch("/api/scraping-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.ok) {
      toast("Configurações do robô de scraping salvas!", "ok");
    } else {
      toast(d.erro || "Erro ao salvar configurações.", "erro");
    }
  } catch (e) {
    toast("Erro ao comunicar com o servidor.", "erro");
  }
}

/* ══ Início ══════════════════════════════════════════════════════════ */
let _appNoAr = false;
async function iniciar() {
  if (_appNoAr) return;              /* login reentra: não sobe duas vezes */
  _appNoAr = true;
  injetarIconesFaltantes();
  ligarEventos();
  tickRelogio();
  setInterval(tickRelogio, 1000);

  const inicial = location.hash.slice(1);
  if (inicial && $("#view-" + inicial)) switchView(inicial);

  await Promise.allSettled([atualizarStatus(), atualizarMetricas(), puxarLogs()]);
  carregarConfig();
  carregarNichos();
  carregarConta();
  carregarFiltros();
  carregarCadencia();
  carregarPublicacao();
  carregarFontesTelegram();

  setInterval(atualizarStatus, 2500);
  setInterval(atualizarMetricas, 8000);
  setInterval(puxarLogs, 1500);
  setInterval(carregarPublicacao, 5000);
}

(async () => {
  // O formulário de login é ligado AQUI, e não em ligarEventos(): este só
  // roda depois que o login passa, e o login é justamente o que ainda
  // não aconteceu. Registrado tarde, o form faria submissão nativa e a
  // página recarregaria em loop.
  $("#loginForm")?.addEventListener("submit", ev => {
    ev.preventDefault();
    entrar();
  });
  if (await abrirLoginSePrecisar()) await iniciar();
})();
</script>
</body>
</html>
"""
