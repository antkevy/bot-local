"""Sistema global de controle de postagem, agendamento, intervalos e pausas.

Garante o controle unificado de:
- Intervalo mínimo entre postagens consecutivas
- Pausa automática após blocos de N postagens
- Limite máximo de postagens por período (ex: 20 posts a cada 24h)
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Tuple

from .config import config

log = logging.getLogger("ofertas.publishing")


class PublishingController:
    """Gerencia intervalos entre posts, pausas automáticas entre blocos e limites de envio."""

    def __init__(self):
        self._lock = threading.Lock()
        self.ultimo_post_ts: float = 0.0
        self.posts_bloco_atual: int = 0
        self.inicio_pausa_ts: float = 0.0
        self.posts_periodo: list[float] = []

    def pode_publicar(self, agora_ts: float | None = None) -> Tuple[bool, str, float]:
        """Verifica se uma nova publicação pode ser feita no momento.
        
        Retorna (pode_postar: bool, motivo_espera: str, segundos_restantes: float).
        """
        agora = agora_ts or dt.datetime.now().timestamp()
        with self._lock:
            # 1. Limpa timestamps do período fora da janela (ex: 24h)
            janela_segundos = max(1, config.periodo_horas) * 3600
            self.posts_periodo = [t for t in self.posts_periodo if agora - t < janela_segundos]

            # 2. Verifica Limite por Período
            if config.max_posts_periodo > 0 and len(self.posts_periodo) >= config.max_posts_periodo:
                mais_antigo = self.posts_periodo[0]
                restante = max(1.0, janela_segundos - (agora - mais_antigo))
                return False, f"limite_periodo_atingido ({len(self.posts_periodo)}/{config.max_posts_periodo} em {config.periodo_horas}h)", restante

            # 3. Verifica se está em período de pausa de bloco
            if self.inicio_pausa_ts > 0:
                decorrido_pausa = agora - self.inicio_pausa_ts
                if decorrido_pausa < config.tempo_pausa_segundos:
                    restante = config.tempo_pausa_segundos - decorrido_pausa
                    return False, f"pausa_de_bloco_ativa ({int(restante // 60)} min restantes)", restante
                else:
                    # Pausa concluída com sucesso
                    self.inicio_pausa_ts = 0.0
                    self.posts_bloco_atual = 0

            # 4. Verifica se atingiu a quantidade de posts antes da pausa
            if config.posts_antes_pausa > 0 and self.posts_bloco_atual >= config.posts_antes_pausa:
                self.inicio_pausa_ts = agora
                return False, f"iniciando_pausa_de_bloco (apos {config.posts_antes_pausa} posts)", float(config.tempo_pausa_segundos)

            # 5. Verifica Intervalo Mínimo entre Posts Consecutivos
            if self.ultimo_post_ts > 0:
                decorrido_post = agora - self.ultimo_post_ts
                if decorrido_post < config.intervalo_entre_posts_segundos:
                    restante = config.intervalo_entre_posts_segundos - decorrido_post
                    return False, f"aguardando_intervalo_minimo ({int(restante)}s restantes)", restante

            return True, "pronto", 0.0

    def registrar_publicacao(self, agora_ts: float | None = None) -> None:
        """Registra que um post acabou de ser enviado com sucesso."""
        agora = agora_ts or dt.datetime.now().timestamp()
        with self._lock:
            self.ultimo_post_ts = agora
            self.posts_bloco_atual += 1
            self.posts_periodo.append(agora)
            log.info(
                "[PUBLISH-CTRL] Post registrado. Bloco: %d/%d, Período: %d/%d",
                self.posts_bloco_atual,
                config.posts_antes_pausa,
                len(self.posts_periodo),
                config.max_posts_periodo,
            )

    def obter_status(self, agora_ts: float | None = None) -> dict:
        """Retorna o estado atual da cadência de publicação."""
        agora = agora_ts or dt.datetime.now().timestamp()
        with self._lock:
            janela = max(1, config.periodo_horas) * 3600
            posts_recentes = [t for t in self.posts_periodo if agora - t < janela]
            em_pausa = False
            pausa_ate = None
            if self.inicio_pausa_ts > 0:
                decorrido = agora - self.inicio_pausa_ts
                if decorrido < config.tempo_pausa_segundos:
                    em_pausa = True
                    pausa_ate = self.inicio_pausa_ts + config.tempo_pausa_segundos
            
            limite_atingido = config.max_posts_periodo > 0 and len(posts_recentes) >= config.max_posts_periodo
            
            return {
                "posts_no_bloco_atual": self.posts_bloco_atual,
                "posts_no_periodo_atual": len(posts_recentes),
                "ultimo_post_ts": self.ultimo_post_ts,
                "em_pausa": em_pausa,
                "pausa_ate": pausa_ate,
                "limite_atingido": limite_atingido,
            }


    def reset(self) -> None:
        """Reseta contadores (usado em testes ou reinicialização manual)."""
        with self._lock:
            self.ultimo_post_ts = 0.0
            self.posts_bloco_atual = 0
            self.inicio_pausa_ts = 0.0
            self.posts_periodo.clear()


publishing_controller = PublishingController()

