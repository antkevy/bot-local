# Mercado Livre: scraping, links de afiliado e fila de pendências

Este documento registra como o Mercado Livre funciona no bot e o que foi
verificado na VPS em 13/11/2026.

## Como o ML funciona aqui

1. **Coleta**: `buscar_ofertas()` lê `https://www.mercadolivre.com.br/ofertas`
   (e o plano B `/mais-vendidos`) em um **Chromium headless autenticado por
   cookie**.
2. **Link de afiliado**: `createLink` (API interna do Linkbuilder), autenticado
   pelo **cookie** configurado em `ML_COOKIE` (ou salvo via `/setcookie`).
3. **Autenticação única**: não existe mais login pelo navegador nem perfil
   persistente em `data/ml_profile`. O cookie é injetado em um contexto
   temporário do Chromium para a coleta e usado no header da chamada `createLink`.
4. **Sem link não publica**: a oferta vai para `ofertas_pendentes_ml` e o admin
   é avisado (com cooldown de 1h).

## A coleta precisa do navegador autenticado

O ML passou a exigir verificação de conta para a página de ofertas:

| requisição | resultado |
|---|---|
| HTTP sem cookie | HTTP 200, mas URL final `/gz/account-verification`, 0 cards |
| HTTP com cookie (fingerprint do `requests`) | HTTP 200, mas URL final `/captcha/wall/web-risk-verification`, 0 cards |
| Chromium com cookies de `ML_COOKIE` injetados | 197 cards parseados em `/mais-vendidos` (validado em 13/11/2026) |

Por isso `buscar_ofertas()` tenta primeiro `_buscar_via_navegador()` e só cai
para HTTP se não houver cookie configurado ou se o navegador falhar. A coleta
usa `_NAVEGADOR_LOCK` para serializar aberturas e evitar disputas de sessão.

## Ritmo: janela rotativa e plano B

Varrer **todas** as páginas a cada ciclo derruba a sessão. Medido em 13/11/2026:
12 categorias × 2 páginas = 24 páginas em ~8 minutos (790 ofertas), e logo
depois `/ofertas` passou a responder `/captcha/wall/logged` — inclusive 2
minutos depois, para uma única página.

Por isso:

- `paginas_por_ciclo` (opcional em `fontes.mercadolivre`, padrão **6**) limita
  quantas páginas entram por ciclo, em janela rotativa. As 24 páginas são
  cobertas em 4 ciclos (~1h40 com intervalo de 25 min), com ~2 min de coleta.
- Se `/ofertas` cair em verificação/captcha, o ciclo usa
  `https://www.mercadolivre.com.br/mais-vendidos` (196 ofertas, sem
  categoria) e marca um cooldown de 1h para não insistir no captcha.
  `/mais-vendidos` não respeita os nichos — é plano B, não o caminho normal.
- Se o captcha aparece no meio da varredura, as ofertas já coletadas são
  aproveitadas em vez de descartadas.

As categorias vêm de `data/nichos.json` (seleção do painel), que **substitui**
`fontes.mercadolivre.categorias` do `config.yaml`. Com nichos selecionados, o
`config.yaml` pode dizer `categorias: {}` e ainda assim a coleta varrer as
categorias dos nichos.

**Sintoma de cookie vencido/inválido**:

```
[ML-AUTH] Cookie do Mercado Livre expirado/inválido: ...
[ML-AUTH] ❌ Falha ao autenticar no Mercado Livre pelo cookie. Bloqueando publicação.
```

Renove enviando `/setcookie <cookie>` no privado do bot, ou colando o
`ML_COOKIE` no painel. O mesmo cookie vale para coleta e para geração de links.

## O que não é produto

`e_url_de_produto()` recusa (e `converter()` levanta erro antes de chamar a
API): `/social/`, `/sec/`, `/scfeed`, `/gz/`, `/afiliados`, `/jms/`,
`/cupons`, `/perfil/`, qualquer caminho com `/lists`, `/ofertas` exato e hosts
`click1.`/`click.`.

`meli.la` continua aceito na checagem porque `converter()` o expande antes. Se
o destino da expansão for perfil, o `converter` já recusa.

## Fila de pendências

- Só entra URL de produto que falhou por autenticação de verdade.
- `processar_ofertas_pendentes_async()` remove pendências cuja URL não é de
  produto; ela roda após um `/setcookie` válido.
- Uma pendência legítima continua na fila até conseguir link (ou até a oferta
  já ter sido postada no intervalo de `nao_repetir_dias`).

## Como verificar rápido na VPS

```bash
systemctl stop bot-local-bot          # libera recursos do navegador
cd ~/bot-local
.venv/bin/python -c "from ofertas.sources import mercadolivre as m; \
print(len(m.buscar_ofertas()))"
systemctl start bot-local-bot
```

Espere algo entre 50 e 400 ofertas por ciclo (6 páginas × ~54 cards, com
`categorias` vindas dos nichos). Zero com cookie válido e sem captcha significa
que a página mudou de layout — confira `_parse_pagina()` e os seletores
`div.poly-card` / `a.poly-component__title`.

Se a saída for 0 e o journal mostrar `verificação/captcha`, `/ofertas` está
bloqueado: o ciclo seguinte cai sozinho em `/mais-vendidos`, e o bloqueio
costuma sair sozinho. Se persistir por horas, renove o `ML_COOKIE`.
