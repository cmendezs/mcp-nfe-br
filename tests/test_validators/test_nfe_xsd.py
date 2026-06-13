"""Tests for NFeXSDValidator (PL_010d, unsigned variant)."""

from __future__ import annotations

from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from mcp_nfe_br.validators.nfe_xsd import NFeXSDValidator
from tests.conftest import make_nfce, make_nfe


def test_valid_nfe_passes() -> None:
    xml = NFeGenerator().generate(make_nfe())
    result = NFeXSDValidator().validate(xml)
    assert result.valid is True
    assert result.errors == []


def test_valid_nfce_passes() -> None:
    xml = NFeGenerator().generate(make_nfce())
    result = NFeXSDValidator().validate(xml)
    assert result.valid is True


def test_invalid_enumeration_fails() -> None:
    xml = NFeGenerator().generate(make_nfe())
    bad_xml = xml.replace("<mod>55</mod>", "<mod>99</mod>")
    result = NFeXSDValidator().validate(bad_xml)
    assert result.valid is False
    assert any("mod" in err for err in result.errors)


def test_malformed_xml_returns_portuguese_error() -> None:
    result = NFeXSDValidator().validate("<NFe><infNFe>")
    assert result.valid is False
    assert any("malformado" in err for err in result.errors)


def test_validate_accepts_bytes() -> None:
    xml = NFeGenerator().generate(make_nfe())
    result = NFeXSDValidator().validate(xml.encode("utf-8"))
    assert result.valid is True


def test_schema_version_metadata() -> None:
    result = NFeXSDValidator().validate(NFeGenerator().generate(make_nfe()))
    assert "PL_010d" in result.metadata["schema_version"]
