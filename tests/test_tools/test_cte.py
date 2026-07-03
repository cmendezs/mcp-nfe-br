"""Tests for br__generate_cte and br__validate_cte_xml (roadmap BR-CTE-9)."""

from __future__ import annotations

from mcp_nfe_br.models.cte import BRCteInfModal, CTeModal
from mcp_nfe_br.tools.cte import br__generate_cte, br__validate_cte_xml
from tests.conftest import make_cte


def test_generate_cte_returns_xml_and_chave() -> None:
    result = br__generate_cte(make_cte().model_dump(mode="json"))
    assert "xml" in result
    assert result["chave_acesso"]
    assert len(result["chave_acesso"]) == 44
    assert "<Signature" not in result["xml"]
    assert result["warnings"]


def test_generate_cte_unsupported_modal_returns_error() -> None:
    data = make_cte(
        modal=CTeModal.AEREO,
        inf_modal=BRCteInfModal(modal=CTeModal.AEREO, rntrc=None),
    ).model_dump(mode="json")
    result = br__generate_cte(data)
    assert "error" in result


def test_validate_cte_xml_accepts_generated_document() -> None:
    gen_result = br__generate_cte(make_cte().model_dump(mode="json"))
    validate_result = br__validate_cte_xml(xml_content=gen_result["xml"])
    assert validate_result["valid"] is True, validate_result["errors"]


def test_validate_cte_xml_rejects_malformed_input() -> None:
    result = br__validate_cte_xml(xml_content="<CTe><infCte>")
    assert result["valid"] is False
    assert result["errors"]


def test_validate_cte_xml_requires_one_input() -> None:
    result = br__validate_cte_xml()
    assert result["valid"] is False
