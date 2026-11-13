"""O painel não pode se achar local quando quem conecta é um túnel.

Contexto real: o painel foi publicado por um quick tunnel do trycloudflare.
Todo pedido do túnel chega de 127.0.0.1, e `_permitido` libera loopback sem
senha quando PAINEL_USUARIO/PAINEL_SENHA não estão definidos. Na prática, o
painel inteiro (config, logs, token do bot, credenciais) ficou acessível para
qualquer pessoa com a URL.

A correção é `_ip_do_pedido`: quando o peer é o proxy local, o IP do cliente
vem dos cabeçalhos que o proxy acrescenta. Uma conexão direta nunca dita o
próprio IP por cabeçalho.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import isolamento  # noqa: E402,F401
import ofertas.painel as painel  # noqa: E402
from ofertas.painel import _ip_do_pedido, _ip_loopback  # noqa: E402


class TestIpDoPedido(unittest.TestCase):
    def test_sem_proxy_usa_o_peer(self):
        self.assertEqual(_ip_do_pedido({}, "127.0.0.1"), "127.0.0.1")
        self.assertEqual(_ip_do_pedido({}, "203.0.113.9"), "203.0.113.9")

    def test_tunel_entrega_o_ip_real_e_nao_loopback(self):
        ip = _ip_do_pedido({"CF-Connecting-IP": "203.0.113.9"}, "127.0.0.1")
        self.assertEqual(ip, "203.0.113.9")
        self.assertFalse(_ip_loopback(ip))

    def test_conexao_direta_nao_forja_ip_por_header(self):
        """Se o HOST virar 0.0.0.0, header não pode transformar remoto em local."""
        ip = _ip_do_pedido({"CF-Connecting-IP": "127.0.0.1"}, "203.0.113.9")
        self.assertEqual(ip, "203.0.113.9")
        self.assertFalse(_ip_loopback(ip))

    def test_x_forwarded_for_usa_o_primeiro_da_lista(self):
        ip = _ip_do_pedido(
            {"X-Forwarded-For": "203.0.113.9, 10.0.0.1, 127.0.0.1"}, "127.0.0.1")
        self.assertEqual(ip, "203.0.113.9")

    def test_x_real_ip(self):
        ip = _ip_do_pedido({"X-Real-IP": "198.51.100.7"}, "127.0.0.1")
        self.assertEqual(ip, "198.51.100.7")

    def test_header_invalido_cai_para_o_peer(self):
        self.assertEqual(
            _ip_do_pedido({"CF-Connecting-IP": "não é ip"}, "127.0.0.1"),
            "127.0.0.1")
        self.assertEqual(
            _ip_do_pedido({"X-Forwarded-For": ""}, "127.0.0.1"), "127.0.0.1")

    def test_ipv6(self):
        ip = _ip_do_pedido({"CF-Connecting-IP": "2001:db8::1"}, "127.0.0.1")
        self.assertEqual(ip, "2001:db8::1")
        self.assertFalse(_ip_loopback(ip))


class TestRotaProtegidaAtrasDoTunel(unittest.TestCase):
    """Pedido HTTP de verdade: socket local + header de proxy."""

    def setUp(self):
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(pasta, ignore_errors=True))
        import ofertas.db as db
        self._db_antigo = db.DB_PATH
        db.DB_PATH = pasta / "painel.db"
        self.addCleanup(setattr, db, "DB_PATH", self._db_antigo)

        self._env_antigo = painel.ENV_PATH
        painel.ENV_PATH = pasta / ".env"      # inexistente: sem credenciais
        self.addCleanup(setattr, painel, "ENV_PATH", self._env_antigo)

        self.servidor = painel.ThreadingHTTPServer(("127.0.0.1", 0), painel.Handler)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.addCleanup(self.servidor.server_close)
        self.addCleanup(self.servidor.shutdown)
        porta = self.servidor.server_address[1]
        self.base = f"http://127.0.0.1:{porta}"

    def _pedir(self, caminho, headers=None):
        pedido = urllib.request.Request(self.base + caminho, headers=headers or {})
        try:
            with urllib.request.urlopen(pedido, timeout=10) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def test_local_sem_header_continua_liberado(self):
        status, _ = self._pedir("/api/extras")
        self.assertEqual(status, 200)

    def test_pedido_de_tunel_sem_senha_e_recusado(self):
        status, corpo = self._pedir(
            "/api/extras", {"CF-Connecting-IP": "203.0.113.9"})
        self.assertEqual(status, 403)
        self.assertIn("PAINEL_USUARIO", json.loads(corpo)["erro"])

    def test_home_continua_publica_mas_api_nao(self):
        status, _ = self._pedir("/", {"CF-Connecting-IP": "203.0.113.9"})
        self.assertEqual(status, 200)
        status, _ = self._pedir(
            "/api/status", {"CF-Connecting-IP": "203.0.113.9"})
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
