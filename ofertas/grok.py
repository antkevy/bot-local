"""Serviço de integração com xAI/Grok para inteligência, normalização e classificação de ofertas.

Funciona como camada de edição/análise inteligente:
- Otimiza títulos extensos removendo poluição de SEO e redundâncias.
- Preserva rigorosamente marcas, modelos, quantidades (kits), capacidades e especificações.
- Detecta e extrai códigos de cupom e benefícios.
- Classifica postagens (produto, cupom, promocao, frete_gratis, informativo, irrelevante).
- Possui cache por hash (SHA-256) para economia de requisições.
- Possui fallback resiliente que nunca derruba o pipeline do bot.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import requests

from .config import DATA_DIR, config

if TYPE_CHECKING:
    from .models import Oferta

log = logging.getLogger("ofertas.grok")

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
CACHE_FILE = DATA_DIR / "grok_cache.json"

TIPOS_VALIDOS = {
    "produto",
    "cupom",
    "promocao",
    "frete_gratis",
    "informativo",
    "irrelevante",
}


@dataclass
class GrokResult:
    tipo: str
    titulo_otimizado: str | None
    tem_cupom: bool
    cupom: str | None
    beneficio_cupom: str | None
    confianca: float
    usou_cache: bool = False
    usou_fallback: bool = False
    raw_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SYSTEM_PROMPT = """Você é um especialista em e-commerce e editor de catálogo para um canal de ofertas no Telegram.
Sua função é analisar o texto/título recebido e retornar EXCLUSIVAMENTE um JSON estruturado.

REGRAS DE CLASSIFICAÇÃO:
- "produto": Anúncio de um produto específico (pode ou não ter cupom junto).
- "cupom": Postagem focada exclusivamente em divulgar um cupom de desconto (sem um produto específico).
- "promocao": Evento de liquidação/promoção geral sem produto único.
- "frete_gratis": Aviso de benefício de frete grátis.
- "informativo": Comunicado ou informação sobre uma loja.
- "irrelevante": Conversas, spam ou texto sem valor de compra/oferta.

REGRAS DE OTIMIZAÇÃO DE TÍTULO (titulo_otimizado):
- Torne o título limpo, claro, atraente e direto para leitura rápida no Telegram.
- PRESERVAR OBRIGATORIAMENTE:
  * Tipo do item (ex: Smart TV, Fone Bluetooth, Tênis, Fritadeira).
  * Marca (ex: Samsung, JBL, Xiaomi, Philips) SE estiver presente no original.
  * Modelo exato (ex: Galaxy A55 5G, Tune 520BT, Airfryer Essential).
  * Quantidade / Kit (ex: "Kit 10", "Pack 3", "2 Unidades").
  * Capacidade / Tamanho / Voltagem (ex: "50\"", "128GB", "4.1L", "Tam. 39-43", "Bivolt", "220V").
  * Características técnicas essenciais (ex: "4K UHD", "ANC", "Sem Fio").
- REMOVER RIGOROSAMENTE:
  * Palavras promocionais genéricas ("oferta imperdível", "promoção", "melhor preço", "compre agora", "barato", "imperdível").
  * Excesso de SEO, sinônimos repetidos e palavras duplicadas ("fone ouvido headset headphone sem fio wireless").
  * Termos de ranqueamento que poluem a leitura.
- NUNCA INVENTAR:
  * Jamais invente marcas, modelos, quantidades ou atributos que não estejam no texto de entrada.
- Se for apenas um cupom sem produto específico, `titulo_otimizado` deve ser null.
- Se o título original já for curto, direto e conciso, mantenha-o com ajustes mínimos.

REGRAS DE CUPOM:
- `tem_cupom`: true se houver código de cupom no texto, false caso contrário.
- `cupom`: Código do cupom em letras maiúsculas (ex: "OFERTA20", "VALE10"), ou null se não houver.
- `beneficio_cupom`: Descrição breve do benefício (ex: "R$ 20 OFF", "10% OFF acima de R$ 100"), ou null.

REGRAS DE CONFIANÇA:
- `confianca`: Número de 0.0 a 1.0 indicando a certeza da análise.

FORMATO DE RESPOSTA OBRIGATÓRIO (JSON estrito):
{
  "tipo": "produto" | "cupom" | "promocao" | "frete_gratis" | "informativo" | "irrelevante",
  "titulo_otimizado": "string limpa" | null,
  "tem_cupom": true | false,
  "cupom": "CODIGO" | null,
  "beneficio_cupom": "detalhe" | null,
  "confianca": 0.95
}"""


class GrokService:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._carregar_cache()

    @property
    def api_key(self) -> str:
        return config.xai_api_key

    @property
    def api_url(self) -> str:
        if self.api_key.startswith("gsk_"):
            return "https://api.groq.com/openai/v1/chat/completions"
        return "https://api.x.ai/v1/chat/completions"

    @property
    def ativo(self) -> bool:
        return bool(config.grok_enabled and self.api_key)

    @property
    def modelo(self) -> str:
        if config.grok_model and config.grok_model != "grok-2-latest":
            return config.grok_model
        if self.api_key.startswith("gsk_"):
            return "openai/gpt-oss-120b"
        return "grok-2-latest"

    @property
    def timeout(self) -> float:
        return config.grok_timeout or 10.0

    @property
    def confidence_threshold(self) -> float:
        return config.grok_confidence_threshold or 0.75

    @property
    def max_input_length(self) -> int:
        return config.grok_max_input_length or 1000

    def _carregar_cache(self) -> None:
        if not CACHE_FILE.exists():
            return
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, dict):
                    self._cache = dados
        except Exception as e:
            log.warning("Não foi possível carregar cache do Grok: %s", e)

    def _salvar_cache(self) -> None:
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                # Mantém no máximo 2000 entradas para controle de tamanho
                if len(self._cache) > 2000:
                    chaves = list(self._cache.keys())[-1500:]
                    self._cache = {k: self._cache[k] for k in chaves}
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("Não foi possível persistir cache do Grok: %s", e)

    def _gerar_hash(self, texto: str) -> str:
        normalizado = re.sub(r"\s+", " ", texto.strip().lower())
        return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()

    def _limpar_texto_entrada(self, texto: str) -> str:
        limpo = re.sub(r"[ \t]+", " ", texto).strip()
        if len(limpo) > self.max_input_length:
            limpo = limpo[: self.max_input_length]
        return limpo

    def _fallback_resultado(
        self,
        texto_original: str,
        titulo_base: str = "",
        motivo: str = "",
    ) -> GrokResult:
        log.info("[GROK] API indisponível ou fallback ativado (%s) — mantendo dados originais", motivo)
        # Detecção heurística básica de cupom para fallback emergencial
        tem_cupom = False
        codigo_cupom = None
        m = re.search(r"(?:cupom|código|code)[:\s]+([A-Z0-9_-]{4,25})\b", texto_original, re.IGNORECASE)
        if m:
            tem_cupom = True
            codigo_cupom = m.group(1).upper()

        titulo = titulo_base or (texto_original if len(texto_original) < 150 else texto_original[:150])
        return GrokResult(
            tipo="produto",
            titulo_otimizado=titulo if titulo else None,
            tem_cupom=tem_cupom,
            cupom=codigo_cupom,
            beneficio_cupom=None,
            confianca=1.0,
            usou_cache=False,
            usou_fallback=True,
        )

    def testar_conexao(self) -> dict[str, Any]:
        if not self.api_key:
            return {"ok": False, "erro": "XAI_API_KEY não está configurada no .env."}
        try:
            resultado = self.analisar_texto("Smart TV 50 Polegadas 4K UHD LED WiFi Bluetooth HDR Alexa Promoção Imperdível", usar_cache=False)
            return {
                "ok": True,
                "msg": f"Conexão com xAI/Grok ({self.modelo}) realizada com sucesso!",
                "exemplo": resultado.to_dict(),
            }
        except Exception as e:
            return {"ok": False, "erro": f"Falha na comunicação com xAI: {e}"}

    def analisar_texto(
        self,
        texto: str,
        titulo_base: str = "",
        usar_cache: bool = True,
    ) -> GrokResult:
        """Analisa um texto/título com Grok retornando dados normalizados e estruturados."""
        if not texto and not titulo_base:
            return self._fallback_resultado("", "", "entrada vazia")

        texto_entrada = self._limpar_texto_entrada(texto or titulo_base)
        chave_hash = self._gerar_hash(texto_entrada)

        if usar_cache and chave_hash in self._cache:
            cache_hit = self._cache[chave_hash]
            log.info("[GROK] Cache hit para hash %s", chave_hash[:8])
            return GrokResult(
                tipo=cache_hit.get("tipo", "produto"),
                titulo_otimizado=cache_hit.get("titulo_otimizado"),
                tem_cupom=bool(cache_hit.get("tem_cupom", False)),
                cupom=cache_hit.get("cupom"),
                beneficio_cupom=cache_hit.get("beneficio_cupom"),
                confianca=float(cache_hit.get("confianca", 0.9)),
                usou_cache=True,
                usou_fallback=False,
            )

        if not self.ativo:
            return self._fallback_resultado(texto_entrada, titulo_base, "GROK_ENABLED=False ou sem XAI_API_KEY")

        log.info("[GROK] Analisando texto com modelo %s (%d caracteres)", self.modelo, len(texto_entrada))

        payload = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analise a seguinte oferta/mensagem:\n\n{texto_entrada}"},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            return self._fallback_resultado(texto_entrada, titulo_base, "timeout na API xAI")
        except Exception as e:
            return self._fallback_resultado(texto_entrada, titulo_base, f"erro de rede xAI: {e}")

        if resp.status_code != 200:
            return self._fallback_resultado(
                texto_entrada,
                titulo_base,
                f"HTTP {resp.status_code}: {resp.text[:120]}",
            )

        try:
            resp_json = resp.json()
            content = resp_json["choices"][0]["message"]["content"]
            dados = json.loads(content)
        except Exception as e:
            return self._fallback_resultado(texto_entrada, titulo_base, f"erro ao decodificar JSON: {e}")

        # Validação e saneamento dos campos
        tipo = str(dados.get("tipo", "produto")).strip().lower()
        if tipo not in TIPOS_VALIDOS:
            tipo = "produto"

        titulo_otimizado = dados.get("titulo_otimizado")
        if titulo_otimizado is not None:
            titulo_otimizado = str(titulo_otimizado).strip()
            if not titulo_otimizado:
                titulo_otimizado = None

        tem_cupom = bool(dados.get("tem_cupom", False))
        cupom = dados.get("cupom")
        if cupom:
            cupom = str(cupom).strip().upper()
            if not cupom:
                cupom = None
                tem_cupom = False
        else:
            tem_cupom = False
            cupom = None

        beneficio_cupom = dados.get("beneficio_cupom")
        if beneficio_cupom:
            beneficio_cupom = str(beneficio_cupom).strip() or None

        try:
            confianca = float(dados.get("confianca", 0.9))
        except (ValueError, TypeError):
            confianca = 0.9

        # Se a confiança for menor que o limite aceitável, aplica fallback seguro
        if confianca < self.confidence_threshold:
            log.warning(
                "[GROK] Classificação com baixa confiança (%.2f < %.2f) — acionando fallback",
                confianca,
                self.confidence_threshold,
            )
            return self._fallback_resultado(texto_entrada, titulo_base, "baixa confiança")

        resultado = GrokResult(
            tipo=tipo,
            titulo_otimizado=titulo_otimizado,
            tem_cupom=tem_cupom,
            cupom=cupom,
            beneficio_cupom=beneficio_cupom,
            confianca=confianca,
            usou_cache=False,
            usou_fallback=False,
            raw_response=dados,
        )

        # Salva no cache
        self._cache[chave_hash] = {
            "tipo": resultado.tipo,
            "titulo_otimizado": resultado.titulo_otimizado,
            "tem_cupom": resultado.tem_cupom,
            "cupom": resultado.cupom,
            "beneficio_cupom": resultado.beneficio_cupom,
            "confianca": resultado.confianca,
        }
        self._salvar_cache()

        log.info(
            "[GROK] Processado: tipo=%s, cupom=%s, conf=%.2f, titulo='%s'",
            resultado.tipo,
            resultado.cupom,
            resultado.confianca,
            resultado.titulo_otimizado or "(vazio)",
        )
        return resultado

    def otimizar_oferta(self, oferta: Oferta, texto_contexto: str = "") -> Oferta:
        """Enriquece uma Oferta existente com títulos normalizados e cupons extraídos.
        NUNCA altera preços, links ou IDs confiáveis da fonte.
        """
        if not oferta.titulo_original:
            oferta.titulo_original = oferta.titulo

        texto_analise = texto_contexto.strip() if texto_contexto else oferta.titulo

        # Se o Grok não estiver ativo, garante que os campos padrão estejam definidos
        if not self.ativo:
            return oferta

        try:
            resultado = self.analisar_texto(texto_analise, titulo_base=oferta.titulo)
            oferta.tipo = resultado.tipo

            if resultado.titulo_otimizado:
                oferta.titulo = resultado.titulo_otimizado

            if resultado.tem_cupom and resultado.cupom:
                oferta.cupom = resultado.cupom
                if resultado.beneficio_cupom:
                    oferta.beneficio_cupom = resultado.beneficio_cupom
        except Exception as e:
            log.error("[GROK] Falha ao otimizar oferta '%s': %s", oferta.titulo[:40], e)

        return oferta


grok_service = GrokService()
