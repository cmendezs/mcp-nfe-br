"""Tests for NFS-e Nacional DPS generation → XSD round-trip (roadmap BR-NFSE-C2..C5)."""

from __future__ import annotations

from mcp_nfe_br.standards.nfse_generator import NFSeGenerator
from mcp_nfe_br.validators.nfse_xsd import NFSeXSDValidator
from tests.conftest import make_nfse


def test_fully_populated_dps_validates_against_xsd() -> None:
    """Guards BR-NFSE-C2 (endNac/endereço), C3 (regEspTrib), C4 (tribMun order),
    and C5 (dCompet format) in a single generate→XSD round-trip."""
    xml = NFSeGenerator().generate(make_nfse())

    result = NFSeXSDValidator().validate(xml)
    assert result.valid is True, result.errors


def test_dcompet_normalizes_from_aaaammdd() -> None:
    xml = NFSeGenerator().generate(make_nfse(d_compet="20260701"))

    assert "<dCompet>2026-07-01</dCompet>" in xml
    result = NFSeXSDValidator().validate(xml)
    assert result.valid is True, result.errors


def test_serie_single_digit_validates_against_xsd() -> None:
    """Guards BR-NFSE-C6: the bundled TSSerieDPS pattern must accept a plain serie."""
    xml = NFSeGenerator().generate(make_nfse(serie="1"))

    result = NFSeXSDValidator().validate(xml)
    assert result.valid is True, result.errors


def test_serie_zero_padded_validates_against_xsd() -> None:
    xml = NFSeGenerator().generate(make_nfse(serie="00001"))

    result = NFSeXSDValidator().validate(xml)
    assert result.valid is True, result.errors


def test_malformed_xml_reports_error() -> None:
    result = NFSeXSDValidator().validate("<DPS><infDPS>")
    assert result.valid is False
    assert result.errors
