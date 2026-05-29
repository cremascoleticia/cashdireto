from datetime import date
from pathlib import Path

from cashdireto_worker.parsers import radar
from cashdireto_worker.parsers.radar import SITUACOES, loader
from cashdireto_worker.parsers.radar.parser import AgendaRegistro, RadarParseResult

FIXTURE = Path(__file__).parent / "fixtures" / "radar_sample.csv"


def _res():
    return radar.parse(FIXTURE.read_bytes(), original_filename="RADAR.csv", fallback_date=date(2026, 5, 29))


def test_quatro_statements_idempotentes():
    sts = loader.gerar_statements(_res(), nome_original="RADAR.csv")
    assert len(sts) == 4
    assert sts[0].startswith("insert into core.titular") and "on conflict (cnpj) do nothing" in sts[0]
    assert "on conflict (sha256)" in sts[1]
    assert sts[2].startswith("delete from core.agenda_ur")          # reprocessável
    assert sts[3].startswith("insert into core.agenda_ur")


def test_agenda_tem_todas_as_celulas():
    sts = loader.gerar_statements(_res(), nome_original="RADAR.csv")
    agenda = sts[3]
    # 4 linhas de origem × 5 janelas por situação = 20 ocorrências de cada situação
    for s in SITUACOES:
        assert agenda.count(f"'{s}'") == 20


def test_escape_de_aspas_simples():
    reg = AgendaRegistro("123", "456", "PAGOS D'OURO", "MCC", "0_30", "livre", 1.0)
    res = RadarParseResult(date(2026, 1, 1), "fallback", "shatest", [reg], {"123"}, 1)
    agenda = loader.gerar_statements(res, nome_original="x.csv")[3]
    assert "'PAGOS D''OURO'" in agenda     # aspas simples escapadas (dobradas)


def test_sql_unico_concatena_com_ponto_e_virgula():
    sql = loader.gerar_sql(_res(), nome_original="RADAR.csv")
    assert sql.count(";") == 4             # 4 statements terminados por ;
