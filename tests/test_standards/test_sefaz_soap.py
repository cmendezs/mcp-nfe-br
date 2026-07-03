"""Tests for the shared _sefaz_soap.py envelope/parsing helper (roadmap BR-CTE-10)."""

from __future__ import annotations

import pytest
from lxml import etree

from mcp_nfe_br.standards._sefaz_soap import parse_response_root, scrape_fields, soap_envelope


def test_soap_envelope_with_payload_element() -> None:
    payload = etree.Element("{http://example.com/ns}foo", nsmap={None: "http://example.com/ns"})
    payload.text = "bar"
    envelope = soap_envelope(
        wsdl_namespace="http://example.com/wsdl/Op",
        operation="doThing",
        dados_msg_element="dadosMsg",
        payload_element=payload,
    )
    xml = envelope.decode("utf-8")
    assert "doThing" in xml
    assert "dadosMsg" in xml
    assert "<foo" in xml and ">bar</foo>" in xml


def test_soap_envelope_with_payload_text() -> None:
    envelope = soap_envelope(
        wsdl_namespace="http://example.com/wsdl/Op",
        operation="doThing",
        dados_msg_element="dadosMsg",
        payload_text="base64stuff",
    )
    xml = envelope.decode("utf-8")
    assert ">base64stuff<" in xml


def test_soap_envelope_requires_exactly_one_payload() -> None:
    with pytest.raises(ValueError):
        soap_envelope(wsdl_namespace="ns", operation="op", dados_msg_element="msg")
    with pytest.raises(ValueError):
        soap_envelope(
            wsdl_namespace="ns",
            operation="op",
            dados_msg_element="msg",
            payload_element=etree.Element("x"),
            payload_text="y",
        )


def test_scrape_fields_and_parse_response_root() -> None:
    xml = b"<root><cStat>100</cStat><xMotivo>OK</xMotivo></root>"
    root = parse_response_root(xml)
    fields = scrape_fields(root, ("cStat", "xMotivo", "missing"))
    assert fields == {"cStat": "100", "xMotivo": "OK"}
