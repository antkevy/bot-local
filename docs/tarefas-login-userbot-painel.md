# Login do userbot Telegram no painel + auto-ativação

Aprovado pelo usuário (design bounded, TDD).

## Passos (com status)

- [x] 1. Ler o harness de testes do painel e o restante do `painel_html.py`
- [x] 2. RED: testes das primitivas de login (`telegram_userbot`) com Telethon fake
- [x] 3. GREEN: implementar `enviar_codigo` / `confirmar_codigo` / status file / idempotência
- [x] 4. RED: testes das rotas do painel (`/api/userbot/*`)
- [x] 5. GREEN: rotas no `painel.py`
- [x] 6. RED: teste do auto-ativação (`_job_userbot`)
- [x] 7. GREEN: job no `bot_interativo.py`
- [x] 8. UI: cartão + JS no `painel_html.py` (local + remendo in loco **construído e validado**)
  - 9/9 testes estruturais verdes contra o `painel_html_vps_patched.py` (bot_externo preservado; +161 linhas exatas)
- [x] 9. Suíte completa local (3 subprocessos) + QA
  - guard-rail `test_isolamento_dados.py` verde (30 suítes em subprocesso, 283s, `data/` intacto)
  - `test_captura_userbot`/`test_scraper_fontes` re-verdes após reset de `_monitor_iniciado`/fake `last_name`
- [x] 10. Deploy: backup + scp dos 4 arquivos + SHA byte-idênticos + `py_compile` OK
- [x] 11. Reiniciar painel + bot (bot aborta 1 ciclo, aprovado) — ambos `active`, painel sem erro
- [x] 12. Verificar: página serve cartão/forms, `/api/userbot/*` respondem guard de login, job `userbot_ativacao` roda a cada 60s no log; **login do usuário pendente**

## Restrições da produção

- `.env`, `data/`, guarda systemd e `painel_html.py` da VPS preservados.
- `painel_html.py` da VPS difere do local → **remendar in loco**, nunca sobrescrever.
- 27/28 arquivos `.py` da VPS já são idênticos ao local (SHA-256 verificado).
