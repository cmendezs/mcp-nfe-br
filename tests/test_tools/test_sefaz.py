"""Tests for the SEFAZ webservice tools (br__submit_nfe, br__consult_sefaz_status,
br__distribute_dfe): confirmation gate and read-only gating.

These do not exercise real SEFAZ network calls — `consultar_status_servico`
itself requires a real endpoint/cert and is covered separately by
`tests/test_standards/test_sefaz_client.py` (mocked transport). A true
end-to-end check against SEFAZ homologation requires a real ICP-Brasil A1
test certificate `[NEED: manual verification]`.
"""

from __future__ import annotations

import pytest
from mcp_einvoicing_core.confirmation import ConfirmationGate, ConfirmationStore

from mcp_nfe_br.tools.sefaz import br__distribute_dfe, br__submit_nfe


@pytest.fixture(autouse=True)
def _isolated_confirmation_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a fresh ConfirmationGate so tests don't share state/HITL-disable env."""
    monkeypatch.delenv("EINVOICING_DISABLE_HITL", raising=False)
    gate = ConfirmationGate(ConfirmationStore())
    monkeypatch.setattr(ConfirmationGate, "_default", gate)


async def test_submit_nfe_read_only_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BR_READ_ONLY", "1")

    result = await br__submit_nfe(
        c_uf="43",
        id_lote="1",
        cert_path="/tmp/does-not-exist.p12",
        xml_content='<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1"/></NFe>',
    )

    assert "error" in result


async def test_submit_nfe_requires_confirmation() -> None:
    result = await br__submit_nfe(
        c_uf="43",
        id_lote="1",
        cert_path="/tmp/does-not-exist.p12",
        xml_content='<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1"/></NFe>',
    )

    assert result.get("status") == "awaiting_confirmation"
    assert "token" in result


async def test_submit_nfe_invalid_environment() -> None:
    result = await br__submit_nfe(
        c_uf="43",
        id_lote="1",
        cert_path="/tmp/does-not-exist.p12",
        xml_content='<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1"/></NFe>',
        tp_amb="9",
    )

    assert "error" in result


async def test_distribute_dfe_requires_exactly_one_mode() -> None:
    result = await br__distribute_dfe(
        c_uf_autor="35",
        document_id="99999999999999",
        cert_path="/tmp/does-not-exist.p12",
    )

    assert "error" in result


async def test_distribute_dfe_requires_confirmation() -> None:
    result = await br__distribute_dfe(
        c_uf_autor="35",
        document_id="99999999999999",
        cert_path="/tmp/does-not-exist.p12",
        ult_nsu="000000000000001",
    )

    assert result.get("status") == "awaiting_confirmation"
    assert "token" in result


async def test_distribute_dfe_read_only_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BR_READ_ONLY", "1")

    result = await br__distribute_dfe(
        c_uf_autor="35",
        document_id="99999999999999",
        cert_path="/tmp/does-not-exist.p12",
        ult_nsu="000000000000001",
    )

    assert "error" in result
