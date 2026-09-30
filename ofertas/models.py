from dataclasses import dataclass


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

