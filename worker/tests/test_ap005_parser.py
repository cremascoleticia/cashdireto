from datetime import date
from pathlib import Path

import pytest

from cashdireto_worker.parsers import ap005
from cashdireto_worker.parsers.ap005 import Ap005ParseError

FIXTURE = Path(__file__).parent / "fixtures" / "ap005_sample.csv"
FALLBACK = date(2026, 5, 29)


def _parse(filename="CERC-AP005_99999999_20260605_0000001_ret.csv"):
    return ap005.parse(FIXTURE.read_bytes(), original_filename=filename, fallback_date=FALLBACK)


def test_estrutura_geral():
    r = _parse()
    assert len(r.urs) == 3
    assert r.usuarios_finais == {"11111111000111", "33333333000133"}
    assert r.total_pagamentos == 4
    assert sum(u.valor_constituido_total for u in r.urs) == 350.0


def test_ur_campos():
    urs = _parse().urs
    u0, u1, u2 = urs
    assert u0.referencia_externa == "IDA" and u0.usuario_final_doc == "11111111000111"
    assert u0.arranjo == "MCD" and u0.constituicao == "1"
    assert u0.data_liquidacao == date(2026, 6, 1)
    assert u0.valor_constituido_total == 100.0 and u0.valor_bloqueado == 0.0
    assert u0.carteira == "CART_A" and u0.atualizado_em == "2026-05-29T10:00:00.000Z"
    assert u1.constituicao == "2" and u1.valor_constituido_total == 50.0
    assert u2.usuario_final_doc == "33333333000133" and u2.valor_bloqueado == 5.0
    # linha = nº da linha física no arquivo (rastreio/idempotência)
    assert [u.linha for u in urs] == [1, 2, 3]


def test_pagamento_unico_domicilio_15_campos():
    p = _parse().urs[0].pagamentos
    assert len(p) == 1
    pag = p[0]
    assert pag.ordem == 1 and pag.tipo_conta == "CC"
    assert pag.conta == "123456-0" and pag.valor_a_pagar == 100.0
    assert pag.tipo_informacao_pagamento == "7"          # domicílio
    assert pag.identificador_cerc_contrato is None        # 12.16 ausente (sub-registro de 15 campos)
    assert pag.data_liquidacao_efetiva is None


def test_pagamentos_multiplos_e_efeito_de_contrato():
    pags = _parse().urs[1].pagamentos
    assert len(pags) == 2
    onus, domicilio = pags
    assert onus.ordem == 1 and onus.tipo_informacao_pagamento == "2"   # ônus cessão fiduciária
    assert onus.titular_domicilio_doc == "22222222000122"
    assert onus.beneficiario_doc == "22222222000122"
    assert onus.valor_a_pagar == 30.0 and onus.valor_onerado == 30.0
    assert onus.data_liquidacao_efetiva == date(2026, 6, 2)
    assert onus.regra_divisao == "1" and onus.indicador_ordem_efeito == "1"
    assert onus.valor_constituido_efeito == 30.0
    assert onus.identificador_cerc_contrato == "abc-123"  # 12.16 presente
    assert domicilio.ordem == 2 and domicilio.tipo_informacao_pagamento == "7"
    assert domicilio.identificador_cerc_contrato is None


def test_data_referencia_do_nome_com_fallback():
    assert _parse().data_referencia == date(2026, 6, 5)       # token _20260605_ (ignora 99999999)
    assert _parse("AP005.csv").data_referencia == FALLBACK    # sem token de data válido


def test_numero_de_colunas_errado_falha():
    with pytest.raises(Ap005ParseError, match="colunas"):
        ap005.parse("a;b;c\n", original_filename="x.csv", fallback_date=FALLBACK)


def test_subregistro_com_mais_de_16_campos_falha():
    sub = ";".join(["x"] * 17)
    linha = f'ID;reg;cred;11111111000111;MCD;2026-06-01;t;1;0;0;0;"{sub}";CART;0;0;2026-05-29T00:00:00Z\n'
    with pytest.raises(Ap005ParseError, match=">16"):
        ap005.parse(linha, original_filename="x.csv", fallback_date=FALLBACK)


def test_usuario_final_vazio_falha():
    linha = 'ID;reg;cred;;MCD;2026-06-01;t;1;0;0;0;"";CART;0;0;2026-05-29T00:00:00Z\n'
    with pytest.raises(Ap005ParseError, match="col4"):
        ap005.parse(linha, original_filename="x.csv", fallback_date=FALLBACK)


def test_arquivo_vazio_falha():
    with pytest.raises(Ap005ParseError, match="sem registros"):
        ap005.parse("\n", original_filename="x.csv", fallback_date=FALLBACK)
