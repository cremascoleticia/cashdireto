from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import raiox
from cashdireto_worker.parsers.raiox import loader

FIXTURE = Path(__file__).parent / "fixtures" / "raiox_sample.html"


def _res():
    return raiox.parse(FIXTURE.read_bytes(), original_filename="RAIOX.html", fallback_date=date(2026, 5, 29))


def test_statements_estrutura():
    sts = loader.gerar_statements(_res(), nome_original="RAIOX.html")
    joined = "\n".join(sts)
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj)" in sts[0]
    assert "insert into core.fonte_arquivo" in sts[1] and "on conflict (sha256)" in sts[1]
    assert any(s.startswith("delete from core.raiox_indicador") for s in sts)
    assert any(s.startswith("delete from core.raiox_serie_mensal") for s in sts)
    assert any(s.startswith("delete from core.raiox_relacionamento") for s in sts)
    assert "insert into core.raiox_indicador" in joined
    assert "insert into core.raiox_serie_mensal" in joined
    assert "insert into core.raiox_relacionamento" in joined


def test_escape_e_valores():
    res = _res()
    joined = "\n".join(loader.gerar_statements(res, nome_original="RAIOX.html"))
    assert "'11.111.111/0001-11'" in joined            # cnpj
    assert "'agenda'" in joined and "'volume_antecipacao'" in joined
    assert "300.0" in joined                            # valor de série (agenda jun)
