import re

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
    return s


def parse_preco_br(texto: str | None) -> float | None:
    """Converte "R$ 1.234,56" / "1.234" / "56,43" em float."""
    t = re.sub(r"[^\d,.]", "", texto or "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or (t.count(".") == 1 and len(t.rsplit(".", 1)[1]) == 3):
        t = t.replace(".", "")  # ponto de milhar, sem centavos
    try:
        return float(t)
    except ValueError:
        return None


def extrair_urls(texto: str | None) -> list[str]:
    return re.findall(r"https?://\S+", texto or "")


# Valor monetario em formato brasileiro, sempre com o "R$" na frente.
#
# O "R$" e obrigatorio de proposito: e o que separa um preco de um numero
# qualquer no texto ("2 pedidos", "32 polegadas", "4.7 estrelas"). Sem o
# simbolo, qualquer numero da mensagem vira preco, e a oferta sai com um valor
# que ninguem escreveu.
#
# As tres alternativas cobrem o que os canais escrevem de verdade:
#   R$ 1.358        -> ponto de milhar
#   R$ 1.358,90     -> milhar com centavos
#   R$1358,90       -> sem milhar, com centavos
_RE_DINHEIRO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")

# Os dois marcadores abaixo sao procurados no texto que vem ANTES do valor, e
# por isso terminam em `$`: casam com a palavra que encosta no "R$".
#
# "de" so conta como preco antigo quando abre a linha. No meio do texto, "de"
# quase nunca e preco antigo: "acima de R$ 49", "a partir de R$ 10" e "ate
# R$ 99" sao limite de cupom, e tratar isso como preco antigo fabrica um
# desconto que ninguem escreveu.
_RE_DE_ANTES = re.compile(r"(?:^|\n)[^\w\n]{0,6}de\s*$", re.IGNORECASE)

# "por R$", "so R$", "por apenas R$", "somente R$": nao ha ambiguidade, e o
# preco atual.
_RE_POR_ANTES = re.compile(r"\b(?:por|so|somente|apenas)\s*$", re.IGNORECASE)

# "acima de R$ 49", "a partir de R$ 10", "limite de R$ 50", "menor que R$ 5":
# sao condicoes do cupom, nao o preco do produto. Sem esta lista, o "acima de
# R$ 49" de um post de cupom entrava como se a oferta custasse 49.
_RE_LIMITE_ANTES = re.compile(
    r"\b(?:acima|a[ ]partir|partindo|at[ée]|menos|menor|limite"
    r"|m[áa]ximo|maximo|m[íi]nimo|minimo)\s*(?:(?:de|que)\s*)?$",
    re.IGNORECASE,
)

# Quantos caracteres antes do valor sao lidos para procurar os marcadores.
# Precisa caber o maior deles: "somente a partir de " tem 20.
JANELA_MARCADOR = 24


def extrair_precos_texto(texto: str | None) -> tuple[float | None, float | None]:
    """Extrai `(preco, preco_antigo)` do texto de uma mensagem de canal.

    Existe porque o preco da oferta nem sempre vem da API. Short link da Shopee
    aponta para produto fora do catalogo de ofertas da Open API, e a API
    responde lista vazia: o preco esta escrito na mensagem e e a unica fonte
    que sobra.

    Devolve `(None, None)` sempre que nao da para saber com seguranca qual e o
    preco. Chutar aqui e pior do que nao ter preco, porque um preco errado
    publica e um preco ausente apenas descarta a oferta.

        "R$ 1.358"                  -> (1358.0, None)
        "De R$ 1.999\\nPor R$ 1.358" -> (1358.0, 1999.0)
        "Frete gr\u00e1tis em 2 pedidos" -> (None, None)
    """
    if not texto:
        return (None, None)

    achados: list[tuple[float, str]] = []
    for m in _RE_DINHEIRO.finditer(texto):
        valor = parse_preco_br(m.group(1))
        if valor is None or valor <= 0:
            continue
        antes = texto[:m.start()].rstrip()[-JANELA_MARCADOR:]
        if _RE_LIMITE_ANTES.search(antes):
            # "acima de R$ 49" e limite de cupom. Nao e preco, entao nem entra
            # na lista -- se entrasse, um post de cupom viraria oferta de R$ 49.
            continue
        achados.append((valor, antes))
    if not achados:
        return (None, None)

    antigo: float | None = None
    atual: float | None = None
    neutro: list[float] = []
    for valor, antes in achados:
        if _RE_POR_ANTES.search(antes):
            if atual is None:
                atual = valor
        elif _RE_DE_ANTES.search(antes):
            if antigo is None:
                antigo = valor
        else:
            neutro.append(valor)

    if atual is not None:
        preco = atual
    elif len(neutro) == 1:
        preco = neutro[0]
    elif not neutro and antigo is not None:
        preco = antigo
    else:
        # Zero ou mais de um preco sem marcacao: nao existe base para escolher
        # um deles, e escolher o primeiro seria inventar preco.
        return (None, None)

    if antigo == preco:
        antigo = None
    return (preco, antigo)
