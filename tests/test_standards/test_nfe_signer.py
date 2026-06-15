"""Tests for ICP-Brasil XML-DSig signing (v0.3.0 item 1)."""

from __future__ import annotations

from pathlib import Path

from lxml import etree
from mcp_einvoicing_core import XMLDSigSigner

from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from mcp_nfe_br.standards.nfe_signer import build_nfe_signer
from mcp_nfe_br.validators.nfe_xsd import NFeXSDValidator
from tests.conftest import make_nfe

_DS_SIGNATURE = "{http://www.w3.org/2000/09/xmldsig#}Signature"


def test_build_nfe_signer_returns_xmldsig_signer(p12_path: Path) -> None:
    signer = build_nfe_signer(str(p12_path), "test")
    assert isinstance(signer, XMLDSigSigner)


def test_sign_appends_signature_as_last_child(p12_path: Path) -> None:
    unsigned_xml = NFeGenerator().generate(make_nfe())
    signed = build_nfe_signer(str(p12_path), "test").sign(unsigned_xml.encode("utf-8"))
    root = etree.fromstring(signed)
    assert root[-1].tag == _DS_SIGNATURE
    assert root[0].tag.endswith("infNFe")


def test_signed_document_validates_against_official_schema(p12_path: Path) -> None:
    unsigned_xml = NFeGenerator().generate(make_nfe())
    signed = build_nfe_signer(str(p12_path), "test").sign(unsigned_xml.encode("utf-8"))

    result = NFeXSDValidator().validate(signed)
    assert result.valid is True, result.errors
    assert "official signed schema" in result.metadata["schema_version"]


def test_unsigned_document_validates_against_unsigned_schema() -> None:
    unsigned_xml = NFeGenerator().generate(make_nfe())

    result = NFeXSDValidator().validate(unsigned_xml)
    assert result.valid is True, result.errors
    assert "unsigned variant" in result.metadata["schema_version"]
