"""Tests for sefaz_cte_client: SOAP envelope shape and mocked-transport round-trips."""

from __future__ import annotations

import base64
import gzip

import httpx
import pytest
from mcp_einvoicing_core.exceptions import PlatformError

from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards.cte_events import build_cancelamento_event_xml
from mcp_nfe_br.standards.sefaz_cte_client import (
    SefazCTeClient,
    build_cte_consulta_envelope,
    build_cte_evento_envelope,
    build_cte_recepcao_envelope,
    build_cte_status_servico_envelope,
    get_cte_endpoint,
    parse_cte_sefaz_response,
)

# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------


def test_build_cte_status_servico_envelope_shape() -> None:
    envelope = build_cte_status_servico_envelope("43", TipoAmbiente.HOMOLOGACAO)
    xml = envelope.decode("utf-8")

    assert "http://www.w3.org/2003/05/soap-envelope" in xml
    assert "cteStatusServicoCT" in xml
    assert "http://www.portalfiscal.inf.br/cte/wsdl/CTeStatusServico" in xml
    assert "<tpAmb>2</tpAmb>" in xml
    assert "<cUF>43</cUF>" in xml
    assert "<xServ>STATUS</xServ>" in xml


def test_build_cte_consulta_envelope_shape() -> None:
    ch_cte = "35260711222333000181570010000000011212199180"
    envelope = build_cte_consulta_envelope(ch_cte, TipoAmbiente.HOMOLOGACAO)
    xml = envelope.decode("utf-8")

    assert "cteConsultaCT" in xml
    assert "http://www.portalfiscal.inf.br/cte/wsdl/CTeConsulta" in xml
    assert "<xServ>CONSULTAR</xServ>" in xml
    assert f"<chCTe>{ch_cte}</chCTe>" in xml


def test_build_cte_recepcao_envelope_is_gzip_base64() -> None:
    signed_xml = b'<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe12345"/></CTe>'
    envelope = build_cte_recepcao_envelope(signed_xml)
    xml = envelope.decode("utf-8")

    assert "cteRecepcao" in xml
    assert "http://www.portalfiscal.inf.br/cte/wsdl/CTeRecepcaoSinc" in xml
    # The wrapper's text content must be the base64 of the gzip of the input,
    # not the raw XML — extract it and round-trip decode/decompress.
    start = xml.index(">", xml.index("cteDadosMsg")) + 1
    end = xml.index("</", start)
    encoded_payload = xml[start:end]
    decompressed = gzip.decompress(base64.b64decode(encoded_payload))
    assert decompressed == signed_xml


def test_build_cte_evento_envelope_shape() -> None:
    event_xml = build_cancelamento_event_xml(
        ch_cte="35260711222333000181570010000000011212199180",
        c_orgao="35",
        tp_amb="2",
        cnpj="11222333000181",
        dh_evento="2026-07-03T10:00:00Z",
        n_prot="135250000000001",
        x_just="Erro de digitação, requer emissão de novo CT-e.",
    ).encode("utf-8")
    envelope = build_cte_evento_envelope(event_xml)
    xml = envelope.decode("utf-8")

    assert "cteRecepcaoEvento" in xml
    assert "http://www.portalfiscal.inf.br/cte/wsdl/CTeRecepcaoEvento" in xml
    assert "<evCancCTe>" in xml  # payload appended as XML, not gzip/base64


# ---------------------------------------------------------------------------
# Endpoint routing
# ---------------------------------------------------------------------------


def test_get_cte_endpoint_always_raises() -> None:
    with pytest.raises(ValueError, match="NEED"):
        get_cte_endpoint("status_servico", cuf="35", tp_amb=TipoAmbiente.HOMOLOGACAO)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def test_parse_cte_sefaz_response_status_servico() -> None:
    response_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <cteResultMsg xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeStatusServico">
      <retConsStatServCTe xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
        <tpAmb>2</tpAmb>
        <cUF>43</cUF>
        <cStat>107</cStat>
        <xMotivo>Servico em Operacao</xMotivo>
      </retConsStatServCTe>
    </cteResultMsg>
  </soap:Body>
</soap:Envelope>"""
    parsed = parse_cte_sefaz_response(response_xml)
    assert parsed["cStat"] == "107"
    assert "Servico em Operacao" in parsed["xMotivo"]
    assert parsed["cUF"] == "43"


def test_parse_cte_sefaz_response_prot_cte() -> None:
    ch_cte = "35260711222333000181570010000000011212199180"
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <cteResultMsg xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeRecepcaoSinc">
      <cteProc xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
        <tpAmb>2</tpAmb>
        <cStat>100</cStat>
        <xMotivo>Autorizado o uso do CT-e</xMotivo>
        <protCTe versao="4.00">
          <infProt>
            <chCTe>{ch_cte}</chCTe>
            <cStat>100</cStat>
            <xMotivo>Autorizado o uso do CT-e</xMotivo>
            <nProt>135250000000002</nProt>
          </infProt>
        </protCTe>
      </cteProc>
    </cteResultMsg>
  </soap:Body>
</soap:Envelope>""".encode()
    parsed = parse_cte_sefaz_response(response_xml)
    assert parsed["cStat"] == "100"
    assert parsed["protCTe"]["nProt"] == "135250000000002"
    assert ch_cte in parsed["protCTe"]["chCTe"]


# ---------------------------------------------------------------------------
# Mocked-transport round-trips (no real network/mTLS)
# ---------------------------------------------------------------------------


class _MockTransportClient(SefazCTeClient):
    """SefazCTeClient subclass injecting an `httpx.MockTransport`."""

    def __init__(self, *args: object, response: httpx.Response, **kwargs: object) -> None:
        self._mock_response = response
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def _get_httpx_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return self._mock_response

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_consultar_status_servico_mocked() -> None:
    response = httpx.Response(
        200,
        content=b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <retConsStatServCTe xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
      <tpAmb>2</tpAmb>
      <cUF>43</cUF>
      <cStat>107</cStat>
      <xMotivo>Servico em Operacao</xMotivo>
    </retConsStatServCTe>
  </soap:Body>
</soap:Envelope>""",
    )
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="status_servico",
        endpoint_override="https://homolog.example/CTeStatusServico4.asmx",
        response=response,
    )

    result = await client.consultar_status_servico()
    assert result["status_code"] == 200
    assert result["cStat"] == "107"


@pytest.mark.asyncio
async def test_autorizar_cte_mocked() -> None:
    ch_cte = "35260711222333000181570010000000011212199180"
    response = httpx.Response(
        200,
        content=f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <cteResultMsg xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeRecepcaoSinc">
      <cteProc xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
        <tpAmb>2</tpAmb>
        <cStat>100</cStat>
        <xMotivo>Autorizado o uso do CT-e</xMotivo>
        <protCTe versao="4.00">
          <infProt>
            <chCTe>{ch_cte}</chCTe>
            <cStat>100</cStat>
            <xMotivo>Autorizado o uso do CT-e</xMotivo>
            <nProt>135250000000002</nProt>
          </infProt>
        </protCTe>
      </cteProc>
    </cteResultMsg>
  </soap:Body>
</soap:Envelope>""".encode(),
    )
    signed_xml = b'<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe12345"/></CTe>'
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="recepcao",
        endpoint_override="https://homolog.example/CTeRecepcaoSincV4.asmx",
        response=response,
    )

    result = await client.autorizar_cte(signed_xml)
    assert result["status_code"] == 200
    assert result["cStat"] == "100"
    assert result["protCTe"]["nProt"] == "135250000000002"


@pytest.mark.asyncio
async def test_enviar_evento_mocked() -> None:
    response = httpx.Response(
        200,
        content=b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <cteResultMsg xmlns="http://www.portalfiscal.inf.br/cte/wsdl/CTeRecepcaoEvento">
      <retEventoCTe xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
        <infEvento>
          <tpAmb>2</tpAmb>
          <cStat>135</cStat>
          <xMotivo>Evento registrado e vinculado ao CT-e</xMotivo>
        </infEvento>
      </retEventoCTe>
    </cteResultMsg>
  </soap:Body>
</soap:Envelope>""",
    )
    event_xml = build_cancelamento_event_xml(
        ch_cte="35260711222333000181570010000000011212199180",
        c_orgao="35",
        tp_amb="2",
        cnpj="11222333000181",
        dh_evento="2026-07-03T10:00:00Z",
        n_prot="135250000000001",
        x_just="Erro de digitação, requer emissão de novo CT-e.",
    ).encode("utf-8")
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="evento",
        endpoint_override="https://homolog.example/CTeRecepcaoEventoV4.asmx",
        response=response,
    )

    result = await client.enviar_evento(event_xml)
    assert result["status_code"] == 200
    assert result["cStat"] == "135"


@pytest.mark.asyncio
async def test_post_soap_raises_platform_error_on_http_failure() -> None:
    response = httpx.Response(500, content=b"internal error")
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="status_servico",
        endpoint_override="https://homolog.example/CTeStatusServico4.asmx",
        response=response,
    )

    with pytest.raises(PlatformError) as exc_info:
        await client.consultar_status_servico()
    assert "internal error" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# 429/503 retry (CORE-3, core audit Step 6)
# ---------------------------------------------------------------------------


class _QueuedResponseClient(SefazCTeClient):
    """SefazCTeClient subclass returning one queued response per HTTP call."""

    def __init__(self, *args: object, responses: list[httpx.Response], **kwargs: object) -> None:
        self._responses = list(responses)
        self.request_count = 0
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def _get_httpx_client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            self.request_count += 1
            return self._responses.pop(0)

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


_CTE_STATUS_SERVICO_OK = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <retConsStatServCTe xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
      <tpAmb>2</tpAmb>
      <cUF>43</cUF>
      <cStat>107</cStat>
      <xMotivo>Servico em Operacao</xMotivo>
    </retConsStatServCTe>
  </soap:Body>
</soap:Envelope>"""


@pytest.mark.asyncio
async def test_post_soap_retries_on_503_then_succeeds() -> None:
    client = _QueuedResponseClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="status_servico",
        endpoint_override="https://homolog.example/CTeStatusServico4.asmx",
        responses=[
            httpx.Response(503, headers={"Retry-After": "0"}),
            httpx.Response(200, content=_CTE_STATUS_SERVICO_OK),
        ],
    )

    result = await client.consultar_status_servico()

    assert result["cStat"] == "107"
    assert client.request_count == 2


@pytest.mark.asyncio
async def test_post_soap_gives_up_after_max_retries() -> None:
    client = _QueuedResponseClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="status_servico",
        endpoint_override="https://homolog.example/CTeStatusServico4.asmx",
        responses=[httpx.Response(503, headers={"Retry-After": "0"}) for _ in range(4)],
    )
    client._max_retries = 3

    with pytest.raises(PlatformError):
        await client.consultar_status_servico()
    assert client.request_count == 4
