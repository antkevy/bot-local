"""Testes dos recursos extras portados do ScanHub.

Regra que estes testes protegem: os recursos são opt-in e vivem em tabelas
NOVAS. O pipeline, a cadência e as tabelas existentes não podem mudar de
comportamento por causa deles.

Também há um teste de isolamento: trocar `db.DB_PATH` precisa mudar o arquivo
usado pelas tabelas extras. É a mesma armadilha que já apagou o histórico real
do usuário quando `db.py` tinha um caminho privado que ninguém redirecionava.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import isolamento  # noqa: E402,F401  (redireciona db/grok/cadência)
from ofertas import (  # noqa: E402
    broadcasts, credentials, db, extras_api, mirrors, protection, smartlink,
    watermark,
)
from ofertas import config as config_mod  # noqa: E402
from ofertas.extra_db import conn, init_db  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        init_db()
        # Cada teste começa com as tabelas extras vazias, sem tocar em nada
        # do banco redirecionado que outras suítes possam ter deixado.
        with conn() as c:
            for tabela in ("mirrors", "broadcasts", "marca_dagua",
                           "credenciais", "smart_links", "protection_scans",
                           "protection_alvos"):
                c.execute(f"DELETE FROM {tabela}")
        with db._conn() as c:
            c.execute("DELETE FROM fontes_telegram")

    def _flag(self, nome, valor):
        """Liga/desliga uma flag só durante o teste."""
        alvo = config_mod.config
        antigo = getattr(alvo, nome)
        setattr(alvo, nome, valor)
        self.addCleanup(setattr, alvo, nome, antigo)


class TestIsolamentoDasTabelasExtras(Base):
    def test_trocar_db_path_muda_o_arquivo_das_tabelas_extras(self):
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        primeiro = pasta / "um.db"
        segundo = pasta / "dois.db"
        original = db.DB_PATH

        db.DB_PATH = primeiro
        init_db()
        mirrors.adicionar("@no_primeiro", "Primeiro")
        self.assertEqual(len(mirrors.listar()), 1)

        db.DB_PATH = segundo
        init_db()
        self.assertEqual(mirrors.listar(), [],
                         "as tabelas extras ignoraram a troca de db.DB_PATH")

        db.DB_PATH = original
        self.assertEqual(mirrors.listar(), [])

    def test_init_nao_altera_tabelas_existentes(self):
        init_db()
        with conn() as c:
            tabelas = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        for nova in ("mirrors", "broadcasts", "marca_dagua", "credenciais",
                     "smart_links", "protection_scans", "protection_alvos"):
            self.assertIn(nova, tabelas)
        for antiga in ("postadas", "fontes_telegram", "mensagens_telegram",
                       "ofertas_pendentes_ml", "reservas"):
            self.assertIn(antiga, tabelas)


class TestEspelhamento(Base):
    def test_cadastrar_listar_e_nao_duplicar(self):
        a = mirrors.adicionar("@canal_a", "Canal A")
        self.assertTrue(a["ativo"])
        mirrors.adicionar("@canal_a", "Canal A renomeado")
        lista = mirrors.listar()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["nome"], "Canal A renomeado")
        self.assertEqual(mirrors.destinos_ativos(), ["@canal_a"])

    def test_alternar_um_nao_mexe_nos_outros(self):
        a = mirrors.adicionar("@canal_a")
        b = mirrors.adicionar("-1001234567890")
        linha = mirrors.alternar(a["id"], False)
        self.assertFalse(linha["ativo"])
        self.assertEqual(mirrors.destinos_ativos(), ["-1001234567890"])
        self.assertTrue(mirrors.alternar(b["id"], True)["ativo"])
        self.assertEqual(len(mirrors.destinos_ativos()), 1)

    def test_remover(self):
        a = mirrors.adicionar("@canal_a")
        self.assertTrue(mirrors.remover(a["id"]))
        self.assertFalse(mirrors.remover(a["id"]))
        self.assertEqual(mirrors.listar(), [])

    def test_destino_invalido(self):
        for ruim in ("", "canal sem arroba", "@a", "javascript:alert(1)"):
            with self.assertRaises(mirrors.ErroEspelhamento):
                mirrors.adicionar(ruim)


class TestDisparos(Base):
    def _bot(self):
        chamadas = []

        async def send_message(**kw):
            chamadas.append(("message", kw))
            if kw["chat_id"] == "@ruim":
                raise RuntimeError("destino recusou")
            return SimpleNamespace(message_id=len(chamadas))

        async def send_photo(**kw):
            chamadas.append(("photo", kw))

        async def send_poll(**kw):
            chamadas.append(("poll", kw))

        return SimpleNamespace(send_message=send_message,
                               send_photo=send_photo,
                               send_poll=send_poll), chamadas

    def test_mensagem_agendada_fica_pendente_ate_a_hora(self):
        agora = dt.datetime(2026, 1, 1, 9, 0)
        b = broadcasts.criar(texto="promo", destinos=["@canal"],
                             agendado_para="2026-01-01 10:00", agora=agora)
        self.assertEqual(b["status"], "pendente")
        self.assertEqual(broadcasts.devidos(agora), [])
        self.assertEqual([x["id"] for x in broadcasts.devidos(
            dt.datetime(2026, 1, 1, 10, 1))], [b["id"]])

    def test_agendamento_no_passado_e_recusado(self):
        with self.assertRaises(broadcasts.ErroDisparo):
            broadcasts.criar(texto="x", destinos=["@canal"],
                             agendado_para="2020-01-01 10:00",
                             agora=dt.datetime(2026, 1, 1, 9, 0))

    def test_enquete_valida_opcoes(self):
        with self.assertRaises(broadcasts.ErroDisparo):
            broadcasts.criar(kind="poll", pergunta="Qual?",
                             opcoes=["só uma"], destinos=["@canal"])
        b = broadcasts.criar(kind="poll", pergunta="Qual?",
                             opcoes=["A", "B"], destinos=["@canal"])
        self.assertEqual(b["kind"], "poll")
        self.assertEqual(b["opcoes"], ["A", "B"])

    def test_sem_destino_ou_texto_vazio(self):
        with self.assertRaises(broadcasts.ErroDisparo):
            broadcasts.criar(texto="x", destinos=[])
        with self.assertRaises(broadcasts.ErroDisparo):
            broadcasts.criar(texto="   ", destinos=["@canal"])

    def test_cancelar_so_o_pendente(self):
        b = broadcasts.criar(texto="x", destinos=["@canal"])
        self.assertTrue(broadcasts.cancelar(b["id"]))
        self.assertFalse(broadcasts.cancelar(b["id"]))
        self.assertEqual(broadcasts.listar()[0]["status"], "cancelado")

    def test_horario_de_silencio(self):
        self.assertTrue(broadcasts.em_horario_silencio(
            dt.datetime(2026, 1, 1, 23, 0), "22:00-08:00"))
        self.assertTrue(broadcasts.em_horario_silencio(
            dt.datetime(2026, 1, 1, 7, 59), "22:00-08:00"))
        self.assertFalse(broadcasts.em_horario_silencio(
            dt.datetime(2026, 1, 1, 12, 0), "22:00-08:00"))
        self.assertFalse(broadcasts.em_horario_silencio(
            dt.datetime(2026, 1, 1, 23, 0), "formato ruim"))

    def test_envio_respeita_silencio_e_ritmo_e_segue_apos_falha(self):
        _flag_antiga = config_mod.config.disparos_horario_silencio
        config_mod.config.disparos_horario_silencio = ""
        self.addCleanup(setattr, config_mod.config,
                        "disparos_horario_silencio", _flag_antiga)
        broadcasts.criar(texto="oi", destinos=["@bom", "@ruim"],
                         ritmo_segundos=7, agora=dt.datetime(2026, 1, 1, 9, 0))
        bot, chamadas = self._bot()
        dormiu = []

        async def dormir(segundos):
            dormiu.append(segundos)

        resumo = asyncio.run(broadcasts.enviar_pendentes(
            bot, agora=dt.datetime(2026, 1, 1, 9, 1), dormir=dormir))
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(dormiu, [7])          # ritmo entre destinos, não depois
        self.assertEqual(resumo[0]["enviados"], 1)
        self.assertIn("@ruim", resumo[0]["falhas"][0])
        registro = broadcasts.listar()[0]
        self.assertEqual(registro["status"], "enviado")
        self.assertIn("@ruim", registro["erro"])

    def test_silencio_nao_consome_a_fila(self):
        antigo = config_mod.config.disparos_horario_silencio
        config_mod.config.disparos_horario_silencio = "22:00-08:00"
        self.addCleanup(setattr, config_mod.config,
                        "disparos_horario_silencio", antigo)
        broadcasts.criar(texto="oi", destinos=["@bom"],
                         agora=dt.datetime(2026, 1, 1, 9, 0))
        bot, chamadas = self._bot()
        resumo = asyncio.run(broadcasts.enviar_pendentes(
            bot, agora=dt.datetime(2026, 1, 1, 23, 0)))
        self.assertEqual(resumo, [])
        self.assertEqual(chamadas, [])
        self.assertEqual(broadcasts.listar()[0]["status"], "pendente")

    def test_enquete_envia_send_poll(self):
        config_mod.config.disparos_horario_silencio = ""
        self.addCleanup(setattr, config_mod.config, "disparos_horario_silencio",
                        "")
        broadcasts.criar(kind="poll", pergunta="Qual?",
                         opcoes=["A", "B"], destinos=["@bom"],
                         agora=dt.datetime(2026, 1, 1, 9, 0))
        bot, chamadas = self._bot()
        asyncio.run(broadcasts.enviar_pendentes(
            bot, agora=dt.datetime(2026, 1, 1, 9, 1)))
        self.assertEqual(chamadas[0][0], "poll")
        self.assertEqual(chamadas[0][1]["options"], ["A", "B"])


class TestProtecao(Base):
    def _fonte(self, chat_id, quando, ativa=True):
        db.salvar_fonte_telegram(chat_id, chat_id.strip("@"), ativa=ativa)
        with db._conn() as c:
            c.execute("UPDATE fontes_telegram SET ultimo_processamento = ?"
                      " WHERE chat_id = ?", (quando, chat_id))

    def test_scan_nao_remove_nada_antes_da_confirmacao(self):
        agora = dt.datetime(2026, 6, 1, 12, 0)
        self._fonte("@saudavel", "2026-05-30T12:00:00")
        self._fonte("@velha", "2020-01-01T12:00:00")
        self._fonte("@desligada", "2026-05-30T12:00:00", ativa=False)

        scan = protection.iniciar_scan(14, agora=agora)
        chaves = {a["chave"] for a in scan["alvos"]}
        self.assertEqual(chaves, {"@velha", "@desligada"})
        self.assertEqual(scan["status"], "revisao")
        self.assertEqual(
            {f["chat_id"] for f in db.listar_fontes_telegram()},
            {"@saudavel", "@velha", "@desligada"},
            "o scan não pode remover antes da revisão",
        )

        # Só a fonte aprovada sai; a desativada que ficou de fora permanece.
        feito = protection.confirmar(scan["id"], ["@velha"])
        self.assertEqual(feito["removidas"], 1)
        self.assertEqual(feito["status"], "concluido")
        self.assertEqual({f["chat_id"] for f in db.listar_fontes_telegram()},
                         {"@saudavel", "@desligada"})

    def test_confirmar_recusa_chave_fora_do_scan(self):
        self._fonte("@velha", "2020-01-01T12:00:00")
        scan = protection.iniciar_scan(14)
        with self.assertRaises(protection.ErroProtecao):
            protection.confirmar(scan["id"], ["@nao_listada"])
        self.assertEqual(len(db.listar_fontes_telegram()), 1)

    def test_cancelar_mantem_tudo(self):
        self._fonte("@velha", "2020-01-01T12:00:00")
        scan = protection.iniciar_scan(14)
        cancelado = protection.cancelar(scan["id"])
        self.assertEqual(cancelado["status"], "cancelado")
        self.assertEqual(cancelado["alvos"][0]["status"], "cancelado")
        self.assertEqual(len(db.listar_fontes_telegram()), 1)
        with self.assertRaises(protection.ErroProtecao):
            protection.confirmar(scan["id"], ["@velha"])

    def test_intervalo_invalido(self):
        with self.assertRaises(protection.ErroProtecao):
            protection.iniciar_scan(0)
        with self.assertRaises(protection.ErroProtecao):
            protection.iniciar_scan(400)


class TestMarcaDagua(Base):
    def test_desligada_devolve_texto_intacto(self):
        watermark.configurar("final", "@canal", ativo=False)
        self.assertEqual(watermark.aplicar("Oferta"), "Oferta")

    def test_presets_e_nao_duplica(self):
        watermark.configurar("final", "@canal", True)
        texto = watermark.aplicar("Oferta")
        self.assertTrue(texto.startswith("Oferta"))
        self.assertIn("@canal", texto)
        self.assertEqual(watermark.aplicar(texto), texto)

        watermark.configurar("topo", "canal", True)
        self.assertTrue(watermark.aplicar("Oferta").startswith("@canal"))
        watermark.configurar("sufixo", "@canal", True)
        self.assertEqual(watermark.aplicar("Oferta"), "Oferta @canal")

    def test_validacoes(self):
        with self.assertRaises(watermark.ErroMarcaDagua):
            watermark.configurar("final", "@a", True)
        with self.assertRaises(watermark.ErroMarcaDagua):
            watermark.configurar("meio", "@canal", True)
        with self.assertRaises(watermark.ErroMarcaDagua):
            watermark.configurar("final", "", True)


class TestSmartLink(Base):
    def test_criar_resolver_e_contar(self):
        link = smartlink.criar("https://produto.example/x", "amazon", "promo")
        self.assertEqual(link["slug"], "promo")
        self.assertEqual(smartlink.resolver("promo"), "https://produto.example/x")
        self.assertEqual(smartlink.obter("promo")["cliques"], 1)
        self.assertIsNone(smartlink.resolver("naoexiste"))
        self.assertEqual(smartlink.overview()["total_cliques"], 1)

    def test_mesma_url_reaproveita_o_link(self):
        a = smartlink.criar("https://produto.example/x", "shopee")
        b = smartlink.criar("https://produto.example/x", "shopee")
        self.assertEqual(a["slug"], b["slug"])
        self.assertEqual(len(smartlink.listar()), 1)

    def test_validacoes(self):
        with self.assertRaises(smartlink.ErroSmartLink):
            smartlink.criar("file:///etc/passwd")
        with self.assertRaises(smartlink.ErroSmartLink):
            smartlink.criar("https://x.example", slug="../etc")
        smartlink.criar("https://x.example", slug="ocupado")
        with self.assertRaises(smartlink.ErroSmartLink):
            smartlink.criar("https://y.example", slug="ocupado")

    def test_remover(self):
        smartlink.criar("https://x.example", slug="some")
        self.assertTrue(smartlink.remover("some"))
        self.assertFalse(smartlink.remover("some"))


class TestCredenciais(Base):
    def test_status_nao_devolve_segredo(self):
        credentials.definir("amazon", "segredo-super-secreto")
        status = credentials.status()
        self.assertEqual(status[0]["plataforma"], "amazon")
        self.assertTrue(status[0]["secretConfigured"])
        self.assertNotIn("segredo-super-secreto", json.dumps(status))
        self.assertEqual(credentials.obter("amazon"), "segredo-super-secreto")

    def test_substituir_e_remover(self):
        credentials.definir("shopee", "um")
        credentials.definir("shopee", "dois")
        self.assertEqual(credentials.obter("shopee"), "dois")
        self.assertTrue(credentials.remover("shopee"))
        self.assertFalse(credentials.remover("shopee"))
        self.assertTrue(credentials.configurada("shopee") is False)

    def test_validacoes(self):
        with self.assertRaises(credentials.ErroCredencial):
            credentials.definir("", "x")
        with self.assertRaises(credentials.ErroCredencial):
            credentials.definir("amazon", "  ")


class TestRotasExtras(Base):
    def setUp(self):
        super().setUp()
        # Recursos começam desligados; cada teste liga só o que usa.
        for flag in ("extras_espelhamento", "extras_disparos",
                     "extras_protecao", "extras_marca_dagua",
                     "extras_smart_link", "extras_credenciais"):
            self._flag(flag, False)

    def test_recurso_desligado_responde_404(self):
        payload, status = extras_api.tratar_get("/api/mirrors")
        self.assertEqual(status, 404)
        payload, status = extras_api.tratar_post(
            "/api/broadcasts", {"texto": "x", "destinos": ["@c"]})
        self.assertEqual(status, 404)

    def test_metadados_sempre_disponiveis(self):
        payload, status = extras_api.tratar_get("/api/extras")
        self.assertEqual(status, 200)
        self.assertFalse(payload["flags"]["espelhamento"])

    def test_fluxo_espelhamento(self):
        self._flag("extras_espelhamento", True)
        payload, status = extras_api.tratar_post(
            "/api/mirrors", {"chat_id": "@canal", "nome": "Canal"})
        self.assertEqual(status, 201)
        mirror_id = payload["id"]
        payload, status = extras_api.tratar_post(
            f"/api/mirrors/{mirror_id}/toggle", {"enabled": False})
        self.assertEqual(status, 200)
        self.assertFalse(payload["ativo"])
        payload, status = extras_api.tratar_get("/api/mirrors")
        self.assertEqual(payload["destinos"], [])

    def test_contrato_de_disparo_aceita_aliases_do_scanhub(self):
        self._flag("extras_disparos", True)
        payload, status = extras_api.tratar_post("/api/broadcasts", {
            "kind": "message", "text": "promo",
            "groupIds": ["@canal"], "pace": 5,
            "scheduledAt": "2030-01-01 10:00",
        })
        self.assertEqual(status, 201)
        self.assertEqual(payload["destinos"], ["@canal"])
        self.assertEqual(payload["ritmo_segundos"], 5)

    def test_erro_de_validacao_vira_400_com_mensagem(self):
        self._flag("extras_disparos", True)
        payload, status = extras_api.tratar_post(
            "/api/broadcasts", {"kind": "message", "text": "", "groupIds": []})
        self.assertEqual(status, 400)
        self.assertIn("destino", payload["erro"].lower())

    def test_fluxo_protecao_pelas_rotas(self):
        self._flag("extras_protecao", True)
        with db._conn() as c:
            c.execute("DELETE FROM fontes_telegram")
        db.salvar_fonte_telegram("@velha", "Velha")
        with db._conn() as c:
            c.execute("UPDATE fontes_telegram SET ultimo_processamento = ?",
                      ("2020-01-01T00:00:00",))
        payload, status = extras_api.tratar_post(
            "/api/protection/scans", {"days": 14})
        self.assertEqual(status, 201)
        scan_id = payload["id"]
        get_payload, status = extras_api.tratar_get(
            f"/api/protection/scans/{scan_id}")
        self.assertEqual(status, 200)
        chave = get_payload["alvos"][0]["chave"]
        confirmado, status = extras_api.tratar_post(
            f"/api/protection/scans/{scan_id}/confirm", {"keys": [chave]})
        self.assertEqual(status, 200)
        self.assertEqual(confirmado["removidas"], 1)

    def test_credencial_nunca_volta_pela_rota(self):
        self._flag("extras_credenciais", True)
        extras_api.tratar_post("/api/credentials",
                               {"platform": "amazon", "secret": "xyz"})
        payload, status = extras_api.tratar_get("/api/credentials")
        self.assertEqual(status, 200)
        self.assertNotIn("xyz", json.dumps(payload))

    def test_smart_link_aceita_slug_e_resolve(self):
        self._flag("extras_smart_link", True)
        payload, status = extras_api.tratar_post("/api/smart-link", {
            "url": "https://x.example/p", "platform": "amazon",
            "slug": "meu-link",
        })
        self.assertEqual(status, 201)
        self.assertEqual(extras_api.tratar_smartlink("meu-link"),
                         "https://x.example/p")
        self.assertIsNone(extras_api.tratar_smartlink("../etc"))

    def test_ligar_flag_grava_secao_extras(self):
        self._flag("extras_smart_link", False)
        gravado = {}

        def fake_salvar(secao, dados):
            gravado[secao] = dados

        with mock.patch.object(config_mod, "salvar_yaml_secao", fake_salvar):
            payload, status = extras_api.tratar_post(
                "/api/extras/config", {"smart_link": True,
                                       "disparos_horario_silencio": "23:00-07:00"})
        self.assertEqual(status, 200)
        self.assertEqual(gravado["extras"]["smart_link"], True)
        self.assertEqual(gravado["extras"]["disparos_horario_silencio"],
                         "23:00-07:00")

    def test_silencio_invalido_e_recusado(self):
        payload, status = extras_api.tratar_post(
            "/api/extras/config", {"disparos_horario_silencio": "25:00-07:00"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
