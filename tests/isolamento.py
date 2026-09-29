"""Redireciona os dados de verdade para fora do caminho, num só lugar.

Por que este módulo existe
--------------------------
`ofertas.db`, `ofertas.grok` e `ofertas.publishing_control` guardam o caminho
do arquivo que leem e escrevem em variáveis de módulo, e o singleton
`publishing_controller` é criado com `persistir=True`. Uma suíte que chama
`pipeline.processar_mensagem_telegram` — ou `executar_ciclo` — chega em
`registrar_publicacao()` e grava no `data/cadencia.json` do usuário sem
perguntar nada.

Isso não é teoria. `data/cadencia.json` chegou a 41 registros com
`intervalo_entre_posts_segundos = 300`, vários com menos de 1 segundo de
distância uns dos outros, contra 2 ofertas realmente publicadas — e a
canário que existe dentro de `registrar_publicacao` disparou o tempo todo
para um log que ninguém lê, porque era a saída do processo de teste. O
contador chegou a segurar a publicação com "limite_periodo_atingido
(126/20)" sem que existisse um único post correspondente.

Cada suíte que precisa disso já fazia o redirecionamento na mão, cada uma
à sua maneira, e duas esqueceram. Importar este módulo resolve as duas e
dá um lugar só para acrescentar o próximo arquivo de dados.
"""
from __future__ import annotations

import atexit
import shutil
import tempfile
from pathlib import Path

# Um diretório por processo: suítes paralelas não disputam o mesmo arquivo.
PASTA = Path(tempfile.mkdtemp(prefix="ofertas_isolado_"))
atexit.register(shutil.rmtree, PASTA, ignore_errors=True)

_cadencia = PASTA / "cadencia.json"
_cache = PASTA / "grok_cache.json"
_banco = PASTA / "ofertas.db"

# `publishing_control.ARQ_ESTADO` é lido por dentro dos métodos, então trocar
# o atributo do módulo é o que redireciona de fato. O singleton já pode ter
# lido o caminho original — daí o reset(), que também o devolve zerado para
# o próximo teste não herdar o estado do anterior.
import ofertas.db as db  # noqa: E402
import ofertas.grok as grok  # noqa: E402
import ofertas.publishing_control as pc  # noqa: E402

db.DB_PATH = _banco
grok.CACHE_FILE = _cache
pc.ARQ_ESTADO = _cadencia
pc.publishing_controller.reset()

db.init_db()


def caminho(nome: str) -> Path:
    """Onde o arquivo `nome` está sendo usado nesta suíte."""
    return {"ofertas.db": _banco,
            "grok_cache.json": _cache,
            "cadencia.json": _cadencia}[nome]
