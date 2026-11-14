# Publicar o painel na VPS (com senha)

O painel escuta em `127.0.0.1:8481` e não deve ser exposto sem senha. Este
documento existe porque um quick tunnel do `trycloudflare.com` publicado sem
`PAINEL_SENHA` deixava o painel inteiro aberto: todo pedido do túnel chega de
`127.0.0.1`, e o painel tratava isso como acesso local.

A correção (`_ip_do_pedido`, em `ofertas/painel.py`) lê `CF-Connecting-IP` /
`X-Forwarded-For` / `X-Real-IP` quando quem conectou é o proxy local. Ainda
assim, **defina a senha**: é ela que protege o painel, não o túnel.

## 1. Conferir o serviço e a porta

```bash
systemctl list-units --type=service | grep -i -E 'oferta|painel|bot'
grep -nE '^(HOST|PORT)' /caminho/do/projeto/ofertas/painel.py
```

O padrão é `127.0.0.1:8481`. Use a porta real nos passos abaixo.

## 2. Atualizar o `painel.py` da VPS

Antes de sobrescrever, compare com o local — a VPS pode ter mudanças de
produção que não estão no repositório:

```bash
scp ubuntu@<vps>:/home/ubuntu/bot-local/ofertas/painel.py /tmp/painel_vps.py
diff -u ofertas/painel.py /tmp/painel_vps.py
```

Em 13/11/2026 os arquivos eram idênticos ao local, exceto pelas mudanças
pendentes de deploy. Se o `diff` mostrar outra coisa, faça backup e mescle
à mão:

```bash
cp ofertas/painel.py ofertas/painel.py.bak-$(date +%F)
python -m py_compile ofertas/painel.py
```

## 3. Definir a senha no `.env`

```bash
cd /caminho/do/projeto
grep -E '^PAINEL_(USUARIO|SENHA)=' .env    # não mostre a senha em log
```

Se estiver vazio, defina com o gerador do sistema (não invente senha curta):

```bash
SENHA=$(python -c 'import secrets; print(secrets.token_urlsafe(18))')
printf 'PAINEL_USUARIO=admin\nPAINEL_SENHA=%s\n' "$SENHA" >> .env
echo "Senha gerada: $SENHA"    # guarde no gerenciador de senhas
```

Alternativa sem editar arquivo: abrir o painel **na própria VPS** (ou por túnel
SSH) e criar a conta na tela de login. A conta criada pelo painel grava as
mesmas chaves no `.env`.

## 4. Reiniciar e conferir de fora

```bash
systemctl restart <serviço-do-painel>
```

Com o túnel no ar, a partir de outra máquina:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://SEU-HOST/api/status
```

- `401` → senha configurada e proteção ativa (esperado).
- `403` → sem senha; o painel recusa quem não é loopback (também seguro, mas
  você não conseguirá usar o painel pelo túnel).
- `200` → **pare**: a correção não foi aplicada ou o túnel não envia os
  cabeçalhos esperados.

`/` continua público de propósito (só serve o HTML; os dados vêm de `/api/`,
que é barrado).

## 5. Subir o túnel

```bash
cloudflared tunnel --url http://127.0.0.1:8481
```

Quick tunnels são efêmeros: a URL muda a cada execução e morre junto com o
processo. Para um endereço fixo, use um túnel nomeado no Cloudflare e, de
preferência, Cloudflare Access na frente.

## Se o painel já ficou exposto

O painel não registra acessos (`log_message` é silenciado), então não há log
para consultar. Trate como possível vazamento e rotacione o que ele expõe:

1. `TELEGRAM_BOT_TOKEN`: `/revoke` no @BotFather e atualizar o `.env`.
2. Credenciais de marketplace no `.env` (Amazon, Shopee, AliExpress, ML).
3. Conferir fontes do Telegram (aba Links) e a configuração.
4. Conferir se há links, configurações ou credenciais cadastrados que você não criou.
