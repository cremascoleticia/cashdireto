"""Testes do agrupamento por loja/grupo (montar_contexto) — puro, sem banco."""
from cashdireto_worker import contexto as c


def test_norm_e_raiz():
    assert c.norm_cnpj("11.111.111/0001-11") == "11111111000111"
    assert c.raiz_cnpj("11.111.111/0001-11") == "11111111"
    assert c.norm_cnpj("") is None and c.raiz_cnpj(None) is None


def test_agrupa_loja_e_grupo_unificando_formato():
    dados = {
        "agenda_ur": [
            {"estabelecimento_cnpj": "11.111.111/0001-11", "valor": 10},   # formatado
            {"estabelecimento_cnpj": "11111111000200", "valor": 20},        # filial (cru)
        ],
        "ap005_ur": [{"usuario_final_doc": "11111111000111", "valor_constituido_total": 5}],
    }
    dossie = {"cnpj": "11.111.111/0001-11", "indicadores": {"x": 1}}
    ctx = c.montar_contexto(dados, raiox_dossies=[dossie])

    # loja: chave normalizada (só dígitos)
    assert set(ctx["loja"]) == {"11111111000111", "11111111000200"}
    matriz = ctx["loja"]["11111111000111"]
    assert len(matriz["agenda_ur"]) == 1 and len(matriz["ap005_ur"]) == 1
    assert matriz["raiox_dossie"] == dossie

    # grupo: mesma raiz junta matriz + filial
    grupo = ctx["grupo"]["11111111"]
    assert len(grupo["agenda_ur"]) == 2                # 10 + 20 do grupo
    assert grupo["raiox_dossies"] == [dossie]


def test_ignora_cnpj_vazio():
    ctx = c.montar_contexto({"agenda_ur": [{"estabelecimento_cnpj": None, "valor": 1}]})
    assert ctx["loja"] == {} and ctx["grupo"] == {}
