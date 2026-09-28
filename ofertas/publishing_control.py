"""Sistema global de controle de postagem, agendamento, intervalos e pausas.

Garante o controle unificado de:
- Intervalo mínimo entre postagens consecutivas
- Pausa automática após blocos de N postagens
- Limite máximo de postagens por período (ex: 20 posts a cada 24h)
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
from typing import Tuple

# Lê a configuração por atributo, e não por `from .config import config`.
# O salvar_yaml_secao() recria o objeto global de config, então quem segura a
# referência antiga passa a usar valores defasados: no painel, salvar o intervalo
# na tela não mudava o intervalo usado de fato no cálculo da cadência.
from . import config as _config_mod
from .config import DATA_DIR

log = logging.getLogger("ofertas.publishing")

# O bot roda em outro processo (o painel o inicia com subprocess.Popen), então
# o controlador do painel e o do bot são objetos diferentes. Com o estado só na
# memória, o card "Status da Cadência" do painel mostrava sempre zero e o
# "Zerar contadores" não afetava o bot. O arquivo abaixo é o estado comum.
ARQ_ESTADO = DATA_DIR / "cadencia.json"


class PublishingController:
    """Gerencia intervalos entre posts, pausas automáticas entre blocos e limites de envio."""

    def __init__(self, persistir: bool = False):
        # Só o singleton persiste. As instâncias criadas direto (usadas nos
        # testes) ficam em memória, senão um ctrl.reset() de teste apagaria o
        # estado real do bot em disco.
        self._persistir = persistir
        self._lock = threading.Lock()
        self.ultimo_post_ts: float = 0.0
        self.posts_bloco_atual: int = 0
        self.inicio_pausa_ts: float = 0.0
        self.posts_periodo: list[float] = []
        # True quando o arquivo existe mas não deu para lê-lo. Nesse estado
        # o histórico é desconhecido, e é justamente aí que nasce a rajada.
        self.cadencia_ilegivel: bool = False

    def _carregar(self) -> None:
        if not self._persistir:
            return
        self.cadencia_ilegivel = False
        try:
            with open(ARQ_ESTADO, encoding="utf-8") as f:
                d = json.load(f)
        except FileNotFoundError:
            # Primeira execução: ainda não existe histórico, e não postar é
            # justamente o certo. Não é estado ilegível.
            return
        except (OSError, ValueError) as e:
            # O arquivo está lá, mas não foi possível lê-lo. Antes isto caía
            # num `return` mudo e o controlador seguia com o que tinha em
            # memória. Num processo recém-subido isso é tudo zerado, e o passo
            # 5 de `pode_publicar` (o que exige intervalo entre posts) é
            # pulado justamente porque `ultimo_post_ts` é 0.0. Resultado
            # observado: 11 registros em posts_periodo em 19 segundos, com
            # intervalo_entre_posts_segundos = 300. Aqui estado desconhecido
            # vira "não publica", e aparece no painel.
            log.warning("[CADENCIA] Não consegui ler %s (%s). Publicação "
                        "travada até o arquivo voltar a ser legível.",
                        ARQ_ESTADO.name, e)
            self._zera()
            self.cadencia_ilegivel = True
            return
        try:
            self.ultimo_post_ts = float(d.get("ultimo_post_ts", 0.0) or 0.0)
            self.posts_bloco_atual = int(d.get("posts_bloco_atual", 0) or 0)
            self.inicio_pausa_ts = float(d.get("inicio_pausa_ts", 0.0) or 0.0)
            self.posts_periodo = [float(t) for t in (d.get("posts_periodo") or [])]
        except (TypeError, ValueError):
            # Arquivo de outra versão/corrompido: melhor começar limpo do que
            # deixar a publicação travada por um valor ilegível.
            log.warning("[CADENCIA] %s tem valores que não são número. "
                        "Publicação travada até o arquivo voltar a ser legível.",
                        ARQ_ESTADO.name)
            self._zera()
            self.cadencia_ilegivel = True

    def _zera(self) -> None:
        self.ultimo_post_ts = 0.0
        self.posts_bloco_atual = 0
        self.inicio_pausa_ts = 0.0
        self.posts_periodo = []

    def _salvar(self) -> None:
        if not self._persistir:
            return
        dados = {
            "ultimo_post_ts": self.ultimo_post_ts,
            "posts_bloco_atual": self.posts_bloco_atual,
            "inicio_pausa_ts": self.inicio_pausa_ts,
            "posts_periodo": self.posts_periodo,
        }
        # O temporário leva o PID de propósito. O painel e o bot são dois
        # processos que reescrevem o mesmo arquivo: com um nome único para o
        # temporário, um nunca apaga o arquivo pela metade do outro, e quem lê
        # nunca pega JSON truncado. Antes era um nome só, e a disputa existia.
        tmp = ARQ_ESTADO.with_name(f"{ARQ_ESTADO.stem}.{os.getpid()}.tmp")
        try:
            # Grava em temporário e troca: o outro processo nunca lê um
            # arquivo pela metade.
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dados, f)
            os.replace(tmp, ARQ_ESTADO)
        except OSError as e:
            log.debug("Não consegui salvar a cadência: %s", e)
            tmp.unlink(missing_ok=True)

    def pode_publicar(self, agora_ts: float | None = None,
                      somente_leitura: bool = False) -> Tuple[bool, str, float]:
        """Verifica se uma nova publicação pode ser feita no momento.

        Retorna (pode_postar: bool, motivo_espera: str, segundos_restantes: float).

        `somente_leitura=True` responde a mesma pergunta sem gravar nada. O
        painel usa esse modo no card de status: agora que o estado é
        compartilhado em arquivo, um GET que só consultasse a cadência também
        poderia iniciar a pausa de bloco no estado do bot — ou seja, um GET
        mudando o estado de quem posta.
        """
        agora = agora_ts or dt.datetime.now().timestamp()
        config = _config_mod.config
        with self._lock:
            self._carregar()
            # Estado ilegível trava a publicação. Sem isso, `ultimo_post_ts`
            # fica 0.0, o passo 5 abaixo é pulado por inteiro (ele só roda
            # `if self.ultimo_post_ts > 0`) e o ciclo pode postar em rajada.
            if self.cadencia_ilegivel:
                return False, "cadencia_ilegivel (arquivo nao legivel)", 300.0
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
                    if not somente_leitura:
                        self.inicio_pausa_ts = 0.0
                        self.posts_bloco_atual = 0
                        self._salvar()

            # 4. Verifica se atingiu a quantidade de posts antes da pausa
            if config.posts_antes_pausa > 0 and self.posts_bloco_atual >= config.posts_antes_pausa:
                if not somente_leitura:
                    self.inicio_pausa_ts = agora
                    self._salvar()
                return False, f"iniciando_pausa_de_bloco (apos {config.posts_antes_pausa} posts)", float(config.tempo_pausa_segundos)

            # 5. Verifica Intervalo Mínimo entre Posts Consecutivos
            if self.ultimo_post_ts > 0:
                decorrido_post = agora - self.ultimo_post_ts
                if decorrido_post < config.intervalo_entre_posts_segundos:
                    restante = config.intervalo_entre_posts_segundos - decorrido_post
                    return False, f"aguardando_intervalo_minimo ({int(restante)}s restantes)", restante

            if not somente_leitura:
                self._salvar()
            return True, "pronto", 0.0

    def registrar_publicacao(self, agora_ts: float | None = None) -> None:
        """Registra que um post acabou de ser enviado com sucesso."""
        agora = agora_ts or dt.datetime.now().timestamp()
        config = _config_mod.config
        with self._lock:
            self._carregar()
            self.ultimo_post_ts = agora
            self.posts_bloco_atual += 1
            self.posts_periodo.append(agora)
            self._salvar()
            # Canário. `pode_publicar` recusa qualquer post dentro de
            # `intervalo_entre_posts_segundos`, então dois registros de
            # `posts_periodo` nunca deveriam ficar a menos de 60s um do outro.
            # Se ficarem, alguma coisa escreveu no arquivo sem passar por um
            # post de verdade — e foi assim que a cadência chegou a 126
            # registros fantasma contra 7 ofertas postadas. O stack sai junto
            # porque, sozinho, o número não diz quem escreveu.
            anterior = self.posts_periodo[-2] if len(self.posts_periodo) > 1 else 0.0
            if anterior and (agora - anterior) < 60:
                import traceback
                log.warning("[CADENCIA] Gap de %.1fs entre registros, mas o "
                            "intervalo minimo e de %ds. PID=%d. Chamado por:\n%s",
                            agora - anterior, config.intervalo_entre_posts_segundos,
                            os.getpid(), "".join(traceback.format_stack()[-9:-1]))
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
        config = _config_mod.config
        with self._lock:
            self._carregar()
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
                "cadencia_ilegivel": self.cadencia_ilegivel,
            }


    def reset(self) -> None:
        """Reseta contadores (usado em testes ou reinicialização manual)."""
        with self._lock:
            self._zera()
            self.cadencia_ilegivel = False
            self._salvar()


# Singleton: é o que o pipeline (bot) e o painel usam. Persiste em disco para
# que os dois processos enxerguem a mesma cadência.
publishing_controller = PublishingController(persistir=True)

