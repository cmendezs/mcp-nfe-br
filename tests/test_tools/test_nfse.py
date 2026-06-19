"""Tests for mcp_nfe_br.tools.nfse — NFS-e ADN submission tools (Sprint 5)."""

import os

import pytest

from mcp_nfe_br.tools.nfse import (
    br__cancel_nfse,
    br__consult_nfse_status,
    br__submit_nfse,
)


class TestSubmitNfse:
    """br__submit_nfse tool tests."""

    @pytest.mark.asyncio
    async def test_submit_nfse_invalid_tp_amb(self):
        result = await br__submit_nfse(
            client_id="id", client_secret="secret", xml_content="<DPS/>", tp_amb="9"
        )
        assert "error" in result
        assert "tp_amb" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_nfse_read_only_blocked(self, monkeypatch):
        monkeypatch.setenv("BR_READ_ONLY", "1")
        result = await br__submit_nfse(
            client_id="id", client_secret="secret", xml_content="<DPS/>"
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_submit_nfse_requires_confirmation(self):
        if os.environ.get("BR_READ_ONLY") == "1":
            pytest.skip("BR_READ_ONLY is set")
        result = await br__submit_nfse(
            client_id="id", client_secret="secret", xml_content="<DPS/>"
        )
        assert "pending" in str(result).lower() or "confirmation" in str(result).lower()

    @pytest.mark.asyncio
    async def test_submit_nfse_no_xml(self):
        result = await br__submit_nfse(client_id="id", client_secret="secret")
        assert "error" in result


class TestConsultNfseStatus:
    """br__consult_nfse_status tool tests."""

    @pytest.mark.asyncio
    async def test_consult_invalid_tp_amb(self):
        result = await br__consult_nfse_status(
            ch_nfse="NFS" + "0" * 50, client_id="id", client_secret="secret", tp_amb="X"
        )
        assert "error" in result


class TestCancelNfse:
    """br__cancel_nfse tool tests."""

    @pytest.mark.asyncio
    async def test_cancel_nfse_invalid_tp_amb(self):
        result = await br__cancel_nfse(
            ch_nfse="NFS" + "0" * 50,
            motivo="teste",
            client_id="id",
            client_secret="secret",
            tp_amb="X",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_cancel_nfse_read_only_blocked(self, monkeypatch):
        monkeypatch.setenv("BR_READ_ONLY", "1")
        result = await br__cancel_nfse(
            ch_nfse="NFS" + "0" * 50,
            motivo="teste",
            client_id="id",
            client_secret="secret",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_cancel_nfse_requires_confirmation(self):
        if os.environ.get("BR_READ_ONLY") == "1":
            pytest.skip("BR_READ_ONLY is set")
        result = await br__cancel_nfse(
            ch_nfse="NFS" + "0" * 50,
            motivo="teste",
            client_id="id",
            client_secret="secret",
        )
        assert "pending" in str(result).lower() or "confirmation" in str(result).lower()


class TestSecretNotInLogs:
    """BR-SH-1 parity: gov.br client_secret must not appear in log records."""

    @pytest.mark.asyncio
    async def test_submit_nfse_password_not_in_logs(self, caplog):
        secret = "GOVBR_SECRET_MUST_NOT_LEAK"
        await br__submit_nfse(
            client_id="id", client_secret=secret, xml_content="<DPS/>"
        )
        for record in caplog.records:
            assert secret not in record.getMessage()
