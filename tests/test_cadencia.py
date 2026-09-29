"""Testes da cadência de publicação.

O foco é o defeito observado em produção: `posts_periodo` chegou a 11
registros em 19 segundos, com `intervalo_entre_posts_segundos = 300`, e o
contador travou a publicação com "limite_periodo_atingido (126/20)" sem
que existisse um único post correspondente.

A causa está em `_carregar`: quando o arquivo existe mas não pode ser lido,
o `return` mudo deixava o controlador com o estado em memória. Num processo
recém-subido esse estado é `ultimo_post_ts = 0.0` e `posts_periodo = []`, e
o passo 5 de `pode_publicar` — o único que exige intervalo entre posts — é
pulado por inteiro porque só roda `if self.ultimo_post_ts > 0`.
"""
import json
import logging
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ofertas.publishing_control as pc
from ofertas.publishing_control import PublishingController


def cfg(**over):
    base = dict(intervalo_entre_posts_segundos=300,
                posts_antes_pausa=20,
                tempo_pausa_segundos=600,
                max_posts_periodo=80,
                periodo_horas=24)
    base.update(over)
    return SimpleNamespace(**base)


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pasta, ignore_errors=True)
        self._arq_original = pc.ARQ_ESTADO
        pc.ARQ_ESTADO = self.pasta / "cadencia.json"
        self.addCleanup(self._restaura_arq)
        # Os testes provocam arquivo ilegível de propósito, e o aviso é o
        # comportamento certo. Sem isto ele cai no handler "last resort" e
        # enche a saída do unittest com o mesmo erro dezenas de vezes.
        lg = logging.getLogger("ofertas.publishing")
        self._prop_original = lg.propagate
        lg.propagate = False
        lg.addHandler(logging.NullHandler())
        self.addCleanup(self._restaura_log, lg)

    def _restaura_log(self, lg):
        lg.propagate = self._prop_original

    def _restaura_arq(self):
        pc.ARQ_ESTADO = self._arq_original

    def _escrever(self, conteudo: str):
        pc.ARQ_ESTADO.write_text(conteudo, encoding="utf-8")

    def _ler(self) -> dict:
        return json.loads(pc.ARQ_ESTADO.read_text(encoding="utf-8"))

    def _cfg(self, **over):
        return mock.patch.object(pc._config_mod, "config", cfg(**over))

    def _ctrl(self):
        return PublishingController(persistir=True)


# ---------------------------------------------------------------- ilegível
class TestArquivoIlegivel(Base):
    """Estado desconhecido não pode virar 'pode publicar tudo'."""

    def test_json_corrompido_trava_a_publicacao(self):
        self._escrever("{isto nao e json")
        c = self._ctrl()
        with self._cfg():
            pode, motivo, _ = c.pode_publicar()
        self.assertFalse(pode, "com o arquivo ilegivel nada pode ser publicado")
        self.assertIn("cadencia_ilegivel", motivo)

    def test_arquivo_inexistente_nao_e_ilegivel(self):
        """Primeira execução: não existe histórico, e não postar é o certo.
        Aqui o arquivo simplesmente não está lá, o que é diferente de estar
        lá e não conseguir ler."""
        c = self._ctrl()
        with self._cfg():
            pode, motivo, _ = c.pode_publicar()
        self.assertTrue(pode, "sem arquivo nenhum o primeiro post tem de passar")
        self.assertEqual(motivo, "pronto")
        self.assertFalse(c.cadencia_ilegivel)

    def test_valores_de_tipo_errado_travam(self):
        self._escrever(json.dumps({"posts_periodo": "abc", "ultimo_post_ts": "xyz"}))
        c = self._ctrl()
        with self._cfg():
            pode, motivo, _ = c.pode_publicar()
        self.assertFalse(pode)
        self.assertIn("cadencia_ilegivel", motivo)

    def test_ilegivel_avisa_no_log(self):
        self._escrever("nao presta")
        c = self._ctrl()
        with self._cfg(), self.assertLogs("ofertas.publishing", "WARNING") as cm:
            c.pode_publicar()
        self.assertTrue(any("CADENCIA" in m for m in cm.output),
                        "silêncio aqui é o que escondeu o defeito")

    def test_status_mostra_o_problema(self):
        """O painel mostra o card de cadência a cada 5s: é ele que precisa
        dizer que algo está errado."""
        self._escrever("lixo")
        c = self._ctrl()
        with self._cfg():
            st = c.obter_status()
        self.assertTrue(st["cadencia_ilegivel"])

    def test_reset_destrava(self):
        self._escrever("lixo")
        c = self._ctrl()
        with self._cfg():
            c.pode_publicar()
        # A trava precisa estar acesa de verdade, senão o teste passa sem
        # exercitar o caminho: o reset é pedido por quem já viu o problema.
        self.assertTrue(c.cadencia_ilegivel)
        c.reset()
        self.assertFalse(c.cadencia_ilegivel, "reset tem que limpar a trava")
        with self._cfg():
            pode, _, _ = c.pode_publicar()
        self.assertTrue(pode)

    def test_arquivo_que_some_preserva_o_intervalo_ja_conhecido(self):
        """O arquivo sumiu, mas este processo sabe quando postou pela última
        vez. Esquecer disso é justamente o que abre a porta para a rajada: um
        `ultimo_post_ts` perdido vira 0.0, e o passo 5 de `pode_publicar` — o
        único que exige intervalo entre posts — é pulado por inteiro."""
        c = self._ctrl()
        t = 1_000_000.0
        with self._cfg():
            self.assertTrue(c.pode_publicar(agora_ts=t)[0])
            c.registrar_publicacao(agora_ts=t)
            pc.ARQ_ESTADO.unlink()
            pode, motivo, _ = c.pode_publicar(agora_ts=t + 60)
        self.assertFalse(pode, "o intervalo já conhecido não pode ser esquecido")
        self.assertIn("aguardando_intervalo_minimo", motivo)


# ------------------------------------------------------- o sintoma real
class TestSemRajada(Base):
    """11 registros em 19s, com intervalo de 300s. Não pode repetir."""

    def test_ciclo_nao_acumula_registros_em_rajada(self):
        self._escrever("{corrompido de proposito")
        c = self._ctrl()
        with self._cfg():
            for _ in range(20):
                pode, _, _ = c.pode_publicar()
                if pode:
                    c.registrar_publicacao()
        self.assertEqual(c.posts_periodo, [],
                         "nenhum registro pode ser criado com a cadência ilegível")

    def test_arquivo_quebrado_no_meio_nao_deixa_o_ciclo_disparar(self):
        """Ciclo começa com o arquivo bom, o arquivo estraga, e o ciclo
        continua. O que importa é que ele para."""
        c = self._ctrl()
        t = 1_000_000.0
        with self._cfg():
            self.assertTrue(c.pode_publicar(agora_ts=t)[0])
            c.registrar_publicacao(agora_ts=t)
            self._escrever("quebrou aqui")
            # mesmo passes plenty tempo: a rajada veio justamente do
            # intervalo sendo ignorado
            for i in range(10):
                pode, _, _ = c.pode_publicar(agora_ts=t + 3600 * (i + 1))
                if pode:
                    c.registrar_publicacao(agora_ts=t + 3600 * (i + 1))
        self.assertLessEqual(len(c.posts_periodo), 1)


# -------------------------------------------------- temporário por processo
class TestTemporarioPorProcesso(Base):
    """O painel e o bot são dois processos reescrevendo o mesmo arquivo."""

    def test_temporario_tem_o_pid(self):
        """Com um nome único, um processo nunca apaga o arquivo pela metade
        do outro — era o que produzia JSON truncado na leitura."""
        c = self._ctrl()
        nomes = []
        real = os.replace

        def espiao(src, dst):
            nomes.append(Path(src).name)
            return real(src, dst)

        with mock.patch("os.replace", espiao):
            c._salvar()
        self.assertTrue(nomes, "a gravação tem que passar por os.replace")
        self.assertIn(str(os.getpid()), nomes[0])

    def test_dois_pids_nao_compartilham_o_temporario(self):
        vistos = []
        real = os.replace
        for pid in (111, 222):
            def espiao(src, dst, _p=pid):
                vistos.append((_p, Path(src).name))
                return real(src, dst)
            with mock.patch("os.replace", espiao), \
                 mock.patch("os.getpid", return_value=pid):
                self._ctrl()._salvar()
        nomes = [n for _, n in vistos]
        self.assertEqual(len(set(nomes)), 2, f"temporário colidiu: {nomes}")

    def test_arquivo_sob_descreve_na_troca(self):
        """Nada de restos: o que fica no diretório é só o cadencia.json."""
        c = self._ctrl()
        c.ultimo_post_ts = 5.0
        c._salvar()
        resto = [p.name for p in self.pasta.iterdir() if p.name != "cadencia.json"]
        self.assertEqual(resto, [], f"sobrou lixo no data/: {resto}")


# ----------------------------------------------------------------- canário
class TestCanario(Base):
    """O arquivo não deve poder mentir sobre o intervalo."""

    def test_avisa_quando_o_gap_viola_o_intervalo(self):
        c = PublishingController(persistir=False)
        t = 1_000_000.0
        with self._cfg():
            c.registrar_publicacao(agora_ts=t)
            with self.assertLogs("ofertas.publishing", "WARNING") as cm:
                c.registrar_publicacao(agora_ts=t + 0.1)
        self.assertTrue(any("CADENCIA" in m for m in cm.output))

    def test_nao_avisa_em_gap_normal(self):
        c = PublishingController(persistir=False)
        t = 1_000_000.0
        with self._cfg():
            c.registrar_publicacao(agora_ts=t)
            with self.assertLogs("ofertas.publishing", "INFO") as cm:
                c.registrar_publicacao(agora_ts=t + 300)
        self.assertFalse(any("CADENCIA" in m for m in cm.output))

    def test_o_stack_vai_junto(self):
        """So o número não diz quem escreveu; sem o stack o canário não
        serve para nada."""
        c = PublishingController(persistir=False)
        t = 1_000_000.0
        with self._cfg():
            c.registrar_publicacao(agora_ts=t)
            with self.assertLogs("ofertas.publishing", "WARNING") as cm:
                c.registrar_publicacao(agora_ts=t)
        texto = "\n".join(cm.output)
        self.assertIn("registrar_publicacao", texto)


# ------------------------------------------------- 0 desliga o limite
class TestZeroDesliga(Base):
    """`0` é o valor do projeto antigo (commit a314bc8, sem secao
    `publicacao`) e precisa desligar cada limite de velocidade, um por um.

    Sem este contrato, voltar a frequencia antiga seria so um numero no
    yaml: ninguem provaria que o controlador parou de barrar. E o silencio
    do canario tambem depende dele - sem `intervalo_entre_posts_segundos > 0`
    um ciclo que posta 3 ofertas seguidas dispararia o aviso de rajada a
    cada post, e o log viraria ruido.
    """

    ZERADO = dict(intervalo_entre_posts_segundos=0, posts_antes_pausa=0,
                  tempo_pausa_segundos=0, max_posts_periodo=0)

    def _rajada(self, over):
        """Tenta 40 ofertas em 20s e devolve quantas passaram."""
        c = self._ctrl()
        t = 1_000_000.0
        postadas = 0
        with self._cfg(**self.ZERADO, **over):
            for i in range(40):
                if not c.pode_publicar(agora_ts=t + i * 0.5)[0]:
                    break
                c.registrar_publicacao(agora_ts=t + i * 0.5)
                postadas += 1
        return postadas

    def test_intervalo_minimo_zero_nao_bloqueia(self):
        # So o intervalo minimo desligado: os outros limites ainda valem,
        # entao o bloqueio vem do periodo (40 > 80? nao -> do bloco/periodo).
        # Aqui o que importa e que o motivo NAO e o intervalo.
        c = self._ctrl()
        t = 1_000_000.0
        with self._cfg(**self.ZERADO):
            c.registrar_publicacao(agora_ts=t)
            pode, motivo, _ = c.pode_publicar(agora_ts=t + 1)
        self.assertTrue(pode, f"intervalo 0 barrou: {motivo}")

    def test_bloco_20_ainda_pausaria_se_o_projeto_antigo_nao_tivesse_zerado(self):
        """Controle: com `posts_antes_pausa = 20` a rajada PARA em 20. E o que
        faz este teste valer como prova - se um dia `0` deixar de desligar, a
        rajada vai a 40 e a diferenca aparece."""
        c = self._ctrl()
        t = 1_000_000.0
        postadas = 0
        with self._cfg(intervalo_entre_posts_segundos=0, posts_antes_pausa=20,
                       tempo_pausa_segundos=600, max_posts_periodo=0):
            for i in range(40):
                if not c.pode_publicar(agora_ts=t + i * 0.5)[0]:
                    break
                c.registrar_publicacao(agora_ts=t + i * 0.5)
                postadas += 1
        self.assertEqual(20, postadas)

    def test_limite_de_periodo_20_para_em_20(self):
        """Controle: com o periodo ligado a rajada PARA em 20. E o que faz o
        teste de baixo valer como prova - se `0` deixar de desligar, os dois
        testes dao o mesmo numero e a diferenca desaparece."""
        c = self._ctrl()
        t = 1_000_000.0
        postadas = 0
        with self._cfg(**dict(self.ZERADO, max_posts_periodo=20)):
            for i in range(40):
                pode, motivo, _ = c.pode_publicar(agora_ts=t + i * 0.5)
                if not pode:
                    self.assertIn("limite_periodo_atingido", motivo)
                    break
                c.registrar_publicacao(agora_ts=t + i * 0.5)
                postadas += 1
        self.assertEqual(20, postadas)

    def test_limite_de_periodo_zero_nao_limita(self):
        """Tudo zerado, as 40 passam - 20 acima do teto do controle."""
        self.assertEqual(40, self._rajada({}))

    def test_todos_os_zerados_deixam_passar_rajada_inteira(self):
        self.assertEqual(40, self._rajada({}))

    def test_zerado_ainda_persiste_os_registros(self):
        """Desligar o limite nao pode desligar a contagem: o painel ainda
        mostra o que foi publicado no dia."""
        c = self._ctrl()
        with self._cfg(**self.ZERADO):
            for i in range(3):
                c.registrar_publicacao(agora_ts=1_000_000.0 + i * 0.5)
        self.assertEqual(3, len(self._ler()["posts_periodo"]))

    def test_canario_cala_sem_intervalo_configurado(self):
        c = PublishingController(persistir=False)
        t = 1_000_000.0
        with self._cfg(**self.ZERADO):
            c.registrar_publicacao(agora_ts=t)
            with self.assertLogs("ofertas.publishing", "INFO") as cm:
                c.registrar_publicacao(agora_ts=t + 0.1)
        self.assertFalse(any("CADENCIA" in m for m in cm.output))

    def test_canario_continua_ativo_quando_ha_intervalo(self):
        """O silencio acima nao pode ter virado silencio universal."""
        c = PublishingController(persistir=False)
        t = 1_000_000.0
        with self._cfg():
            c.registrar_publicacao(agora_ts=t)
            with self.assertLogs("ofertas.publishing", "WARNING") as cm:
                c.registrar_publicacao(agora_ts=t + 0.1)
        self.assertTrue(any("CADENCIA" in m for m in cm.output))


# ----------------------------------------------------- comportamento antigo
class TestCadenciaNormal(Base):
    """O que já funcionava não pode ter quebrado."""

    def test_sequencia_normal_respeita_o_intervalo(self):
        c = self._ctrl()
        t = 1_000_000.0
        with self._cfg():
            self.assertTrue(c.pode_publicar(agora_ts=t)[0])
            c.registrar_publicacao(agora_ts=t)
            pode, motivo, _ = c.pode_publicar(agora_ts=t + 60)
        self.assertFalse(pode)
        self.assertIn("aguardando_intervalo_minimo", motivo)

    def test_primeiro_post_nao_e_bloqueado_pelo_intervalo(self):
        """ultimo_post_ts == 0.0 significa 'nunca postou', e o primeiro post
        tem de passar. É o que a guarda nova não pode estragar."""
        c = self._ctrl()
        with self._cfg():
            pode, _, _ = c.pode_publicar(agora_ts=1_000_000.0)
        self.assertTrue(pode)

    def test_limite_de_periodo_continua_valendo(self):
        c = self._ctrl()
        t = 1_000_000.0
        with self._cfg(max_posts_periodo=3):
            for i in range(3):
                self.assertTrue(c.pode_publicar(agora_ts=t + i * 400)[0])
                c.registrar_publicacao(agora_ts=t + i * 400)
            pode, motivo, _ = c.pode_publicar(agora_ts=t + 3 * 400)
        self.assertFalse(pode)
        self.assertIn("limite_periodo_atingido", motivo)

    def test_persiste_entre_dois_controladores(self):
        """O painel e o bot são processos diferentes: o estado tem de
        sobreviver na troca."""
        a = self._ctrl()
        t = 1_000_000.0
        with self._cfg():
            a.pode_publicar(agora_ts=t)
            a.registrar_publicacao(agora_ts=t)
        b = self._ctrl()
        with self._cfg():
            pode, motivo, _ = b.pode_publicar(agora_ts=t + 1)
        self.assertFalse(pode, "o segundo processo precisa ver o post do primeiro")
        self.assertIn("aguardando_intervalo_minimo", motivo)


if __name__ == "__main__":
    unittest.main()
