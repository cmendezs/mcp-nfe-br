"""Tests for mcp_nfe_br.standards.adn_client."""

import pytest

from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards.adn_client import (
    _ADN_BASE_URLS,
    ADNClient,
    _parse_adn_xml_response,
)
from mcp_nfe_br.standards.govbr_auth import build_govbr_oauth


def test_adn_base_url_homologacao():
    oauth = build_govbr_oauth("id", "secret", homologacao=True)
    client = ADNClient(tp_amb=TipoAmbiente.HOMOLOGACAO, oauth=oauth)
    assert client._base_url == _ADN_BASE_URLS["2"]


def test_adn_base_url_producao():
    oauth = build_govbr_oauth("id", "secret", homologacao=False)
    client = ADNClient(tp_amb=TipoAmbiente.PRODUCAO, oauth=oauth)
    assert client._base_url == _ADN_BASE_URLS["1"]


def test_adn_endpoint_override():
    oauth = build_govbr_oauth("id", "secret")
    client = ADNClient(
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        oauth=oauth,
        endpoint_override="https://custom.endpoint.example",
    )
    assert client._base_url == "https://custom.endpoint.example"


def test_parse_adn_xml_response_basic():
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<retEnviDPS>"
        b"<cStat>100</cStat>"
        b"<xMotivo>Lote processado</xMotivo>"
        b"<verAplic>ADN1.0</verAplic>"
        b"</retEnviDPS>"
    )
    result = _parse_adn_xml_response(xml)
    assert result["cStat"] == "100"
    assert "xMotivo" in result


def test_parse_adn_xml_response_with_nfse():
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<retEnviDPS>"
        b"<cStat>100</cStat>"
        b"<NFSe><infNFSe>test</infNFSe></NFSe>"
        b"</retEnviDPS>"
    )
    result = _parse_adn_xml_response(xml)
    assert "nfse_xml" in result
    assert "<infNFSe>" in result["nfse_xml"]


class TestADNClientPasswordNotInLogs:
    """BR-SH-1 parity: gov.br client_secret must not appear in log records."""

    @pytest.mark.asyncio
    async def test_submit_nfse_secret_not_in_logs(self, caplog):
        secret = "SUPER_SECRET_VALUE_12345"
        oauth = build_govbr_oauth("id", secret, homologacao=True)
        client = ADNClient(
            tp_amb=TipoAmbiente.HOMOLOGACAO,
            oauth=oauth,
            endpoint_override="https://nonexistent.example.com",
        )
        try:
            await client.submit_dps(b"<DPS/>")
        except Exception:
            pass
        for record in caplog.records:
            assert secret not in record.getMessage(), (
                f"client_secret leaked in log record: {record.getMessage()}"
            )
