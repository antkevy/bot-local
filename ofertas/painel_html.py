"""A página HTML do painel de controle de alta fidelidade visual (servida por painel.py)."""

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
    --bg-main: #070d1e;
    --bg-sidebar: #0a1329;
    --bg-card: rgba(14, 25, 52, 0.72);
    --bg-card-hover: rgba(20, 35, 70, 0.85);
    --bg-subcard: #0c1630;
    --bg-subcard2: #0f1d3d;
    --border-color: #1a2c56;
    --border-light: #243b70;
    --border-glow: rgba(0, 102, 255, 0.35);
    --tx-main: #f0f4fc;
    --tx-muted: #7e91b0;
    --tx-dim: #546888;
    --primary: #0066ff;
    --primary-hover: #1e78ff;
    --primary-glow: 0 0 20px rgba(0, 102, 255, 0.4);
    --success: #00e676;
    --success-bg: rgba(0, 230, 118, 0.12);
    --warning: #ffb300;
    --danger: #ff4757;
    --danger-bg: rgba(255, 71, 87, 0.12);
    --font-main: 'Plus Jakarta Sans', 'Segoe UI', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', Consolas, monospace;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background-color: var(--bg-main);
    background-image: 
      radial-gradient(circle at 20% 0%, rgba(0, 102, 255, 0.12) 0%, transparent 50%),
      radial-gradient(circle at 80% 100%, rgba(139, 92, 246, 0.08) 0%, transparent 50%);
    color: var(--tx-main);
    font-family: var(--font-main);
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    overflow-x: hidden;
  }

  /* Scrollbars */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #1c2e56; border-radius: 99px; }
  ::-webkit-scrollbar-thumb:hover { background: #2a437c; }

  /* Layout Structure */
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
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #38bdf8 0%, #0066ff 60%, #0243aa 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 16px rgba(0, 102, 255, 0.5);
    position: relative;
    flex-shrink: 0;
  }
  .brand-icon::after {
    content: '';
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid #fff;
    background: #0066ff;
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
    background: #111d38;
    color: #8da4c4;
    border: 1px solid #1f335e;
  }
  .nav-item.active .nav-badge {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
    border-color: transparent;
  }

  /* Sidebar Bottom Bot Status Card */
  .sidebar-bot-card {
    background: var(--bg-subcard);
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
    background: var(--bg-subcard2);
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

  /* ── Main Content Area ── */
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
    font-size: 16px;
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
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
  }

  .time-display {
    text-align: right;
  }
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
    background: #1e3a8a;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #93c5fd;
  }
  .user-info {
    line-height: 1.2;
  }
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
    box-shadow: 0 0 24px rgba(0, 102, 255, 0.55);
  }
  .btn-primary:active { transform: translateY(0); }

  .btn-dark {
    background: #0d1a36;
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
    background: #15274d;
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

  /* Content Grid */
  .content-body {
    padding: 8px 32px 32px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    flex: 1;
  }

  .dash-card {
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 20px;
    position: relative;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
    transition: border-color 0.2s;
  }
  .dash-card:hover { border-color: var(--border-light); }

  /* Platforms Row */
  .platforms-row {
    display: grid;
    grid-template-columns: 1.6fr 1fr 1fr 1fr 1fr;
    gap: 14px;
  }
  @media (max-width: 1200px) { .platforms-row { grid-template-columns: 1fr 1fr 1fr; } }
  @media (max-width: 768px) { .platforms-row { grid-template-columns: 1fr; } }

  .ml-featured-card {
    background: linear-gradient(135deg, rgba(16, 30, 64, 0.9) 0%, rgba(10, 18, 40, 0.9) 100%);
    border: 1px solid #1f376a;
    border-radius: var(--radius-md);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 14px;
  }
  .ml-card-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .ml-logo-box {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: #ffe600;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    box-shadow: 0 4px 12px rgba(255, 230, 0, 0.25);
    flex-shrink: 0;
  }
  .platform-title-wrap { flex: 1; }
  .platform-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .platform-title-row h4 {
    font-size: 15px;
    font-weight: 700;
    color: #fff;
  }
  .badge-connected {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 600;
    color: var(--success);
    background: var(--success-bg);
    border: 1px solid rgba(0, 230, 118, 0.25);
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
    background: rgba(255, 179, 0, 0.12);
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
  .platform-desc {
    font-size: 12px;
    color: var(--tx-muted);
    margin-top: 2px;
  }
  .ml-actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ml-actions .btn-primary {
    justify-content: center;
    padding: 9px 14px;
    font-size: 13px;
  }
  .ml-actions .btn-dark {
    justify-content: center;
    padding: 8px 14px;
    font-size: 12.5px;
    background: #0d1a36;
  }

  .platform-mini-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 16px 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 8px;
  }
  .platform-icon-box {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 800;
    color: #fff;
    margin-bottom: 2px;
  }
  .icon-amazon { background: #ff9900; box-shadow: 0 4px 12px rgba(255, 153, 0, 0.25); }
  .icon-shopee { background: #ee4d2d; box-shadow: 0 4px 12px rgba(238, 77, 45, 0.25); }
  .icon-aliexpress { background: #ff4747; box-shadow: 0 4px 12px rgba(255, 71, 71, 0.25); }
  .icon-promogram { background: #8b5cf6; box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25); }

  .platform-mini-card h4 {
    font-size: 14px;
    font-weight: 700;
    color: #fff;
  }
  .platform-mini-card .platform-sub {
    font-size: 11px;
    color: var(--tx-dim);
  }
  .platform-mini-card .btn-dark {
    width: 100%;
    justify-content: center;
    padding: 6px 10px;
    font-size: 12px;
    margin-top: 4px;
  }

  /* 2-Column Split */
  .dash-main-grid {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 1100px) { .dash-main-grid { grid-template-columns: 1fr; } }

  .dash-left-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* Metrics Row */
  .metrics-row {
    display: grid;
    grid-template-columns: 1.1fr 1fr 1.3fr;
    gap: 14px;
  }
  @media (max-width: 900px) { .metrics-row { grid-template-columns: 1fr; } }

  .metric-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .metric-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .metric-title-group svg { color: var(--primary); }
  .metric-title-group h4 {
    font-size: 13.5px;
    font-weight: 700;
    color: #fff;
  }
  .metric-subtitle {
    font-size: 11px;
    color: var(--tx-dim);
  }
  .metric-stat-group { text-align: right; }
  .metric-big-val {
    font-size: 20px;
    font-weight: 800;
    color: #fff;
    line-height: 1.1;
  }
  .metric-growth-badge {
    font-size: 11px;
    font-weight: 700;
    color: var(--success);
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }

  .chart-canvas-wrap {
    width: 100%;
    height: 140px;
    position: relative;
  }
  canvas {
    width: 100% !important;
    height: 100% !important;
  }

  .top-platforms-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 6px;
  }
  .top-platform-item {
    display: grid;
    grid-template-columns: 20px 80px 1fr 40px 45px;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }
  .top-platform-icon {
    width: 18px;
    height: 18px;
    border-radius: 4px;
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
    height: 6px;
    background: #111e3b;
    border-radius: 99px;
    overflow: hidden;
  }
  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #0066ff, #38bdf8);
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

  /* Bottom Cards Row */
  .bottom-cards-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 14px;
  }
  @media (max-width: 960px) { .bottom-cards-row { grid-template-columns: 1fr; } }

  .card-top-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .card-top-title-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-top-title-left h4 {
    font-size: 14px;
    font-weight: 700;
    color: #fff;
  }
  .card-top-title a {
    font-size: 12px;
    color: var(--primary);
    text-decoration: none;
    font-weight: 600;
  }
  .card-top-title a:hover { text-decoration: underline; }

  .activity-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .activity-item {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .act-icon {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .act-icon.green { background: rgba(0, 230, 118, 0.15); color: var(--success); }
  .act-icon.blue { background: rgba(0, 102, 255, 0.15); color: #60a5fa; }
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
    font-size: 11px;
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

  .vps-checklist {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: 12px 0 16px;
    font-size: 12.5px;
    color: #cbd5e1;
  }
  .vps-checklist li {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .vps-checklist li svg {
    color: var(--success);
    flex-shrink: 0;
  }

  .tip-box {
    background: rgba(255, 179, 0, 0.08);
    border: 1px solid rgba(255, 179, 0, 0.2);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    display: flex;
    gap: 10px;
    font-size: 11.5px;
    color: #f1c40f;
    line-height: 1.4;
    margin-top: 14px;
  }
  .tip-box svg { flex-shrink: 0; margin-top: 2px; }

  /* Right Panels Column */
  .dash-right-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .right-panel-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 18px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  }

  .ml-status-box {
    background: var(--bg-subcard);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 12px;
    margin: 12px 0 14px;
  }
  .ml-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 700;
    color: var(--success);
    margin-bottom: 4px;
  }
  .ml-status-desc {
    font-size: 12px;
    color: var(--tx-muted);
  }

  .recent-links-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 10px;
  }
  .recent-link-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 7px 10px;
    background: var(--bg-subcard);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font-size: 12px;
  }
  .recent-link-left {
    display: flex;
    align-items: center;
    gap: 8px;
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
    font-size: 10.5px;
    color: var(--tx-dim);
    margin-top: 1px;
  }
  .btn-copy-icon {
    background: transparent;
    border: 0;
    color: var(--tx-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: 0.15s;
    display: flex;
  }
  .btn-copy-icon:hover { color: #fff; background: rgba(255, 255, 255, 0.1); }

  /* Global Footer */
  .global-footer {
    padding: 14px 32px;
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
    gap: 20px;
  }
  @media (max-width: 900px) { .config-grid { grid-template-columns: 1fr; } }
  
  .form-group-title {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #60a5fa;
    font-weight: 700;
    margin: 16px 0 10px;
  }
  .form-group-title:first-of-type { margin-top: 0; }
  .form-field { margin-bottom: 14px; }
  .form-field label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 5px;
  }
  .form-field input, .form-field select {
    width: 100%;
    padding: 10px 12px;
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
    box-shadow: 0 0 0 3px rgba(0, 102, 255, 0.2);
  }
  .form-field .field-help {
    font-size: 11.5px;
    color: var(--tx-dim);
    margin-top: 4px;
  }

  .nichos-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 8px;
    margin: 12px 0;
  }
  .nicho-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: var(--bg-subcard);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    user-select: none;
    transition: 0.15s;
  }
  .nicho-card:hover { border-color: var(--primary); }
  .nicho-card.selected {
    background: rgba(0, 102, 255, 0.15);
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
    gap: 16px;
    height: calc(100vh - 240px);
    min-height: 400px;
  }
  @media (max-width: 900px) { .logs-terminal-container { grid-template-columns: 1fr; height: auto; } }

  .terminal-box {
    background: #060b17;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .terminal-header {
    background: #0b1429;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12.5px;
    font-weight: 700;
  }
  .terminal-body {
    flex: 1;
    padding: 14px;
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
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
    font-size: 13px;
  }
  table.data-table th {
    background: #0b152d;
    padding: 12px 16px;
    color: var(--tx-muted);
    font-weight: 700;
    border-bottom: 1px solid var(--border-color);
  }
  table.data-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #142244;
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
    background: #0c1630;
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
    background: #080f22;
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
    background: #0f2347;
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
  
  <!-- ── Left Sidebar ── -->
  <aside class="sidebar">
    <a href="#" class="brand" onclick="switchView('dashboard')">
      <div class="brand-icon"></div>
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
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
        Produtos
      </a>
      <a class="nav-item" data-view="listas" onclick="switchView('listas')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
        Listas
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
        <div class="title" id="sideBotTitle">Bot Desligado</div>
        <div class="subtitle" id="sideBotSub">Clique para iniciar</div>
      </div>
      <div class="bot-status-arrow">›</div>
    </div>

    <div class="sidebar-footer">
      <strong>Ofertas Pro v2.0.0</strong><br>
      Painel de Afiliados - VPS
    </div>
  </aside>

  <!-- ── Main Area ── -->
  <main class="main-wrapper">
    
    <!-- Top Header -->
    <header class="top-header">
      <div class="greeting-section">
        <h2>Olá! 👋</h2>
        <h3>Bem-vindo ao seu painel de afiliados</h3>
        <p>Aqui você gerencia seus links, acompanha o desempenho e faz o controle das suas ofertas.</p>
      </div>

      <div class="header-actions">
        <div class="sys-online-pill">
          <span class="sys-dot"></span>
          Sistema Online
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
            <div class="badge">Premium</div>
          </div>
        </div>

        <button class="btn-primary" onclick="abrirModalLink()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
          Gerar Link Rápido
        </button>
      </div>
    </header>

    <!-- ── TAB 1: DASHBOARD (Real Data Only) ── -->
    <div id="view-dashboard" class="content-body view-tab-content active-view">
      
      <!-- Top Row: Platforms Cards -->
      <section class="platforms-row">
        <!-- Mercado Livre (Featured Card) -->
        <div class="ml-featured-card">
          <div class="ml-card-header">
            <div class="ml-logo-box">🤝</div>
            <div class="platform-title-wrap">
              <div class="platform-title-row">
                <h4>Mercado Livre</h4>
                <span class="badge-pending" id="mlBadge"><span class="dot"></span>Verificando</span>
              </div>
              <div class="platform-desc" id="mlDesc">Sessão pendente</div>
            </div>
          </div>

          <div class="ml-actions">
            <button class="btn-primary" onclick="execAcao('ml-login')">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
              Login no Mercado Livre
            </button>
            <button class="btn-dark" onclick="abrirTelaML()">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"></rect></svg>
              Abrir tela do Mercado Livre
            </button>
          </div>
        </div>

        <!-- Amazon -->
        <div class="platform-mini-card">
          <div class="platform-icon-box icon-amazon">a</div>
          <h4>Amazon</h4>
          <span class="badge-connected" id="badgeAmz"><span class="dot"></span>Conectado</span>
          <span class="platform-sub" id="subAmz">Tag de associado</span>
          <button class="btn-dark" onclick="switchView('config')">Gerenciar</button>
        </div>

        <!-- Shopee -->
        <div class="platform-mini-card">
          <div class="platform-icon-box icon-shopee">🛍</div>
          <h4>Shopee</h4>
          <span class="badge-connected" id="badgeShp"><span class="dot"></span>Conectado</span>
          <span class="platform-sub" id="subShp">API de afiliados</span>
          <button class="btn-dark" onclick="switchView('config')">Gerenciar</button>
        </div>

        <!-- AliExpress -->
        <div class="platform-mini-card">
          <div class="platform-icon-box icon-aliexpress">🛒</div>
          <h4>AliExpress</h4>
          <span class="badge-connected"><span class="dot"></span>Conectado</span>
          <span class="platform-sub">API ativa</span>
          <button class="btn-dark" onclick="switchView('config')">Gerenciar</button>
        </div>

        <!-- Promogram -->
        <div class="platform-mini-card">
          <div class="platform-icon-box icon-promogram">P</div>
          <h4>Promogram</h4>
          <span class="badge-connected"><span class="dot"></span>Conectado</span>
          <span class="platform-sub">API ativa</span>
          <button class="btn-dark" onclick="switchView('config')">Gerenciar</button>
        </div>
      </section>

      <!-- Main 2-Column Split -->
      <div class="dash-main-grid">
        
        <!-- Left Section -->
        <div class="dash-left-column">
          
          <!-- Performance Metrics & Charts Row -->
          <section class="metrics-row">
            
            <!-- Card 1: Links Gerados (Line Chart) -->
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

            <!-- Card 2: Conversão (Bar Chart) -->
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

          <!-- Lower Row: Atividade Recente, Chrome VPS, Gerenciar Sessão -->
          <section class="bottom-cards-row">
            
            <!-- Atividade Recente -->
            <div class="dash-card">
              <div class="card-top-title">
                <div class="card-top-title-left">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                  <h4>Atividade Recente</h4>
                </div>
                <a href="#" onclick="switchView('logs')">Ver todos</a>
              </div>

              <div class="activity-list" id="activityListWrap">
                <div class="empty-placeholder">Nenhuma atividade registrada ainda.</div>
              </div>
            </div>

            <!-- Acesse o Chrome da VPS -->
            <div class="dash-card">
              <div class="card-top-title">
                <div class="card-top-title-left">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
                  <h4>Acesse o Chrome da VPS</h4>
                </div>
              </div>
              <p style="font-size: 12px; color: var(--tx-muted);">Faça login no Mercado Livre diretamente na VPS através do seu navegador.</p>
              <div style="margin: 8px 0;">
                <span class="badge-connected"><span class="dot"></span>Seguro e rápido</span>
              </div>

              <ul class="vps-checklist">
                <li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> Chrome real na VPS</li>
                <li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> Acesso via noVNC</li>
                <li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> Sessão persistente</li>
                <li><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> Mesmo perfil do Link Builder</li>
              </ul>

              <button class="btn-primary" style="width: 100%; justify-content: center;" onclick="execAcao('ml-login')">
                Abrir Tela do Mercado Livre ↗
              </button>
              <p style="font-size: 11px; color: var(--tx-dim); margin-top: 8px; text-align: center;">ⓘ Use esta opção apenas para fazer o login manual.</p>
            </div>

            <!-- Gerenciar Sessão -->
            <div class="dash-card">
              <div class="card-top-title">
                <div class="card-top-title-left">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                  <h4>Gerenciar Sessão</h4>
                </div>
              </div>
              <p style="font-size: 12px; color: var(--tx-muted);">Você pode gerenciar sua sessão do Mercado Livre e verificar o status da autenticação.</p>

              <div style="display: flex; gap: 10px; margin: 16px 0 12px;">
                <button class="btn-dark" style="flex: 1; justify-content: center;" onclick="verificarSessao()">Verificar Sessão</button>
                <button class="btn-outline-danger" style="flex: 1; justify-content: center;" onclick="limparSessao()">Limpar Sessão</button>
              </div>

              <div class="tip-box">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C7.03 2 3 6.03 3 11c0 2.78 1.28 5.26 3.28 6.91.44.36.72.9.72 1.47V20c0 .55.45 1 1 1h8c.55 0 1-.45 1-1v-.62c0-.57.28-1.11.72-1.47C19.72 16.26 21 13.78 21 11c0-4.97-4.03-9-9-9zm-1 16h2v1h-2v-1zm0-3h2v1h-2v-1z"/></svg>
                <div><strong>Dica:</strong> Mantenha sua sessão ativa para garantir o funcionamento do Link Builder e a geração de links de afiliado.</div>
              </div>
            </div>
          </section>

        </div>

        <!-- Right Side Panels Column -->
        <div class="dash-right-column">
          
          <!-- Status do Mercado Livre -->
          <div class="right-panel-card">
            <div class="card-top-title" style="margin-bottom: 4px;">
              <div class="card-top-title-left">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00e676" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>
                <h4>Status do Mercado Livre</h4>
              </div>
            </div>

            <div class="ml-status-box">
              <div class="ml-status-pill" id="panelMlStatusDot"><span class="sys-dot"></span>Verificando...</div>
              <div class="ml-status-desc" id="panelMlStatusText">Verificando autenticação...</div>
            </div>

            <button class="btn-dark" style="width: 100%; justify-content: center;" onclick="abrirModalSessao()">
              Ver detalhes da sessão
            </button>
          </div>

          <!-- Link Builder -->
          <div class="right-panel-card">
            <div class="card-top-title" style="margin-bottom: 4px;">
              <div class="card-top-title-left">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                <h4>Link Builder</h4>
              </div>
            </div>
            <p style="font-size: 12px; color: var(--tx-muted); margin: 6px 0 14px;">Pronto para gerar links de afiliado</p>

            <button class="btn-primary" style="width: 100%; justify-content: center;" onclick="abrirModalLink()">
              Abrir Link Builder ↗
            </button>
            <p style="text-align: center; margin-top: 10px;">
              <a href="#" onclick="abrirModalComoFunciona()" style="font-size: 12px; color: var(--tx-muted); text-decoration: none;">ⓘ Como funciona?</a>
            </p>
          </div>

          <!-- Links Recentes -->
          <div class="right-panel-card">
            <div class="card-top-title">
              <div class="card-top-title-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                <h4>Links Recentes</h4>
              </div>
              <a href="#" onclick="switchView('links')">Ver todos</a>
            </div>

            <div class="recent-links-list" id="recentLinksListWrap">
              <div class="empty-placeholder">Nenhum link recente postado.</div>
            </div>
          </div>

        </div>

      </div>

    </div>

    <!-- ── TAB 2: PRODUTOS / OFERTAS ── -->
    <div id="view-produtos" class="content-body view-tab-content">
      <div class="dash-card">
        <div class="card-top-title">
          <div class="card-top-title-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
            <h3>Produtos Postados</h3>
          </div>
          <button class="btn-dark" onclick="carregarProdutos()">🔄 Atualizar</button>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 16px;">Histórico de todas as ofertas capturadas e publicadas automaticamente no Telegram.</p>

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

    <!-- ── TAB 3: LISTAS / CATEGORIAS ── -->
    <div id="view-listas" class="content-body view-tab-content">
      <div class="dash-card">
        <div class="card-top-title">
          <div class="card-top-title-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line></svg>
            <h3>Categorias do Canal (Nichos)</h3>
          </div>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 16px;">
          Selecione os nichos de produtos que você deseja enviar no canal do Telegram.
          <strong>Nada marcado = busca promoções de todas as categorias.</strong>
        </p>

        <div class="nichos-grid" id="nichosGrid">Carregando categorias...</div>

        <div style="display: flex; gap: 12px; margin-top: 20px; align-items: center;">
          <button class="btn-primary" onclick="salvarNichos()">💾 Salvar Categorias</button>
          <button class="btn-dark" onclick="limparNichos()">Limpar (Pegar tudo)</button>
          <span style="font-size: 12.5px; color: var(--tx-muted);" id="nichosCountLabel"></span>
        </div>
      </div>
    </div>

    <!-- ── TAB 4: LINKS ── -->
    <div id="view-links" class="content-body view-tab-content">
      <div class="dash-card">
        <div class="card-top-title">
          <div class="card-top-title-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
            <h3>Gerenciador de Links de Afiliado</h3>
          </div>
          <button class="btn-primary" onclick="abrirModalLink()">+ Novo Link Rápido</button>
        </div>

        <div class="recent-links-list" id="allLinksListWrap" style="margin-top: 16px;">
          <div class="empty-placeholder">Nenhum link gerado ainda.</div>
        </div>
      </div>
    </div>

    <!-- ── TAB 5: PLATAFORMAS ── -->
    <div id="view-plataformas" class="content-body view-tab-content">
      <div class="dash-card" style="margin-bottom: 20px;">
        <div class="card-top-title">
          <div class="card-top-title-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"></rect><rect x="2" y="14" width="20" height="8" rx="2"></rect></svg>
            <h3>Central de Testes de Plataformas</h3>
          </div>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 16px;">Execute testes pontuais e valide suas credenciais em cada marketplace suportado.</p>

        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="btn-dark" onclick="execAcao('instalar-navegador')" id="btnInstalarNav">⬇️ Instalar Navegador Playwright</button>
          <button class="btn-dark" onclick="execAcao('ml-login')">🔑 Fazer Login ML</button>
          <button class="btn-dark" onclick="execAcao('testar-ml')">🧪 Testar Mercado Livre</button>
          <button class="btn-dark" onclick="execAcao('testar-amazon')">🧪 Testar Amazon</button>
          <button class="btn-dark" onclick="execAcao('testar-shopee')">🧪 Testar Shopee</button>
          <button class="btn-primary" onclick="execAcao('ciclo')">⚡ Executar 1 Ciclo Completo</button>
        </div>
      </div>

      <div class="dash-card">
        <h4 style="margin-bottom: 10px;">Terminal de Ação</h4>
        <div class="terminal-body" id="logAcaoTerminal" style="height: 240px; background: #060b17; border-radius: 8px; border: 1px solid var(--border-color);">Aguardando comando...</div>
      </div>
    </div>

    <!-- ── TAB 6: CONFIGURAÇÕES ── -->
    <div id="view-config" class="content-body view-tab-content">
      <div class="dash-card">
        <div class="card-top-title">
          <div class="card-top-title-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            <h3>Configuração Geral (.env)</h3>
          </div>
          <button class="btn-primary" onclick="salvarConfig()">💾 Salvar Configurações</button>
        </div>
        <p style="font-size: 13px; color: var(--tx-muted); margin-bottom: 20px;">Preencha suas chaves e tokens de afiliados para integração automatizada.</p>

        <div id="camposFormWrap" class="config-grid">Carregando campos...</div>

        <div style="display: flex; gap: 12px; margin-top: 24px; align-items: center; border-top: 1px solid var(--border-color); padding-top: 18px;">
          <button class="btn-primary" onclick="salvarConfig()">💾 Salvar Tudo</button>
          <button class="btn-dark" onclick="detectarIds()">🔎 Detectar IDs do Telegram</button>
        </div>

        <div id="idsDetectionBox" style="margin-top: 16px; display: none;"></div>
      </div>
    </div>

    <!-- ── TAB 7: LOGS ── -->
    <div id="view-logs" class="content-body view-tab-content">
      <div class="logs-terminal-container">
        <!-- Bot Live Log -->
        <div class="terminal-box">
          <div class="terminal-header">
            <span>● Log ao Vivo do Bot</span>
            <button class="btn-dark" style="padding: 4px 8px; font-size: 11px;" onclick="limparTerminal('logBotBody')">Limpar</button>
          </div>
          <div class="terminal-body" id="logBotBody">O bot está pronto. Inicie pelo painel para acompanhar os logs em tempo real.</div>
        </div>

        <!-- Action / Setup Log -->
        <div class="terminal-box">
          <div class="terminal-header">
            <span>● Log de Ações e Testes</span>
            <button class="btn-dark" style="padding: 4px 8px; font-size: 11px;" onclick="limparTerminal('logAcaoBody')">Limpar</button>
          </div>
          <div class="terminal-body" id="logAcaoBody">Nenhuma ação executada recentemente.</div>
        </div>
      </div>
    </div>

    <!-- ── TAB 8: SUPORTE ── -->
    <div id="view-suporte" class="content-body view-tab-content">
      <div class="dash-card">
        <div class="card-top-title">
          <div class="card-top-title-left">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>
            <h3>Central de Suporte e Ajuda</h3>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 14px; margin-top: 16px;">
          <div style="background: var(--bg-subcard); padding: 16px; border-radius: 8px; border: 1px solid var(--border-color);">
            <h4 style="color: #fff; margin-bottom: 6px;">Como obter o Token do Bot?</h4>
            <p style="font-size: 13px; color: var(--tx-muted);">Abra o Telegram, pesquise por <code>@BotFather</code>, envie o comando <code>/newbot</code> e siga as instruções para obter seu Token da API.</p>
          </div>

          <div style="background: var(--bg-subcard); padding: 16px; border-radius: 8px; border: 1px solid var(--border-color);">
            <h4 style="color: #fff; margin-bottom: 6px;">Como descobrir os IDs do Canal e Dono?</h4>
            <p style="font-size: 13px; color: var(--tx-muted);">Após salvar o token do bot, adicione o bot como Administrador do canal. Envie uma mensagem no canal e no privado do bot, depois use o botão "Detectar IDs" nas Configurações.</p>
          </div>

          <div style="background: var(--bg-subcard); padding: 16px; border-radius: 8px; border: 1px solid var(--border-color);">
            <h4 style="color: #fff; margin-bottom: 6px;">Como manter a sessão do Mercado Livre ativa?</h4>
            <p style="font-size: 13px; color: var(--tx-muted);">Utilize o botão "Login no Mercado Livre" para abrir a janela do navegador Chromium local, faça seu login normalmente e pronto! A sessão fica salva de forma persistente.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Global Bottom Footer ── -->
    <footer class="global-footer">
      <div class="footer-left">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#00e676" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
        Conectado à VPS - Sistema estável e seguro
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
          <input type="text" id="modalOutputUrl" readonly style="font-family: var(--font-mono); font-size: 12.5px; background: #070d1e;">
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
      <h3>🛡️ Detalhes da Sessão do Mercado Livre</h3>
      <button class="btn-modal-close" onclick="fecharModalSessao()">&times;</button>
    </div>
    <div class="modal-body">
      <div id="modalSessaoConteudo" style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
        Carregando informações da sessão...
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn-dark" onclick="fecharModalSessao()">Fechar</button>
      <button class="btn-primary" onclick="execAcao('ml-login')">Refazer Login</button>
    </div>
  </div>
</div>

<!-- ── MODAL 3: COMO FUNCIONA ── -->
<div class="modal-overlay" id="modalComoFunciona">
  <div class="modal-container">
    <div class="modal-header">
      <h3>💡 Como Funciona o Link Builder & Bot</h3>
      <button class="btn-modal-close" onclick="fecharModalComoFunciona()">&times;</button>
    </div>
    <div class="modal-body" style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
      <p style="margin-bottom: 12px;">O sistema funciona através de 3 etapas automatizadas:</p>
      <ol style="padding-left: 20px; display: flex; flex-direction: column; gap: 8px;">
        <li><strong>Busca de Promoções:</strong> O bot varre os nichos configurados buscando itens com desconto real.</li>
        <li><strong>Geração do Link de Afiliado:</strong> O motor transforma as URLs com sua tag/etiqueta oficial.</li>
        <li><strong>Postagem no Telegram:</strong> A oferta formatada com imagem, título, preço e link é postada no seu canal.</li>
      </ol>
    </div>
    <div class="modal-footer">
      <button class="btn-primary" onclick="fecharModalComoFunciona()">Entendi</button>
    </div>
  </div>
</div>

<!-- Toast Container -->
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
  if (viewName === 'listas') carregarNichos();
  if (viewName === 'config') carregarConfig();
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

  // Grid lines
  ctx.strokeStyle = '#142244';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#64748b';
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

  // Area gradient
  const grad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
  grad.addColorStop(0, 'rgba(0, 102, 255, 0.35)');
  grad.addColorStop(1, 'rgba(0, 102, 255, 0.0)');

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

  // Stroke line
  ctx.beginPath();
  ctx.strokeStyle = '#38bdf8';
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

  // Dots & X Labels
  pts.forEach(p => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#0066ff';
    ctx.stroke();

    ctx.fillStyle = '#64748b';
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
  ctx.strokeStyle = '#142244';
  ctx.lineWidth = 1;
  ctx.fillStyle = '#64748b';
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
    grad.addColorStop(0, '#00e676');
    grad.addColorStop(1, '#00b894');

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
    if (sideTitle) sideTitle.textContent = on ? 'Bot Ativo' : 'Bot Desligado';
    if (sideSub) sideSub.textContent = on ? 'Rodando normalmente' : 'Clique para iniciar';

    const btnNav = $("#btnInstalarNav");
    if (btnNav) {
      btnNav.textContent = statusAtual.navegador ? '✓ Navegador Instalado' : '⬇️ Instalar Navegador Playwright';
    }

    if (statusAtual.plataformas && statusAtual.plataformas.mercadolivre) {
      const ml = statusAtual.plataformas.mercadolivre;
      const desc = $("#mlDesc");
      if (desc) desc.textContent = ml.status;
      const badge = $("#mlBadge");
      if (badge) {
        badge.className = ml.conectado ? 'badge-connected' : 'badge-pending';
        badge.innerHTML = `<span class="dot"></span>${ml.conectado ? 'Conectado' : 'Pendente'}`;
      }
      const dot = $("#panelMlStatusDot");
      const text = $("#panelMlStatusText");
      if (dot) dot.innerHTML = `<span class="sys-dot"></span>${ml.conectado ? 'Sessão ativa' : 'Sessão pendente'}`;
      if (text) text.textContent = ml.conectado ? 'Você está autenticado no Mercado Livre.' : 'Faça login para ativar a automação.';
    }

    if (statusAtual.plataformas && statusAtual.plataformas.amazon) {
      const amz = statusAtual.plataformas.amazon;
      const badgeAmz = $("#badgeAmz");
      const subAmz = $("#subAmz");
      if (badgeAmz) {
        badgeAmz.className = amz.conectado ? 'badge-connected' : 'badge-pending';
        badgeAmz.innerHTML = `<span class="dot"></span>${amz.conectado ? 'Conectado' : 'Pendente'}`;
      }
      if (subAmz) subAmz.textContent = amz.status;
    }

    if (statusAtual.plataformas && statusAtual.plataformas.shopee) {
      const shp = statusAtual.plataformas.shopee;
      const badgeShp = $("#badgeShp");
      const subShp = $("#subShp");
      if (badgeShp) {
        badgeShp.className = shp.conectado ? 'badge-connected' : 'badge-pending';
        badgeShp.innerHTML = `<span class="dot"></span>${shp.conectado ? 'Conectado' : 'Pendente'}`;
      }
      if (subShp) subShp.textContent = shp.status;
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

    // Charts
    renderLineChart('chartLinks', d.grafico_dias_labels, d.grafico_dias_valores);
    renderBarChart('chartConversao', d.grafico_conversao_valores);

    // Top platforms
    const topWrap = $("#topPlataformasWrap");
    if (topWrap) {
      if (d.top_plataformas && d.top_plataformas.length) {
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
        topWrap.innerHTML = `<div class="empty-placeholder">Nenhum clique registrado ainda.</div>`;
      }
    }

    // Recent Activities
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

    // Recent Links
    const linkWrap = $("#recentLinksListWrap");
    const allLinkWrap = $("#allLinksListWrap");
    if (d.links_recentes && d.links_recentes.length) {
      const html = d.links_recentes.map(l => `
        <div class="recent-link-item">
          <div class="recent-link-left">
            <span class="sys-dot" style="width: 6px; height: 6px;"></span>
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
        <td style="color:#00e676; font-weight:700;">${p.preco ? 'R$ ' + Number(p.preco).toFixed(2).replace('.', ',') : '—'}</td>
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
  box.innerHTML = 'Verificando diretório e cookies de sessão...';
  try {
    const r = await (await fetch('/api/verificar-sessao', { method: 'POST' })).json();
    box.innerHTML = `
      <div style="background:var(--bg-subcard); padding:14px; border-radius:8px; border:1px solid var(--border-color);">
        <p><strong>Status da Sessão:</strong> ${r.sessao_ml ? '<span style="color:var(--success)">✓ Ativa e Persistente</span>' : '<span style="color:var(--warning)">Pendente</span>'}</p>
        <p><strong>Arquivos de Sessão no Perfil:</strong> ${r.arquivos} arquivos</p>
        <p style="font-size:11px; color:var(--tx-dim); margin-top:8px; word-break:break-all;"><strong>Caminho:</strong> ${r.caminho}</p>
      </div>
    `;
  } catch (e) {
    box.innerHTML = '<span style="color:var(--danger)">Erro ao verificar status da sessão.</span>';
  }
}

async function verificarSessao() {
  abrirModalSessao();
}

async function limparSessao() {
  if (!confirm('Deseja realmente limpar a sessão persistente do Mercado Livre? Será necessário fazer login novamente.')) return;
  try {
    const r = await (await fetch('/api/limpar-sessao', { method: 'POST' })).json();
    toast(r.msg || 'Sessão limpa.', 'success');
    atualizarStatus();
  } catch (e) {
    toast('Erro ao limpar sessão.', 'error');
  }
}

function abrirModalComoFunciona() {
  $("#modalComoFunciona").classList.add('show');
}
function fecharModalComoFunciona() {
  $("#modalComoFunciona").classList.remove('show');
}

function abrirTelaML() {
  execAcao('ml-login');
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

// Initial boot
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
