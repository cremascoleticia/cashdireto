"""Testes do orquestrador de ingestão — detecção de fonte e registro completo."""
import pytest

from cashdireto_worker import ingest
from cashdireto_worker.ingest import IngestError, REGISTRO


def test_detecta_cerc_ap_por_mascara():
    assert ingest.detectar_tipo("CERC-AP005_44198946_20260529_0000001_ret.csv") == "AP005"
    assert ingest.detectar_tipo("CERC-AP007_53462828_20260530_0000001_ret.csv") == "AP007"
    assert ingest.detectar_tipo("CERC-AP013_53462828_20190221_0000001_ret.csv") == "AP013"
    # os mais longos não podem ser confundidos com AP013
    assert ingest.detectar_tipo("CERC-AP013A_53462828_20190221_0000001_ret.csv") == "AP013A"
    assert ingest.detectar_tipo("CERC-AP013B_53462828_20190221_0000001_ret.csv") == "AP013B"
    assert ingest.detectar_tipo("CERC-AP013C_53462828_20190221_0000001_ret.csv") == "AP013C"


def test_detecta_radar_e_raiox():
    assert ingest.detectar_tipo("RADAR.csv") == "RADAR"
    assert ingest.detectar_tipo("radar_2026.csv") == "RADAR"
    assert ingest.detectar_tipo("RAIOX.html") == "RAIOX"
    assert ingest.detectar_tipo("dossie.HTM") == "RAIOX"        # html → RAIOX


def test_tipo_desconhecido_falha():
    with pytest.raises(IngestError, match="CERC"):
        ingest.detectar_tipo("CERC-AP999_x_y_z.csv")
    with pytest.raises(IngestError, match="não reconheci"):
        ingest.detectar_tipo("planilha.xlsx")
    with pytest.raises(IngestError):
        ingest.detectar_tipo("")


def test_registro_cobre_as_8_fontes_com_parse_e_carregar():
    assert set(REGISTRO) == {"RADAR", "RAIOX", "AP005", "AP007", "AP013", "AP013A", "AP013B", "AP013C"}
    for tipo, (parse, carregar) in REGISTRO.items():
        assert callable(parse) and callable(carregar), tipo


def test_processar_arquivo_usa_parser_e_loader(monkeypatch):
    # processa o AP005 de fixture com um loader falso (sem banco), validando o fluxo + resumo
    from datetime import date
    from pathlib import Path

    amostra = (Path(__file__).parent / "fixtures" / "ap005_sample.csv").read_bytes()
    chamou = {}

    def carregar_falso(conn, res, *, nome_original):
        chamou["nome"] = nome_original
        chamou["urs"] = len(res.urs)

    monkeypatch.setitem(REGISTRO, "AP005", (REGISTRO["AP005"][0], carregar_falso))
    resumo = ingest.processar_arquivo(
        conn=None, nome_arquivo="CERC-AP005_44198946_20260605_0000001_ret.csv",
        conteudo=amostra, fallback_date=date(2026, 5, 29),
    )
    assert resumo["tipo"] == "AP005"
    assert resumo["data_referencia"] == date(2026, 6, 5)       # token do nome
    assert chamou["nome"].startswith("CERC-AP005") and chamou["urs"] == 3
