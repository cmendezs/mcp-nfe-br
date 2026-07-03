"""Shared SOAP 1.2 envelope helpers for SEFAZ webservices (NF-e and CT-e).

Extracted from `sefaz_client.py` (BR-CTE-10) so `sefaz_cte_client.py` can
reuse the same envelope-building and response-parsing primitives without
duplicating them. Private module — not part of the package's public API.

The `<Body>` payload wrapper element differs by document family
(`nfeDadosMsg` for NF-e, `cteDadosMsg` for CT-e, both `[Verified locally]`
against their respective MOCs), and CT-e's `CTeRecepcaoSincV4` additionally
requires the payload to be GZip-compressed and Base64-encoded before being
placed as the wrapper element's text content (`[Verified locally]` — MOC
CT-e Visão Geral v4.00 §3.4.1: "Para o serviço de recepção de CTe...a
mensagem deverá ser compactada no padrão GZip...Para os demais serviços a
mensagem deverá utilizar XML sem compactação"). `soap_envelope` supports
both shapes via `payload_element` (appended as child XML) or `payload_text`
(set as the wrapper's text content).
"""

from __future__ import annotations

from lxml import etree
from mcp_einvoicing_core.xml_utils import safe_fromstring

SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"


def soap_envelope(
    *,
    wsdl_namespace: str,
    operation: str,
    dados_msg_element: str,
    payload_element: etree._Element | None = None,
    payload_text: str | None = None,
) -> bytes:
    """Wrap a payload in a SOAP 1.2 envelope for a SEFAZ webservice operation.

    Exactly one of *payload_element* (appended as child XML — the plain,
    uncompressed shape used by most SEFAZ services) or *payload_text* (set
    as the wrapper element's text content — the GZip+Base64 shape required
    by `CTeRecepcaoSincV4`) must be provided.

    Args:
        wsdl_namespace: The operation's WSDL target namespace (e.g.
            ``http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4``).
        operation: The SOAP operation element's local name (e.g.
            ``nfeAutorizacaoLote``).
        dados_msg_element: The message-wrapper element's local name inside
            the operation (e.g. ``nfeDadosMsg``, ``cteDadosMsg``).
        payload_element: An XML element to append as the wrapper's child.
        payload_text: Text content to set on the wrapper element.

    Raises:
        ValueError: If zero or both of *payload_element*/*payload_text* are given.
    """
    if (payload_element is None) == (payload_text is None):
        raise ValueError("Exactly one of payload_element or payload_text must be provided.")

    nsmap = {"soap": SOAP_NS}
    envelope = etree.Element(f"{{{SOAP_NS}}}Envelope", nsmap=nsmap)
    etree.SubElement(envelope, f"{{{SOAP_NS}}}Header")
    body = etree.SubElement(envelope, f"{{{SOAP_NS}}}Body")

    operation_el = etree.SubElement(body, f"{{{wsdl_namespace}}}{operation}")
    dados_msg = etree.SubElement(operation_el, f"{{{wsdl_namespace}}}{dados_msg_element}")
    if payload_element is not None:
        dados_msg.append(payload_element)
    else:
        dados_msg.text = payload_text

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def scrape_fields(element: etree._Element, fields: tuple[str, ...]) -> dict[str, object]:
    """Extract *fields* from *element* (or its descendants) using
    namespace-agnostic `local-name()` lookups (per the
    `mcp-facturacion-electronica-es` SII precedent, since the response
    namespace varies by webservice/UF). Returns raw (untrusted-unmarked)
    values — callers apply `mark_untrusted_fields` themselves so nested
    sub-groups (e.g. `protNFe`/`protCTe`) can be marked independently."""
    result: dict[str, object] = {}
    for field in fields:
        elems = element.xpath(f".//*[local-name()='{field}']")
        if elems:
            result[field] = elems[0].text
    return result


def parse_response_root(response_xml: bytes) -> etree._Element:
    """Parse a SEFAZ SOAP response body into an lxml element for `scrape_fields`."""
    return safe_fromstring(response_xml)
