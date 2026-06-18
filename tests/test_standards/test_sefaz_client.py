"""Tests for sefaz_client: SOAP envelope shape and mocked-transport round-trips."""

from __future__ import annotations

import httpx
import pytest
from mcp_einvoicing_core.exceptions import PlatformError

from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards.sefaz_client import (
    SefazClient,
    build_autorizacao_envelope,
    build_dist_dfe_envelope,
    build_status_servico_envelope,
    get_endpoint,
    parse_sefaz_response,
)

# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------


def test_build_status_servico_envelope_shape() -> None:
    envelope = build_status_servico_envelope("43", TipoAmbiente.HOMOLOGACAO)
    xml = envelope.decode("utf-8")

    assert "http://www.w3.org/2003/05/soap-envelope" in xml
    assert "nfeStatusServicoNF" in xml
    assert "http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4" in xml
    assert "<tpAmb>2</tpAmb>" in xml
    assert "<cUF>43</cUF>" in xml
    assert "<xServ>STATUS</xServ>" in xml


def test_build_autorizacao_envelope_shape() -> None:
    signed_xml = b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe12345"/></NFe>'
    envelope = build_autorizacao_envelope(signed_xml, id_lote="1", tp_amb=TipoAmbiente.HOMOLOGACAO)
    xml = envelope.decode("utf-8")

    assert "nfeAutorizacaoLote" in xml
    assert "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4" in xml
    assert "<idLote>1</idLote>" in xml
    assert "<indSinc>1</indSinc>" in xml
    assert 'Id="NFe12345"' in xml


def test_build_dist_dfe_envelope_dist_nsu() -> None:
    envelope = build_dist_dfe_envelope(
        TipoAmbiente.PRODUCAO, c_uf_autor="35", document_id="99999999999999", ult_nsu="000000000000001"
    )
    xml = envelope.decode("utf-8")

    assert "nfeDistDFeInteresse" in xml
    assert "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe" in xml
    assert '<distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">' in xml
    assert "<tpAmb>1</tpAmb>" in xml
    assert "<cUFAutor>35</cUFAutor>" in xml
    assert "<CNPJ>99999999999999</CNPJ>" in xml
    assert "<distNSU><ultNSU>000000000000001</ultNSU></distNSU>" in xml


def test_build_dist_dfe_envelope_cons_ch_nfe() -> None:
    ch_nfe = "35220499999999999999550010020000001240556603"
    envelope = build_dist_dfe_envelope(
        TipoAmbiente.HOMOLOGACAO,
        c_uf_autor="35",
        document_id="99999999999",
        document_id_type="CPF",
        ch_nfe=ch_nfe,
    )
    xml = envelope.decode("utf-8")

    assert "<CPF>99999999999</CPF>" in xml
    assert f"<consChNFe><chNFe>{ch_nfe}</chNFe></consChNFe>" in xml


def test_build_dist_dfe_envelope_requires_exactly_one_mode() -> None:
    with pytest.raises(ValueError):
        build_dist_dfe_envelope(TipoAmbiente.PRODUCAO, c_uf_autor="35", document_id="99999999999999")
    with pytest.raises(ValueError):
        build_dist_dfe_envelope(
            TipoAmbiente.PRODUCAO,
            c_uf_autor="35",
            document_id="99999999999999",
            ult_nsu="1",
            nsu="2",
        )


def test_build_dist_dfe_envelope_invalid_document_id_type() -> None:
    with pytest.raises(ValueError):
        build_dist_dfe_envelope(
            TipoAmbiente.PRODUCAO,
            c_uf_autor="35",
            document_id="x",
            document_id_type="CPFX",
            nsu="1",
        )


# ---------------------------------------------------------------------------
# Endpoint routing
# ---------------------------------------------------------------------------


def test_get_endpoint_distribuicao_dfe_uses_ambiente_nacional() -> None:
    url = get_endpoint("distribuicao_dfe", cuf="35", tp_amb=TipoAmbiente.HOMOLOGACAO)
    assert "hom1.nfe.fazenda.gov.br" in url


def test_get_endpoint_svrs() -> None:
    url = get_endpoint("status_servico", cuf="43", tp_amb=TipoAmbiente.PRODUCAO)
    assert "svrs.rs.gov.br" in url


def test_get_endpoint_unconfigured_cuf_raises() -> None:
    with pytest.raises(ValueError):
        get_endpoint("status_servico", cuf="99", tp_amb=TipoAmbiente.PRODUCAO)


# BR-LC-1: all 27 UFs must resolve to a non-empty https:// URL.
_ALL_CUFS = [
    "12", "27", "16", "13", "29", "23", "53", "32", "52", "21",
    "15", "25", "26", "33", "28", "17", "35", "31", "41", "43",
    "50", "51", "22", "24", "11", "14", "42",
]


@pytest.mark.parametrize("cuf", _ALL_CUFS)
def test_all_cufs_resolve_status_servico_homologacao(cuf: str) -> None:
    url = get_endpoint("status_servico", cuf=cuf, tp_amb=TipoAmbiente.HOMOLOGACAO)
    assert url, f"Empty URL for cUF={cuf}"
    assert url.startswith("https://"), f"Non-https URL for cUF={cuf}: {url}"


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def test_parse_sefaz_response_status_servico() -> None:
    response_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">
      <retConsStatServ xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
        <tpAmb>2</tpAmb>
        <cUF>43</cUF>
        <cStat>107</cStat>
        <xMotivo>Servico em Operacao</xMotivo>
      </retConsStatServ>
    </nfeResultMsg>
  </soap:Body>
</soap:Envelope>"""
    parsed = parse_sefaz_response(response_xml)
    assert parsed["cStat"] == "107"
    # xMotivo is wrapped by mark_untrusted_fields — check the underlying text is present.
    assert "Servico em Operacao" in parsed["xMotivo"]
    assert parsed["cUF"] == "43"


def test_parse_sefaz_response_prot_nfe() -> None:
    response_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">
      <retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
        <tpAmb>2</tpAmb>
        <cStat>104</cStat>
        <xMotivo>Lote processado</xMotivo>
        <protNFe versao="4.00">
          <infProt>
            <chNFe>35220499999999999999550010020000001240556603</chNFe>
            <cStat>100</cStat>
            <xMotivo>Autorizado o uso da NF-e</xMotivo>
            <nProt>135250000000001</nProt>
          </infProt>
        </protNFe>
      </retEnviNFe>
    </nfeResultMsg>
  </soap:Body>
</soap:Envelope>"""
    parsed = parse_sefaz_response(response_xml)
    assert parsed["cStat"] == "104"
    assert parsed["protNFe"]["nProt"] == "135250000000001"
    assert parsed["protNFe"]["cStat"] == "100"
    # xMotivo and chNFe inside protNFe are wrapped by mark_untrusted_fields.
    assert "Autorizado o uso da NF-e" in parsed["protNFe"]["xMotivo"]
    assert "35220499999999999999550010020000001240556603" in parsed["protNFe"]["chNFe"]


# ---------------------------------------------------------------------------
# Mocked-transport round-trips
# ---------------------------------------------------------------------------


class _MockTransportClient(SefazClient):
    """SefazClient subclass injecting an `httpx.MockTransport` (no real network/mTLS)."""

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
    <retConsStatServ xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
      <tpAmb>2</tpAmb>
      <cUF>43</cUF>
      <cStat>107</cStat>
      <xMotivo>Servico em Operacao</xMotivo>
    </retConsStatServ>
  </soap:Body>
</soap:Envelope>""",
    )
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="status_servico",
        response=response,
    )

    result = await client.consultar_status_servico()
    assert result["status_code"] == 200
    assert result["cStat"] == "107"


@pytest.mark.asyncio
async def test_autorizar_nfe_mocked() -> None:
    """BR-LC-3 round-trip: NFeAutorizacao4 envelope shape + protNFe parsing.

    Verifies `[Verified locally — MOC 7.0 §5.1]`: ``enviNFe`` root, method
    ``nfeAutorizacaoLote``, synchronous ``protNFe`` in the response.
    """
    ch_nfe = "35220499999999999999550010020000001240556603"
    response = httpx.Response(
        200,
        content=f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
  <soap:Body>
    <nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">
      <retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
        <tpAmb>2</tpAmb>
        <cStat>104</cStat>
        <xMotivo>Lote processado</xMotivo>
        <protNFe versao="4.00">
          <infProt>
            <chNFe>{ch_nfe}</chNFe>
            <cStat>100</cStat>
            <xMotivo>Autorizado o uso da NF-e</xMotivo>
            <nProt>135250000000001</nProt>
          </infProt>
        </protNFe>
      </retEnviNFe>
    </nfeResultMsg>
  </soap:Body>
</soap:Envelope>""".encode(),
    )
    signed_xml = b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe12345"/></NFe>'
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="autorizacao",
        response=response,
    )

    result = await client.autorizar_nfe(signed_xml, id_lote="1")
    assert result["status_code"] == 200
    assert result["cStat"] == "104"
    assert result["protNFe"]["nProt"] == "135250000000001"
    assert result["protNFe"]["cStat"] == "100"
    assert ch_nfe in result["protNFe"]["chNFe"]


@pytest.mark.asyncio
async def test_post_soap_raises_platform_error_on_http_failure() -> None:
    response = httpx.Response(500, content=b"internal error")
    client = _MockTransportClient(
        cuf="43",
        tp_amb=TipoAmbiente.HOMOLOGACAO,
        cert_path="/tmp/does-not-need-to-exist.p12",
        service="status_servico",
        response=response,
    )

    with pytest.raises(PlatformError) as exc_info:
        await client.consultar_status_servico()
    # BR-SH-2: raw response body must not appear in the PlatformError message.
    assert "internal error" not in str(exc_info.value)
