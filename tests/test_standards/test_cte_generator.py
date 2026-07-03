"""Tests for CT-e (modelo 57) XML generation (roadmap BR-CTE-8)."""

from __future__ import annotations

import pytest
from lxml import etree
from mcp_einvoicing_core import DocumentGenerationError

from mcp_nfe_br.models.cte import BRCteInfModal, CTeModal
from mcp_nfe_br.standards.cte_generator import CTeGenerator
from mcp_nfe_br.validators.cte_xsd import CTeXSDValidator
from tests.conftest import make_cte

_NAMESPACE = "http://www.portalfiscal.inf.br/cte"


def test_generate_produces_infcte_with_id() -> None:
    xml = CTeGenerator().generate(make_cte())
    root = etree.fromstring(xml.encode("utf-8"))
    assert root.tag == f"{{{_NAMESPACE}}}CTe"
    inf_cte = root[0]
    assert inf_cte.tag == f"{{{_NAMESPACE}}}infCte"
    assert inf_cte.get("Id").startswith("CTe")
    assert len(inf_cte.get("Id")) == len("CTe") + 44


def test_generate_unsigned_document_validates_against_xsd() -> None:
    xml = CTeGenerator().generate(make_cte())
    result = CTeXSDValidator().validate(xml)
    assert result.valid is True, result.errors
    assert "unsigned variant" in result.metadata["schema_version"]


def test_generate_rejects_non_cte_document() -> None:
    with pytest.raises(DocumentGenerationError, match="BRCTeDocument"):
        CTeGenerator().generate(object())  # type: ignore[arg-type]


def test_generate_rejects_unsupported_modal() -> None:
    cte = make_cte(
        modal=CTeModal.AEREO,
        inf_modal=BRCteInfModal(modal=CTeModal.AEREO, rntrc=None),
    )
    with pytest.raises(DocumentGenerationError, match="rodoviário"):
        CTeGenerator().generate(cte)


def test_generate_rejects_mismatched_chave_acesso() -> None:
    cte = make_cte(chave_acesso="0" * 44)
    with pytest.raises(DocumentGenerationError, match="chave de acesso"):
        CTeGenerator().generate(cte)
