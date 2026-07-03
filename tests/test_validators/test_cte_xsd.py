"""Tests for CT-e XSD validation (roadmap BR-CTE-9)."""

from __future__ import annotations

from mcp_nfe_br.standards.cte_generator import CTeGenerator
from mcp_nfe_br.validators.cte_xsd import CTeXSDValidator
from tests.conftest import make_cte


def test_unsigned_document_validates_against_unsigned_schema() -> None:
    unsigned_xml = CTeGenerator().generate(make_cte())

    result = CTeXSDValidator().validate(unsigned_xml)
    assert result.valid is True, result.errors
    assert "unsigned variant" in result.metadata["schema_version"]


def test_malformed_xml_reports_error() -> None:
    result = CTeXSDValidator().validate("<CTe><infCte>")
    assert result.valid is False
    assert result.errors


def test_get_schema_version_and_path() -> None:
    validator = CTeXSDValidator()
    assert "CT-e 4.00" in validator.get_schema_version()
    assert validator.get_schema_path().endswith("cte_v4.00_unsigned.xsd")
