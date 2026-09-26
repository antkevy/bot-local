# 🛍️ Guia de Integração — AliExpress Open Platform (Afiliados)

Este guia orienta o passo a passo para conectar a **API Oficial de Afiliados do AliExpress** ao **Ofertas Pro** (`bot-local`).

---

## 1. Como obter as Credenciais no AliExpress

### Passo 1: Cadastro no AliExpress Portals (Programa de Afiliados)
1. Acesse o portal oficial de afiliados do AliExpress: [portals.aliexpress.com](https://portals.aliexpress.com/).
2. Faça login com a sua conta do AliExpress e complete o cadastro no programa de afiliados.
3. No painel de afiliados, acesse **Account Settings > Tracking ID** para criar ou visualizar seu **Tracking ID** (exemplo: `seunome_br` ou `canal_ofertas`).

### Passo 2: Acesso ao AliExpress Open Platform
1. Acesse o portal de desenvolvedores: [openservice.aliexpress.com](https://openservice.aliexpress.com/) (ou através do menu **Tools > API** no Portals).
2. Cadastre-se como desenvolvedor (Individual ou Enterprise).
3. Vá em **Console > App Management > Create App**.
4. Crie uma aplicação do tipo **Affiliate API** (ou **Affiliate / Tools**).
5. Após a criação da aplicação, você terá acesso a:
   - **App Key** (chave pública da aplicação)
   - **App Secret** (segredo de assinatura)

---

## 2. Onde configurar no Ofertas Pro

Você pode preencher as credenciais de duas formas:

### Opção A: Pelo Painel Gráfico (Recomendado)
1. Abra o painel no seu navegador: `http://127.0.0.1:8481`
2. Vá até a aba **Configurações** (ou clique em **Configurar** no card do AliExpress na aba **Plataformas**).
3. Preencha os campos da seção **AliExpress**:
   - **App Key**: Cole sua App Key.
   - **App Secret**: Cole seu App Secret.
   - **Tracking ID**: Digite seu Tracking ID (opcional se sua conta já tiver um padrão).
4. Clique em **Salvar credenciais**.

### Opção B: Pelo arquivo `.env`
Edite o arquivo `.env` na raiz do projeto:
```env
ALIEXPRESS_APP_KEY=sua_app_key_aqui
ALIEXPRESS_APP_SECRET=seu_app_secret_aqui
ALIEXPRESS_TRACKING_ID=seu_tracking_id_aqui
```

---

## 3. Como testar a Conexão

### Teste 1: Pelo Painel Gráfico
1. Na aba **Plataformas**, localize o bloco **AliExpress**.
2. Clique no botão **Testar conexão**.
3. O painel executará uma chamada à API oficial e exibirá o log no terminal de ações.
4. Quando configurado corretamente, o selo mudará para **Conectado** 🟢.

### Teste 2: Pela Linha de Comando (CLI)
No terminal do projeto, execute:
```bash
uv run python -m ofertas testar aliexpress
```
O comando fará a autenticação, teste de assinatura e listará as ofertas encontradas.

---

## 4. Como testar a Busca de Ofertas e Categorias

- O bot busca produtos automaticamente no AliExpress de acordo com os nichos selecionados em **Categorias do canal** no painel ou configurados em `config.yaml`.
- Para testar uma busca completa do pipeline:
```bash
uv run python -m ofertas ciclo
```

---

## 5. Como testar a Geração e Conversão de Links

### Pelo Painel (Link Builder)
1. Clique no botão **Gerar link** no topo do painel.
2. Cole qualquer link de produto do AliExpress (ex: `https://pt.aliexpress.com/item/1005001234567890.html` ou link encurtado `https://a.aliexpress.com/...`).
3. Clique em **Gerar link**. O sistema consultará a API e devolverá o link de afiliado oficial.

### Pelo Telegram
1. Envie um link de produto do AliExpress para o bot no chat privado.
2. O bot converterá e enviará uma prévia com o botão **🛒 Pegar oferta** e **✅ Postar no canal**.

### Pela CLI
```bash
uv run python -m ofertas converter "https://pt.aliexpress.com/item/1005001234567890.html"
```
