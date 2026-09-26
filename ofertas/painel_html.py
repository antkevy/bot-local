"""Interface web do painel Ofertas Pro (servida localmente por painel.py)."""

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ofertas Pro — Painel de Afiliados</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-main: #061525;
    --bg-main2: #081A2B;
    --bg-sidebar: #061220;
    --bg-card: #0B2035;
    --bg-card2: #0D263F;
    --bg-subcard: #081a2e;
    --border-color: #173957;
    --border-light: #204d75;
    --tx-main: #FFFFFF;
    --tx-muted: #8EA6BF;
    --tx-dim: #5c7896;
    --primary: #087BFF;
    --primary-hover: #0D8BFF;
    --primary-glow: 0 0 20px rgba(8, 123, 255, 0.4);
    --success: #20D889;
    --success-bg: rgba(32, 216, 137, 0.12);
    --warning: #ffb300;
    --warning-bg: rgba(255, 179, 0, 0.12);
    --danger: #ff4757;
    --danger-bg: rgba(255, 71, 87, 0.12);
    --font-main: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', Consolas, monospace;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background-color: var(--bg-main);
    background-image: 
      radial-gradient(circle at 15% 0%, rgba(8, 123, 255, 0.1) 0%, transparent 45%),
      radial-gradient(circle at 85% 100%, rgba(32, 216, 137, 0.05) 0%, transparent 45%);
    color: var(--tx-main);
    font-family: var(--font-main);
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    overflow-x: hidden;
  }

  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #173957; border-radius: 99px; }
  ::-webkit-scrollbar-thumb:hover { background: #204d75; }

  .app-layout {
    display: flex;
    width: 100%;
    min-height: 100vh;
  }

  /* ── Sidebar ── */
  .sidebar {
    width: 230px;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    padding: 22px 14px 18px;
    flex-shrink: 0;
    position: sticky;
    top: 0;
    height: 100vh;
    z-index: 50;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 8px 24px;
    text-decoration: none;
  }
  .brand-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: linear-gradient(135deg, #087BFF 0%, #0050b3 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 16px rgba(8, 123, 255, 0.5);
    flex-shrink: 0;
    color: #fff;
  }
  .brand-text h1 {
    font-size: 16px;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.3px;
    line-height: 1.2;
  }
  .brand-text span {
    font-size: 11px;
    color: var(--tx-muted);
    font-weight: 500;
    display: block;
  }

  .nav-menu {
    display: flex;
    flex-direction: column;
    gap: 5px;
    list-style: none;
    margin-bottom: auto;
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    color: var(--tx-muted);
    text-decoration: none;
    font-weight: 600;
    font-size: 13.5px;
    cursor: pointer;
    transition: all 0.18s ease;
    user-select: none;
    border: 1px solid transparent;
  }
  .nav-item:hover {
    color: var(--tx-main);
    background: rgba(255, 255, 255, 0.04);
  }
  .nav-item.active {
    background: var(--primary);
    color: #fff;
    box-shadow: var(--primary-glow);
    border-color: rgba(255, 255, 255, 0.15);
  }
  .nav-item svg {
    width: 18px;
    height: 18px;
    stroke-width: 2;
    flex-shrink: 0;
  }
  .nav-badge {
    margin-left: auto;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 99px;
    background: #081a2e;
    color: #8EA6BF;
    border: 1px solid #173957;
  }
  .nav-item.active .nav-badge {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
    border-color: transparent;
  }

  /* Sidebar Bot Status Card */
  .sidebar-bot-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .sidebar-bot-card:hover {
    border-color: var(--border-light);
    background: var(--bg-card2);
  }
  .bot-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--tx-dim);
    flex-shrink: 0;
    transition: 0.3s;
  }
  .bot-status-dot.active {
    background: var(--success);
    box-shadow: 0 0 10px var(--success);
  }
  .bot-status-info {
    flex: 1;
    overflow: hidden;
  }
  .bot-status-info .title {
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
  }
  .bot-status-info .subtitle {
    font-size: 11px;
    color: var(--tx-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bot-status-arrow {
    color: var(--tx-muted);
    font-size: 14px;
  }

  .sidebar-footer {
    padding: 14px 6px 0;
    font-size: 11px;
    color: var(--tx-dim);
    line-height: 1.4;
  }
  .sidebar-footer strong {
    color: var(--tx-muted);
    font-weight: 600;
  }

  /* ── Main Area ── */
  .main-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow-y: auto;
  }

  .top-header {
    padding: 24px 32px 16px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    flex-wrap: wrap;
  }

  .greeting-section h2 {
    font-size: 26px;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.5px;
    line-height: 1.2;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .greeting-section h3 {
    font-size: 15.5px;
    font-weight: 600;
    color: #cbd5e1;
    margin-top: 2px;
  }
  .greeting-section p {
    font-size: 13px;
    color: var(--tx-muted);
    margin-top: 4px;
    max-width: 600px;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .sys-online-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--tx-muted);
  }
  .sys-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--tx-dim);
    transition: 0.3s;
  }

  .time-display { text-align: right; }
  .time-display .clock {
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    font-variant-numeric: tabular-nums;
  }
  .time-display .date {
    font-size: 11px;
    color: var(--tx-dim);
  }

  .user-profile-pill {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-left: 6px;
    border-left: 1px solid var(--border-color);
  }
  .user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #0d3663;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #93c5fd;
  }
  .user-info { line-height: 1.2; }
  .user-info .name {
    font-size: 13px;
    font-weight: 700;
    color: #fff;
  }
  .user-info .badge {
    font-size: 10.5px;
    color: var(--tx-muted);
  }

  /* Buttons */
  .btn-primary {
    background: var(--primary);
    color: #fff;
    font-family: inherit;
    font-size: 13.5px;
    font-weight: 700;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: var(--radius-sm);
    padding: 10px 18px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    box-shadow: var(--primary-glow);
    transition: all 0.18s ease;
    text-decoration: none;
    white-space: nowrap;
  }
  .btn-primary:hover {
    background: var(--primary-hover);
    transform: translateY(-1px);
    box-shadow: 0 0 24px rgba(8, 123, 255, 0.55);
  }
  .btn-primary:active { transform: translateY(0); }

  .btn-dark {
    background: var(--bg-card);
    color: #cbd5e1;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 8px 14px;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    cursor: pointer;
    transition: all 0.15s ease;
    text-decoration: none;
  }
  .btn-dark:hover {
    background: var(--bg-card2);
    color: #fff;
    border-color: var(--border-light);
  }

  .btn-outline-danger {
    background: transparent;
    color: #ff6b81;
    border: 1px solid rgba(255, 71, 87, 0.4);
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    border-radius: var(--radius-sm);
    padding: 8px 14px;
    cursor: pointer;
    transition: 0.15s;
  }
  .btn-outline-danger:hover {
    background: var(--danger-bg);
    border-color: var(--danger);
  }

  /* Content Body */
  .content-body {
    padding: 24px 36px 40px;
    display: flex;
    flex-direction: column;
    gap: 26px;
    flex: 1;
  }

  .dash-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 24px 28px;
    position: relative;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
    transition: border-color 0.2s;
  }
  .dash-card:hover { border-color: var(--border-light); }

  /* ── 4 Symmetrical Marketplaces Cards on Dashboard ── */
  .marketplaces-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
  }
  @media (max-width: 1100px) { .marketplaces-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 650px) { .marketplaces-grid { grid-template-columns: 1fr; } }

  .mp-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 22px 18px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 10px;
    transition: transform 0.15s, border-color 0.15s;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  }
  .mp-card:hover {
    transform: translateY(-2px);
    border-color: var(--border-light);
  }

  .mp-icon-box {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 800;
    color: #fff;
    margin-bottom: 2px;
  }
  .icon-ml { background: #ffe600; color: #000; box-shadow: 0 4px 12px rgba(255, 230, 0, 0.2); }
  .icon-amazon { background: #ff9900; box-shadow: 0 4px 12px rgba(255, 153, 0, 0.2); }
  .icon-shopee { background: #ee4d2d; box-shadow: 0 4px 12px rgba(238, 77, 45, 0.2); }
  .icon-aliexpress { background: #ff4747; box-shadow: 0 4px 12px rgba(255, 71, 71, 0.2); }

  .mp-card h4 {
    font-size: 15px;
    font-weight: 700;
    color: #fff;
  }
  .mp-card .mp-sub {
    font-size: 12px;
    color: var(--tx-dim);
    min-height: 18px;
  }
  .mp-card .btn-dark {
    width: 100%;
    justify-content: center;
    padding: 8px 12px;
    font-size: 12.5px;
    margin-top: 8px;
  }

  .badge-connected {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 600;
    color: var(--success);
    background: var(--success-bg);
    border: 1px solid rgba(32, 216, 137, 0.25);
    padding: 2px 8px;
    border-radius: 99px;
  }
  .badge-connected .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--success);
  }
  .badge-pending {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 600;
    color: var(--warning);
    background: var(--warning-bg);
    border: 1px solid rgba(255, 179, 0, 0.25);
    padding: 2px 8px;
    border-radius: 99px;
  }
  .badge-pending .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--warning);
  }

  /* 2-Column Split */
  .dash-main-grid {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 24px;
    align-items: start;
  }
  @media (max-width: 1100px) { .dash-main-grid { grid-template-columns: 1fr; } }

  .dash-left-column {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  /* Metrics Row */
  .metrics-row {
    display: grid;
    grid-template-columns: 1.1fr 1fr 1.3fr;
    gap: 20px;
  }
  @media (max-width: 900px) { .metrics-row { grid-template-columns: 1fr; } }

  .metric-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .metric-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .metric-title-group svg { color: var(--primary); }
  .metric-title-group h4 {
    font-size: 14px;
    font-weight: 700;
    color: #fff;
  }
  .metric-subtitle {
    font-size: 11.5px;
    color: var(--tx-dim);
    margin-top: 2px;
  }
  .metric-stat-group { text-align: right; }
  .metric-big-val {
    font-size: 22px;
    font-weight: 800;
    color: #fff;
    line-height: 1.1;
  }
  .metric-growth-badge {
    font-size: 11.5px;
    font-weight: 700;
    color: var(--success);
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-top: 3px;
  }

  .chart-canvas-wrap {
    width: 100%;
    height: 140px;
    position: relative;
    margin-top: 6px;
  }
  canvas {
    width: 100% !important;
    height: 100% !important;
  }

  .top-platforms-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 10px;
  }
  .top-platform-item {
    display: grid;
    grid-template-columns: 20px 80px 1fr 40px 45px;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .top-platform-icon {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 700;
  }
  .top-platform-name {
    font-weight: 600;
    color: #cbd5e1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .progress-bar-bg {
    height: 7px;
    background: #081a2e;
    border-radius: 99px;
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #087BFF, #38bdf8);
    border-radius: 99px;
  }
  .top-platform-clicks {
    text-align: right;
    color: #cbd5e1;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .top-platform-pct {
    text-align: right;
    color: var(--tx-dim);
    font-variant-numeric: tabular-nums;
  }

  /* Activity List */
  .activity-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .activity-item {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12.5px;
  }
  .act-icon {
    width: 32px;
    height: 32px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .act-icon.green { background: rgba(32, 216, 137, 0.15); color: var(--success); }
  .act-icon.blue { background: rgba(8, 123, 255, 0.15); color: #60a5fa; }
  .act-icon.orange { background: rgba(255, 153, 0, 0.15); color: #ff9900; }
  .act-icon.purple { background: rgba(139, 92, 246, 0.15); color: #a78bfa; }
  
  .act-content {
    flex: 1;
    overflow: hidden;
  }
  .act-content .title {
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .act-content .desc {
    font-size: 11.5px;
    color: var(--tx-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .act-time {
    font-size: 11px;
    color: var(--tx-dim);
    font-variant-numeric: tabular-nums;
  }

  /* Right Side Panels */
  .dash-right-column {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .right-panel-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  }

  .recent-links-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 14px;
  }
  .recent-link-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 14px;
    background: var(--bg-subcard);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    font-size: 12.5px;
  }
  .recent-link-left {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
  }
  .recent-link-url {
    color: #93c5fd;
    font-family: var(--font-mono);
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .recent-link-date {
    font-size: 11px;
    color: var(--tx-dim);
    margin-top: 2px;
  }
  .btn-copy-icon {
    background: transparent;
    border: 0;
    color: var(--tx-muted);
    cursor: pointer;
    padding: 5px;
    border-radius: 6px;
    transition: 0.15s;
    display: flex;
  }
  .btn-copy-icon:hover { color: #fff; background: rgba(255, 255, 255, 0.1); }

  /* ── Dedicated Plataformas Blocks ── */
  .platform-block {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 26px 28px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-bottom: 24px;
    transition: border-color 0.2s;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.2);
  }
  .platform-block:last-child {
    margin-bottom: 0;
  }
  .platform-block.highlighted {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(8, 123, 255, 0.3);
  }
  .pb-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color);
  }
  .pb-header-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .pb-header-left h3 {
    font-size: 17px;
    font-weight: 700;
    color: #fff;
  }
  .pb-content-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
  }
  .pb-info-card {
    background: var(--bg-subcard);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 14px 18px;
  }
  .pb-info-card label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--tx-muted);
    font-weight: 700;
    display: block;
    margin-bottom: 6px;
  }
  .pb-info-card .val {
    font-size: 14px;
    color: #fff;
    font-weight: 600;
    word-break: break-all;
  }
  .pb-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
    margin-top: 4px;
  }

  /* Global Footer */
  .global-footer {
    padding: 18px 36px;
    border-top: 1px solid var(--border-color);
    background: var(--bg-sidebar);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: var(--tx-dim);
    margin-top: auto;
  }
  .footer-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .footer-right {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  /* Views Switching */
  .view-tab-content { display: none; }
  .view-tab-content.active-view {
    display: block;
    animation: fadeIn 0.2s ease-in-out;
  }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

  .empty-placeholder {
    padding: 24px 12px;
    text-align: center;
    color: var(--tx-dim);
    font-size: 12.5px;
  }

  /* Config / Form */
  .config-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-top: 8px;
  }
  @media (max-width: 900px) { .config-grid { grid-template-columns: 1fr; } }
  
  .form-group-title {
    font-size: 13.5px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #60a5fa;
    font-weight: 700;
    margin: 24px 0 14px;
  }
  .form-group-title:first-of-type { margin-top: 4px; }
  .form-field { margin-bottom: 18px; }
  .form-field label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 8px;
  }
  .form-field input, .form-field select {
    width: 100%;
    padding: 11px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    background: var(--bg-subcard);
    color: #fff;
    font-family: inherit;
    font-size: 13.5px;
    transition: 0.15s;
  }
  .form-field input:focus, .form-field select:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(8, 123, 255, 0.2);
  }
  .form-field .field-help {
    font-size: 12px;
    color: var(--tx-dim);
    margin-top: 6px;
    line-height: 1.4;
  }

  .nichos-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
    margin: 18px 0;
  }
  .nicho-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: var(--bg-subcard);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    cursor: pointer;
    user-select: none;
    transition: 0.15s;
  }
  .nicho-card:hover { border-color: var(--primary); }
  .nicho-card.selected {
    background: rgba(8, 123, 255, 0.15);
    border-color: var(--primary);
    color: #fff;
  }
  .nicho-card .n-check {
    margin-left: auto;
    font-size: 12px;
    color: var(--primary);
    opacity: 0;
  }
  .nicho-card.selected .n-check { opacity: 1; }

  /* Terminals */
  .logs-terminal-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    height: calc(100vh - 240px);
    min-height: 440px;
  }
  @media (max-width: 900px) { .logs-terminal-container { grid-template-columns: 1fr; height: auto; } }

  .terminal-box {
    background: #040d17;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }
  .terminal-header {
    background: var(--bg-subcard);
    padding: 12px 20px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    font-weight: 700;
  }
  .terminal-body {
    flex: 1;
    padding: 16px 20px;
    font-family: var(--font-mono);
    font-size: 12px;
    color: #94a3b8;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.6;
  }

  .data-table-wrap {
    overflow-x: auto;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-color);
    margin-top: 14px;
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 13px;
  }
  table.data-table th {
    background: #081a2e;
    padding: 14px 20px;
    color: var(--tx-muted);
    font-weight: 700;
    border-bottom: 1px solid var(--border-color);
  }
  table.data-table td {
    padding: 14px 20px;
    border-bottom: 1px solid #102d4a;
    color: #cbd5e1;
  }
  table.data-table tr:hover td { background: rgba(255, 255, 255, 0.02); }

  /* Modals */
  .modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(3, 7, 18, 0.75);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    z-index: 999;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
  }
  .modal-overlay.show {
    opacity: 1;
    pointer-events: auto;
  }
  .modal-container {
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 540px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
    overflow: hidden;
    transform: scale(0.95);
    transition: transform 0.2s ease;
  }
  .modal-overlay.show .modal-container { transform: scale(1); }
  .modal-header {
    padding: 18px 22px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .modal-header h3 {
    font-size: 16px;
    font-weight: 700;
    color: #fff;
  }
  .btn-modal-close {
    background: transparent;
    border: 0;
    color: var(--tx-muted);
    font-size: 20px;
    cursor: pointer;
    line-height: 1;
  }
  .modal-body { padding: 22px; }
  .modal-footer {
    padding: 14px 22px;
    background: var(--bg-subcard);
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }

  .toast-container {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
  }
  .toast-card {
    background: #0d2a4a;
    border: 1px solid var(--border-light);
    color: #fff;
    padding: 12px 20px;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 13px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    gap: 10px;
    transform: translateY(20px);
    opacity: 0;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: auto;
  }
  .toast-card.show {
    transform: translateY(0);
    opacity: 1;
  }
  .toast-card.success { border-color: var(--success); }
  .toast-card.error { border-color: var(--danger); }
</style>
</head>
<body>

<div class="app-layout">
  
  <!-- ── Sidebar ── -->
  <aside class="sidebar">
    <a href="#" class="brand" onclick="switchView('dashboard')">
      <div class="brand-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>
      </div>
      <div class="brand-text">
        <h1>Ofertas Pro</h1>
        <span>Painel de Afiliados</span>
      </div>
    </a>

    <nav class="nav-menu">
      <a class="nav-item active" data-view="dashboard" onclick="switchView('dashboard')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="14" width="7" height="7" rx="1.5"></rect><rect x="3" y="14" width="7" height="7" rx="1.5"></rect></svg>
        Dashboard
      </a>
      <a class="nav-item" data-view="produtos" onclick="switchView('produtos')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>
        Produtos
      </a>
      <a class="nav-item" data-view="links" onclick="switchView('links')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
        Links
        <span class="nav-badge" id="navLinkCount">0</span>
      </a>
      <a class="nav-item" data-view="plataformas" onclick="switchView('plataformas')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="2" y="2" width="20" height="8" rx="2"></rect><rect x="2" y="14" width="20" height="8" rx="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>
        Plataformas
      </a>
      <a class="nav-item" data-view="config" onclick="switchView('config')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        Configurações
      </a>
      <a class="nav-item" data-view="logs" onclick="switchView('logs')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
        Logs
      </a>
      <a class="nav-item" data-view="suporte" onclick="switchView('suporte')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>
        Suporte
      </a>
    </nav>

    <!-- Bot Status Widget -->
    <div class="sidebar-bot-card" onclick="toggleBot()">
      <div class="bot-status-dot" id="sideBotDot"></div>
      <div class="bot-status-info">
        <div class="title" id="sideBotTitle">Bot Parado</div>
        <div class="subtitle" id="sideBotSub">Aguardando início</div>
      </div>
      <div class="bot-status-arrow">›</div>
    </div>

    <div class="sidebar-footer">
      <strong>Ofertas Pro v2.0.0</strong><br>
      Painel Local
    </div>
  </aside>

  <!-- ── Main Content ── -->
  <main class="main-wrapper">
    
    <!-- Top Header -->
    <header class="top-header">
      <div class="greeting-section">
        <h2>Olá! 👋</h2>
        <h3>Bem-vindo ao seu painel de afiliados</h3>
        <p>Aqui você gerencia seus links, acompanha o desempenho e controla suas ofertas.</p>
      </div>

      <div class="header-actions">
        <div class="sys-online-pill" id="headerBotPill">
          <span class="sys-dot" id="headerBotDot"></span>
          <span id="headerBotText">Bot Parado</span>
        </div>

        <div class="time-display">
          <div class="clock" id="liveClock">--:--</div>
          <div class="date" id="liveDate">--/--/----</div>
        </div>

        <div class="user-profile-pill">
          <div class="user-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
          </div>
          <div class="user-info">
            <div class="name">Usuário</div>
            <div class="badge">Local</div>
          </div>
        </div>

        <button class="btn-primary" onclick="abrirModalLink()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
          Gerar Link Rápido
        </button>
      </div>
    </header>

    <!-- ── TAB 1: DASHBOARD ── -->
    <div id="view-dashboard" class="content-body view-tab-content active-view">
      
      <!-- 5 Symmetrical Marketplaces Row -->
      <section class="marketplaces-grid">
        <!-- Mercado Livre -->
        <div class="mp-card">
          <div class="mp-icon-box icon-ml">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M11 15h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 17"></path><path d="m7 21 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.8-2.8L15 14"></path></svg>
          </div>
          <h4>Mercado Livre</h4>
          <span class="badge-pending" id="dashMlBadge"><span class="dot"></span>Não configurado</span>
          <span class="mp-sub" id="dashMlSub">Não configurado</span>
          <button class="btn-dark" onclick="gerenciarPlataforma('mercadolivre')">Gerenciar</button>
        </div>

        <!-- Amazon -->
        <div class="mp-card">
          <div class="mp-icon-box icon-amazon">a</div>
          <h4>Amazon</h4>
          <span class="badge-pending" id="dashAmzBadge"><span class="dot"></span>Não configurado</span>
          <span class="mp-sub" id="dashAmzSub">Não configurado</span>
          <button class="btn-dark" onclick="gerenciarPlataforma('amazon')">Gerenciar</button>
        </div>

        <!-- Shopee -->
        <div class="mp-card">
          <div class="mp-icon-box icon-shopee">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
          </div>
          <h4>Shopee</h4>
          <span class="badge-pending" id="dashShpBadge"><span class="dot"></span>Não configurado</span>
          <span class="mp-sub" id="dashShpSub">Não configurado</span>
          <button class="btn-dark" onclick="gerenciarPlataforma('shopee')">Gerenciar</button>
        </div>

        <!-- AliExpress -->
        <div class="mp-card">
          <div class="mp-icon-box icon-aliexpress">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>
          </div>
          <h4>AliExpress</h4>
          <span class="badge-pending" id="dashAliBadge"><span class="dot"></span>Não configurado</span>
          <span class="mp-sub" id="dashAliSub">Não configurado</span>
          <button class="btn-dark" onclick="gerenciarPlataforma('aliexpress')">Gerenciar</button>
        </div>
      </section>

      <!-- Main 2-Column Split -->
      <div class="dash-main-grid">
        
        <!-- Left Section (Metrics + Activity) -->
        <div class="dash-left-column">
          
          <section class="metrics-row">
            <!-- Card 1: Links Gerados -->
            <div class="dash-card">
              <div class="metric-card-header">
                <div>
                  <div class="metric-title-group">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                    <h4>Links Gerados</h4>
                  </div>
                  <div class="metric-subtitle">Últimos 7 dias</div>
                </div>
                <div class="metric-stat-group">
                  <div class="metric-big-val" id="valLinksGerados">0</div>
                  <div class="metric-growth-badge" id="badgeLinksCresc">0%</div>
                </div>
              </div>
              <div class="chart-canvas-wrap">
                <canvas id="chartLinks"></canvas>
              </div>
            </div>

            <!-- Card 2: Conversão -->
            <div class="dash-card">
              <div class="metric-card-header">
                <div>
                  <div class="metric-title-group">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
                    <h4>Conversão</h4>
                  </div>
                  <div class="metric-subtitle">Últimos 7 dias</div>
                </div>
                <div class="metric-stat-group">
                  <div class="metric-big-val" id="valConversao">0,0%</div>
                  <div class="metric-growth-badge" id="badgeConvCresc">0%</div>
                </div>
              </div>
              <div class="chart-canvas-wrap">
                <canvas id="chartConversao"></canvas>
              </div>
            </div>

            <!-- Card 3: Top Plataformas -->
            <div class="dash-card">
              <div class="metric-card-header" style="margin-bottom: 8px;">
                <div>
                  <div class="metric-title-group">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="8" r="7"></circle><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"></polyline></svg>
                    <h4>Top Plataformas</h4>
                  </div>
                  <div class="metric-subtitle">Cliques no período</div>
                </div>
              </div>

              <div class="top-platforms-list" id="topPlataformasWrap">
                <div class="empty-placeholder">Nenhum clique registrado ainda.</div>
              </div>
            </div>
          </section>

          <!-- Atividade Recente Card -->
          <div class="dash-card">
            <div class="card-top-title" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                <h4 style="font-size: 14px; font-weight: 700; color: #fff;">Atividade Recente</h4>
              </div>
              <a href="#" onclick="switchView('logs')" style="font-size: 12px; color: var(--primary); text-decoration: none; font-weight: 600;">Ver todos os logs</a>
            </div>

            <div class="activity-list" id="activityListWrap">
              <div class="empty-placeholder">Nenhuma atividade registrada ainda.</div>
            </div>
          </div>

        </div>

        <!-- Right Side Panel -->
        <div class="dash-right-column">
          
          <!-- Link Builder Quick Trigger -->
          <div class="right-panel-card">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
              <h4 style="font-size: 14px; font-weight: 700; color: #fff;">Link Builder Rápido</h4>
            </div>
            <p style="font-size: 12px; color: var(--tx-muted); margin: 6px 0 14px;">Converta qualquer link em link de afiliado instantaneamente.</p>

            <button class="btn-primary" style="width: 100%; justify-content: center;" onclick="abrirModalLink()">
              Abrir Link Builder ↗
            </button>
          </div>

          <!-- Links Recentes -->
          <div class="right-panel-card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                <h4 style="font-size: 14px; font-weight: 700; color: #fff;">Links Recentes</h4>
              </div>
              <a href="#" onclick="switchView('links')" style="font-size: 12px; color: var(--primary); text-decoration: none; font-weight: 600;">Ver todos</a>
            </div>

            <div class="recent-links-list" id="recentLinksListWrap">
              <div class="empty-placeholder">Nenhum link recente postado.</div>
            </div>
          </div>

        </div>

      </div>

    </div>

    <!-- ── TAB 2: PRODUTOS ── -->
    <div id="view-produtos" class="content-body view-tab-content">
      <div class="dash-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>
            <h3 style="font-size: 16px; font-weight: 700; color: #fff;">Produtos & Ofertas Postadas</h3>
          </div>
          <button class="btn-dark" onclick="carregarProdutos()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
            Atualizar
          </button>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 16px;">Histórico de todas as ofertas capturadas e publicadas automaticamente no seu canal do Telegram.</p>

        <div class="data-table-wrap">
          <table class="data-table" id="produtosTable">
            <thead>
              <tr>
                <th>Plataforma</th>
                <th>Título do Produto</th>
                <th>Preço</th>
                <th>Data / Hora</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody id="produtosTableBody">
              <tr><td colspan="5" style="text-align: center; color: var(--tx-dim);">Carregando produtos...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ── TAB 3: LINKS ── -->
    <div id="view-links" class="content-body view-tab-content">
      <div class="dash-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
            <h3 style="font-size: 16px; font-weight: 700; color: #fff;">Gerenciador de Links de Afiliado</h3>
          </div>
          <button class="btn-primary" onclick="abrirModalLink()">+ Novo Link Rápido</button>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 16px;">Acompanhe e copie os links de afiliados gerados para suas postagens e promoções.</p>

        <div class="recent-links-list" id="allLinksListWrap">
          <div class="empty-placeholder">Nenhum link gerado ainda.</div>
        </div>
      </div>
    </div>

    <!-- ── TAB 4: PLATAFORMAS ── -->
    <div id="view-plataformas" class="content-body view-tab-content">
      
      <div class="dash-card" style="margin-bottom: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
          <div>
            <h3 style="font-size: 18px; font-weight: 800; color: #fff;">Plataformas de Afiliados</h3>
            <p style="font-size: 13px; color: var(--tx-muted); margin-top: 4px;">Configure suas contas, autenticações e valide conexões de cada marketplace.</p>
          </div>
          <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button class="btn-dark" onclick="execAcao('instalar-navegador')" id="btnInstalarNav">⬇️ Instalar Playwright Chromium</button>
            <button class="btn-primary" onclick="execAcao('ciclo')">⚡ Executar 1 Ciclo de Postagem</button>
          </div>
        </div>
      </div>

      <!-- 1. Mercado Livre Block -->
      <div class="platform-block" id="block-mercadolivre">
        <div class="pb-header">
          <div class="pb-header-left">
            <div class="mp-icon-box icon-ml">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M11 15h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 17"></path><path d="m7 21 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.8-2.8L15 14"></path></svg>
            </div>
            <div>
              <h3>Mercado Livre</h3>
              <span style="font-size: 12px; color: var(--tx-muted);">Link Builder e Autenticação de Sessão Local</span>
            </div>
          </div>
          <span class="badge-pending" id="pbMlBadge"><span class="dot"></span>Não configurado</span>
        </div>

        <div class="pb-content-grid">
          <div class="pb-info-card">
            <label>Etiqueta de Afiliado (ML_ETIQUETA)</label>
            <div class="val" id="pbMlEtiqueta">Não configurado</div>
          </div>
          <div class="pb-info-card">
            <label>Sessão do Navegador Local</label>
            <div class="val" id="pbMlSessaoStatus">Não configurado</div>
          </div>
        </div>

        <div class="pb-actions">
          <button class="btn-primary" onclick="execAcao('ml-login')">🔑 Fazer Login no Mercado Livre</button>
          <button class="btn-dark" onclick="execAcao('testar-ml')">🧪 Testar Conexão ML</button>
          <button class="btn-dark" onclick="verificarSessaoModal()">🔍 Detalhes da Sessão</button>
          <button class="btn-outline-danger" onclick="limparSessao()">Limpar Sessão Local</button>
        </div>
      </div>

      <!-- 2. Amazon Block -->
      <div class="platform-block" id="block-amazon">
        <div class="pb-header">
          <div class="pb-header-left">
            <div class="mp-icon-box icon-amazon">a</div>
            <div>
              <h3>Amazon</h3>
              <span style="font-size: 12px; color: var(--tx-muted);">Amazon Associados & Creators API</span>
            </div>
          </div>
          <span class="badge-pending" id="pbAmzBadge"><span class="dot"></span>Não configurado</span>
        </div>

        <div class="pb-content-grid">
          <div class="pb-info-card">
            <label>Tag de Associado (AMAZON_TAG)</label>
            <div class="val" id="pbAmzTag">Não configurado</div>
          </div>
          <div class="pb-info-card">
            <label>Creators API ID & Secret</label>
            <div class="val" id="pbAmzApiStatus">Não configurado</div>
          </div>
        </div>

        <div class="pb-actions">
          <button class="btn-dark" onclick="execAcao('testar-amazon')">🧪 Testar Conexão Amazon</button>
          <button class="btn-dark" onclick="switchView('config')">⚙️ Editar Credenciais Amazon</button>
        </div>
      </div>

      <!-- 3. Shopee Block -->
      <div class="platform-block" id="block-shopee">
        <div class="pb-header">
          <div class="pb-header-left">
            <div class="mp-icon-box icon-shopee">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
            </div>
            <div>
              <h3>Shopee</h3>
              <span style="font-size: 12px; color: var(--tx-muted);">Programa de Afiliados Shopee Open API</span>
            </div>
          </div>
          <span class="badge-pending" id="pbShpBadge"><span class="dot"></span>Não configurado</span>
        </div>

        <div class="pb-content-grid">
          <div class="pb-info-card">
            <label>App ID (SHOPEE_APP_ID)</label>
            <div class="val" id="pbShpAppId">Não configurado</div>
          </div>
          <div class="pb-info-card">
            <label>App Secret</label>
            <div class="val" id="pbShpSecretStatus">Não configurado</div>
          </div>
        </div>

        <div class="pb-actions">
          <button class="btn-dark" onclick="execAcao('testar-shopee')">🧪 Testar Conexão Shopee</button>
          <button class="btn-dark" onclick="switchView('config')">⚙️ Editar Credenciais Shopee</button>
        </div>
      </div>

      <!-- 4. AliExpress Block -->
      <div class="platform-block" id="block-aliexpress">
        <div class="pb-header">
          <div class="pb-header-left">
            <div class="mp-icon-box icon-aliexpress">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>
            </div>
            <div>
              <h3>AliExpress</h3>
              <span style="font-size: 12px; color: var(--tx-muted);">Links diretos e promoções globais</span>
            </div>
          </div>
          <span class="badge-pending" id="pbAliBadge"><span class="dot"></span>Não configurado</span>
        </div>

        <div class="pb-content-grid">
          <div class="pb-info-card">
            <label>Status da Integração</label>
            <div class="val" id="pbAliStatus">Não configurado</div>
          </div>
        </div>
      </div>

      <!-- Terminal de Ação das Plataformas -->
      <div class="dash-card" style="margin-top: 10px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <h4 style="font-size: 14px; font-weight: 700; color: #fff;">Saída do Terminal de Testes</h4>
          <button class="btn-dark" style="padding: 4px 10px; font-size: 11.5px;" onclick="limparTerminal('logAcaoTerminal')">Limpar Terminal</button>
        </div>
        <div class="terminal-body" id="logAcaoTerminal" style="height: 200px; background: #040d17; border-radius: 10px; border: 1px solid var(--border-color);">Aguardando execução de testes...</div>
      </div>

    </div>

    <!-- ── TAB 5: CONFIGURAÇÕES ── -->
    <div id="view-config" class="content-body view-tab-content">
      <div class="dash-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            <h3 style="font-size: 16px; font-weight: 700; color: #fff;">Configurações do Sistema & Credenciais</h3>
          </div>
          <button class="btn-primary" onclick="salvarConfig()">💾 Salvar Configurações</button>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 20px;">Gerencie suas chaves, credenciais do Telegram e tags de afiliados salvas no arquivo <code>.env</code>.</p>

        <div id="camposFormWrap" class="config-grid">Carregando campos...</div>

        <div style="display: flex; gap: 12px; margin-top: 24px; align-items: center; border-top: 1px solid var(--border-color); padding-top: 18px;">
          <button class="btn-primary" onclick="salvarConfig()">💾 Salvar Tudo</button>
          <button class="btn-dark" onclick="detectarIds()">🔎 Detectar IDs do Telegram</button>
        </div>

        <div id="idsDetectionBox" style="margin-top: 16px; display: none;"></div>
      </div>

      <!-- Categorias & Nichos Card -->
      <div class="dash-card">
        <h3 style="font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 6px;">Categorias & Nichos do Canal</h3>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 16px;">
          Selecione os nichos de produtos para publicação no Telegram. <strong>Nenhum nicho selecionado = busca em todas as categorias.</strong>
        </p>

        <div class="nichos-grid" id="nichosGrid">Carregando categorias...</div>

        <div style="display: flex; gap: 12px; margin-top: 18px; align-items: center;">
          <button class="btn-primary" onclick="salvarNichos()">💾 Salvar Categorias</button>
          <button class="btn-dark" onclick="limparNichos()">Limpar (Pegar Tudo)</button>
          <span style="font-size: 12.5px; color: var(--tx-muted);" id="nichosCountLabel"></span>
        </div>
      </div>
    </div>

    <!-- ── TAB 6: LOGS ── -->
    <div id="view-logs" class="content-body view-tab-content">
      <div class="logs-terminal-container">
        <div class="terminal-box">
          <div class="terminal-header">
            <span>● Log Contínuo do Bot</span>
            <button class="btn-dark" style="padding: 4px 8px; font-size: 11px;" onclick="limparTerminal('logBotBody')">Limpar</button>
          </div>
          <div class="terminal-body" id="logBotBody">O bot está pronto. Inicie pelo painel para acompanhar os logs em tempo real.</div>
        </div>

        <div class="terminal-box">
          <div class="terminal-header">
            <span>● Log de Ações e Testes</span>
            <button class="btn-dark" style="padding: 4px 8px; font-size: 11px;" onclick="limparTerminal('logAcaoBody')">Limpar</button>
          </div>
          <div class="terminal-body" id="logAcaoBody">Nenhuma ação executada recentemente.</div>
        </div>
      </div>
    </div>

    <!-- ── TAB 7: SUPORTE ── -->
    <div id="view-suporte" class="content-body view-tab-content">
      <div class="dash-card">
        <h3 style="font-size: 17px; font-weight: 800; color: #fff; margin-bottom: 6px;">Central de Ajuda e Suporte</h3>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 20px;">Documentação rápida e diagnóstico do seu ambiente local.</p>

        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div class="pb-info-card">
            <h4 style="color: #fff; margin-bottom: 6px;">Como obter o Token do Bot no Telegram?</h4>
            <p style="font-size: 13px; color: var(--tx-muted);">Abra o Telegram, pesquise por <code>@BotFather</code>, envie o comando <code>/newbot</code> e siga as instruções para obter seu Token. Cole o token na aba <strong>Configurações</strong>.</p>
          </div>

          <div class="pb-info-card">
            <h4 style="color: #fff; margin-bottom: 6px;">Como descobrir os IDs de Dono e Canal?</h4>
            <p style="font-size: 13px; color: var(--tx-muted);">Após salvar o token, adicione o bot como Administrador do canal. Envie uma mensagem no canal e uma mensagem no privado do bot, depois use o botão <strong>"Detectar IDs do Telegram"</strong>.</p>
          </div>

          <div class="pb-info-card">
            <h4 style="color: #fff; margin-bottom: 6px;">Como funciona o Login no Mercado Livre?</h4>
            <p style="font-size: 13px; color: var(--tx-muted);">Clique em <strong>"Fazer Login no Mercado Livre"</strong> na aba Plataformas. Uma janela do Chromium abrirá no seu computador para você fazer o login. A sessão será salva localmente em <code>data/ml_profile</code>.</p>
          </div>

          <div class="pb-info-card">
            <h4 style="color: #fff; margin-bottom: 6px;">Status do Ambiente Local</h4>
            <p style="font-size: 13px; color: var(--tx-muted);" id="suporteAmbienteInfo">Carregando diagnóstico do sistema...</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Footer ── -->
    <footer class="global-footer">
      <div class="footer-left">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#20D889" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
        Ofertas Pro — Ambiente Local Ativo e Seguro
      </div>

      <div class="footer-right">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
        Última atualização: <span id="footerTime">--/--/---- --:--</span>
      </div>
    </footer>

  </main>
</div>

<!-- ── MODAL 1: LINK BUILDER ── -->
<div class="modal-overlay" id="modalLinkBuilder">
  <div class="modal-container">
    <div class="modal-header">
      <h3>🔗 Link Builder — Gerar Link de Afiliado</h3>
      <button class="btn-modal-close" onclick="fecharModalLink()">&times;</button>
    </div>
    <div class="modal-body">
      <div class="form-field">
        <label>Cole a URL do Produto</label>
        <input type="text" id="modalInputUrl" placeholder="https://www.mercadolivre.com.br/p/MLB... ou amazon.com.br/dp/...">
      </div>

      <div class="form-field">
        <label>Plataforma (Opcional)</label>
        <select id="modalSelectPlat">
          <option value="">Detecção Automática</option>
          <option value="mercadolivre">Mercado Livre</option>
          <option value="amazon">Amazon</option>
          <option value="shopee">Shopee</option>
          <option value="aliexpress">AliExpress</option>
        </select>
      </div>

      <button class="btn-primary" style="width: 100%; justify-content: center; margin-top: 8px;" onclick="converterLinkModal()">
        ⚡ Gerar Link de Afiliado
      </button>

      <div id="modalLinkResult" style="display: none; margin-top: 16px;">
        <label style="font-size: 12px; color: var(--tx-muted); font-weight: 600;">Link Pronto para Postar:</label>
        <div style="display: flex; gap: 8px; margin-top: 5px;">
          <input type="text" id="modalOutputUrl" readonly style="font-family: var(--font-mono); font-size: 12.5px; background: #081a2e;">
          <button class="btn-primary" onclick="copiarOutputModal()">Copiar</button>
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn-dark" onclick="fecharModalLink()">Fechar</button>
    </div>
  </div>
</div>

<!-- ── MODAL 2: DETALHES DA SESSÃO ── -->
<div class="modal-overlay" id="modalSessao">
  <div class="modal-container">
    <div class="modal-header">
      <h3>🛡️ Detalhes da Sessão Local do Mercado Livre</h3>
      <button class="btn-modal-close" onclick="fecharModalSessao()">&times;</button>
    </div>
    <div class="modal-body">
      <div id="modalSessaoConteudo" style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
        Verificando sessão...
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn-dark" onclick="fecharModalSessao()">Fechar</button>
      <button class="btn-primary" onclick="execAcao('ml-login')">Abrir Login Local</button>
    </div>
  </div>
</div>

<!-- Toast Box -->
<div class="toast-container" id="toastBox"></div>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

let CFG = {};
let statusAtual = {};

const CAMPOS = [
  ["TELEGRAM_BOT_TOKEN", "Token do Bot", "Telegram", true, "Crie no @BotFather com /newbot e cole aqui."],
  ["TELEGRAM_OWNER_ID", "Seu User ID", "Telegram", false, "Use o botão 'Detectar IDs' para preencher automaticamente."],
  ["TELEGRAM_CHAT_ID", "ID do Canal", "Telegram", false, "O canal onde o bot posta as ofertas."],
  ["ML_ETIQUETA", "Etiqueta do Afiliado", "Mercado Livre", false, "A 'Etiqueta em uso' que aparece no Linkbuilder do ML."],
  ["AMAZON_TAG", "Tag de Associado", "Amazon", false, "Sua tag do Amazon Associados (ex: seunome-20)."],
  ["AMAZON_CREDENTIAL_ID", "Creators API — ID", "Amazon", false, "Opcional. Associates Central > Creators API."],
  ["AMAZON_CREDENTIAL_SECRET", "Creators API — Secret", "Amazon", true, "Opcional. Creators API Secret."],
  ["SHOPEE_APP_ID", "App ID", "Shopee", false, "Painel de afiliados Shopee > menu 'Abrir API'."],
  ["SHOPEE_APP_SECRET", "App Secret", "Shopee", true, "Painel de afiliados Shopee > menu 'Abrir API'."],
];

function switchView(viewName) {
  $$('.nav-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-view') === viewName);
  });
  $$('.view-tab-content').forEach(el => {
    el.classList.remove('active-view');
  });
  const target = $(`#view-${viewName}`);
  if (target) target.classList.add('active-view');

  if (viewName === 'produtos') carregarProdutos();
  if (viewName === 'config') { carregarConfig(); carregarNichos(); }
}

function gerenciarPlataforma(platKey) {
  switchView('plataformas');
  $$('.platform-block').forEach(b => b.classList.remove('highlighted'));
  const el = $(`#block-${platKey}`);
  if (el) {
    el.classList.add('highlighted');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function updateClock() {
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const timeStr = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const dateStr = `${pad(now.getDate())}/${pad(now.getMonth() + 1)}/${now.getFullYear()}`;
  
  const elTime = $("#liveClock");
  const elDate = $("#liveDate");
  const elFooter = $("#footerTime");
  if (elTime) elTime.textContent = timeStr;
  if (elDate) elDate.textContent = dateStr;
  if (elFooter) elFooter.textContent = `${dateStr} ${timeStr}`;
}
setInterval(updateClock, 1000);
updateClock();

function renderLineChart(canvasId, labels, values) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width, h = rect.height;
  const padTop = 15, padBottom = 25, padLeft = 32, padRight = 15;
  const chartW = w - padLeft - padRight;
  const chartH = h - padTop - padBottom;

  ctx.clearRect(0, 0, w, h);

  const rawMax = Math.max(...values, 0);
  const maxVal = rawMax > 0 ? rawMax * 1.25 : 10;

  ctx.strokeStyle = '#173957';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#8EA6BF';
  ctx.font = '10px Plus Jakarta Sans, sans-serif';

  const gridSteps = 4;
  for (let i = 0; i <= gridSteps; i++) {
    const y = padTop + (chartH / gridSteps) * i;
    const val = Math.round(maxVal - (maxVal / gridSteps) * i);
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();
    ctx.fillText(val, 5, y + 3);
  }

  const pts = values.map((v, i) => {
    const x = padLeft + (chartW / (values.length - 1 || 1)) * i;
    const y = padTop + chartH - (v / maxVal) * chartH;
    return { x, y, val: v, label: labels[i] || '' };
  });

  const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
  grad.addColorStop(0, 'rgba(8, 123, 255, 0.35)');
  grad.addColorStop(1, 'rgba(8, 123, 255, 0.0)');

  ctx.beginPath();
  ctx.moveTo(pts[0].x, padTop + chartH);
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.lineTo(p.x, p.y);
    else {
      const prev = pts[idx - 1];
      const cx = (prev.x + p.x) / 2;
      ctx.bezierCurveTo(cx, prev.y, cx, p.y, p.x, p.y);
    }
  });
  ctx.lineTo(pts[pts.length - 1].x, padTop + chartH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  ctx.strokeStyle = '#087BFF';
  ctx.lineWidth = 2.5;
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else {
      const prev = pts[idx - 1];
      const cx = (prev.x + p.x) / 2;
      ctx.bezierCurveTo(cx, prev.y, cx, p.y, p.x, p.y);
    }
  });
  ctx.stroke();

  pts.forEach(p => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#087BFF';
    ctx.stroke();

    ctx.fillStyle = '#8EA6BF';
    ctx.textAlign = 'center';
    ctx.fillText(p.label, p.x, h - 6);
  });
}

function renderBarChart(canvasId, values) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const w = rect.width, h = rect.height;
  const padTop = 15, padBottom = 20, padLeft = 32, padRight = 10;
  const chartW = w - padLeft - padRight;
  const chartH = h - padTop - padBottom;

  ctx.clearRect(0, 0, w, h);

  const rawMax = Math.max(...values, 0);
  const maxVal = rawMax > 0 ? rawMax * 1.3 : 5;
  const gridSteps = 4;
  ctx.strokeStyle = '#173957';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#8EA6BF';
  ctx.font = '10px Plus Jakarta Sans, sans-serif';

  for (let i = 0; i <= gridSteps; i++) {
    const y = padTop + (chartH / gridSteps) * i;
    const val = (Math.round((maxVal - (maxVal / gridSteps) * i) * 10) / 10) + '%';
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(w - padRight, y);
    ctx.stroke();
    ctx.fillText(val, 5, y + 3);
  }

  const barWidth = 14;
  const gap = (chartW - (values.length * barWidth)) / (values.length + 1);

  values.forEach((v, i) => {
    const x = padLeft + gap + i * (barWidth + gap);
    const barH = v > 0 ? (v / maxVal) * chartH : 2;
    const y = padTop + chartH - barH;

    const grad = ctx.createLinearGradient(0, y, 0, y + barH);
    grad.addColorStop(0, '#20D889');
    grad.addColorStop(1, '#059669');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(x, y, barWidth, barH, [4, 4, 0, 0]);
    ctx.fill();
  });
}

async function atualizarStatus() {
  try {
    const r = await fetch('/api/status');
    statusAtual = await r.json();

    const on = statusAtual.bot_rodando;
    const sideDot = $("#sideBotDot");
    const sideTitle = $("#sideBotTitle");
    const sideSub = $("#sideBotSub");

    if (sideDot) sideDot.className = 'bot-status-dot' + (on ? ' active' : '');
    if (sideTitle) sideTitle.textContent = on ? 'Bot Ativo' : 'Bot Parado';
    if (sideSub) sideSub.textContent = on ? 'Rodando normalmente' : 'Aguardando início';

    const hDot = $("#headerBotDot");
    const hText = $("#headerBotText");
    if (hDot) {
      hDot.style.background = on ? '#20D889' : '#5c7896';
      hDot.style.boxShadow = on ? '0 0 8px #20D889' : 'none';
    }
    if (hText) hText.textContent = on ? 'Bot Rodando' : 'Bot Parado';

    const btnNav = $("#btnInstalarNav");
    if (btnNav) {
      btnNav.textContent = statusAtual.navegador ? '✓ Playwright Chromium Instalado' : '⬇️ Instalar Playwright Chromium';
    }

    if (statusAtual.plataformas) {
      // Mercado Livre
      const ml = statusAtual.plataformas.mercadolivre;
      const bDashMl = $("#dashMlBadge");
      const bPbMl = $("#pbMlBadge");
      const subDashMl = $("#dashMlSub");
      const etiqMl = $("#pbMlEtiqueta");
      const sttSessao = $("#pbMlSessaoStatus");

      const mlConectado = ml && ml.conectado;
      if (bDashMl) {
        bDashMl.className = mlConectado ? 'badge-connected' : 'badge-pending';
        bDashMl.innerHTML = `<span class="dot"></span>${mlConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (bPbMl) {
        bPbMl.className = mlConectado ? 'badge-connected' : 'badge-pending';
        bPbMl.innerHTML = `<span class="dot"></span>${mlConectado ? 'Sessão Ativa' : 'Não configurado'}`;
      }
      if (subDashMl) subDashMl.textContent = mlConectado ? 'Sessão Conectada' : 'Não configurado';
      if (etiqMl) etiqMl.textContent = (ml && ml.etiqueta) ? ml.etiqueta : 'Não configurado';
      if (sttSessao) sttSessao.textContent = statusAtual.sessao_ml ? 'Perfil local salvo ✓' : 'Não configurado (sem sessão)';

      // Amazon
      const amz = statusAtual.plataformas.amazon;
      const bDashAmz = $("#dashAmzBadge");
      const bPbAmz = $("#pbAmzBadge");
      const subDashAmz = $("#dashAmzSub");
      const tagAmz = $("#pbAmzTag");
      const apiAmz = $("#pbAmzApiStatus");

      const amzConectado = amz && amz.conectado;
      if (bDashAmz) {
        bDashAmz.className = amzConectado ? 'badge-connected' : 'badge-pending';
        bDashAmz.innerHTML = `<span class="dot"></span>${amzConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (bPbAmz) {
        bPbAmz.className = amzConectado ? 'badge-connected' : 'badge-pending';
        bPbAmz.innerHTML = `<span class="dot"></span>${amzConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (subDashAmz) subDashAmz.textContent = amzConectado ? 'Tag configurada' : 'Não configurado';
      if (tagAmz) tagAmz.textContent = (amz && amz.tag) ? amz.tag : 'Não configurado';
      if (apiAmz) apiAmz.textContent = (amz && amz.api_ativa) ? 'Configurado ✓' : 'Não configurado';

      // Shopee
      const shp = statusAtual.plataformas.shopee;
      const bDashShp = $("#dashShpBadge");
      const bPbShp = $("#pbShpBadge");
      const subDashShp = $("#dashShpSub");
      const appIdShp = $("#pbShpAppId");
      const secShp = $("#pbShpSecretStatus");

      const shpConectado = shp && shp.conectado;
      if (bDashShp) {
        bDashShp.className = shpConectado ? 'badge-connected' : 'badge-pending';
        bDashShp.innerHTML = `<span class="dot"></span>${shpConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (bPbShp) {
        bPbShp.className = shpConectado ? 'badge-connected' : 'badge-pending';
        bPbShp.innerHTML = `<span class="dot"></span>${shpConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (subDashShp) subDashShp.textContent = shpConectado ? 'API configurada' : 'Não configurado';
      if (appIdShp) appIdShp.textContent = (shp && shp.app_id) ? shp.app_id : 'Não configurado';
      if (secShp) secShp.textContent = shpConectado ? '••••••••' : 'Não configurado';

      // AliExpress
      const ali = statusAtual.plataformas.aliexpress;
      const bDashAli = $("#dashAliBadge");
      const bPbAli = $("#pbAliBadge");
      const subDashAli = $("#dashAliSub");
      const sttAli = $("#pbAliStatus");
      const aliConectado = ali && ali.conectado;
      if (bDashAli) {
        bDashAli.className = aliConectado ? 'badge-connected' : 'badge-pending';
        bDashAli.innerHTML = `<span class="dot"></span>${aliConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (bPbAli) {
        bPbAli.className = aliConectado ? 'badge-connected' : 'badge-pending';
        bPbAli.innerHTML = `<span class="dot"></span>${aliConectado ? 'Conectado' : 'Não configurado'}`;
      }
      if (subDashAli) subDashAli.textContent = aliConectado ? 'Configurado' : 'Não configurado';
      if (sttAli) sttAli.textContent = aliConectado ? 'Configurado ✓' : 'Não configurado';
    }

    const supInfo = $("#suporteAmbienteInfo");
    if (supInfo) {
      supInfo.innerHTML = `Chromium: <b>${statusAtual.navegador ? 'Instalado ✓' : 'Não instalado'}</b> | Sessão ML: <b>${statusAtual.sessao_ml ? 'Ativa ✓' : 'Não configurado'}</b> | Configurações (.env): <b>${statusAtual.pronto ? 'Pronto ✓' : 'Não configurado'}</b>`;
    }
  } catch (e) {
    console.error(e);
  }
}

async function atualizarMetricas() {
  try {
    const r = await fetch('/api/metricas');
    const d = await r.json();

    if ($("#valLinksGerados")) $("#valLinksGerados").textContent = d.links_gerados_total;
    if ($("#badgeLinksCresc")) $("#badgeLinksCresc").textContent = d.links_gerados_crescimento;
    if ($("#valConversao")) $("#valConversao").textContent = d.conversao_taxa;
    if ($("#badgeConvCresc")) $("#badgeConvCresc").textContent = d.conversao_crescimento;
    if ($("#navLinkCount")) $("#navLinkCount").textContent = d.links_gerados_total;

    renderLineChart('chartLinks', d.grafico_dias_labels, d.grafico_dias_valores);
    renderBarChart('chartConversao', d.grafico_conversao_valores);

    const topWrap = $("#topPlataformasWrap");
    if (topWrap) {
      if (d.top_plataformas && d.top_plataformas.length && d.links_gerados_total > 0) {
        topWrap.innerHTML = d.top_plataformas.map(p => `
          <div class="top-platform-item">
            <div class="top-platform-icon" style="background:${p.cor}; color:#000;">●</div>
            <div class="top-platform-name">${p.nome}</div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${p.pct}%;"></div>
            </div>
            <div class="top-platform-clicks">${p.cliques}</div>
            <div class="top-platform-pct">${p.pct}%</div>
          </div>
        `).join('');
      } else {
        topWrap.innerHTML = `<div class="empty-placeholder">Nenhum clique ou post registrado ainda.</div>`;
      }
    }

    const actWrap = $("#activityListWrap");
    if (actWrap) {
      if (d.atividades && d.atividades.length) {
        actWrap.innerHTML = d.atividades.map(a => {
          let iconClass = 'blue';
          let iconSvg = '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>';
          if (a.plataforma === 'amazon') iconClass = 'orange';
          else if (a.plataforma === 'shopee') iconClass = 'purple';
          else if (a.plataforma === 'mercadolivre') iconClass = 'green';

          return `
            <div class="activity-item">
              <div class="act-icon ${iconClass}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">${iconSvg}</svg>
              </div>
              <div class="act-content">
                <div class="title">${a.titulo}</div>
                <div class="desc">${a.detalhe}</div>
              </div>
              <div class="act-time">${a.hora}</div>
            </div>
          `;
        }).join('');
      } else {
        actWrap.innerHTML = `<div class="empty-placeholder">Nenhuma atividade registrada ainda.</div>`;
      }
    }

    const linkWrap = $("#recentLinksListWrap");
    const allLinkWrap = $("#allLinksListWrap");
    if (d.links_recentes && d.links_recentes.length) {
      const html = d.links_recentes.map(l => `
        <div class="recent-link-item">
          <div class="recent-link-left">
            <span class="sys-dot" style="width: 6px; height: 6px; background: #20D889;"></span>
            <div>
              <a href="https://${l.url}" target="_blank" class="recent-link-url">${l.url}</a>
              <div class="recent-link-date">${l.data}</div>
            </div>
          </div>
          <button class="btn-copy-icon" title="Copiar link" onclick="copiarTexto('https://${l.url}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>
      `).join('');

      if (linkWrap) linkWrap.innerHTML = html;
      if (allLinkWrap) allLinkWrap.innerHTML = html;
    } else {
      if (linkWrap) linkWrap.innerHTML = `<div class="empty-placeholder">Nenhum link recente postado.</div>`;
      if (allLinkWrap) allLinkWrap.innerHTML = `<div class="empty-placeholder">Nenhum link gerado ainda.</div>`;
    }
  } catch (e) {
    console.error(e);
  }
}

async function puxarLogs() {
  try {
    const [lb, la] = await Promise.all([
      fetch('/api/logs?bot').then(r => r.json()),
      fetch('/api/logs?acao').then(r => r.json())
    ]);

    if (lb && lb.linhas) {
      const el = $("#logBotBody");
      if (el && lb.linhas.length) {
        const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
        el.textContent = lb.linhas.join('\n');
        if (atBottom) el.scrollTop = el.scrollHeight;
      }
    }

    if (la && la.linhas) {
      const elAcao = $("#logAcaoBody");
      const elTerm = $("#logAcaoTerminal");
      const txt = la.linhas.length ? la.linhas.join('\n') : 'Nenhuma ação executada.';
      if (elAcao) {
        const atBottom = elAcao.scrollTop + elAcao.clientHeight >= elAcao.scrollHeight - 40;
        elAcao.textContent = txt;
        if (atBottom) elAcao.scrollTop = elAcao.scrollHeight;
      }
      if (elTerm) {
        elTerm.textContent = txt;
        elTerm.scrollTop = elTerm.scrollHeight;
      }
    }
  } catch (e) {
    console.error(e);
  }
}

async function toggleBot() {
  const rota = statusAtual.bot_rodando ? '/api/stop' : '/api/start';
  try {
    const r = await (await fetch(rota, { method: 'POST' })).json();
    toast(r.rodando ? 'Bot iniciado com sucesso!' : 'Bot desligado.', r.rodando ? 'success' : 'info');
    atualizarStatus();
  } catch (e) {
    toast('Erro ao comunicar com o servidor.', 'error');
  }
}

async function execAcao(nome) {
  try {
    toast(`Iniciando ação: ${nome}...`, 'info');
    const r = await (await fetch('/api/acao', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome })
    })).json();

    if (r.erro) {
      toast(r.erro, 'error');
    } else {
      toast('Ação em execução. Acompanhe a saída.', 'success');
      switchView('plataformas');
    }
  } catch (e) {
    toast('Erro ao executar ação.', 'error');
  }
}

async function carregarConfig() {
  try {
    CFG = await (await fetch('/api/config')).json();
    const wrap = $("#camposFormWrap");
    if (!wrap) return;

    let html = '', grupoAtual = '';
    for (const [k, rot, grp, seg, ajuda] of CAMPOS) {
      if (grp !== grupoAtual) {
        html += `<div class="form-group-title" style="grid-column: 1 / -1;">${grp}</div>`;
        grupoAtual = grp;
      }
      const set = CFG[k + '__set'];
      const tick = set ? `<span style="color:var(--success); font-size:11px;">✓ Configurado</span>` : '';
      const ph = seg && set ? '•••••• (preenchido — deixe em branco para manter)' : '';

      html += `
        <div class="form-field">
          <label>${rot} ${tick}</label>
          <input id="cfg_${k}" type="${seg ? 'password' : 'text'}" placeholder="${ph}" value="${seg ? '' : (CFG[k] || '')}">
          <div class="field-help">${ajuda}</div>
        </div>
      `;
    }
    wrap.innerHTML = html;
  } catch (e) {
    console.error(e);
  }
}

async function salvarConfig() {
  const body = {};
  for (const [k] of CAMPOS) {
    const el = $("#cfg_" + k);
    if (el) body[k] = el.value.trim();
  }
  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    toast('Configurações salvas com sucesso!', 'success');
    await carregarConfig();
    atualizarStatus();
  } catch (e) {
    toast('Erro ao salvar configurações.', 'error');
  }
}

async function detectarIds() {
  const box = $("#idsDetectionBox");
  box.style.display = 'block';
  box.innerHTML = `<p style="color:var(--tx-muted); font-size:13px;">Consultando o Telegram...</p>`;

  try {
    const r = await (await fetch('/api/detectar-ids', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    })).json();

    if (r.erro) {
      box.innerHTML = `<p style="color:var(--warning); font-size:13px;">${r.erro}</p>`;
      return;
    }
    if (r.vazio) {
      box.innerHTML = `
        <div style="background:var(--bg-subcard); padding:12px; border-radius:8px; border:1px solid var(--border-color); font-size:13px; color:var(--tx-muted);">
          Nada encontrado ainda. No Telegram: envie <b>/start</b> e <b>/id</b> para o bot, e <b>encaminhe uma postagem do canal</b> para ele. Em seguida, clique novamente.
        </div>
      `;
      return;
    }

    let h = '<div style="display:flex; flex-direction:column; gap:8px;">';
    if (r.pessoas && r.pessoas.length) {
      h += `<p style="font-size:12px; font-weight:700; color:#fff;">Clique no seu usuário (dono):</p>`;
      for (const p of r.pessoas) {
        h += `<button class="btn-dark" onclick="setCampoId('TELEGRAM_OWNER_ID','${p.id}')">👤 ${p.nome} — <code>${p.id}</code></button>`;
      }
    }
    if (r.canais && r.canais.length) {
      h += `<p style="font-size:12px; font-weight:700; color:#fff; margin-top:8px;">Clique no seu canal:</p>`;
      for (const c of r.canais) {
        h += `<button class="btn-dark" onclick="setCampoId('TELEGRAM_CHAT_ID','${c.id}')">📢 ${c.nome} — <code>${c.id}</code></button>`;
      }
    }
    h += '</div>';
    box.innerHTML = h;
  } catch (e) {
    box.innerHTML = `<p style="color:var(--danger); font-size:13px;">Erro ao consultar IDs.</p>`;
  }
}

function setCampoId(campo, val) {
  const el = $("#cfg_" + campo);
  if (el) el.value = val;
  toast(`Campo ${campo} preenchido! Não esqueça de salvar.`, 'success');
}

let NICHOS_SEL = new Set();
async function carregarNichos() {
  try {
    const r = await (await fetch('/api/nichos')).json();
    NICHOS_SEL = new Set(r.selecionados || []);
    const grid = $("#nichosGrid");
    if (!grid) return;

    grid.innerHTML = r.catalogo.map(n => `
      <div class="nicho-card ${NICHOS_SEL.has(n.chave) ? 'selected' : ''}" onclick="toggleNicho('${n.chave}', this)">
        <span style="font-size:18px;">${n.emoji}</span>
        <span style="font-size:13px; font-weight:600;">${n.nome}</span>
        <span class="n-check">✓</span>
      </div>
    `).join('');

    atualizarLabelNichos();
  } catch (e) {
    console.error(e);
  }
}

function toggleNicho(chave, el) {
  if (NICHOS_SEL.has(chave)) NICHOS_SEL.delete(chave);
  else NICHOS_SEL.add(chave);
  el.classList.toggle('selected');
  atualizarLabelNichos();
}

function atualizarLabelNichos() {
  const lbl = $("#nichosCountLabel");
  if (!lbl) return;
  const n = NICHOS_SEL.size;
  lbl.textContent = n === 0 ? 'Buscando em todas as categorias' : `${n} categoria(s) selecionada(s)`;
}

async function salvarNichos() {
  try {
    await fetch('/api/nichos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selecionados: [...NICHOS_SEL] })
    });
    toast('Categorias salvas com sucesso!', 'success');
  } catch (e) {
    toast('Erro ao salvar categorias.', 'error');
  }
}

function limparNichos() {
  NICHOS_SEL.clear();
  $$('.nicho-card').forEach(el => el.classList.remove('selected'));
  atualizarLabelNichos();
}

async function carregarProdutos() {
  const tbody = $("#produtosTableBody");
  if (!tbody) return;
  try {
    const r = await (await fetch('/api/produtos')).json();
    const lista = r.produtos || [];
    if (!lista.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--tx-dim); padding:24px;">Nenhuma oferta postada ainda no banco de dados.</td></tr>`;
      return;
    }

    tbody.innerHTML = lista.map(p => `
      <tr>
        <td><span class="badge-connected"><span class="dot"></span>${p.plataforma || 'Mercado Livre'}</span></td>
        <td style="font-weight:600; color:#fff;">${p.titulo || 'Produto sem título'}</td>
        <td style="color:#20D889; font-weight:700;">${p.preco ? 'R$ ' + Number(p.preco).toFixed(2).replace('.', ',') : '—'}</td>
        <td style="color:var(--tx-dim); font-size:12px;">${p.postada_em || 'Recente'}</td>
        <td>
          <button class="btn-dark" style="padding:4px 10px; font-size:11px;" onclick="copiarTexto('${p.uid}')">Copiar ID</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--danger);">Erro ao carregar produtos.</td></tr>`;
  }
}

function abrirModalLink() {
  $("#modalLinkBuilder").classList.add('show');
  $("#modalInputUrl").focus();
}
function fecharModalLink() {
  $("#modalLinkBuilder").classList.remove('show');
}

async function converterLinkModal() {
  const url = $("#modalInputUrl").value.trim();
  const plat = $("#modalSelectPlat").value;
  if (!url) { toast('Cole uma URL de produto primeiro.', 'warning'); return; }

  try {
    const r = await (await fetch('/api/gerar-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, plataforma: plat })
    })).json();

    if (r.ok && r.url_afiliado) {
      $("#modalLinkResult").style.display = 'block';
      $("#modalOutputUrl").value = r.url_afiliado;
      toast('Link de afiliado gerado com sucesso!', 'success');
      atualizarMetricas();
    } else {
      toast(r.erro || 'Erro ao gerar link.', 'error');
    }
  } catch (e) {
    toast('Erro de rede ao gerar link.', 'error');
  }
}

function copiarOutputModal() {
  const el = $("#modalOutputUrl");
  copiarTexto(el.value);
}

function abrirModalSessao() {
  $("#modalSessao").classList.add('show');
  verificarSessaoModal();
}
function fecharModalSessao() {
  $("#modalSessao").classList.remove('show');
}

async function verificarSessaoModal() {
  const box = $("#modalSessaoConteudo");
  box.innerHTML = 'Verificando diretório e cookies de sessão local...';
  try {
    const r = await (await fetch('/api/verificar-sessao', { method: 'POST' })).json();
    box.innerHTML = `
      <div style="background:var(--bg-subcard); padding:14px; border-radius:8px; border:1px solid var(--border-color);">
        <p><strong>Status da Sessão Local:</strong> ${r.sessao_ml ? '<span style="color:var(--success)">✓ Ativa e Persistente</span>' : '<span style="color:var(--warning)">Pendente</span>'}</p>
        <p><strong>Arquivos salvos no perfil:</strong> ${r.arquivos} arquivos</p>
        <p style="font-size:11px; color:var(--tx-dim); margin-top:8px; word-break:break-all;"><strong>Caminho Local:</strong> ${r.caminho}</p>
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<span style="color:var(--danger)">Erro ao verificar status da sessão.</span>';
  }
}

async function limparSessao() {
  if (!confirm('Deseja realmente limpar a sessão local do Mercado Livre? Será necessário fazer login novamente.')) return;
  try {
    const r = await (await fetch('/api/limpar-sessao', { method: 'POST' })).json();
    toast(r.msg || 'Sessão limpa.', 'success');
    atualizarStatus();
  } catch (e) {
    toast('Erro ao limpar sessão.', 'error');
  }
}

function copiarTexto(txt) {
  navigator.clipboard.writeText(txt).then(() => {
    toast('Copiado para a área de transferência!', 'success');
  }).catch(() => {
    toast('Não foi possível copiar.', 'error');
  });
}

function limparTerminal(id) {
  const el = document.getElementById(id);
  if (el) el.textContent = 'Terminal limpo.';
}

function toast(msg, type = 'info') {
  const box = $("#toastBox");
  if (!box) return;
  const t = document.createElement('div');
  t.className = `toast-card ${type}`;
  t.textContent = msg;
  box.appendChild(t);

  setTimeout(() => t.classList.add('show'), 10);
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.remove(), 300);
  }, 3500);
}

window.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('show');
  }
});

// Boot
carregarConfig();
carregarNichos();
atualizarStatus();
atualizarMetricas();
puxarLogs();

setInterval(atualizarStatus, 2500);
setInterval(atualizarMetricas, 8000);
setInterval(puxarLogs, 1500);
</script>
</body>
</html>
"""
