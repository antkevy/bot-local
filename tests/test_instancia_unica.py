"""Regressão da trava de instância única.

O sintoma que estes testes existem para impedir: o bot subindo em vários
lugares ao mesmo tempo (painel, terminal, segundo painel) e publicando a
mesma oferta mais de uma vez.

O caso que mais engana é o do Windows: depois que um processo morre,
`OpenProcess` e `GetProcessTimes` continuam respondendo por ele. Uma checagem
só de "o PID existe" acha que o bot derrubado ainda está de pé e trava o
processo novo contra um fantasma. Daí a importância de `GetExitCodeProcess`.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import instancia

# Python do próprio ambiente: os testes sobem subprocessos de verdade.
PYTHON = sys.executable
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestProcessoVivo(unittest.TestCase):
    """A pergunta 'esse PID ainda roda?' precisa responder certo nos dois sentidos."""

    def test_pid_inexistente(self):
        # PID alto e improvável; o Windows reservou esse intervalo para o SO.
        self.assertFalse(instancia.processo_vivo(999999))

    def test_pid_invalido_nao_levanta(self):
        for valor in (0, -1, "abc", None):
            with self.subTest(valor=valor):
                self.assertFalse(instancia.processo_vivo(valor))

    def test_processo_vivo_real(self):
        alvo = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(60)"])
        try:
            self.assertTrue(instancia.processo_vivo(alvo.pid))
        finally:
            alvo.kill()
            alvo.wait(timeout=15)

    def test_morre_de_verdade_apos_o_encerramento(self):
        """Regressão do Windows: PID morto continuava parecendo vivo.

        Foi o bug que fazia `aguardar_morte` estourar o tempo todo e o
        `adquirir` derrubar um bot que já não existia, batendo contra a trava
        de um processo fantasma.
        """
        alvo = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(60)"])
        alvo.kill()
        alvo.wait(timeout=15)
        self.assertFalse(
            instancia.processo_vivo(alvo.pid),
            "processo encerrado ainda é reportado como vivo",
        )

    def test_pid_reciclado_nao_confunde_com_a_trava(self):
        """Mesmo PID, outro processo: a trava antiga não é nossa.

        Sem comparar o horário de criação, um PID reciclado faria o novo
        processo derrubar um programa sem nenhuma relação com o bot.
        """
        self.assertFalse(
            instancia.processo_vivo(os.getpid(), 1.0),
            "PID recycled com outro horário de criação foi aceito como o mesmo processo",
        )

    def test_tempo_criacao_proprio_e_estavel(self):
        a = instancia.tempo_criacao(os.getpid())
        b = instancia.tempo_criacao(os.getpid())
        self.assertIsNotNone(a)
        self.assertAlmostEqual(a, b, delta=0.01)


class TestTravas(unittest.TestCase):
    """Grava e lê a trava num diretório temporário, sem tocar em data/."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "instancia"
        self._dir_original = instancia.DIR_INSTANCIA
        instancia.DIR_INSTANCIA = self.dir

    def tearDown(self):
        instancia.DIR_INSTANCIA = self._dir_original

    def test_trava_livre_e_assumida_e_devolvida(self):
        self.assertIsNone(instancia.titular_vivo("bot"))
        inst = instancia.adquirir("bot")
        self.assertIsNotNone(inst)
        self.assertEqual(inst.pid, os.getpid())

        st = instancia.status("bot")
        self.assertTrue(st["ocupado"])
        self.assertTrue(st["esta_e"])

        inst.liberar()
        self.assertFalse(instancia.caminho_trava("bot").exists())
        self.assertFalse(instancia.status("bot")["ocupado"])

    def test_lock_corrompida_nao_trava_o_bot(self):
        instancia.caminho_trava("bot").parent.mkdir(parents=True, exist_ok=True)
        instancia.caminho_trava("bot").write_text("{isto nao e json", encoding="utf-8")
        inst = instancia.adquirir("bot")
        self.assertIsNotNone(inst, "trava corrompida impediu o bot de subir")
        inst.liberar()

    def test_trava_de_json_nao_lista(self):
        instancia.caminho_trava("bot").parent.mkdir(parents=True, exist_ok=True)
        instancia.caminho_trava("bot").write_text("[1, 2, 3]", encoding="utf-8")
        inst = instancia.adquirir("bot")
        self.assertIsNotNone(inst, "trava com lista no lugar de objeto impediu o bot de subir")
        inst.liberar()

    def test_trava_de_processo_morto_e_ignorada(self):
        instancia._escrever(instancia.caminho_trava("bot"),
                            {"pid": 999999, "nascido_em": 1.0, "papel": "bot"})
        self.assertIsNone(instancia.titular_vivo("bot"))
        self.assertFalse(instancia.status("bot")["ocupado"])
        self.assertTrue(instancia.limpar_trava_oufa("bot"))
        self.assertFalse(instancia.caminho_trava("bot").exists())

    def test_limpar_trava_oufa_nao_apaga_trava_viva(self):
        inst = instancia.adquirir("bot")
        self.assertFalse(instancia.limpar_trava_oufa("bot"),
                         "limpar_trava_oufa apagou a trava de um processo vivo")
        self.assertTrue(instancia.caminho_trava("bot").exists())
        inst.liberar()

    def test_liberar_nao_apaga_trava_de_outro_processo(self):
        inst = instancia.adquirir("bot")
        # Simula outro processo assumindo a trava no meio da vida do nosso.
        instancia._escrever(instancia.caminho_trava("bot"),
                            {"pid": 999999, "nascido_em": 1.0, "papel": "bot"})
        inst.liberar()
        self.assertTrue(
            instancia.caminho_trava("bot").exists(),
            "liberar() apagou a trava que já era de outro processo",
        )

    def test_claim_orfao_nao_bloqueia(self):
        """Uma reivindicação abandonada por um processo morto não pode
        impedir o bot de subir para sempre."""
        instancia.caminho_reivindicao("bot").parent.mkdir(parents=True, exist_ok=True)
        claim = instancia.caminho_reivindicao("bot")
        claim.write_text("lixo", encoding="utf-8")
        velho = time.time() - 9999
        os.utime(claim, (velho, velho))
        inst = instancia.adquirir("bot")
        self.assertIsNotNone(inst, "claim órfão impediu o bot de subir")
        inst.liberar()

    def test_status_de_papel_livre(self):
        st = instancia.status("painel")
        self.assertFalse(st["ocupado"])
        self.assertIsNone(st["pid"])


class TestDerrubadaDeInstancia(unittest.TestCase):
    """O requisito: subir de novo em outro lugar desliga o que estava antes."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp()) / "instancia"
        self._dir_original = instancia.DIR_INSTANCIA
        instancia.DIR_INSTANCIA = self.dir
        self.filhos = []

    def tearDown(self):
        instancia.DIR_INSTANCIA = self._dir_original
        for p in self.filhos:
            try:
                p.kill()
                p.wait(timeout=10)
            except Exception:
                pass

    @staticmethod
    def _esperar_pid(p, limite=90):
        """Lê a saída do filho até achar a linha com o PID real dele.

        Antes disso pode vir o aviso de derrubamento da instância anterior, que
        aparece em stderr e chega antes do print do PID.
        """
        buf, t0 = "", time.monotonic()
        while time.monotonic() - t0 < limite:
            linha = p.stdout.readline()
            if not linha:
                break
            buf += linha
            if "PID_REAL=" in buf:
                return int(buf.split("PID_REAL=")[1].split()[0])
        raise AssertionError(f"o processo não informou o PID: {buf!r}")

    def _subir(self, papel="bot"):
        """Sobe um processo que assume a trava e fica de pé. Devolve seu PID real."""
        codigo = (
            "import os, sys, time\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from pathlib import Path\n"
            "import ofertas.instancia as inst\n"
            "inst.DIR_INSTANCIA = Path(sys.argv[2])\n"
            "r = inst.adquirir(sys.argv[3])\n"
            "print('PID_REAL=%d ADQUIRIU=%s' % (os.getpid(), r is not None), flush=True)\n"
            "time.sleep(120)\n"
        )
        p = subprocess.Popen([PYTHON, "-c", codigo, REPO, str(self.dir), papel],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.filhos.append(p)
        linha = p.stdout.readline()
        self.assertIn("ADQUIRIU=True", linha, f"o processo não assumiu a trava: {linha!r}")
        return int(linha.split("PID_REAL=")[1].split()[0])

    def test_subir_de_novo_derruba_a_instancia_anterior(self):
        pid_antigo = self._subir()
        self.assertTrue(instancia.processo_vivo(pid_antigo))

        inst = instancia.adquirir("bot")          # assume no processo deste teste
        try:
            self.assertIsNotNone(inst)
            self.assertFalse(
                instancia.processo_vivo(pid_antigo),
                "a instância anterior continuou viva depois da nova assumir",
            )
            self.assertEqual(instancia.status("bot")["pid"], os.getpid())
        finally:
            inst.liberar()

    def test_sem_derrubar_recusa_e_preserva_a_anterior(self):
        pid_antigo = self._subir()
        self.assertIsNone(
            instancia.adquirir("bot", derrubar_anterior=False),
            "deveria recusar subir sem derrubar a instância anterior",
        )
        self.assertTrue(
            instancia.processo_vivo(pid_antigo),
            "a recusa derrubou a instância anterior mesmo assim",
        )

    def test_so_um_sobrevive_quando_varios_subem_junto(self):
        """Corrida entre processos que sobem no mesmo instante."""
        codigo = (
            "import os, sys, time\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from pathlib import Path\n"
            "import ofertas.instancia as inst\n"
            "inst.DIR_INSTANCIA = Path(sys.argv[2])\n"
            "r = inst.adquirir('bot')\n"
            "print('PID_REAL=%d' % os.getpid(), flush=True)\n"
            "time.sleep(120)\n"
        )
        ps = [subprocess.Popen([PYTHON, "-c", codigo, REPO, str(self.dir)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
              for _ in range(3)]
        self.filhos.extend(ps)
        pids = []
        for p in ps:
            # A primeira linha pode ser o aviso de "outro bot está rodando",
            # que é justamente o que esta corrida provoca.
            pid = self._esperar_pid(p)
            pids.append(pid)
        time.sleep(1.5)
        vivos = [p for p in pids if instancia.processo_vivo(p)]
        self.assertEqual(
            len(vivos), 1,
            f"esperado exatamente 1 processo sobrevivente, sobraram {vivos} de {pids}",
        )
        self.assertEqual(instancia.status("bot")["pid"], vivos[0])
        # O sobrevivente fica de propósito de pé até o fim (é ele quem tem a
        # trava), então quem mata é o tearDown.


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipIf(sys.platform == "win32", "grupo de processos é conceito Unix")
class TestEncerrarNaoSeMata(unittest.TestCase):
    """`killpg` no nosso próprio grupo manda o sinal de volta para nós.

    O sintoma que estes testes existem para impedir: em Linux, derrubar uma
    instância que dividia o grupo de processos derrubava também quem estava
    derrubando. No Windows isso não aparecia — `os.killpg` não existe lá, o
    código cai no `taskkill /T /F` e cada processo leva só o seu. Por isso a
    suíte passava noindows e matava o próprio runner na VPS.
    """

    def test_alvo_no_meu_grupo_so_toma_o_pid(self):
        filho = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(300)"])
        try:
            self.assertEqual(os.getpgid(filho.pid), os.getpgid(0),
                             "o teste precisa de um filho no NOSSO grupo")
            self.assertFalse(instancia._pode_matar_grupo(filho.pid))
            instancia.encerrar(filho.pid)
            self.assertFalse(instancia.processo_vivo(filho.pid),
                             "o alvo não morreu")
        finally:
            try:
                filho.kill()
                filho.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
        # Chegar aqui É a prova: com o `killpg` sem guarda, este processo
        # recebia SIGTERM junto com o filho e o runner morria (rc 143).

    def test_alvo_com_grupo_proprio_continua_mortando_a_arvore(self):
        """A guarda não pode desligar o `killpg` de verdade.

        `start_new_session=True` dá grupo próprio ao filho — o caso do bot
        sob systemd. Ali derrubar a árvore continua sendo o certo.
        """
        filho = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(300)"],
                                 start_new_session=True)
        try:
            self.assertEqual(os.getpgid(filho.pid), filho.pid)
            self.assertTrue(instancia._pode_matar_grupo(filho.pid))
            instancia.encerrar(filho.pid)
            self.assertFalse(instancia.processo_vivo(filho.pid),
                             "o alvo com grupo próprio não morreu")
        finally:
            try:
                filho.kill()
                filho.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass

    def test_pid_inexistente_nao_derruba_o_grupo(self):
        """Sem grupo conhecido (o PID já sumiu), a resposta é não."""
        self.assertFalse(instancia._pode_matar_grupo(999999))
        self.assertFalse(instancia.encerrar(999999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
