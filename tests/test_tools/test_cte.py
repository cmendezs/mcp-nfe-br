"""Tests for CT-e generation/validation (BR-CTE-9) and SEFAZ tools (BR-CTE-12).

The SEFAZ tool tests cover confirmation-gate and read-only gating only —
no CT-e endpoint is bundled/verified, so real network calls always require
`endpoint_override` and are exercised separately (mocked transport) in
`tests/test_standards/test_sefaz_cte_client.py`.
"""

from __future__ import annotations

import pytest
from mcp_einvoicing_core.confirmation import ConfirmationGate, ConfirmationStore

from mcp_nfe_br.models.cte import BRCteInfModal, CTeModal
from mcp_nfe_br.tools.cte import (
    br__consult_cte,
    br__consult_cte_sefaz_status,
    br__generate_cte,
    br__submit_cte,
    br__validate_cte_xml,
)
from tests.conftest import make_cte


@pytest.fixture(autouse=True)
def _isolated_confirmation_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a fresh ConfirmationGate so tests don't share state/HITL-disable env."""
    monkeypatch.delenv("EINVOICING_DISABLE_HITL", raising=False)
    gate = ConfirmationGate(ConfirmationStore())
    monkeypatch.setattr(ConfirmationGate, "_default", gate)


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


async def test_consult_cte_sefaz_status_invalid_environment() -> None:
    result = await br__consult_cte_sefaz_status(
        c_uf="43",
        cert_path="/tmp/does-not-exist.p12",
        endpoint_override="https://homolog.example/CTeStatusServico4.asmx",
        tp_amb="9",
    )
    assert "error" in result


async def test_consult_cte_no_confirmation_needed() -> None:
    """br__consult_cte is read-only (queries one already-known chCTe) — no gate.

    Uses an unreachable local port so the connection fails immediately
    (no DNS lookup, no timeout) rather than exercising real network I/O.
    """
    result = await br__consult_cte(
        ch_cte="35260711222333000181570010000000011212199180",
        c_uf="43",
        cert_path="/tmp/does-not-exist.p12",
        endpoint_override="http://127.0.0.1:1/CTeConsultaV4.asmx",
    )
    assert result.get("status") != "awaiting_confirmation"
    assert "error" in result


async def test_submit_cte_read_only_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BR_CTE_READ_ONLY", "1")

    result = await br__submit_cte(
        c_uf="43",
        cert_path="/tmp/does-not-exist.p12",
        endpoint_override="https://homolog.example/CTeRecepcaoSincV4.asmx",
        xml_content='<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe1"/></CTe>',
    )

    assert "error" in result


async def test_submit_cte_requires_confirmation() -> None:
    result = await br__submit_cte(
        c_uf="43",
        cert_path="/tmp/does-not-exist.p12",
        endpoint_override="https://homolog.example/CTeRecepcaoSincV4.asmx",
        xml_content='<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe1"/></CTe>',
    )

    assert result.get("status") == "awaiting_confirmation"
    assert "token" in result


async def test_submit_cte_invalid_environment() -> None:
    result = await br__submit_cte(
        c_uf="43",
        cert_path="/tmp/does-not-exist.p12",
        endpoint_override="https://homolog.example/CTeRecepcaoSincV4.asmx",
        xml_content='<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe1"/></CTe>',
        tp_amb="9",
    )

    assert "error" in result
