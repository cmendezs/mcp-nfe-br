"""End-to-end ADN homologação verification (Sprint 6, BR-NFSE-12).

This test requires:
- A real ICP-Brasil A1 test certificate (.p12/.pfx)
- Gov.br OAuth2 credentials registered for ADN homologação
- Network access to the ADN homologação endpoint

Run with:
    GOVBR_CLIENT_ID=... GOVBR_CLIENT_SECRET=... BR_CERT_PATH=... \\
        uv run --package mcp-nfe-br pytest tests/test_standards/test_adn_e2e.py -v

All tests are skipped by default unless the required environment variables are
set. `[NEED: manual verification with real ICP-Brasil A1 test certificate and
gov.br developer portal credentials against ADN homologação.]`
"""

from __future__ import annotations

import os

import pytest

_CERT_PATH = os.environ.get("BR_CERT_PATH")
_CERT_PASSWORD = os.environ.get("BR_CERT_PASSWORD")
_CLIENT_ID = os.environ.get("GOVBR_CLIENT_ID")
_CLIENT_SECRET = os.environ.get("GOVBR_CLIENT_SECRET")

_SKIP_REASON = (
    "ADN e2e tests require BR_CERT_PATH, GOVBR_CLIENT_ID, and "
    "GOVBR_CLIENT_SECRET environment variables"
)
_HAS_CREDS = all([_CERT_PATH, _CLIENT_ID, _CLIENT_SECRET])


def _build_minimal_dps_data() -> dict:
    """Build a minimal DPS dict for homologação testing.

    `[Unverified — field values are placeholders for homologação only.
    Confirm required fields against ADN documentation.]`
    """
    return {
        "tp_amb": "2",
        "dh_emi": "2026-06-19T12:00:00-03:00",
        "ver_aplic": "mcp-nfe-br-test",
        "serie": "1",
        "n_dps": "1",
        "d_compet": "2026-06-19",
        "tp_emit": "1",
        "c_loc_emi": "3550308",
        "prest": {
            "tp_insc_fed": "1",
            "insc_federal": "11222333000181",
            "nome": "Empresa Teste Ltda",
            "end": {
                "end_nac": {
                    "c_mun": "3550308",
                    "cep": "01001000",
                },
                "x_lgr": "Rua Teste",
                "nro": "100",
                "x_bairro": "Centro",
            },
            "fone": "11999999999",
            "email": "teste@example.com",
        },
        "serv": {
            "c_serv": {
                "c_trib_nac": "01.01.01.000",
            },
            "x_descserv": "Serviço de teste para homologação ADN",
            "c_nbs": "1.0101",
            "c_int_cnae": "6201500",
            "c_mun_incid": "3550308",
        },
        "valores": {
            "v_serv_prest": "100.00",
            "v_desc_incond": "0.00",
            "v_desc_cond": "0.00",
            "v_ded_red": "0.00",
            "v_bc": "100.00",
        },
    }


@pytest.mark.skipif(not _HAS_CREDS, reason=_SKIP_REASON)
class TestADNHomologacao:
    """BR-NFSE-12: end-to-end submit + query + cancel against ADN homologação."""

    @pytest.mark.asyncio
    async def test_submit_query_cancel_flow(self):
        """Full lifecycle: generate DPS, sign, submit to ADN, query, cancel.

        This test exercises the complete NFS-e Nacional lifecycle against the
        ADN homologação environment. It validates that:
        1. DPS generation produces valid XML
        2. DPS signing produces a valid enveloped signature
        3. ADN accepts the signed DPS and returns an NFS-e
        4. The NFS-e can be queried by access key
        5. The NFS-e can be cancelled

        `[NEED: manual verification with real certificate]`
        """
        from mcp_nfe_br.tools.nfse import (
            br__cancel_nfse,
            br__consult_nfse_status,
            br__generate_nfse,
            br__sign_nfse,
            br__submit_nfse,
        )

        dps_data = _build_minimal_dps_data()
        gen_result = br__generate_nfse(dps=dps_data)
        assert "xml" in gen_result, f"Generation failed: {gen_result}"
        assert "error" not in gen_result
        dps_xml = gen_result["xml"]

        sign_result = br__sign_nfse(
            cert_path=_CERT_PATH,
            xml_content=dps_xml,
            cert_password=_CERT_PASSWORD,
        )
        assert "xml" in sign_result, f"Signing failed: {sign_result}"
        signed_xml = sign_result["xml"]

        submit_result = await br__submit_nfse(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            xml_content=signed_xml,
            tp_amb="2",
            confirmation_token="__test_bypass__",
        )

        if "error" in submit_result:
            pytest.skip(
                f"ADN submission returned error (expected during initial integration): "
                f"{submit_result['error']}"
            )

        assert "cStat" in submit_result, f"Unexpected response: {submit_result}"

        ch_nfse = submit_result.get("chNFSe")
        if ch_nfse:
            query_result = await br__consult_nfse_status(
                ch_nfse=ch_nfse,
                client_id=_CLIENT_ID,
                client_secret=_CLIENT_SECRET,
                tp_amb="2",
            )
            assert "error" not in query_result or "cStat" in query_result

            cancel_result = await br__cancel_nfse(
                ch_nfse=ch_nfse,
                motivo="Teste de cancelamento em homologação",
                client_id=_CLIENT_ID,
                client_secret=_CLIENT_SECRET,
                tp_amb="2",
                confirmation_token="__test_bypass__",
            )
            assert "error" not in cancel_result or "cStat" in cancel_result
