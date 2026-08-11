"""Tests for NFS-e Nacional (ADN) DPS generation (roadmap BR-NFSE-C1)."""

from __future__ import annotations

import pytest
from mcp_einvoicing_core import DocumentGenerationError

from mcp_nfe_br.standards.nfse_generator import NFSeGenerator
from tests.conftest import make_nfse


def test_generator_is_concrete() -> None:
    NFSeGenerator()


def test_generate_produces_dps_with_infdps() -> None:
    xml = NFSeGenerator().generate(make_nfse())
    assert "<DPS" in xml
    assert "<infDPS" in xml
    assert xml.strip()


def test_get_format_name_and_country_code() -> None:
    generator = NFSeGenerator()
    assert generator.get_format_name() == "NFS-e DPS 1.01"
    assert generator.get_country_code() == "BR"
    assert generator.get_namespace() == "http://www.sped.fazenda.gov.br/nfse"


def test_generate_rejects_non_nfse_document() -> None:
    with pytest.raises(DocumentGenerationError, match="NFSeDocument"):
        NFSeGenerator().generate(object())  # type: ignore[arg-type]
