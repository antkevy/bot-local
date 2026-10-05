"""Modelo da oferta e o que conta como "o mesmo tipo de produto".

Por que existe a parte de baixo deste arquivo
---------------------------------------------
O dedup por `uid` (plataforma + id) não pega o que o canal sente: três mochilas
de fabricantes diferentes são três uids, três "bolas de pet" de lojas
diferentes são três uids — e para quem lê o canal são a mesma oferta repetida.
Medido em produção (60 posts): zero uid repetido e nenhuma chave de título
repetida, e mesmo assim três mochilas, duas creatinas e duas bolas no mesmo dia.

Por isso a comparação é por PALAVRAS: dois títulos são o mesmo tipo quando
compartilham as palavras significativas, e não quando repetem o uid. As
palavras de ligação ("de", "com", "para"), os números e a propaganda
("premium", "original", "frete grátis") são descartados porque não dizem qual
é o produto.
"""
import re
import unicodedata
from dataclasses import dataclass

# Palavras que aparecem em quase todo título e, portanto, não identificam o
# produto: conectivos, unidades e adjetivos de marketing. "agua"/"prova"/
# "anti" entram por causa de "à prova d'água": sem elas, um kit de cabelo e uma
# câmera IP compartilham a mesma característica e o filtro tratava um como
# repetido do outro — o produto é outro, a propriedade é a mesma.
PALAVRAS_GENERICAS = frozenset({
    "para", "com", "sem", "por", "que", "nao", "mais", "voce", "seu", "sua",
    "novo", "nova", "tipo", "unidade", "unidades", "pacote", "pack", "kit",
    "pcs", "pc", "original", "premium", "qualidade", "melhor", "frete",
    "gratis", "oferta", "promocao", "vendas", "unico", "exclusivo",
    "agua", "prova", "anti",
})


def palavras_significativas(titulo: str) -> list[str]:
    """Palavras do título que dizem qual é o produto, na ordem em que aparecem."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", titulo or "")
        if not unicodedata.combining(c)
    )
    palavras = re.findall(r"[a-z]+", sem_acento.lower())
    return [p for p in palavras if len(p) >= 3 and p not in PALAVRAS_GENERICAS]


def tokens_conteudo(titulo: str) -> frozenset[str]:
    """Conjunto de palavras significativas — a "digital" do tipo de produto."""
    return frozenset(palavras_significativas(titulo))


def tipo_principal(titulo: str) -> str:
    """Primeira palavra significativa: o tipo do produto ("mochila", "bola")."""
    palavras = palavras_significativas(titulo)
    return palavras[0] if palavras else ""


@dataclass
class Oferta:
    plataforma: str            # "mercadolivre" | "shopee" | "amazon"
    id_produto: str
    titulo: str
    url_afiliado: str = ""          # vazio até o link de afiliado ser gerado
    url_produto: str = ""
    preco: float | None = None
    preco_original: float | None = None
    desconto_pct: int | None = None
    imagem: str | bytes | None = None   # URL da plataforma OU bytes da foto da mensagem
    extra: str | None = None   # avaliação, frete grátis, "no Pix" etc.
    titulo_original: str = ""
    tipo: str = "produto"      # "produto" | "cupom" | "promocao" | "frete_gratis" | "informativo" | "irrelevante"
    cupom: str | None = None
    beneficio_cupom: str | None = None
    avaliacao: float | None = None    # Nota em escala de 0.0 a 5.0
    vendas: int | None = None         # Quantidade de vendas/pedidos
    comissao: float | None = None     # Dado técnico interno — NUNCA enviado ao template
    comissao_pct: float | None = None # Dado técnico interno — NUNCA enviado ao template

    @property
    def preco_antigo(self) -> float | None:
        return self.preco_original

    @property
    def uid(self) -> str:
        return f"{self.plataforma}:{self.id_produto}"

    @property
    def desconto(self) -> int | None:
        if self.desconto_pct:
            return self.desconto_pct
        if self.preco and self.preco_original and self.preco_original > self.preco:
            return round(100 * (1 - self.preco / self.preco_original))
        return None

