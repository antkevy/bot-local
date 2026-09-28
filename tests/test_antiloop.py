"""Anti-loop: nunca reprocessar publicação do próprio canal de destino.

O `lstrip("-100")` que estava aqui antes não removia o prefixo, removia o
conjunto de caracteres {'-','1','0'} do começo da string. Num canal cujo id
começa com -1001... isso comia dígitos do id e a comparação deixava de
valer — que é exatamente o que o anti-loop precisa fazer.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ofertas.bot_interativo import _e_mesmo_canal


class TestAntiLoop(unittest.TestCase):
    def test_prefixo_exato(self):
        # caso do config.yaml atual
        self.assertTrue(_e_mesmo_canal("-1003942213987", "-1003942213987"))

    def test_o_canal_mesmo_veio_sem_prefixo(self):
        self.assertTrue(_e_mesmo_canal("3942213987", "-1003942213987"))

    def test_o_destino_veio_sem_prefixo(self):
        self.assertTrue(_e_mesmo_canal("-1003942213987", "3942213987"))

    def test_id_que_comeca_com_1001(self):
        """O caso que o lstrip comia. id bruto 1234567 -> '-1001234567'.
        lstrip("-100") produzia '234567', que não bate com nada."""
        self.assertTrue(_e_mesmo_canal("-1001234567", "-1001234567"))
        self.assertTrue(_e_mesmo_canal("1234567", "-1001234567"))

    def test_outro_canal_nao_confere(self):
        self.assertFalse(_e_mesmo_canal("-1001465877129", "-1003942213987"))
        self.assertFalse(_e_mesmo_canal("1465877129", "-1003942213987"))

    def test_prefixo_similar_nao_confunde(self):
        """-10039... e -100394...: um é o canal, o outro é outro canal.
        Uma comparação por 'começa com' aqui seria um falso positivo que
        deixaria de postar no destino."""
        self.assertFalse(_e_mesmo_canal("-100394", "-1003942213987"))
        self.assertFalse(_e_mesmo_canal("-10039422139870", "-1003942213987"))

    def test_vazio_nao_confere(self):
        self.assertFalse(_e_mesmo_canal("", "-1003942213987"))
        self.assertFalse(_e_mesmo_canal("-1003942213987", ""))

    def test_destino_vazio_nao_casa_com_um_id_curto(self):
        """Sem a guarda, dest_id vazio produz '-100' + '' = '-100', e um
        chat cujo id seja '-100' casaria com um destino que não existe."""
        self.assertFalse(_e_mesmo_canal("-100", ""))
        self.assertFalse(_e_mesmo_canal("", ""))

    def test_grupo_comum_tem_id_negativo_sem_o_prefixo_100(self):
        """Grupo comum é -123..., não -100123.... Não pode ser confundido
        com um canal de mesmo número."""
        self.assertFalse(_e_mesmo_canal("-3942213987", "-1003942213987"))


if __name__ == "__main__":
    unittest.main()
